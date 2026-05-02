"""Shipment tracking service — stateful shipment lifecycle management.

Parses shipment ETAs from emails, tracks them as stateful objects,
and auto-updates the Digital Twin when follow-up emails indicate
status changes (rerouted, cancelled, delayed, delivered).

🔴 CRITICAL: asyncio.Lock() guards all mutating methods to prevent
   in-memory state corruption from concurrent requests.
"""
from __future__ import annotations

import asyncio
import csv
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ShipmentStatus(str, Enum):
    """Shipment lifecycle states."""
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"
    REROUTED = "rerouted"
    CANCELLED = "cancelled"
    DELAYED = "delayed"


# ---------------------------------------------------------------------------
# Status detection keywords — matched against email body
# Order matters: first match wins (most specific first)
# ---------------------------------------------------------------------------
STATUS_KEYWORDS: dict[ShipmentStatus, list[str]] = {
    ShipmentStatus.CANCELLED: [
        "cancelled", "canceled", "order cancelled", "order canceled",
        "shipment cancelled", "shipment canceled",
    ],
    ShipmentStatus.DELIVERED: [
        "delivered", "delivery confirmed", "cleared customs",
        "available for pickup",
    ],
    ShipmentStatus.REROUTED: [
        "rerouted", "re-routed", "diverted", "rerouting",
        "transshipment", "backup facility",
    ],
    ShipmentStatus.DELAYED: [
        "delayed", "delay", "customs hold", "customs delay",
        "power outage", "held at", "postponed", "additional days",
    ],
}

# Risk score adjustments when shipment status changes
STATUS_RISK_MAP: dict[ShipmentStatus, float] = {
    ShipmentStatus.CANCELLED: 0.85,
    ShipmentStatus.REROUTED: 0.65,
    ShipmentStatus.DELAYED: 0.55,
    ShipmentStatus.DELIVERED: 0.0,
    ShipmentStatus.IN_TRANSIT: 0.0,
}


@dataclass
class Shipment:
    """A tracked shipment in the system."""
    id: str
    supplier: str
    material: str
    origin: str
    destination: str
    eta_days: int
    status: ShipmentStatus = ShipmentStatus.IN_TRANSIT
    departure_date: str = ""
    last_updated: str = ""
    tracking_number: str = ""
    email_reference_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to API-friendly dict."""
        return {
            "shipment_id": self.id,
            "supplier": self.supplier,
            "material": self.material,
            "status": self.status.value,
            "eta_days": self.eta_days,
            "origin": self.origin,
            "destination": self.destination,
            "tracking_number": self.tracking_number,
            "departure_date": self.departure_date,
            "last_updated": self.last_updated,
        }


@dataclass
class ShipmentUpdateResult:
    """Result of processing a status update."""
    shipment_id: str
    supplier: str
    old_status: str
    new_status: str
    node_id: Optional[str] = None
    risk_score_change: Optional[float] = None


class ShipmentTracker:
    """Singleton shipment tracker with thread-safe mutations.

    🔴 CRITICAL FIX #1: All mutating methods are guarded by asyncio.Lock()
    to prevent in-memory state corruption from concurrent requests.
    """
    _instance: Optional[ShipmentTracker] = None

    def __new__(cls) -> ShipmentTracker:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._shipments: dict[str, Shipment] = {}
            cls._instance._tracking_index: dict[str, str] = {}  # tracking_number → shipment_id
            cls._instance._supplier_index: dict[str, list[str]] = {}  # supplier_lower → [shipment_ids]
            cls._instance._lock = asyncio.Lock()
        return cls._instance

    def __init__(self) -> None:
        pass

    # -----------------------------------------------------------------------
    # Ingestion — parse shipments from email events
    # -----------------------------------------------------------------------

    async def ingest_shipments(self, events: list[dict[str, Any]]) -> int:
        """Parse email events and create Shipment objects.

        🔴 Lock-guarded to prevent concurrent corruption.

        Args:
            events: Email event dicts from ingestion pipeline

        Returns:
            Number of shipments created
        """
        async with self._lock:
            created = 0
            for event in events:
                shipment = self._parse_shipment_from_event(event)
                if shipment:
                    self._shipments[shipment.id] = shipment

                    # Build tracking number index
                    if shipment.tracking_number:
                        self._tracking_index[shipment.tracking_number.lower()] = shipment.id

                    # Build supplier index
                    supplier_key = shipment.supplier.lower().strip()
                    if supplier_key not in self._supplier_index:
                        self._supplier_index[supplier_key] = []
                    if shipment.id not in self._supplier_index[supplier_key]:
                        self._supplier_index[supplier_key].append(shipment.id)

                    created += 1

            logger.info(f"ShipmentTracker ingested {created} shipments from {len(events)} events")
            return created

    # -----------------------------------------------------------------------
    # Status updates — detect and apply status changes from follow-up emails
    # -----------------------------------------------------------------------

    async def process_status_updates(
        self, events: list[dict[str, Any]]
    ) -> list[ShipmentUpdateResult]:
        """Process follow-up emails for shipment status changes.

        🔴 Lock-guarded to prevent concurrent corruption.

        Matching priority:
        1. Exact tracking number match (highest confidence)
        2. Supplier name + material fuzzy match (fallback)

        Args:
            events: Email event dicts that may contain status updates

        Returns:
            List of ShipmentUpdateResult for events that triggered changes
        """
        async with self._lock:
            results: list[ShipmentUpdateResult] = []
            for event in events:
                result = self._process_single_update(event)
                if result:
                    results.append(result)

            if results:
                logger.info(
                    f"ShipmentTracker processed {len(results)} status updates "
                    f"from {len(events)} events"
                )
            return results

    # -----------------------------------------------------------------------
    # Queries — read-only, no lock needed
    # -----------------------------------------------------------------------

    def get_all_shipments(self) -> list[dict[str, Any]]:
        """Get all tracked shipments."""
        return [s.to_dict() for s in self._shipments.values()]

    def get_shipments_for_supplier(self, supplier_name: str) -> list[dict[str, Any]]:
        """Get all shipments for a supplier by name."""
        supplier_key = supplier_name.lower().strip()
        results = []

        # Exact key match first
        if supplier_key in self._supplier_index:
            for sid in self._supplier_index[supplier_key]:
                if sid in self._shipments:
                    results.append(self._shipments[sid].to_dict())
            return results

        # Partial match fallback
        for key, sids in self._supplier_index.items():
            if supplier_key in key or key in supplier_key:
                for sid in sids:
                    if sid in self._shipments:
                        results.append(self._shipments[sid].to_dict())

        return results

    def get_shipments_for_node(self, node_id: str, node_name: str = "") -> list[dict[str, Any]]:
        """Get shipments for a Digital Twin node.

        Maps node name to supplier name for lookup.
        """
        if node_name:
            return self.get_shipments_for_supplier(node_name)

        # Try extracting supplier name from node_id
        # e.g., "live_alpha_metals" → "alpha metals"
        clean_name = node_id.replace("live_", "").replace("_", " ").strip()
        return self.get_shipments_for_supplier(clean_name)

    def get_shipment_count_for_supplier(self, supplier_name: str) -> int:
        """Quick count without building full dicts."""
        supplier_key = supplier_name.lower().strip()
        if supplier_key in self._supplier_index:
            return len(self._supplier_index[supplier_key])
        # Partial match
        count = 0
        for key, sids in self._supplier_index.items():
            if supplier_key in key or key in supplier_key:
                count += len(sids)
        return count

    # -----------------------------------------------------------------------
    # Internal parsing
    # -----------------------------------------------------------------------

    def _parse_shipment_from_event(self, event: dict[str, Any]) -> Optional[Shipment]:
        """Extract a Shipment from an email event dict."""
        text = str(event.get("text", ""))
        meta = event.get("metadata", {}) or {}
        supplier = (
            event.get("supplier")
            or meta.get("sender_name")
            or ""
        )
        if not supplier:
            return None

        # Extract tracking number from body
        tracking = self._extract_tracking_number(text)

        # Extract ETA days
        eta_days = self._extract_eta_days(text, meta)
        if eta_days is None:
            eta_days = int(meta.get("eta_days", 0) or 0)

        # Extract material
        material = meta.get("material", "") or self._extract_material(text)

        # Extract origin
        origin = meta.get("origin_location", "") or self._extract_origin(text)

        if not material and not tracking:
            return None  # Not enough data to create a meaningful shipment

        # Build shipment ID
        ref_id = event.get("reference_id", "")
        shipment_id = f"SHP-{ref_id}" if ref_id else f"SHP-{supplier[:10]}-{hash(text) % 10000}"

        # Skip if already exists
        if shipment_id in self._shipments:
            return None

        return Shipment(
            id=shipment_id,
            supplier=supplier,
            material=material,
            origin=origin,
            destination="",  # Will be enriched from graph
            eta_days=eta_days,
            status=ShipmentStatus.IN_TRANSIT,
            departure_date=event.get("event_time", "") or meta.get("date", ""),
            last_updated=datetime.now(timezone.utc).isoformat(),
            tracking_number=tracking,
            email_reference_id=ref_id,
        )

    def _process_single_update(self, event: dict[str, Any]) -> Optional[ShipmentUpdateResult]:
        """Process a single email for status change signals."""
        text = str(event.get("text", "")).lower()
        meta = event.get("metadata", {}) or {}

        # Detect new status from keywords
        new_status = self._detect_status(text)
        if new_status is None:
            return None  # Not a status update email

        # 🔴 PRIORITY MATCHING: tracking number first, supplier name fallback
        matched_shipment = self._match_shipment(event, text)
        if not matched_shipment:
            return None

        old_status = matched_shipment.status.value
        if new_status == matched_shipment.status:
            return None  # No actual change

        # Apply the update
        matched_shipment.status = new_status
        matched_shipment.last_updated = datetime.now(timezone.utc).isoformat()

        # Update ETA if a new one is mentioned
        new_eta = self._extract_eta_days(text, meta)
        if new_eta is not None:
            matched_shipment.eta_days = new_eta

        risk_change = STATUS_RISK_MAP.get(new_status, 0.0)

        logger.info(
            f"Shipment {matched_shipment.id} status: {old_status} → {new_status.value} "
            f"(supplier: {matched_shipment.supplier})"
        )

        return ShipmentUpdateResult(
            shipment_id=matched_shipment.id,
            supplier=matched_shipment.supplier,
            old_status=old_status,
            new_status=new_status.value,
            risk_score_change=risk_change,
        )

    def _match_shipment(
        self, event: dict[str, Any], text_lower: str
    ) -> Optional[Shipment]:
        """Match an update email to an existing shipment.

        Priority:
        1. Exact tracking number match (highest confidence)
        2. Supplier + material fuzzy match (fallback)
        """
        # 1. Try tracking number exact match first
        tracking = self._extract_tracking_number(text_lower)
        if tracking and tracking.lower() in self._tracking_index:
            sid = self._tracking_index[tracking.lower()]
            return self._shipments.get(sid)

        # 2. Fallback: supplier name + material
        supplier = (
            event.get("supplier", "")
            or event.get("metadata", {}).get("sender_name", "")
        ).lower().strip()

        if not supplier:
            return None

        # Find shipments for this supplier
        candidate_ids: list[str] = []
        if supplier in self._supplier_index:
            candidate_ids = self._supplier_index[supplier]
        else:
            for key, sids in self._supplier_index.items():
                if supplier in key or key in supplier:
                    candidate_ids.extend(sids)

        if not candidate_ids:
            return None

        # If only one shipment from this supplier, match it
        if len(candidate_ids) == 1:
            return self._shipments.get(candidate_ids[0])

        # Multiple shipments — try material match
        material = (event.get("metadata", {}).get("material", "") or "").lower()
        for sid in candidate_ids:
            shipment = self._shipments.get(sid)
            if shipment and material and material in shipment.material.lower():
                return shipment

        # Last resort: return the most recent
        return self._shipments.get(candidate_ids[-1])

    def _detect_status(self, text_lower: str) -> Optional[ShipmentStatus]:
        """Detect shipment status from email body keywords."""
        for status, keywords in STATUS_KEYWORDS.items():
            for kw in keywords:
                if re.search(r"\b" + re.escape(kw) + r"\b", text_lower):
                    return status
        return None

    # -----------------------------------------------------------------------
    # Regex extractors — patterns designed to match shipment_updates.csv format
    # -----------------------------------------------------------------------

    def _extract_tracking_number(self, text: str) -> str:
        """Extract tracking/reference numbers from email body.

        Patterns match data in supplier_emails.csv and shipment_updates.csv:
        - COSCO-88412, PFPC-221, DX-55-TRACK, NP-7823
        """
        patterns = [
            r"(?:tracking(?:\s+number)?|shipment|container|batch|order|invoice\s*#?)\s*[:.]?\s*([A-Z]{2,}[\-][A-Z0-9\-]+)",
            r"\b([A-Z]{2,}[\-]\d{2,}(?:[\-][A-Z]+)?)\b",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).upper()
        return ""

    def _extract_eta_days(self, text: str, meta: dict) -> Optional[int]:
        """Extract ETA in days from email body."""
        patterns = [
            r"(?:eta|estimated?\s*(?:transit\s*time|arrival|delivery)?)\s*[:.]?\s*(\d+)\s*days?",
            r"(\d+)\s*days?\s*(?:from|after|transit|via)",
            r"in\s+(\d+)\s+days?",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return int(match.group(1))
        return None

    def _extract_material(self, text: str) -> str:
        """Extract material type from email body."""
        patterns = [
            r"(?:units?\s+)([a-zA-Z\s]{3,30}?)(?:\)|has|will|is|,)",
            r"(?:kg|tons?)\s+([a-zA-Z\s]{3,25}?)(?:\s+(?:dispatched|shipped|from))",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return ""

    def _extract_origin(self, text: str) -> str:
        """Extract origin location from email body."""
        patterns = [
            r"(?:from\s+(?:our\s+)?|left\s+(?:our\s+)?|at\s+(?:our\s+)?)([A-Z][a-zA-Z\s]{2,25}?)(?:\s+(?:facility|plant|warehouse|terminal|hub|port))",
            r"(?:from|via)\s+([A-Z][a-zA-Z\s]{2,20}?)(?:\s+(?:has|to|and|,|\.))",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()
        return ""

    # -----------------------------------------------------------------------
    # CSV loader for shipment_updates.csv
    # -----------------------------------------------------------------------

    def load_shipment_updates_csv(self, path: str = "data/shipment_updates.csv") -> list[dict[str, Any]]:
        """Load follow-up shipment emails from CSV.

        Returns events in the same format as email ingestion pipeline.
        """
        events: list[dict[str, Any]] = []
        try:
            with open(path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    events.append({
                        "source": "shipment_update",
                        "reference_id": row.get("email_id", ""),
                        "supplier": row.get("supplier", ""),
                        "event_time": row.get("date", ""),
                        "text": f"{row.get('subject', '')}. {row.get('body', '')}",
                        "metadata": {
                            "subject": row.get("subject", ""),
                            "sender_name": row.get("supplier", ""),
                            "origin_location": row.get("origin_location", ""),
                            "eta_days": row.get("eta_days", ""),
                            "material": row.get("material", ""),
                            "is_update": row.get("is_update", "false").lower() == "true",
                        },
                    })
            logger.info(f"Loaded {len(events)} shipment update events from {path}")
        except FileNotFoundError:
            logger.warning(f"Shipment updates file not found: {path}")
        except Exception as e:
            logger.error(f"Failed to load shipment updates: {e}")
        return events

"""Vessel tracking integration for IMO/MMSI based shipment monitoring."""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

import requests

from app.models.schemas import ShipmentInput

logger = logging.getLogger(__name__)


DEMO_VESSELS = {
    "9811000": {
        "name": "EVER GIVEN",
        "imo_number": "9811000",
        "mmsi": "353136000",
        "flag": "Panama",
        "vessel_type": "Container Ship",
        "origin": "Yantian, CN",
        "destination": "Rotterdam, NL",
        "speed_knots": 13.4,
        "course_degrees": 287.0,
        "latitude": 28.94,
        "longitude": 49.23,
        "status": "UNDERWAY",
        "progress_percent": 62,
        "dwt": "220,940 DWT",
        "built": "2018",
        "eta": "2025-05-12",
        "operator": "Evergreen Marine",
    },
    "9703291": {
        "name": "MSC OSCAR",
        "imo_number": "9703291",
        "mmsi": "255806260",
        "flag": "Panama",
        "vessel_type": "Container Ship",
        "origin": "Shanghai, CN",
        "destination": "Hamburg, DE",
        "speed_knots": 11.2,
        "course_degrees": 310.0,
        "latitude": 14.5,
        "longitude": 52.3,
        "status": "ANCHORED",
        "progress_percent": 31,
        "dwt": "197,362 DWT",
        "built": "2014",
        "eta": "2025-05-20",
        "operator": "MSC",
    },
    "9795736": {
        "name": "COSCO SHIPPING UNIVERSE",
        "imo_number": "9795736",
        "mmsi": "477339800",
        "flag": "Hong Kong",
        "vessel_type": "VLCC Tanker",
        "origin": "Ras Tanura, SA",
        "destination": "Ningbo, CN",
        "speed_knots": 14.1,
        "course_degrees": 75.0,
        "latitude": 12.8,
        "longitude": 68.4,
        "status": "UNDERWAY",
        "progress_percent": 48,
        "dwt": "300,800 DWT",
        "built": "2017",
        "eta": "2025-05-08",
        "operator": "COSCO Shipping",
    },
}


class VesselTrackerClient:
    """Fetch vessel telemetry by IMO number.

    If VESSEL_TRACKER_API_URL is configured, this client calls that endpoint
    with `imo` and optional bearer auth. Otherwise, it uses the demo vessel
    records from the local vessel tracker page.
    """

    def __init__(
        self,
        api_url: str | None = None,
        api_key: str | None = None,
        timeout_seconds: int = 20,
    ) -> None:
        self.api_url = (api_url or os.getenv("VESSEL_TRACKER_API_URL") or "").strip()
        self.api_key = api_key or os.getenv("VESSEL_TRACKER_API_KEY")
        self.timeout_seconds = timeout_seconds

    def get_vessel_by_imo(self, imo_number: str) -> dict[str, Any] | None:
        """Return normalized vessel telemetry for one IMO number."""
        imo = normalize_imo(imo_number)
        if not imo:
            return None

        if self.api_url:
            try:
                return normalize_vessel_payload(self._fetch_live_vessel(imo))
            except Exception as exc:
                logger.warning("Live vessel tracker failed for IMO %s: %s", imo, exc)

        demo = DEMO_VESSELS.get(imo)
        if not demo:
            return None
        return normalize_vessel_payload({**demo, "data_source": "demo_vessel_tracker"})

    def _fetch_live_vessel(self, imo_number: str) -> dict[str, Any]:
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        response = requests.get(
            self.api_url,
            params={"imo": imo_number},
            headers=headers,
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return response.json()


def normalize_vessel_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize common vessel tracker fields into one JSON shape."""
    return {
        "name": _str_or_none(payload.get("name") or payload.get("vessel_name")),
        "imo_number": _str_or_none(payload.get("imo_number") or payload.get("imo")),
        "mmsi": _str_or_none(payload.get("mmsi")),
        "flag": _str_or_none(payload.get("flag")),
        "vessel_type": _str_or_none(payload.get("vessel_type") or payload.get("type")),
        "origin": _str_or_none(payload.get("origin") or payload.get("departure_port")),
        "destination": _str_or_none(payload.get("destination") or payload.get("dest") or payload.get("arrival_port")),
        "latitude": _float_or_none(payload.get("latitude") or payload.get("lat")),
        "longitude": _float_or_none(payload.get("longitude") or payload.get("lon")),
        "speed_knots": _float_or_none(payload.get("speed_knots") or payload.get("speed")),
        "course_degrees": _float_or_none(payload.get("course_degrees") or payload.get("course")),
        "status": _str_or_none(payload.get("status")) or "UNKNOWN",
        "progress_percent": _float_or_none(payload.get("progress_percent") or payload.get("progress")),
        "eta": _str_or_none(payload.get("eta")),
        "operator": _str_or_none(payload.get("operator")),
        "data_source": _str_or_none(payload.get("data_source")) or "live_vessel_tracker",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "raw": payload,
    }


def vessel_from_shipment(shipment: ShipmentInput) -> dict[str, Any] | None:
    """Build vessel telemetry from live tracker values already present on a shipment."""
    if shipment.vessel_latitude is None or shipment.vessel_longitude is None:
        return None

    return normalize_vessel_payload(
        {
            "name": shipment.vessel_name,
            "imo_number": shipment.imo_number,
            "mmsi": shipment.mmsi,
            "origin": shipment.origin,
            "destination": shipment.destination,
            "latitude": shipment.vessel_latitude,
            "longitude": shipment.vessel_longitude,
            "speed_knots": shipment.vessel_speed_knots,
            "course_degrees": shipment.vessel_course_degrees,
            "status": shipment.vessel_status or "UNDERWAY",
            "progress_percent": shipment.vessel_progress_percent,
            "data_source": "shipment_vessel_tracker_payload",
        }
    )


def normalize_vessel_event(vessel: dict[str, Any]) -> dict[str, Any]:
    """Convert vessel telemetry into the advisor intelligence event format."""
    name = vessel.get("name") or vessel.get("imo_number") or "Unknown vessel"
    status = vessel.get("status", "UNKNOWN")
    origin = vessel.get("origin") or "unknown origin"
    destination = vessel.get("destination") or "unknown destination"
    speed = vessel.get("speed_knots")
    speed_text = f"{speed:.1f} kn" if isinstance(speed, (int, float)) else "unknown speed"

    text = (
        f"Vessel {name} status {status}. Route {origin} to {destination}. "
        f"Current position lat {vessel.get('latitude')}, lon {vessel.get('longitude')}. "
        f"Speed {speed_text}. ETA {vessel.get('eta') or 'unknown'}."
    )

    return {
        "source": "vessel_tracker",
        "reference_id": f"VESSEL-{vessel.get('imo_number')}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "supplier": "Ocean Carrier",
        "event_time": vessel.get("fetched_at") or datetime.now(timezone.utc).isoformat(),
        "text": text,
        "metadata": {
            "title": f"Vessel tracker update: {name}",
            "summary": text,
            **vessel,
            "severity": vessel_status_severity(vessel),
        },
    }


def vessel_status_severity(vessel: dict[str, Any]) -> str:
    """Map vessel status/speed into a coarse risk severity."""
    status = str(vessel.get("status", "")).lower()
    speed = _float_or_none(vessel.get("speed_knots")) or 0.0

    if any(term in status for term in ["disabled", "aground", "not under command", "stopped"]):
        return "critical"
    if any(term in status for term in ["anchored", "moored", "waiting"]) or speed < 1.0:
        return "high"
    if speed < 6.0:
        return "medium"
    return "low"


def normalize_imo(value: str | None) -> str:
    """Normalize IMO input to digits."""
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def _str_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _float_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(str(value).replace("kn", "").replace("°", "").strip())
    except (TypeError, ValueError):
        return None

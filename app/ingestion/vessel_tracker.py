"""Vessel tracking integration for IMO/MMSI based shipment monitoring.

Fetches real-time vessel positions from the configured AIS provider
(AISHub, MarineTraffic) via the AIS engine. No hardcoded positions.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any

import requests

from app.models.schemas import ShipmentInput

logger = logging.getLogger(__name__)


class VesselTrackerClient:
    """Fetch vessel telemetry by IMO number.

    Uses the AIS engine (backed by AISHub/MarineTraffic) for real-time
    positions. Falls back to a direct HTTP call if VESSEL_TRACKER_API_URL
    is configured separately.
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
        """Return normalized vessel telemetry for one IMO number.

        Resolution order:
        1. AIS engine (real-time AISHub/MarineTraffic data)
        2. Direct VESSEL_TRACKER_API_URL if configured
        """
        imo = normalize_imo(imo_number)
        if not imo:
            return None

        # Try the AIS engine first (real-time provider)
        vessel = self._fetch_from_ais_engine(imo)
        if vessel:
            return normalize_vessel_payload({**vessel, "data_source": "ais_engine_live"})

        # Fallback: direct API URL if configured
        if self.api_url:
            try:
                return normalize_vessel_payload(self._fetch_live_vessel(imo))
            except Exception as exc:
                logger.warning("Live vessel tracker failed for IMO %s: %s", imo, exc)

        logger.warning("No real-time data available for IMO %s", imo)
        return None

    def _fetch_from_ais_engine(self, imo_number: str) -> dict[str, Any] | None:
        """Fetch from the running AIS engine synchronously."""
        try:
            from app.ingestion.ais.vessel_worker import get_vessel_worker

            worker = get_vessel_worker()
            engine = worker.engine
            if not engine:
                return None

            # Check in-memory vessel states first (latest polled data)
            vessel = engine._vessel_states.get(imo_number)
            if vessel:
                return vessel

            # Check database for latest position
            latest = engine.db.get_latest_position(imo_number)
            if latest:
                return {
                    "imo_number": imo_number,
                    "latitude": latest.get("lat"),
                    "longitude": latest.get("lon"),
                    "speed": latest.get("speed"),
                    "course": latest.get("course"),
                    "heading": latest.get("heading"),
                    "nav_status": latest.get("nav_status"),
                    "destination": latest.get("destination"),
                    "eta": latest.get("eta"),
                    "last_update": latest.get("timestamp"),
                }

            # Try a synchronous fetch from the provider
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # We're inside an async context, use thread
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        future = pool.submit(
                            asyncio.run,
                            engine.provider.get_vessel_by_imo(imo_number)
                        )
                        vessel = future.result(timeout=self.timeout_seconds)
                else:
                    vessel = loop.run_until_complete(
                        engine.provider.get_vessel_by_imo(imo_number)
                    )
                return vessel
            except Exception as exc:
                logger.debug("Direct provider fetch failed for IMO %s: %s", imo_number, exc)
                return None

        except Exception as exc:
            logger.debug("AIS engine fetch failed for IMO %s: %s", imo_number, exc)
            return None

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
        "origin": _str_or_none(payload.get("origin") or payload.get("departure_port") or payload.get("origin_port")),
        "destination": _str_or_none(payload.get("destination") or payload.get("dest") or payload.get("arrival_port")),
        "latitude": _float_or_none(payload.get("latitude") or payload.get("lat")),
        "longitude": _float_or_none(payload.get("longitude") or payload.get("lon")),
        "speed_knots": _float_or_none(payload.get("speed_knots") or payload.get("speed")),
        "course_degrees": _float_or_none(payload.get("course_degrees") or payload.get("course")),
        "status": _str_or_none(payload.get("status") or payload.get("nav_status")) or "UNKNOWN",
        "progress_percent": _float_or_none(payload.get("progress_percent") or payload.get("progress")),
        "eta": _str_or_none(payload.get("eta")),
        "operator": _str_or_none(payload.get("operator")),
        "data_source": _str_or_none(payload.get("data_source")) or "live_vessel_tracker",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "raw": payload,
    }


def vessel_from_shipment(shipment: ShipmentInput) -> dict[str, Any] | None:
    """Build vessel telemetry from live tracker values already present on a shipment.

    If the shipment has no embedded coordinates but has an IMO or MMSI number,
    fetch real-time position from the AIS engine.
    """
    # If shipment already has coordinates, use them
    if shipment.vessel_latitude is not None and shipment.vessel_longitude is not None:
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

    # No embedded coordinates — try fetching real-time from AIS engine
    # Try IMO first, then MMSI
    if shipment.imo_number:
        client = VesselTrackerClient()
        vessel = client.get_vessel_by_imo(shipment.imo_number)
        if vessel:
            vessel["origin"] = vessel.get("origin") or shipment.origin
            vessel["destination"] = vessel.get("destination") or shipment.destination
            vessel["name"] = vessel.get("name") or shipment.vessel_name
            return vessel

    # Try MMSI lookup via AIS engine
    if shipment.mmsi:
        try:
            from app.ingestion.ais.vessel_worker import get_vessel_worker
            worker = get_vessel_worker()
            engine = worker.engine
            if engine:
                # Check in-memory states keyed by MMSI
                vessel = engine._vessel_states.get(shipment.mmsi)
                if vessel:
                    return normalize_vessel_payload({
                        **vessel,
                        "origin": vessel.get("origin") or shipment.origin,
                        "destination": vessel.get("destination") or shipment.destination,
                        "name": vessel.get("name") or shipment.vessel_name,
                        "data_source": "ais_engine_mmsi_lookup",
                    })

                # Check AISStream provider cache directly
                from app.ingestion.ais.aisstream_provider import AISStreamProvider
                if isinstance(engine.provider, AISStreamProvider):
                    cached = engine.provider._mmsi_cache.get(shipment.mmsi)
                    if cached:
                        return normalize_vessel_payload({
                            **cached,
                            "origin": cached.get("origin") or shipment.origin,
                            "destination": cached.get("destination") or shipment.destination,
                            "name": cached.get("name") or shipment.vessel_name,
                            "data_source": "aisstream_mmsi_cache",
                        })
        except Exception as exc:
            logger.debug("MMSI lookup failed for %s: %s", shipment.mmsi, exc)

    return None


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

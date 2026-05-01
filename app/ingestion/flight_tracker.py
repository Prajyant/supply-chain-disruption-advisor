"""Real-time flight tracking via OpenSky Network for air cargo shipments."""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

import requests

from app.models.schemas import ShipmentInput

logger = logging.getLogger(__name__)

OPENSKY_API_URL = "https://opensky-network.org/api/states/all"

# Cache all-states responses for 30 seconds to avoid hammering the API
_states_cache: dict[str, Any] = {"data": None, "timestamp": 0.0}
_CACHE_TTL_SECONDS = 30

DEMO_FLIGHTS = {
    "FDX5678": {
        "callsign": "FDX5678",
        "icao24": "a1c2d3",
        "origin_country": "China",
        "latitude": 52.1,
        "longitude": -168.4,
        "altitude_m": 10668,
        "velocity_ms": 257.0,
        "heading": 48.0,
        "on_ground": False,
        "operator": "FedEx Express",
        "aircraft_type": "Boeing 777F",
        "origin": "Shanghai Pudong (PVG)",
        "destination": "Memphis (MEM)",
    },
    "UAE9872": {
        "callsign": "UAE9872",
        "icao24": "b4e5f6",
        "origin_country": "United Arab Emirates",
        "latitude": 38.2,
        "longitude": 42.6,
        "altitude_m": 11582,
        "velocity_ms": 248.0,
        "heading": 315.0,
        "on_ground": False,
        "operator": "Emirates SkyCargo",
        "aircraft_type": "Boeing 777F",
        "origin": "Dubai (DXB)",
        "destination": "Frankfurt (FRA)",
    },
}


class FlightTrackerClient:
    """Fetch real-time aircraft positions from OpenSky Network.

    Looks up flights by callsign or ICAO24 transponder code. Falls back to
    demo flight data when OpenSky is unreachable or the flight is not airborne.
    """

    def __init__(self, timeout_seconds: int = 30) -> None:
        self.timeout_seconds = timeout_seconds

    def get_flight_by_callsign(self, callsign: str) -> dict[str, Any] | None:
        """Return normalized flight telemetry for a callsign (e.g. 'FDX5678')."""
        normalized = callsign.strip().upper()
        if not normalized:
            return None

        # Try live OpenSky lookup
        try:
            state = self._find_state_by_callsign(normalized)
            if state:
                return normalize_flight_payload(parse_state_vector(state), data_source="opensky_live")
        except Exception as exc:
            logger.warning("OpenSky callsign lookup failed for %s: %s", normalized, exc)

        # Fall back to demo data
        demo = DEMO_FLIGHTS.get(normalized)
        if demo:
            return normalize_flight_payload(demo, data_source="demo_flight_tracker")

        return None

    def get_flight_by_icao24(self, icao24: str) -> dict[str, Any] | None:
        """Return normalized flight telemetry for an ICAO24 hex code."""
        hex_code = icao24.strip().lower()
        if not hex_code:
            return None

        try:
            state = self._fetch_by_icao24(hex_code)
            if state:
                return normalize_flight_payload(parse_state_vector(state), data_source="opensky_live")
        except Exception as exc:
            logger.warning("OpenSky ICAO24 lookup failed for %s: %s", hex_code, exc)

        # Check demo data by icao24
        for demo in DEMO_FLIGHTS.values():
            if demo.get("icao24", "").lower() == hex_code:
                return normalize_flight_payload(demo, data_source="demo_flight_tracker")

        return None

    def _fetch_by_icao24(self, icao24: str) -> list | None:
        """Direct ICAO24 lookup — fast, single aircraft."""
        response = requests.get(
            OPENSKY_API_URL,
            params={"icao24": icao24},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()
        states = data.get("states") or []
        return states[0] if states else None

    def _find_state_by_callsign(self, callsign: str) -> list | None:
        """Search all airborne aircraft for a matching callsign."""
        states = self._get_cached_states()
        if not states:
            return None

        for state in states:
            if state[1] and state[1].strip().upper() == callsign:
                return state

        return None

    def _get_cached_states(self) -> list:
        """Get all-states from OpenSky with a 30-second cache."""
        now = time.time()
        if _states_cache["data"] is not None and (now - _states_cache["timestamp"]) < _CACHE_TTL_SECONDS:
            return _states_cache["data"]

        response = requests.get(OPENSKY_API_URL, timeout=self.timeout_seconds)
        response.raise_for_status()
        data = response.json()
        states = data.get("states") or []
        _states_cache["data"] = states
        _states_cache["timestamp"] = now
        logger.info("Cached %d aircraft states from OpenSky", len(states))
        return states


def parse_state_vector(state: list) -> dict[str, Any]:
    """Parse an OpenSky state vector array into a readable dict.

    State vector indices:
    0: icao24, 1: callsign, 2: origin_country, 3: time_position,
    4: last_contact, 5: longitude, 6: latitude, 7: baro_altitude,
    8: on_ground, 9: velocity (m/s), 10: true_track, 11: vertical_rate,
    12: sensors, 13: geo_altitude, 14: squawk, 15: spi, 16: position_source
    """
    return {
        "icao24": _safe_index(state, 0),
        "callsign": _safe_str(state, 1),
        "origin_country": _safe_str(state, 2),
        "latitude": _safe_float(state, 6),
        "longitude": _safe_float(state, 5),
        "altitude_m": _safe_float(state, 7) or _safe_float(state, 13),
        "on_ground": _safe_bool(state, 8),
        "velocity_ms": _safe_float(state, 9),
        "heading": _safe_float(state, 10),
        "vertical_rate": _safe_float(state, 11),
        "squawk": _safe_str(state, 14),
    }


def normalize_flight_payload(payload: dict[str, Any], data_source: str = "opensky_live") -> dict[str, Any]:
    """Normalize flight data into a consistent JSON shape."""
    velocity_ms = payload.get("velocity_ms") or 0.0
    speed_knots = velocity_ms * 1.94384 if velocity_ms else None

    return {
        "callsign": _str_or_none(payload.get("callsign")),
        "icao24": _str_or_none(payload.get("icao24")),
        "origin_country": _str_or_none(payload.get("origin_country")),
        "operator": _str_or_none(payload.get("operator")),
        "aircraft_type": _str_or_none(payload.get("aircraft_type")),
        "origin": _str_or_none(payload.get("origin")),
        "destination": _str_or_none(payload.get("destination")),
        "latitude": payload.get("latitude"),
        "longitude": payload.get("longitude"),
        "altitude_m": payload.get("altitude_m"),
        "altitude_ft": round(payload["altitude_m"] * 3.28084) if payload.get("altitude_m") else None,
        "speed_knots": round(speed_knots, 1) if speed_knots else None,
        "heading": payload.get("heading"),
        "on_ground": payload.get("on_ground", False),
        "vertical_rate": payload.get("vertical_rate"),
        "status": "ON_GROUND" if payload.get("on_ground") else "IN_FLIGHT",
        "data_source": data_source,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def flight_from_shipment(shipment: ShipmentInput) -> dict[str, Any] | None:
    """Build flight telemetry from values already present on a shipment."""
    if shipment.transport_mode.lower().strip() != "air":
        return None
    if shipment.vessel_latitude is None or shipment.vessel_longitude is None:
        return None

    return normalize_flight_payload(
        {
            "callsign": shipment.flight_callsign or shipment.vessel_name,
            "icao24": shipment.flight_icao24,
            "latitude": shipment.vessel_latitude,
            "longitude": shipment.vessel_longitude,
            "altitude_m": shipment.flight_altitude_m,
            "velocity_ms": (shipment.vessel_speed_knots or 0) / 1.94384 if shipment.vessel_speed_knots else None,
            "heading": shipment.vessel_course_degrees,
            "on_ground": False,
            "origin": shipment.origin,
            "destination": shipment.destination,
        },
        data_source="shipment_flight_payload",
    )


def normalize_flight_event(flight: dict[str, Any]) -> dict[str, Any]:
    """Convert flight telemetry into the advisor intelligence event format."""
    callsign = flight.get("callsign") or flight.get("icao24") or "Unknown flight"
    status = flight.get("status", "UNKNOWN")
    origin = flight.get("origin") or "unknown origin"
    destination = flight.get("destination") or "unknown destination"
    altitude = flight.get("altitude_ft")
    altitude_text = f"{altitude:,} ft" if altitude else "unknown altitude"
    speed = flight.get("speed_knots")
    speed_text = f"{speed:.0f} kn" if speed else "unknown speed"

    text = (
        f"Flight {callsign} status {status}. Route {origin} to {destination}. "
        f"Current position lat {flight.get('latitude')}, lon {flight.get('longitude')}. "
        f"Altitude {altitude_text}. Speed {speed_text}."
    )

    return {
        "source": "flight_tracker",
        "reference_id": f"FLIGHT-{callsign}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "supplier": "Air Carrier",
        "event_time": flight.get("fetched_at") or datetime.now(timezone.utc).isoformat(),
        "text": text,
        "metadata": {
            "title": f"Flight tracker update: {callsign}",
            "summary": text,
            **flight,
            "severity": flight_status_severity(flight),
        },
    }


def flight_status_severity(flight: dict[str, Any]) -> str:
    """Map flight status into a coarse risk severity."""
    if flight.get("on_ground"):
        return "high"
    status = str(flight.get("status", "")).lower()
    if "ground" in status or "delayed" in status or "diverted" in status:
        return "high"
    speed = flight.get("speed_knots") or 0
    if speed < 50 and not flight.get("on_ground"):
        return "medium"
    return "low"


def _safe_index(lst: list, idx: int) -> Any:
    return lst[idx] if idx < len(lst) else None


def _safe_str(lst: list, idx: int) -> str | None:
    val = _safe_index(lst, idx)
    return str(val).strip() if val is not None else None


def _safe_float(lst: list, idx: int) -> float | None:
    val = _safe_index(lst, idx)
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _safe_bool(lst: list, idx: int) -> bool:
    val = _safe_index(lst, idx)
    return bool(val) if val is not None else False


def _str_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None

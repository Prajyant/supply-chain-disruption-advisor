"""
Abstract base class for async AIS data providers.

Adapted from maritime_ai_platform/ais/provider_base.py:
- Converted from sync to async (httpx-based)
- Added IMO as primary lookup key
- Added batch operations for watchlist polling
- Added vessel track history retrieval
"""

from abc import ABC, abstractmethod
from typing import Any


class AISProviderBase(ABC):
    """Abstract async AIS data provider interface.

    All providers must implement IMO-based lookups and async HTTP calls.
    The primary key for vessel identification is IMO number (not MMSI).
    """

    @abstractmethod
    async def get_vessel_by_imo(self, imo_number: str) -> dict[str, Any] | None:
        """Fetch current position and status for a vessel by IMO number.

        Args:
            imo_number: The vessel's IMO number (7 digits).

        Returns:
            Normalized vessel dict or None if not found.
        """
        ...

    @abstractmethod
    async def get_vessel_track(
        self, imo_number: str, hours: int = 24
    ) -> list[dict[str, Any]]:
        """Fetch historical track (position history) for a vessel.

        Args:
            imo_number: The vessel's IMO number.
            hours: Number of hours of history to retrieve.

        Returns:
            List of position dicts ordered by timestamp ascending.
        """
        ...

    @abstractmethod
    async def search_vessel(self, query: str) -> list[dict[str, Any]]:
        """Search for vessels by name (partial match).

        Args:
            query: Vessel name or partial name.

        Returns:
            List of matching vessel identity dicts.
        """
        ...

    @abstractmethod
    async def get_vessels_batch(
        self, imo_numbers: list[str]
    ) -> list[dict[str, Any]]:
        """Fetch current positions for multiple vessels.

        Implementations should handle rate limiting internally.

        Args:
            imo_numbers: List of IMO numbers to fetch.

        Returns:
            List of normalized vessel dicts (may be fewer than input if some fail).
        """
        ...

    @abstractmethod
    async def is_available(self) -> bool:
        """Check if the provider API is reachable and authenticated."""
        ...

    @staticmethod
    def normalize_vessel_data(raw: dict[str, Any]) -> dict[str, Any]:
        """Normalize raw provider data to standard format.

        Standard vessel dict keys:
        - imo_number, mmsi, name, vessel_type, call_sign, flag
        - length, beam, draught
        - latitude, longitude, course, speed, heading
        - destination, eta, nav_status, last_update
        """
        return {
            "imo_number": str(raw.get("imo_number") or raw.get("imo") or "").strip(),
            "mmsi": str(raw.get("mmsi") or "").strip(),
            "name": str(raw.get("name") or raw.get("vessel_name") or "Unknown").strip(),
            "vessel_type": str(raw.get("vessel_type") or "Unknown"),
            "call_sign": str(raw.get("call_sign") or raw.get("callsign") or ""),
            "flag": str(raw.get("flag") or ""),
            "length": _safe_float(raw.get("length")),
            "beam": _safe_float(raw.get("beam") or raw.get("width")),
            "draught": _safe_float(raw.get("draught")),
            "latitude": _safe_float(raw.get("latitude") or raw.get("lat")),
            "longitude": _safe_float(raw.get("longitude") or raw.get("lon")),
            "course": _safe_float(raw.get("course") or raw.get("cog")),
            "speed": _safe_float(raw.get("speed") or raw.get("sog")),
            "heading": _safe_float(raw.get("heading")),
            "destination": str(raw.get("destination") or ""),
            "eta": str(raw.get("eta") or ""),
            "nav_status": str(raw.get("nav_status") or ""),
            "last_update": str(raw.get("last_update") or ""),
        }


def _safe_float(value: Any) -> float:
    """Safely convert a value to float, returning 0.0 on failure."""
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0

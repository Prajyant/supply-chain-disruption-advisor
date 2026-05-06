"""
AISHub async data provider.

Adapted from maritime_ai_platform/ais/aishub_provider.py:
- Converted from sync requests to async httpx
- Added IMO-based lookup (AISHub primarily uses MMSI, so we maintain an IMO→MMSI map)
- Added rate-limit handling for 60-vessel watchlists
- Added batch operations with staggered requests
"""

import asyncio
import logging
from datetime import datetime
from typing import Any

import httpx

from app.ingestion.ais.provider_base import AISProviderBase

logger = logging.getLogger(__name__)

# AISHub vessel type classification (AIS type codes)
VESSEL_TYPE_MAP = {
    range(20, 30): "Wing in Ground",
    range(30, 36): "Fishing",
    range(36, 40): "Sailing/Pleasure",
    range(40, 50): "High Speed Craft",
    range(50, 55): "Special Craft",
    range(60, 70): "Passenger",
    range(70, 80): "Cargo",
    range(80, 90): "Tanker",
    range(90, 100): "Other",
}


def classify_vessel_type(type_code: int) -> str:
    """Map AIS numeric type code to human-readable vessel type."""
    for range_key, name in VESSEL_TYPE_MAP.items():
        if type_code in range_key:
            return name
    if type_code == 35:
        return "Military"
    return "Unknown"


class AISHubProvider(AISProviderBase):
    """AISHub API provider — async implementation.

    AISHub returns all vessels in a geographic area. To support IMO-based
    lookups, we fetch all vessels and filter by IMO. For batch operations,
    we use a single API call and filter the results.

    Rate limit: AISHub allows ~1 request per minute on most plans.
    """

    def __init__(self, api_key: str, base_url: str = "http://data.aishub.net/ws.php"):
        self.api_key = api_key
        self.base_url = base_url
        self._client: httpx.AsyncClient | None = None
        # Cache: IMO → latest vessel data (refreshed on each fetch)
        self._imo_cache: dict[str, dict[str, Any]] = {}
        self._last_fetch: datetime | None = None
        # Rate limit: minimum seconds between API calls
        self._min_interval = 60.0
        self._fetch_lock = asyncio.Lock()

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers={"User-Agent": "SupplyChainAdvisor/1.0"},
            )
        return self._client

    async def _fetch_all_vessels(self) -> list[dict[str, Any]]:
        """Fetch all vessels from AISHub, respecting rate limits."""
        async with self._fetch_lock:
            # Rate limit check
            if self._last_fetch:
                elapsed = (datetime.utcnow() - self._last_fetch).total_seconds()
                if elapsed < self._min_interval:
                    # Return cached data instead of hitting API
                    return list(self._imo_cache.values())

            client = await self._get_client()
            params = {
                "username": self.api_key,
                "format": "1",
                "output": "json",
                "compress": "0",
            }

            try:
                response = await client.get(self.base_url, params=params)
                response.raise_for_status()
                data = response.json()

                if isinstance(data, list) and len(data) >= 2:
                    metadata = data[0]
                    vessels_raw = data[1]

                    if isinstance(metadata, dict) and metadata.get("ERROR", False):
                        logger.error(f"AISHub API error: {metadata}")
                        return list(self._imo_cache.values())

                    vessels = []
                    self._imo_cache.clear()
                    for raw in vessels_raw:
                        vessel = self._parse_vessel(raw)
                        if vessel and vessel["latitude"] != 0 and vessel["longitude"] != 0:
                            vessels.append(vessel)
                            if vessel["imo_number"]:
                                self._imo_cache[vessel["imo_number"]] = vessel

                    self._last_fetch = datetime.utcnow()
                    logger.info(f"AISHub: Fetched {len(vessels)} vessels, {len(self._imo_cache)} with IMO")
                    return vessels

                logger.warning("AISHub: Unexpected response format")
                return list(self._imo_cache.values())

            except httpx.TimeoutException:
                logger.error("AISHub API timeout")
                return list(self._imo_cache.values())
            except httpx.HTTPError as e:
                logger.error(f"AISHub API request failed: {e}")
                return list(self._imo_cache.values())
            except (ValueError, KeyError) as e:
                logger.error(f"AISHub API parse error: {e}")
                return list(self._imo_cache.values())

    async def get_vessel_by_imo(self, imo_number: str) -> dict[str, Any] | None:
        """Fetch vessel by IMO. Uses cached data or triggers a fresh fetch."""
        imo = imo_number.strip()
        if imo in self._imo_cache:
            return self._imo_cache[imo]

        # Trigger a fresh fetch
        await self._fetch_all_vessels()
        return self._imo_cache.get(imo)

    async def get_vessel_track(
        self, imo_number: str, hours: int = 24
    ) -> list[dict[str, Any]]:
        """AISHub does not provide historical tracks — returns empty list.

        Route history is stored locally in vessel_positions table.
        """
        return []

    async def search_vessel(self, query: str) -> list[dict[str, Any]]:
        """Search cached vessels by name."""
        query_lower = query.lower()
        await self._fetch_all_vessels()
        return [
            v for v in self._imo_cache.values()
            if query_lower in v.get("name", "").lower()
        ]

    async def get_vessels_batch(
        self, imo_numbers: list[str]
    ) -> list[dict[str, Any]]:
        """Fetch positions for multiple IMOs.

        AISHub returns all vessels in one call, so we fetch once and filter.
        """
        await self._fetch_all_vessels()
        results = []
        for imo in imo_numbers:
            vessel = self._imo_cache.get(imo.strip())
            if vessel:
                results.append(vessel)
        return results

    async def is_available(self) -> bool:
        """Check if AISHub API is reachable."""
        try:
            client = await self._get_client()
            response = await client.get(
                self.base_url,
                params={
                    "username": self.api_key,
                    "format": "1",
                    "output": "json",
                    "compress": "0",
                },
                timeout=10.0,
            )
            return response.status_code == 200
        except Exception:
            return False

    def _parse_vessel(self, raw: dict[str, Any]) -> dict[str, Any] | None:
        """Parse AISHub raw vessel data to normalized format."""
        try:
            type_code = int(raw.get("TYPE", 0) or 0)

            # AISHub uses scaled integers for lat/lon in some responses
            raw_lat = float(raw.get("LATITUDE", 0) or 0)
            raw_lon = float(raw.get("LONGITUDE", 0) or 0)
            lat = raw_lat / 600000.0 if abs(raw_lat) > 1000 else raw_lat
            lon = raw_lon / 600000.0 if abs(raw_lon) > 1000 else raw_lon

            raw_cog = float(raw.get("COG", 0) or 0)
            raw_sog = float(raw.get("SOG", 0) or 0)
            course = raw_cog / 10.0 if raw_cog > 360 else raw_cog
            speed = raw_sog / 10.0 if raw_sog > 100 else raw_sog

            imo_raw = str(raw.get("IMO", "") or "")
            # Strip "IMO" prefix if present, keep only digits
            imo_number = "".join(c for c in imo_raw if c.isdigit())

            return {
                "imo_number": imo_number,
                "mmsi": str(raw.get("MMSI", "")),
                "name": str(raw.get("NAME", "Unknown")).strip(),
                "vessel_type": classify_vessel_type(type_code),
                "call_sign": str(raw.get("CALLSIGN", "")),
                "flag": str(raw.get("FLAG", "")),
                "length": float(raw.get("A", 0) or 0) + float(raw.get("B", 0) or 0),
                "beam": float(raw.get("C", 0) or 0) + float(raw.get("D", 0) or 0),
                "draught": float(raw.get("DRAUGHT", 0) or 0) / 10.0,
                "latitude": lat,
                "longitude": lon,
                "course": course,
                "speed": speed,
                "heading": float(raw.get("HEADING", 0) or 0),
                "destination": str(raw.get("DEST", "") or ""),
                "eta": str(raw.get("ETA", "") or ""),
                "nav_status": str(raw.get("NAVSTAT", "") or ""),
                "last_update": str(raw.get("TIME", "") or datetime.utcnow().isoformat()),
            }
        except (ValueError, TypeError) as e:
            logger.debug(f"Failed to parse AISHub vessel: {e}")
            return None

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

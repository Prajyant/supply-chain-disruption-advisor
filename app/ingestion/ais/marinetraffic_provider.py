"""
MarineTraffic async data provider.

Adapted from maritime_ai_platform/ais/marinetraffic_provider.py:
- Converted from sync requests to async httpx
- Added IMO-based lookup endpoints (MarineTraffic supports direct IMO queries)
- Added rate-limit handling with staggered requests
- Added vessel track history via their track API
"""

import asyncio
import logging
from datetime import datetime
from typing import Any

import httpx

from app.ingestion.ais.provider_base import AISProviderBase
from app.ingestion.ais.aishub_provider import classify_vessel_type

logger = logging.getLogger(__name__)


class MarineTrafficProvider(AISProviderBase):
    """MarineTraffic API provider — async implementation.

    MarineTraffic supports direct IMO lookups and historical track data.
    Rate limits vary by plan; we implement a semaphore to control concurrency.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://services.marinetraffic.com/api",
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._client: httpx.AsyncClient | None = None
        # Concurrency limiter: max 2 concurrent requests to avoid rate limits
        self._semaphore = asyncio.Semaphore(2)
        # Minimum delay between requests (seconds)
        self._request_delay = 1.0

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers={"User-Agent": "SupplyChainAdvisor/1.0"},
            )
        return self._client

    async def get_vessel_by_imo(self, imo_number: str) -> dict[str, Any] | None:
        """Fetch vessel position by IMO using MarineTraffic PS07 (Single Vessel Positions)."""
        async with self._semaphore:
            client = await self._get_client()
            # PS07 endpoint: single vessel position by IMO
            url = f"{self.base_url}/exportvessel/v:5/{self.api_key}/imo:{imo_number}/protocol:jsono"

            try:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()

                if isinstance(data, list) and data:
                    return self._parse_vessel(data[0])
                elif isinstance(data, dict):
                    # Some endpoints return a single object
                    return self._parse_vessel(data)

                logger.warning(f"MarineTraffic: No data for IMO {imo_number}")
                return None

            except httpx.TimeoutException:
                logger.error(f"MarineTraffic timeout for IMO {imo_number}")
                return None
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    logger.info(f"MarineTraffic: IMO {imo_number} not found")
                else:
                    logger.error(f"MarineTraffic HTTP error for IMO {imo_number}: {e}")
                return None
            except Exception as e:
                logger.error(f"MarineTraffic error for IMO {imo_number}: {e}")
                return None

    async def get_vessel_track(
        self, imo_number: str, hours: int = 24
    ) -> list[dict[str, Any]]:
        """Fetch vessel track history using MarineTraffic PS06 (Vessel Historical Track)."""
        async with self._semaphore:
            client = await self._get_client()
            # PS06 endpoint: vessel track
            url = (
                f"{self.base_url}/exportvesseltrack/v:2/{self.api_key}"
                f"/imo:{imo_number}/days:{max(1, hours // 24)}/protocol:jsono"
            )

            try:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()

                if isinstance(data, list):
                    positions = []
                    for point in data:
                        positions.append({
                            "latitude": float(point.get("LAT", 0) or 0),
                            "longitude": float(point.get("LON", 0) or 0),
                            "speed": float(point.get("SPEED", 0) or 0) / 10.0,
                            "course": float(point.get("COURSE", 0) or 0),
                            "timestamp": str(point.get("TIMESTAMP", "")),
                        })
                    return positions

                return []

            except Exception as e:
                logger.error(f"MarineTraffic track error for IMO {imo_number}: {e}")
                return []

    async def search_vessel(self, query: str) -> list[dict[str, Any]]:
        """Search vessels by name using MarineTraffic VD01 (Vessel Data)."""
        async with self._semaphore:
            client = await self._get_client()
            url = (
                f"{self.base_url}/exportvessels/v:8/{self.api_key}"
                f"/shipname:{query}/protocol:jsono"
            )

            try:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()

                if isinstance(data, list):
                    return [self._parse_vessel(v) for v in data if v]

                return []

            except Exception as e:
                logger.error(f"MarineTraffic search error for '{query}': {e}")
                return []

    async def get_vessels_batch(
        self, imo_numbers: list[str]
    ) -> list[dict[str, Any]]:
        """Fetch positions for multiple IMOs with staggered requests.

        Staggers requests with a delay to respect rate limits.
        """
        results = []
        for i, imo in enumerate(imo_numbers):
            if i > 0:
                await asyncio.sleep(self._request_delay)
            vessel = await self.get_vessel_by_imo(imo)
            if vessel:
                results.append(vessel)
        return results

    async def is_available(self) -> bool:
        """Check if MarineTraffic API is reachable."""
        try:
            client = await self._get_client()
            # Use a lightweight endpoint to check connectivity
            url = f"{self.base_url}/exportvessels/v:8/{self.api_key}/protocol:jsono"
            response = await client.head(url, timeout=10.0)
            return response.status_code in (200, 401, 403)
        except Exception:
            return False

    def _parse_vessel(self, raw: dict[str, Any]) -> dict[str, Any] | None:
        """Parse MarineTraffic raw vessel data to normalized format."""
        try:
            type_code = int(raw.get("SHIP_TYPE", 0) or raw.get("TYPE_NAME", 0) or 0)
            type_name = raw.get("TYPE_NAME", "") or classify_vessel_type(type_code)

            raw_speed = float(raw.get("SPEED", 0) or raw.get("SOG", 0) or 0)
            # MarineTraffic returns speed in tenths of knots
            speed = raw_speed / 10.0 if raw_speed > 50 else raw_speed

            imo_raw = str(raw.get("IMO", "") or "")
            imo_number = "".join(c for c in imo_raw if c.isdigit())

            return {
                "imo_number": imo_number,
                "mmsi": str(raw.get("MMSI", "")),
                "name": str(raw.get("SHIPNAME", "") or raw.get("NAME", "Unknown")).strip(),
                "vessel_type": type_name if isinstance(type_name, str) else str(type_name),
                "call_sign": str(raw.get("CALLSIGN", "")),
                "flag": str(raw.get("FLAG", "")),
                "length": float(raw.get("LENGTH", 0) or 0),
                "beam": float(raw.get("WIDTH", 0) or 0),
                "draught": float(raw.get("DRAUGHT", 0) or 0),
                "latitude": float(raw.get("LAT", 0) or 0),
                "longitude": float(raw.get("LON", 0) or 0),
                "course": float(raw.get("COURSE", 0) or raw.get("COG", 0) or 0),
                "speed": speed,
                "heading": float(raw.get("HEADING", 0) or 0),
                "destination": str(raw.get("DESTINATION", "") or ""),
                "eta": str(raw.get("ETA", "") or ""),
                "nav_status": str(raw.get("STATUS", "") or raw.get("NAVSTAT", "") or ""),
                "last_update": str(
                    raw.get("TIMESTAMP", "")
                    or raw.get("LAST_POS", "")
                    or datetime.utcnow().isoformat()
                ),
            }
        except (ValueError, TypeError) as e:
            logger.debug(f"Failed to parse MarineTraffic vessel: {e}")
            return None

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

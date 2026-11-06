"""VesselAPI REST provider for live AIS positions and vessel search."""
from __future__ import annotations

import logging
import asyncio
from datetime import datetime, timezone
from typing import Any

import httpx

from app.ingestion.ais.provider_base import AISProviderBase

logger = logging.getLogger(__name__)


class VesselApiProvider(AISProviderBase):
    """Provider for https://api.vesselapi.com/v1.

    VesselAPI accepts batch queries for up to 50 identifiers by MMSI or IMO.
    Fetches real-time live AIS positions across global commercial fleets.
    """

    def __init__(self, api_key: str, base_url: str = "https://api.vesselapi.com/v1"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "User-Agent": "SupplyChainAdvisor/1.0",
                },
            )
        return self._client

    @staticmethod
    def _identifier_type(identifier: str) -> str:
        # MMSIs are 9 digits; IMO numbers are 7 digits.
        digits = "".join(filter(str.isdigit, str(identifier)))
        return "mmsi" if len(digits) == 9 else "imo"

    async def get_vessel_by_imo(self, imo_number: str) -> dict[str, Any] | None:
        identifier = str(imo_number).strip()
        if not identifier:
            return None
        client = await self._get_client()
        id_type = self._identifier_type(identifier)
        try:
            response = await client.get(
                f"{self.base_url}/vessel/{identifier}/position",
                params={"filter.idType": id_type},
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            data = response.json()
            # If response is a list or has vesselPosition key
            raw = data.get("vesselPosition") if isinstance(data, dict) else data
            if isinstance(raw, dict):
                return self._parse_position(raw)
            return None
        except httpx.HTTPError as exc:
            logger.warning("VesselAPI lookup failed for %s: %s", identifier, exc)
            return None

    async def get_vessels_batch(self, identifiers: list[str]) -> list[dict[str, Any]]:
        cleaned = [str(val).strip() for val in identifiers if val and str(val).strip()]
        if not cleaned:
            return []

        # Separate into MMSIs and IMOs so VesselAPI filter.idType matches
        mmsis = [v for v in cleaned if self._identifier_type(v) == "mmsi"][:50]
        imos = [v for v in cleaned if self._identifier_type(v) == "imo"][:50]

        client = await self._get_client()
        raw_positions: list[dict[str, Any]] = []

        async def fetch_subset(ids: list[str], id_type: str):
            if not ids:
                return
            try:
                response = await client.get(
                    f"{self.base_url}/vessels/positions",
                    params={
                        "filter.ids": ",".join(ids),
                        "filter.idType": id_type,
                        "pagination.limit": 50,
                    },
                )
                response.raise_for_status()
                data = response.json()
                items = data.get("vesselPositions", [])
                raw_positions.extend(items)
            except httpx.HTTPError as exc:
                logger.warning("VesselAPI batch fetch failed for %s: %s", id_type, exc)

        tasks = []
        if mmsis:
            tasks.append(fetch_subset(mmsis, "mmsi"))
        if imos:
            tasks.append(fetch_subset(imos, "imo"))

        if tasks:
            await asyncio.gather(*tasks)

        # De-duplicate: Keep only newest observation per vessel
        newest: dict[str, dict[str, Any]] = {}
        for raw in raw_positions:
            mmsi = str(raw.get("mmsi") or "")
            imo = str(raw.get("imo") or "")
            key = imo if imo and imo != "0" else mmsi
            if not key:
                continue
            ts = str(raw.get("timestamp") or "")
            if key not in newest or ts > str(newest[key].get("timestamp", "")):
                newest[key] = raw

        return [self._parse_position(raw) for raw in newest.values()]

    async def get_vessel_track(self, imo_number: str, hours: int = 24) -> list[dict[str, Any]]:
        # The application persists positions in SQLite; returns stored track
        return []

    async def search_vessel(self, query: str) -> list[dict[str, Any]]:
        client = await self._get_client()
        try:
            response = await client.get(
                f"{self.base_url}/search/vessels",
                params={"filter.name": query, "pagination.limit": 20},
            )
            response.raise_for_status()
            data = response.json()
            results = []
            for item in data.get("vessels", []):
                norm = self.normalize_vessel_data(item)
                results.append(norm)
            return results
        except httpx.HTTPError as exc:
            logger.warning("VesselAPI search failed for %s: %s", query, exc)
            return []

    async def is_available(self) -> bool:
        client = await self._get_client()
        try:
            response = await client.get(
                f"{self.base_url}/vessels/positions",
                params={"filter.ids": "305268000", "filter.idType": "mmsi"},
            )
            return response.status_code in (200, 404)
        except httpx.HTTPError:
            return False

    def _parse_position(self, raw: dict[str, Any]) -> dict[str, Any]:
        imo = str(raw.get("imo") or "").strip()
        mmsi = str(raw.get("mmsi") or "").strip()
        if imo == "0":
            imo = ""
        # Guarantee non-empty identifier
        identifier = imo if imo else mmsi

        name = str(raw.get("vessel_name") or raw.get("name") or raw.get("name_ais") or f"Vessel {identifier}").strip()

        try:
            lat = float(raw.get("latitude") or 0.0)
            lon = float(raw.get("longitude") or 0.0)
        except (ValueError, TypeError):
            lat, lon = 0.0, 0.0

        try:
            speed = float(raw.get("sog") or raw.get("speed") or 0.0)
        except (ValueError, TypeError):
            speed = 0.0

        try:
            course = float(raw.get("cog") or raw.get("course") or 0.0)
        except (ValueError, TypeError):
            course = 0.0

        try:
            heading = float(raw.get("heading") or course or 0.0)
        except (ValueError, TypeError):
            heading = course

        return {
            "imo_number": identifier,
            "mmsi": mmsi,
            "name": name,
            "vessel_type": str(raw.get("vessel_type") or "Cargo"),
            "call_sign": str(raw.get("call_sign") or ""),
            "flag": str(raw.get("country") or raw.get("flag") or ""),
            "length": float(raw.get("length") or 0.0),
            "beam": float(raw.get("breadth") or raw.get("beam") or 0.0),
            "draught": float(raw.get("draught_calculated_avg") or raw.get("draught") or 0.0),
            "latitude": lat,
            "longitude": lon,
            "course": course,
            "speed": speed,
            "heading": heading,
            "destination": str(raw.get("destination") or ""),
            "eta": str(raw.get("eta") or ""),
            "nav_status": str(raw.get("nav_status") or ""),
            "last_update": str(raw.get("timestamp") or datetime.now(timezone.utc).isoformat()),
        }

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

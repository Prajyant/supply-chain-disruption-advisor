"""
MarineTraffic data provider implementation.
Fetches real-time AIS data from the MarineTraffic API.
"""

import logging
import requests
from typing import List, Dict, Any, Optional
from datetime import datetime

from ais.provider_base import AISProviderBase
from ais.aishub_provider import classify_vessel_type

logger = logging.getLogger(__name__)


class MarineTrafficProvider(AISProviderBase):
    """MarineTraffic API provider for real-time AIS vessel data."""

    def __init__(self, api_key: str, base_url: str = "https://services.marinetraffic.com/api/exportvessels/v:8"):
        self.api_key = api_key
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "MaritimeAI-Platform/1.0"})

    def fetch_vessels(self, bounds: Dict[str, float] = None) -> List[Dict[str, Any]]:
        """Fetch vessels from MarineTraffic API."""
        url = f"{self.base_url}/{self.api_key}/protocol:jsono"

        params = {}
        if bounds:
            params["MINLAT"] = bounds.get("lat_min", -90)
            params["MAXLAT"] = bounds.get("lat_max", 90)
            params["MINLON"] = bounds.get("lon_min", -180)
            params["MAXLON"] = bounds.get("lon_max", 180)

        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            vessels = []
            if isinstance(data, list):
                for raw in data:
                    vessel = self._parse_mt_vessel(raw)
                    if vessel and vessel["latitude"] != 0 and vessel["longitude"] != 0:
                        vessels.append(vessel)

            logger.info(f"MarineTraffic: Fetched {len(vessels)} vessels")
            return vessels

        except requests.exceptions.Timeout:
            logger.error("MarineTraffic API timeout")
            return []
        except requests.exceptions.RequestException as e:
            logger.error(f"MarineTraffic API request failed: {e}")
            return []
        except (ValueError, KeyError) as e:
            logger.error(f"MarineTraffic API parse error: {e}")
            return []

    def get_vessel_details(self, mmsi: str) -> Dict[str, Any]:
        """Fetch details for a specific vessel."""
        url = f"{self.base_url}/{self.api_key}/protocol:jsono/mmsi:{mmsi}"
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()
            if isinstance(data, list) and data:
                return self._parse_mt_vessel(data[0])
        except Exception as e:
            logger.error(f"MarineTraffic vessel detail fetch failed for {mmsi}: {e}")
        return {}

    def is_available(self) -> bool:
        """Check if MarineTraffic API is reachable."""
        try:
            response = self.session.head(
                f"{self.base_url}/{self.api_key}/protocol:jsono",
                timeout=10
            )
            return response.status_code in (200, 401, 403)
        except Exception:
            return False

    def _parse_mt_vessel(self, raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse MarineTraffic raw vessel data to standard format."""
        try:
            type_code = int(raw.get("SHIP_TYPE", 0) or raw.get("TYPE_NAME", 0) or 0)
            vessel = {
                "mmsi": str(raw.get("MMSI", "")),
                "imo": str(raw.get("IMO", "")),
                "name": str(raw.get("SHIPNAME", "") or raw.get("NAME", "Unknown")).strip(),
                "vessel_type": raw.get("TYPE_NAME", "") or classify_vessel_type(type_code),
                "callsign": str(raw.get("CALLSIGN", "")),
                "flag": str(raw.get("FLAG", "")),
                "length": float(raw.get("LENGTH", 0) or 0),
                "width": float(raw.get("WIDTH", 0) or 0),
                "draught": float(raw.get("DRAUGHT", 0) or 0),
                "latitude": float(raw.get("LAT", 0) or 0),
                "longitude": float(raw.get("LON", 0) or 0),
                "course": float(raw.get("COURSE", 0) or raw.get("COG", 0) or 0),
                "speed": float(raw.get("SPEED", 0) or raw.get("SOG", 0) or 0) / 10.0,
                "heading": float(raw.get("HEADING", 0) or 0),
                "destination": str(raw.get("DESTINATION", "") or ""),
                "eta": str(raw.get("ETA", "") or ""),
                "nav_status": str(raw.get("STATUS", "") or raw.get("NAVSTAT", "") or ""),
                "last_update": str(raw.get("TIMESTAMP", "") or raw.get("LAST_POS", "") or datetime.utcnow().isoformat()),
            }
            return vessel
        except (ValueError, TypeError) as e:
            logger.debug(f"Failed to parse MarineTraffic vessel: {e}")
            return None

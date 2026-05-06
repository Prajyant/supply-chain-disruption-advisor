"""
AISHub data provider implementation.
Fetches real-time AIS data from the AISHub API.
"""

import logging
import requests
from typing import List, Dict, Any, Optional
from datetime import datetime

from ais.provider_base import AISProviderBase

logger = logging.getLogger(__name__)

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
    for range_key, name in VESSEL_TYPE_MAP.items():
        if type_code in range_key:
            return name
    if type_code == 35:
        return "Military"
    return "Unknown"


class AISHubProvider(AISProviderBase):
    """AISHub API provider for real-time AIS vessel data."""

    def __init__(self, api_key: str, base_url: str = "http://data.aishub.net/ws.php"):
        self.api_key = api_key
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "MaritimeAI-Platform/1.0"})

    def fetch_vessels(self, bounds: Dict[str, float] = None) -> List[Dict[str, Any]]:
        """Fetch vessels from AISHub API."""
        params = {
            "username": self.api_key,
            "format": "1",
            "output": "json",
            "compress": "0",
        }

        if bounds:
            params["latmin"] = bounds.get("lat_min", -90)
            params["latmax"] = bounds.get("lat_max", 90)
            params["lonmin"] = bounds.get("lon_min", -180)
            params["lonmax"] = bounds.get("lon_max", 180)

        try:
            response = self.session.get(self.base_url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            if isinstance(data, list) and len(data) >= 2:
                metadata = data[0]
                vessels_raw = data[1]

                if isinstance(metadata, dict) and metadata.get("ERROR", False):
                    logger.error(f"AISHub API error: {metadata}")
                    return []

                vessels = []
                for raw in vessels_raw:
                    vessel = self._parse_aishub_vessel(raw)
                    if vessel and vessel["latitude"] != 0 and vessel["longitude"] != 0:
                        vessels.append(vessel)

                logger.info(f"AISHub: Fetched {len(vessels)} vessels")
                return vessels
            else:
                logger.warning(f"AISHub: Unexpected response format")
                return []

        except requests.exceptions.Timeout:
            logger.error("AISHub API timeout")
            return []
        except requests.exceptions.RequestException as e:
            logger.error(f"AISHub API request failed: {e}")
            return []
        except (ValueError, KeyError) as e:
            logger.error(f"AISHub API parse error: {e}")
            return []

    def get_vessel_details(self, mmsi: str) -> Dict[str, Any]:
        """Fetch details for a specific vessel by MMSI."""
        params = {
            "username": self.api_key,
            "format": "1",
            "output": "json",
            "compress": "0",
            "mmsi": mmsi,
        }
        try:
            response = self.session.get(self.base_url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            if isinstance(data, list) and len(data) >= 2 and data[1]:
                return self._parse_aishub_vessel(data[1][0])
        except Exception as e:
            logger.error(f"AISHub vessel detail fetch failed for {mmsi}: {e}")
        return {}

    def is_available(self) -> bool:
        """Check if AISHub API is reachable."""
        try:
            response = self.session.get(self.base_url, params={
                "username": self.api_key, "format": "1", "output": "json", "compress": "0"
            }, timeout=10)
            return response.status_code == 200
        except Exception:
            return False

    def _parse_aishub_vessel(self, raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse AISHub raw vessel data to standard format."""
        try:
            type_code = int(raw.get("TYPE", 0) or 0)
            vessel = {
                "mmsi": str(raw.get("MMSI", "")),
                "imo": str(raw.get("IMO", "")),
                "name": str(raw.get("NAME", "Unknown")).strip(),
                "vessel_type": classify_vessel_type(type_code),
                "callsign": str(raw.get("CALLSIGN", "")),
                "flag": str(raw.get("FLAG", "")),
                "length": float(raw.get("A", 0) or 0) + float(raw.get("B", 0) or 0),
                "width": float(raw.get("C", 0) or 0) + float(raw.get("D", 0) or 0),
                "draught": float(raw.get("DRAUGHT", 0) or 0) / 10.0,
                "latitude": float(raw.get("LATITUDE", 0) or 0) / 600000.0 if float(raw.get("LATITUDE", 0) or 0) > 1000 else float(raw.get("LATITUDE", 0) or 0),
                "longitude": float(raw.get("LONGITUDE", 0) or 0) / 600000.0 if float(raw.get("LONGITUDE", 0) or 0) > 1000 else float(raw.get("LONGITUDE", 0) or 0),
                "course": float(raw.get("COG", 0) or 0) / 10.0 if float(raw.get("COG", 0) or 0) > 360 else float(raw.get("COG", 0) or 0),
                "speed": float(raw.get("SOG", 0) or 0) / 10.0 if float(raw.get("SOG", 0) or 0) > 100 else float(raw.get("SOG", 0) or 0),
                "heading": float(raw.get("HEADING", 0) or 0),
                "destination": str(raw.get("DEST", "") or ""),
                "eta": str(raw.get("ETA", "") or ""),
                "nav_status": str(raw.get("NAVSTAT", "") or ""),
                "last_update": str(raw.get("TIME", "") or datetime.utcnow().isoformat()),
            }
            return vessel
        except (ValueError, TypeError) as e:
            logger.debug(f"Failed to parse vessel: {e}")
            return None

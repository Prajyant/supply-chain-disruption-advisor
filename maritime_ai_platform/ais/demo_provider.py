"""
Demo AIS data provider for testing without a real API key.
Generates realistic vessel data for demonstration purposes.
"""

import random
import logging
from typing import List, Dict, Any
from datetime import datetime, timedelta

from ais.provider_base import AISProviderBase

logger = logging.getLogger(__name__)

DEMO_VESSELS = [
    {"mmsi": "211234567", "imo": "9876543", "name": "EVER FORTUNE", "vessel_type": "Cargo", "flag": "DE", "destination": "SINGAPORE", "length": 366, "width": 51},
    {"mmsi": "311456789", "imo": "9765432", "name": "MAERSK SEALAND", "vessel_type": "Cargo", "flag": "DK", "destination": "ROTTERDAM", "length": 399, "width": 59},
    {"mmsi": "412345678", "imo": "9654321", "name": "PACIFIC VOYAGER", "vessel_type": "Tanker", "flag": "PA", "destination": "FUJAIRAH", "length": 274, "width": 48},
    {"mmsi": "512345678", "imo": "9543210", "name": "OCEAN PEARL", "vessel_type": "Passenger", "flag": "BS", "destination": "MIAMI", "length": 362, "width": 47},
    {"mmsi": "612345678", "imo": "9432109", "name": "BLUE MARLIN", "vessel_type": "Cargo", "flag": "NL", "destination": "JEDDAH", "length": 225, "width": 42},
    {"mmsi": "712345678", "imo": "9321098", "name": "GOLDEN STAR", "vessel_type": "Tanker", "flag": "LR", "destination": "RAS TANURA", "length": 333, "width": 60},
    {"mmsi": "812345678", "imo": "9210987", "name": "NORDIC SPIRIT", "vessel_type": "Cargo", "flag": "NO", "destination": "SHANGHAI", "length": 294, "width": 32},
    {"mmsi": "912345678", "imo": "9109876", "name": "ATLANTIC FISHER", "vessel_type": "Fishing", "flag": "ES", "destination": "LAS PALMAS", "length": 85, "width": 14},
    {"mmsi": "213456789", "imo": "9098765", "name": "HMS DEFENDER", "vessel_type": "Military", "flag": "GB", "destination": "PORTSMOUTH", "length": 152, "width": 21},
    {"mmsi": "314567890", "imo": "9087654", "name": "CORAL PRINCESS", "vessel_type": "Passenger", "flag": "BM", "destination": "BARCELONA", "length": 294, "width": 32},
    {"mmsi": "415678901", "imo": "9076543", "name": "STENA BULK", "vessel_type": "Tanker", "flag": "SE", "destination": "BANDAR ABBAS", "length": 250, "width": 44},
    {"mmsi": "516789012", "imo": "9065432", "name": "MSC OSCAR", "vessel_type": "Cargo", "flag": "PA", "destination": "FELIXSTOWE", "length": 395, "width": 59},
    {"mmsi": "617890123", "imo": "9054321", "name": "JADE FORTUNE", "vessel_type": "Cargo", "flag": "HK", "destination": "BUSAN", "length": 336, "width": 46},
    {"mmsi": "718901234", "imo": "9043210", "name": "ARABIAN SEA", "vessel_type": "Tanker", "flag": "SA", "destination": "YANBU", "length": 300, "width": 50},
    {"mmsi": "819012345", "imo": "9032109", "name": "LIBERTY STAR", "vessel_type": "Cargo", "flag": "US", "destination": "LONG BEACH", "length": 280, "width": 40},
    {"mmsi": "920123456", "imo": "9021098", "name": "DEEP EXPLORER", "vessel_type": "Tanker", "flag": "MT", "destination": "LAGOS", "length": 260, "width": 46},
    {"mmsi": "221234567", "imo": "9010987", "name": "VIKING GRACE", "vessel_type": "Passenger", "flag": "FI", "destination": "STOCKHOLM", "length": 214, "width": 31},
    {"mmsi": "322345678", "imo": "9009876", "name": "CAPE HORN", "vessel_type": "Cargo", "flag": "CL", "destination": "VALPARAISO", "length": 190, "width": 30},
    {"mmsi": "423456789", "imo": "9008765", "name": "DRAGON KING", "vessel_type": "Cargo", "flag": "CN", "destination": "HONG KONG", "length": 350, "width": 51},
    {"mmsi": "524567890", "imo": "9007654", "name": "SAHARA WIND", "vessel_type": "Tanker", "flag": "LY", "destination": "TRIPOLI", "length": 180, "width": 28},
]

ROUTE_POSITIONS = [
    {"lat": 13.5, "lon": 42.5},   # Red Sea
    {"lat": 12.0, "lon": 45.0},   # Gulf of Aden
    {"lat": 26.0, "lon": 56.0},   # Strait of Hormuz
    {"lat": 4.0, "lon": 2.0},     # Gulf of Guinea
    {"lat": 10.0, "lon": 110.0},  # South China Sea
    {"lat": 1.5, "lon": 104.0},   # Malacca Strait
    {"lat": 35.0, "lon": -5.0},   # Gibraltar
    {"lat": 30.0, "lon": 32.5},   # Suez Canal
    {"lat": 51.0, "lon": 1.5},    # English Channel
    {"lat": 22.0, "lon": 120.0},  # Taiwan Strait
    {"lat": -34.0, "lon": 18.5},  # Cape of Good Hope
    {"lat": 40.0, "lon": -74.0},  # New York approach
    {"lat": 1.3, "lon": 103.8},   # Singapore
    {"lat": 25.2, "lon": 55.3},   # Dubai
    {"lat": 37.0, "lon": -122.0}, # San Francisco
    {"lat": -33.8, "lon": 151.2}, # Sydney
    {"lat": 35.4, "lon": 139.7},  # Tokyo Bay
    {"lat": 21.3, "lon": -157.8}, # Honolulu
    {"lat": 5.0, "lon": 47.0},    # Somalia Coast
    {"lat": 14.5, "lon": 41.0},   # Bab el-Mandeb
]


class DemoAISProvider(AISProviderBase):
    """Demo provider that generates realistic vessel data for testing."""

    def __init__(self):
        self._vessels = self._generate_initial_positions()
        logger.info("Demo AIS provider initialized with 20 vessels")

    def _generate_initial_positions(self) -> List[Dict[str, Any]]:
        """Generate initial vessel positions."""
        vessels = []
        for i, base in enumerate(DEMO_VESSELS):
            pos = ROUTE_POSITIONS[i % len(ROUTE_POSITIONS)]
            lat_offset = random.uniform(-2.0, 2.0)
            lon_offset = random.uniform(-2.0, 2.0)

            vessel = {
                **base,
                "latitude": pos["lat"] + lat_offset,
                "longitude": pos["lon"] + lon_offset,
                "course": random.uniform(0, 360),
                "speed": random.uniform(5, 22),
                "heading": random.uniform(0, 360),
                "draught": random.uniform(8, 16),
                "callsign": f"{base['flag']}{random.randint(1000, 9999)}",
                "eta": (datetime.utcnow() + timedelta(days=random.randint(1, 14))).strftime("%m-%d %H:%M"),
                "nav_status": random.choice(["Under way using engine", "At anchor", "Moored", "Under way using engine"]),
                "last_update": datetime.utcnow().isoformat(),
            }
            vessels.append(vessel)
        return vessels

    def fetch_vessels(self, bounds: Dict[str, float] = None) -> List[Dict[str, Any]]:
        """Return demo vessels with slight position updates to simulate movement."""
        for vessel in self._vessels:
            speed_kts = vessel["speed"]
            course_rad = vessel["course"] * 3.14159 / 180.0
            hours_elapsed = 5.0 / 60.0

            import math
            delta_lat = (speed_kts * hours_elapsed / 60.0) * math.cos(course_rad)
            delta_lon = (speed_kts * hours_elapsed / 60.0) * math.sin(course_rad)

            vessel["latitude"] += delta_lat + random.uniform(-0.01, 0.01)
            vessel["longitude"] += delta_lon + random.uniform(-0.01, 0.01)
            vessel["latitude"] = max(-85, min(85, vessel["latitude"]))
            vessel["longitude"] = max(-180, min(180, vessel["longitude"]))
            vessel["speed"] = max(0, vessel["speed"] + random.uniform(-0.5, 0.5))
            vessel["course"] = (vessel["course"] + random.uniform(-5, 5)) % 360
            vessel["last_update"] = datetime.utcnow().isoformat()

        if bounds:
            filtered = [
                v for v in self._vessels
                if bounds.get("lat_min", -90) <= v["latitude"] <= bounds.get("lat_max", 90)
                and bounds.get("lon_min", -180) <= v["longitude"] <= bounds.get("lon_max", 180)
            ]
            return filtered

        logger.info(f"Demo provider: returning {len(self._vessels)} vessels")
        return self._vessels

    def get_vessel_details(self, mmsi: str) -> Dict[str, Any]:
        """Get details for a specific demo vessel."""
        for v in self._vessels:
            if v["mmsi"] == mmsi:
                return v
        return {}

    def is_available(self) -> bool:
        """Demo provider is always available."""
        return True

"""
Demo AIS data provider — generates realistic vessel data without API keys.

Adapted from maritime_ai_platform/ais/demo_provider.py:
- Converted to async
- CSV-watchlist-aware: simulates data for IMOs in the watchlist
- Generates realistic 7-day route histories on first run
- Simulates anomalies (AIS gaps, speed drops, danger zone transits)
- Supports up to 60 vessels with realistic shipping lane routes
"""

import logging
import math
import random
from datetime import datetime, timedelta
from typing import Any

from app.ingestion.ais.provider_base import AISProviderBase

logger = logging.getLogger(__name__)

# Well-known vessels database for demo mode
KNOWN_VESSELS: list[dict[str, Any]] = [
    # Container Ships
    {"imo_number": "9811000", "mmsi": "353136000", "name": "EVER GIVEN", "vessel_type": "Container Ship", "flag": "Panama"},
    {"imo_number": "9703291", "mmsi": "255806260", "name": "MSC OSCAR", "vessel_type": "Container Ship", "flag": "Panama"},
    {"imo_number": "9484525", "mmsi": "477328800", "name": "CSCL GLOBE", "vessel_type": "Container Ship", "flag": "Hong Kong"},
    {"imo_number": "9708837", "mmsi": "636092799", "name": "MOL TRIUMPH", "vessel_type": "Container Ship", "flag": "Liberia"},
    {"imo_number": "9893890", "mmsi": "352986146", "name": "EVER ACE", "vessel_type": "Container Ship", "flag": "Panama"},
    {"imo_number": "9795736", "mmsi": "477339800", "name": "COSCO SHIPPING UNIVERSE", "vessel_type": "Container Ship", "flag": "Hong Kong"},
    {"imo_number": "9732319", "mmsi": "636018505", "name": "MADRID MAERSK", "vessel_type": "Container Ship", "flag": "Denmark"},
    {"imo_number": "9619907", "mmsi": "477588600", "name": "OOCL HONG KONG", "vessel_type": "Container Ship", "flag": "Hong Kong"},
    {"imo_number": "9839179", "mmsi": "228386700", "name": "MSC GULSUN", "vessel_type": "Container Ship", "flag": "France"},
    {"imo_number": "9863297", "mmsi": "440326000", "name": "HMM ALGECIRAS", "vessel_type": "Container Ship", "flag": "South Korea"},
    # Tankers
    {"imo_number": "9929429", "mmsi": "636022601", "name": "TI EUROPE", "vessel_type": "VLCC Tanker", "flag": "Liberia"},
    {"imo_number": "9934735", "mmsi": "636022600", "name": "TI OCEANIA", "vessel_type": "VLCC Tanker", "flag": "Liberia"},
    {"imo_number": "9929431", "mmsi": "636022604", "name": "FRONT ALTA", "vessel_type": "VLCC Tanker", "flag": "Liberia"},
    {"imo_number": "9934747", "mmsi": "636022920", "name": "NAVE ANDROMEDA", "vessel_type": "Product Tanker", "flag": "Liberia"},
    {"imo_number": "9931290", "mmsi": "636023098", "name": "PACIFIC JEWEL", "vessel_type": "LNG Carrier", "flag": "Liberia"},
    # Bulk Carriers
    {"imo_number": "9931288", "mmsi": "636023099", "name": "VALE BRASIL", "vessel_type": "Bulk Carrier", "flag": "Liberia"},
    {"imo_number": "9908097", "mmsi": "477886300", "name": "ORE TIANJIN", "vessel_type": "Bulk Carrier", "flag": "Hong Kong"},
    {"imo_number": "9908138", "mmsi": "477890700", "name": "STELLAR BANNER", "vessel_type": "Bulk Carrier", "flag": "Hong Kong"},
    {"imo_number": "9922512", "mmsi": "477890700", "name": "BERGE STAHL", "vessel_type": "Bulk Carrier", "flag": "Hong Kong"},
    {"imo_number": "9908140", "mmsi": "477895500", "name": "CAPE BRUNNY", "vessel_type": "Bulk Carrier", "flag": "Hong Kong"},
    # Other vessels
    {"imo_number": "9939137", "mmsi": "636022889", "name": "GOLDEN STAR", "vessel_type": "Tanker", "flag": "Liberia"},
    {"imo_number": "9933004", "mmsi": "636023002", "name": "EVER FORTUNE", "vessel_type": "Cargo", "flag": "Liberia"},
    {"imo_number": "9933119", "mmsi": "636022963", "name": "MAERSK SEALAND", "vessel_type": "Cargo", "flag": "Liberia"},
    {"imo_number": "9933016", "mmsi": "636023290", "name": "PACIFIC VOYAGER", "vessel_type": "Tanker", "flag": "Liberia"},
    {"imo_number": "9930038", "mmsi": "636022516", "name": "OCEAN PEARL", "vessel_type": "Passenger", "flag": "Liberia"},
    {"imo_number": "9930040", "mmsi": "636022516", "name": "BLUE MARLIN", "vessel_type": "Cargo", "flag": "Liberia"},
    {"imo_number": "9936616", "mmsi": "636022603", "name": "NORDIC SPIRIT", "vessel_type": "Cargo", "flag": "Liberia"},
    {"imo_number": "9936630", "mmsi": "636022604", "name": "ATLANTIC FISHER", "vessel_type": "Fishing", "flag": "Liberia"},
    {"imo_number": "9893955", "mmsi": "352001259", "name": "CORAL PRINCESS", "vessel_type": "Passenger", "flag": "Panama"},
    {"imo_number": "9948748", "mmsi": "219561000", "name": "STENA BULK", "vessel_type": "Tanker", "flag": "Denmark"},
]

# Shipping lane waypoints for realistic route generation
SHIPPING_LANES = {
    "asia_europe_suez": [
        (31.23, 121.47),  # Shanghai
        (22.55, 114.24),  # Yantian/Shenzhen
        (1.35, 103.82),   # Singapore
        (6.0, 80.0),      # Sri Lanka
        (12.5, 43.5),     # Bab-el-Mandeb
        (30.0, 32.5),     # Suez Canal
        (35.9, -5.3),     # Gibraltar
        (51.92, 4.48),    # Rotterdam
    ],
    "gulf_europe_suez": [
        (26.64, 50.16),   # Ras Tanura
        (26.0, 56.0),     # Strait of Hormuz
        (12.5, 43.5),     # Bab-el-Mandeb
        (30.0, 32.5),     # Suez Canal
        (35.9, -5.3),     # Gibraltar
        (53.55, 9.99),    # Hamburg
    ],
    "west_africa_europe": [
        (4.0, 2.0),       # Gulf of Guinea
        (6.0, -1.0),      # Ghana
        (14.7, -17.4),    # Dakar
        (35.76, -5.83),   # Tangier
        (51.92, 4.48),    # Rotterdam
    ],
    "asia_americas_pacific": [
        (31.23, 121.47),  # Shanghai
        (35.18, 129.08),  # Busan
        (35.44, 139.64),  # Yokohama
        (28.0, -160.0),   # Mid-Pacific
        (33.75, -118.25), # Los Angeles
    ],
    "intra_asia_malacca": [
        (22.55, 114.24),  # Yantian
        (10.0, 110.0),    # South China Sea
        (1.35, 103.82),   # Singapore
        (6.0, 80.0),      # Sri Lanka
        (19.08, 72.88),   # Mumbai
    ],
}

# Speed profiles by vessel type (knots)
SPEED_PROFILES = {
    "Container Ship": (18, 24),
    "VLCC Tanker": (10, 14),
    "Product Tanker": (12, 16),
    "LNG Carrier": (16, 20),
    "Bulk Carrier": (12, 16),
    "General Cargo": (10, 15),
    "Cargo": (12, 18),
    "Tanker": (11, 15),
    "Passenger": (18, 22),
    "Fishing": (8, 12),
}


class DemoAISProvider(AISProviderBase):
    """Demo provider that generates realistic vessel data for testing.

    On initialization, generates 7 days of route history for all vessels
    in the watchlist. Simulates movement and anomalies on each poll.
    """

    def __init__(self, watchlist_imos: list[str] | None = None):
        self._vessels: dict[str, dict[str, Any]] = {}
        self._route_histories: dict[str, list[dict[str, Any]]] = {}
        self._initialized = False
        self._watchlist_imos = watchlist_imos or []
        # Track anomaly state
        self._anomaly_state: dict[str, dict[str, Any]] = {}

    async def _ensure_initialized(self) -> None:
        """Initialize demo data on first access."""
        if self._initialized:
            return

        imos_to_simulate = self._watchlist_imos or [v["imo_number"] for v in KNOWN_VESSELS]

        for imo in imos_to_simulate:
            vessel_info = self._get_vessel_info(imo)
            if vessel_info:
                self._generate_vessel_with_history(vessel_info)

        self._initialized = True
        logger.info(f"Demo provider initialized with {len(self._vessels)} vessels and 7-day histories")

    def _get_vessel_info(self, imo: str) -> dict[str, Any] | None:
        """Look up vessel info from known vessels database."""
        for v in KNOWN_VESSELS:
            if v["imo_number"] == imo:
                return v
        # Generate a synthetic vessel for unknown IMOs
        return {
            "imo_number": imo,
            "mmsi": f"3{imo[:8]}",
            "name": f"VESSEL-{imo}",
            "vessel_type": random.choice(["Container Ship", "Bulk Carrier", "Product Tanker"]),
            "flag": random.choice(["Panama", "Liberia", "Marshall Islands", "Hong Kong"]),
            "length": random.uniform(200, 400),
            "beam": random.uniform(30, 65),
            "dwt": random.randint(50000, 300000),
        }

    def _generate_vessel_with_history(self, vessel_info: dict[str, Any]) -> None:
        """Generate a vessel with 7 days of route history."""
        imo = vessel_info["imo_number"]
        vessel_type = vessel_info.get("vessel_type", "Container Ship")

        # Pick a random shipping lane
        lane_name = random.choice(list(SHIPPING_LANES.keys()))
        waypoints = SHIPPING_LANES[lane_name]

        # Determine speed range
        speed_range = SPEED_PROFILES.get(vessel_type, (12, 18))
        base_speed = random.uniform(*speed_range)

        # Generate 7 days of history (position every 5 minutes = 2016 points)
        history = []
        total_points = 7 * 24 * 12  # 7 days, 12 points per hour

        # Calculate total route distance and pick a random starting progress
        progress = random.uniform(0.1, 0.7)  # Start somewhere along the route

        for i in range(total_points):
            timestamp = datetime.utcnow() - timedelta(minutes=(total_points - i) * 5)

            # Advance along route
            speed_variation = random.uniform(-1.0, 1.0)
            current_speed = max(1.0, base_speed + speed_variation)
            # Convert speed to progress (rough: 1 knot ≈ 1.852 km/h)
            progress += (current_speed * 5 / 60) / 5000.0  # Normalize to route length

            if progress >= 1.0:
                progress = progress - 1.0  # Loop back (return voyage)

            # Interpolate position along waypoints
            lat, lon = self._interpolate_route(waypoints, progress % 1.0)

            # Add some noise
            lat += random.uniform(-0.05, 0.05)
            lon += random.uniform(-0.05, 0.05)

            # Calculate course from movement
            course = self._calculate_course(waypoints, progress % 1.0)

            position = {
                "imo_number": imo,
                "mmsi": vessel_info.get("mmsi", ""),
                "latitude": lat,
                "longitude": lon,
                "speed": round(current_speed, 1),
                "course": round(course, 1),
                "heading": round(course + random.uniform(-5, 5), 1) % 360,
                "nav_status": "Under way using engine",
                "timestamp": timestamp.isoformat(),
            }
            history.append(position)

        self._route_histories[imo] = history

        # Set current position to the latest history point
        latest = history[-1]
        self._vessels[imo] = {
            **vessel_info,
            "latitude": latest["latitude"],
            "longitude": latest["longitude"],
            "speed": latest["speed"],
            "course": latest["course"],
            "heading": latest["heading"],
            "nav_status": "Under way using engine",
            "origin_port": self._pick_origin(lane_name),
            "destination": self._pick_destination(lane_name),
            "eta": (datetime.utcnow() + timedelta(days=random.randint(2, 14))).strftime("%Y-%m-%d %H:%M"),
            "last_update": datetime.utcnow().isoformat(),
            "draught": random.uniform(8, 16),
            "call_sign": f"{vessel_info.get('flag', 'PA')[:2]}{random.randint(1000, 9999)}",
        }

    def _interpolate_route(
        self, waypoints: list[tuple[float, float]], progress: float
    ) -> tuple[float, float]:
        """Interpolate position along a route given progress (0.0 to 1.0)."""
        if not waypoints:
            return (0.0, 0.0)

        n_segments = len(waypoints) - 1
        if n_segments <= 0:
            return waypoints[0]

        segment_progress = progress * n_segments
        segment_idx = min(int(segment_progress), n_segments - 1)
        local_progress = segment_progress - segment_idx

        start = waypoints[segment_idx]
        end = waypoints[min(segment_idx + 1, len(waypoints) - 1)]

        lat = start[0] + (end[0] - start[0]) * local_progress
        lon = start[1] + (end[1] - start[1]) * local_progress

        return (lat, lon)

    def _calculate_course(
        self, waypoints: list[tuple[float, float]], progress: float
    ) -> float:
        """Calculate approximate course heading along route."""
        n_segments = len(waypoints) - 1
        if n_segments <= 0:
            return 0.0

        segment_idx = min(int(progress * n_segments), n_segments - 1)
        start = waypoints[segment_idx]
        end = waypoints[min(segment_idx + 1, len(waypoints) - 1)]

        dlat = end[0] - start[0]
        dlon = end[1] - start[1]

        course = math.degrees(math.atan2(dlon, dlat)) % 360
        return course

    def _pick_destination(self, lane_name: str) -> str:
        """Pick a realistic destination based on shipping lane (end of route)."""
        destinations = {
            "asia_europe_suez": "ROTTERDAM",
            "gulf_europe_suez": "HAMBURG",
            "west_africa_europe": "ROTTERDAM",
            "asia_americas_pacific": "LOS ANGELES",
            "intra_asia_malacca": "MUMBAI",
        }
        return destinations.get(lane_name, "UNKNOWN")

    def _pick_origin(self, lane_name: str) -> str:
        """Pick the origin port based on shipping lane (start of route)."""
        origins = {
            "asia_europe_suez": "SHANGHAI",
            "gulf_europe_suez": "RAS TANURA",
            "west_africa_europe": "LAGOS",
            "asia_americas_pacific": "BUSAN",
            "intra_asia_malacca": "YANTIAN",
        }
        return origins.get(lane_name, "UNKNOWN")

    async def get_vessel_by_imo(self, imo_number: str) -> dict[str, Any] | None:
        """Get current vessel position by IMO."""
        await self._ensure_initialized()
        vessel = self._vessels.get(imo_number)
        if vessel:
            # Simulate movement since last update
            self._advance_vessel(imo_number)
            return self._vessels[imo_number]
        return None

    async def get_vessel_track(
        self, imo_number: str, hours: int = 24
    ) -> list[dict[str, Any]]:
        """Get route history for a vessel."""
        await self._ensure_initialized()
        history = self._route_histories.get(imo_number, [])
        if not history:
            return []

        # Filter by time range
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        return [
            p for p in history
            if datetime.fromisoformat(p["timestamp"]) >= cutoff
        ]

    async def search_vessel(self, query: str) -> list[dict[str, Any]]:
        """Search known vessels by name."""
        await self._ensure_initialized()
        query_lower = query.lower()
        results = []
        for v in KNOWN_VESSELS:
            if query_lower in v["name"].lower():
                results.append(v)
        return results[:20]

    async def get_vessels_batch(
        self, imo_numbers: list[str]
    ) -> list[dict[str, Any]]:
        """Get positions for multiple vessels."""
        await self._ensure_initialized()
        results = []
        for imo in imo_numbers:
            vessel = await self.get_vessel_by_imo(imo)
            if vessel:
                results.append(vessel)
        return results

    async def is_available(self) -> bool:
        """Demo provider is always available."""
        return True

    def _advance_vessel(self, imo: str) -> None:
        """Advance a vessel's position to simulate movement."""
        vessel = self._vessels.get(imo)
        if not vessel:
            return

        speed = vessel.get("speed", 12.0)
        course = vessel.get("course", 0.0)

        # 5 minutes of movement
        hours_elapsed = 5.0 / 60.0
        course_rad = math.radians(course)

        delta_lat = (speed * hours_elapsed / 60.0) * math.cos(course_rad)
        delta_lon = (speed * hours_elapsed / 60.0) * math.sin(course_rad)

        vessel["latitude"] += delta_lat + random.uniform(-0.01, 0.01)
        vessel["longitude"] += delta_lon + random.uniform(-0.01, 0.01)
        vessel["latitude"] = max(-85, min(85, vessel["latitude"]))
        vessel["longitude"] = max(-180, min(180, vessel["longitude"]))
        vessel["speed"] = max(0, speed + random.uniform(-0.3, 0.3))
        vessel["course"] = (course + random.uniform(-3, 3)) % 360
        vessel["last_update"] = datetime.utcnow().isoformat()

        # Simulate anomalies periodically
        self._maybe_simulate_anomaly(imo)

        # Append to history
        history = self._route_histories.setdefault(imo, [])
        history.append({
            "imo_number": imo,
            "mmsi": vessel.get("mmsi", ""),
            "latitude": vessel["latitude"],
            "longitude": vessel["longitude"],
            "speed": vessel["speed"],
            "course": vessel["course"],
            "heading": vessel.get("heading", vessel["course"]),
            "nav_status": vessel.get("nav_status", "Under way using engine"),
            "timestamp": vessel["last_update"],
        })

        # Keep history manageable (max 7 days at 5-min intervals)
        if len(history) > 2016:
            self._route_histories[imo] = history[-2016:]

    def _maybe_simulate_anomaly(self, imo: str) -> None:
        """Randomly simulate anomalies for demo realism.

        Anomaly types:
        - AIS silence (stop updating for a period)
        - Speed drop (sudden deceleration)
        - Danger zone transit (vessel enters a high-risk area)
        """
        # 0.5% chance per poll of triggering an anomaly
        if random.random() > 0.005:
            return

        vessel = self._vessels[imo]
        anomaly_type = random.choice(["ais_silence", "speed_drop", "course_change"])

        if anomaly_type == "ais_silence":
            # Simulate AIS going silent (set last_update to hours ago)
            silence_hours = random.uniform(2, 8)
            vessel["last_update"] = (
                datetime.utcnow() - timedelta(hours=silence_hours)
            ).isoformat()
            logger.info(f"Demo anomaly: {vessel['name']} AIS silent for {silence_hours:.1f}h")

        elif anomaly_type == "speed_drop":
            # Sudden speed drop
            vessel["speed"] = random.uniform(0.5, 3.0)
            vessel["nav_status"] = "Not under command"
            logger.info(f"Demo anomaly: {vessel['name']} speed dropped to {vessel['speed']:.1f} kts")

        elif anomaly_type == "course_change":
            # Erratic course change
            vessel["course"] = (vessel["course"] + random.uniform(90, 180)) % 360
            logger.info(f"Demo anomaly: {vessel['name']} erratic course change")

    def update_watchlist(self, imo_numbers: list[str]) -> None:
        """Update the watchlist and generate data for new IMOs."""
        new_imos = set(imo_numbers) - set(self._vessels.keys())
        self._watchlist_imos = imo_numbers

        for imo in new_imos:
            vessel_info = self._get_vessel_info(imo)
            if vessel_info:
                self._generate_vessel_with_history(vessel_info)
                logger.info(f"Demo: Generated data for new watchlist vessel {imo}")

    async def close(self) -> None:
        """No resources to close for demo provider."""
        pass

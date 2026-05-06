"""Sea route distance calculator using the Searoute library.

Provides realistic maritime routing with nautical mile distances for:
- ETA predictions
- Route deviation detection
- Fuel cost estimates
- Off-route risk flagging
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

try:
    import searoute
    SEAROUTE_AVAILABLE = True
except ImportError:
    SEAROUTE_AVAILABLE = False
    logger.warning("searoute not installed — run: pip install searoute")


# Major port coordinates (lon, lat) — GeoJSON format
PORT_COORDINATES: dict[str, tuple[float, float]] = {
    # Asia
    "shanghai": (121.47, 31.23),
    "yantian": (114.28, 22.57),
    "shenzhen": (114.07, 22.55),
    "guangzhou": (113.26, 23.13),
    "ningbo": (121.55, 29.87),
    "busan": (129.04, 35.10),
    "tokyo": (139.77, 35.68),
    "kobe": (135.20, 34.69),
    "osaka": (135.50, 34.69),
    "kaohsiung": (120.30, 22.63),
    "singapore": (103.85, 1.29),
    "hong kong": (114.17, 22.32),
    "ho chi minh": (106.66, 10.80),
    "mumbai": (72.88, 18.93),
    "mundra": (69.72, 22.84),
    "chennai": (80.30, 13.09),
    "colombo": (79.84, 6.94),
    "dubai": (55.27, 25.20),
    "jeddah": (39.17, 21.49),
    "ras tanura": (50.16, 26.64),
    # Europe - Major
    "rotterdam": (4.48, 51.92),
    "europoort": (4.03, 51.95),
    "hamburg": (9.97, 53.55),
    "antwerp": (4.40, 51.22),
    "felixstowe": (1.35, 51.96),
    "southampton": (-1.40, 50.91),
    "portsmouth": (-1.09, 50.82),
    "le havre": (0.11, 49.49),
    "piraeus": (23.63, 37.94),
    "istanbul": (28.98, 41.01),
    "constanta": (28.63, 44.18),
    "barcelona": (2.17, 41.38),
    "valencia": (-0.38, 39.47),
    "palma": (2.65, 39.57),
    "genoa": (8.93, 44.41),
    "bastia": (9.45, 42.70),
    "marseille": (5.37, 43.30),
    # Europe - Scandinavia & Baltic
    "gothenburg": (11.97, 57.71),
    "malmo": (13.00, 55.61),
    "stockholm": (18.07, 59.33),
    "copenhagen": (12.57, 55.68),
    "esbjerg": (8.45, 55.48),
    "odense": (10.40, 55.40),
    "oslo": (10.75, 59.91),
    "stavanger": (5.73, 58.97),
    "bergen": (5.32, 60.39),
    "tromso": (18.96, 69.65),
    "harstad": (16.54, 68.80),
    "hammerfest": (23.68, 70.66),
    "helsinki": (24.94, 60.17),
    "gdansk": (18.65, 54.35),
    "klaipeda": (21.14, 55.70),
    "kiel": (10.12, 54.32),
    "rostock": (12.10, 54.09),
    "bremerhaven": (8.58, 53.54),
    # Europe - UK & Ireland
    "immingham": (-0.21, 53.61),
    "belfast": (-5.93, 54.60),
    "dublin": (-6.26, 53.35),
    "london": (-0.13, 51.51),
    "tilbury": (0.35, 51.46),
    # Europe - Netherlands
    "amsterdam": (4.90, 52.37),
    "den helder": (4.76, 52.95),
    "ijmuiden": (4.60, 52.46),
    # Americas
    "los angeles": (-118.25, 33.74),
    "long beach": (-118.19, 33.77),
    "new york": (-74.01, 40.71),
    "savannah": (-81.10, 32.08),
    "houston": (-95.01, 29.73),
    "galveston": (-94.80, 29.30),
    "santos": (-46.30, -23.95),
    "recife": (-34.88, -8.05),
    "salvador": (-38.51, -12.97),
    "colon": (-79.90, 9.36),
    # Africa
    "durban": (31.03, -29.86),
    "cape town": (18.42, -33.92),
    "port said": (32.30, 31.26),
    # Oceania
    "sydney": (151.21, -33.87),
    "melbourne": (144.96, -37.81),
    "perth": (115.86, -31.95),
}


@dataclass
class RouteResult:
    """Result of a sea route calculation."""
    origin: str
    destination: str
    distance_nm: float
    distance_km: float
    estimated_days: float
    route_geometry: list[list[float]] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "origin": self.origin,
            "destination": self.destination,
            "distance_nm": round(self.distance_nm, 1),
            "distance_km": round(self.distance_km, 1),
            "estimated_days": round(self.estimated_days, 1),
            "has_geometry": self.route_geometry is not None,
        }


def calculate_sea_route(
    origin: str,
    destination: str,
    speed_knots: float = 14.0,
) -> RouteResult | None:
    """Calculate sea route distance between two ports.

    Args:
        origin: Port name (must be in PORT_COORDINATES)
        destination: Port name (must be in PORT_COORDINATES)
        speed_knots: Vessel speed in knots for ETA calculation

    Returns:
        RouteResult with distance and ETA, or None if ports not found
    """
    origin_key = origin.lower().strip()
    dest_key = destination.lower().strip()

    # Try to match port names (fuzzy)
    origin_coords = _resolve_port(origin_key)
    dest_coords = _resolve_port(dest_key)

    if not origin_coords or not dest_coords:
        logger.warning("Could not resolve ports: %s → %s", origin, destination)
        return None

    if SEAROUTE_AVAILABLE:
        return _calculate_with_searoute(origin, destination, origin_coords, dest_coords, speed_knots)
    else:
        return _calculate_great_circle(origin, destination, origin_coords, dest_coords, speed_knots)


def calculate_route_from_coords(
    origin_lon: float,
    origin_lat: float,
    dest_lon: float,
    dest_lat: float,
    speed_knots: float = 14.0,
) -> RouteResult | None:
    """Calculate sea route from raw coordinates."""
    origin_coords = (origin_lon, origin_lat)
    dest_coords = (dest_lon, dest_lat)

    if SEAROUTE_AVAILABLE:
        return _calculate_with_searoute(
            f"({origin_lat:.2f}, {origin_lon:.2f})",
            f"({dest_lat:.2f}, {dest_lon:.2f})",
            origin_coords, dest_coords, speed_knots,
        )
    else:
        return _calculate_great_circle(
            f"({origin_lat:.2f}, {origin_lon:.2f})",
            f"({dest_lat:.2f}, {dest_lon:.2f})",
            origin_coords, dest_coords, speed_knots,
        )


def detect_route_deviation(
    vessel_lat: float,
    vessel_lon: float,
    origin: str,
    destination: str,
    threshold_nm: float = 50.0,
) -> dict[str, Any]:
    """Detect if a vessel has deviated from its expected route.

    Args:
        vessel_lat: Current vessel latitude
        vessel_lon: Current vessel longitude
        origin: Origin port name
        destination: Destination port name
        threshold_nm: Distance threshold in nautical miles to flag deviation

    Returns:
        Dict with deviation status and distance from route
    """
    origin_coords = _resolve_port(origin.lower().strip())
    dest_coords = _resolve_port(destination.lower().strip())

    if not origin_coords or not dest_coords:
        return {"deviated": False, "reason": "Could not resolve ports"}

    # Calculate distance from vessel to the great circle route
    deviation_nm = _point_to_line_distance_nm(
        vessel_lon, vessel_lat,
        origin_coords[0], origin_coords[1],
        dest_coords[0], dest_coords[1],
    )

    deviated = deviation_nm > threshold_nm

    return {
        "deviated": deviated,
        "deviation_nm": round(deviation_nm, 1),
        "threshold_nm": threshold_nm,
        "severity": (
            "critical" if deviation_nm > threshold_nm * 3
            else "high" if deviation_nm > threshold_nm * 2
            else "medium" if deviated
            else "low"
        ),
    }


def _calculate_with_searoute(
    origin_name: str,
    dest_name: str,
    origin_coords: tuple[float, float],
    dest_coords: tuple[float, float],
    speed_knots: float,
) -> RouteResult:
    """Calculate route using the searoute library."""
    try:
        route = searoute.searoute(origin_coords, dest_coords, units="nm")
        distance_nm = route["properties"]["length"]
        distance_km = distance_nm * 1.852
        estimated_days = distance_nm / (speed_knots * 24) if speed_knots > 0 else 0

        # Extract route geometry
        geometry = route.get("geometry", {}).get("coordinates", [])

        return RouteResult(
            origin=origin_name,
            destination=dest_name,
            distance_nm=distance_nm,
            distance_km=distance_km,
            estimated_days=estimated_days,
            route_geometry=geometry if geometry else None,
        )
    except Exception as exc:
        logger.warning("Searoute calculation failed: %s — falling back to great circle", exc)
        return _calculate_great_circle(origin_name, dest_name, origin_coords, dest_coords, speed_knots)


def _calculate_great_circle(
    origin_name: str,
    dest_name: str,
    origin_coords: tuple[float, float],
    dest_coords: tuple[float, float],
    speed_knots: float,
) -> RouteResult:
    """Fallback: great circle distance (less accurate but no dependency)."""
    distance_nm = _haversine_nm(
        origin_coords[1], origin_coords[0],
        dest_coords[1], dest_coords[0],
    )
    # Add 20% for realistic sea routing (straits, canals, coastlines)
    distance_nm *= 1.2
    distance_km = distance_nm * 1.852
    estimated_days = distance_nm / (speed_knots * 24) if speed_knots > 0 else 0

    return RouteResult(
        origin=origin_name,
        destination=dest_name,
        distance_nm=distance_nm,
        distance_km=distance_km,
        estimated_days=estimated_days,
        route_geometry=None,
    )


def _resolve_port(name: str) -> tuple[float, float] | None:
    """Resolve a port name to coordinates with fuzzy matching."""
    # Direct match
    if name in PORT_COORDINATES:
        return PORT_COORDINATES[name]

    # Partial match
    for port_name, coords in PORT_COORDINATES.items():
        if port_name in name or name in port_name:
            return coords

    # Try matching country/region codes
    name_parts = name.replace(",", " ").split()
    for part in name_parts:
        part = part.strip().lower()
        if part in PORT_COORDINATES:
            return PORT_COORDINATES[part]

    return None


def _haversine_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great circle distance in nautical miles."""
    R_NM = 3440.065  # Earth radius in nautical miles

    lat1_r, lat2_r = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))

    return R_NM * c


def _point_to_line_distance_nm(
    px: float, py: float,
    x1: float, y1: float,
    x2: float, y2: float,
) -> float:
    """Calculate perpendicular distance from a point to a great circle line in nm."""
    # Simplified: use cross-track distance formula
    d13 = _haversine_nm(y1, x1, py, px)
    bearing_13 = _initial_bearing(y1, x1, py, px)
    bearing_12 = _initial_bearing(y1, x1, y2, x2)

    # Cross-track distance
    xtd = abs(math.asin(math.sin(d13 / 3440.065) * math.sin(math.radians(bearing_13 - bearing_12))) * 3440.065)
    return xtd


def _initial_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate initial bearing between two points in degrees."""
    lat1_r, lat2_r = math.radians(lat1), math.radians(lat2)
    dlon = math.radians(lon2 - lon1)

    x = math.sin(dlon) * math.cos(lat2_r)
    y = math.cos(lat1_r) * math.sin(lat2_r) - math.sin(lat1_r) * math.cos(lat2_r) * math.cos(dlon)

    return math.degrees(math.atan2(x, y)) % 360

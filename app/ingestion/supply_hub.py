"""Industry graph data — Open Supply Hub integration.

Free data source: opensupplyhub.org (Free API)
Provides factory/supplier locations, ownership links, and facility data.

Used to build the industry knowledge graph for cascading risk detection.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

import requests

logger = logging.getLogger(__name__)

# Open Supply Hub API
OSH_API_BASE = "https://opensupplyhub.org/api"
OSH_API_TOKEN = os.getenv("OPEN_SUPPLY_HUB_API_TOKEN", "")  # Free API token


class OpenSupplyHubClient:
    """Client for Open Supply Hub API.

    Provides access to global facility data including:
    - Factory/supplier locations
    - Ownership and parent company links
    - Industry sector classification
    - Geographic coordinates for mapping
    """

    def __init__(self) -> None:
        self.api_token = OSH_API_TOKEN
        self.timeout = 15

    @property
    def is_configured(self) -> bool:
        return bool(self.api_token)

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "User-Agent": "SupplyChainAdvisor/1.0",
        }
        if self.api_token:
            headers["Authorization"] = f"Token {self.api_token}"
        return headers

    def search_facilities(
        self,
        query: str = "",
        country: str = "",
        sector: str = "",
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Search for facilities in Open Supply Hub.

        Args:
            query: Free text search (facility name, address)
            country: ISO2 country code filter
            sector: Industry sector filter
            limit: Max results to return
        """
        params: dict[str, Any] = {"pageSize": min(limit, 100)}
        if query:
            params["q"] = query
        if country:
            params["countries"] = country
        if sector:
            params["sectors"] = sector

        try:
            response = requests.get(
                f"{OSH_API_BASE}/facilities/",
                params=params,
                headers=self._headers(),
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()

            facilities = []
            for feature in data.get("features", []):
                props = feature.get("properties", {})
                geometry = feature.get("geometry", {})
                coords = geometry.get("coordinates", [None, None])

                facilities.append({
                    "os_id": feature.get("id", ""),
                    "name": props.get("name", ""),
                    "address": props.get("address", ""),
                    "country_code": props.get("country_code", ""),
                    "country_name": props.get("country_name", ""),
                    "sector": props.get("sector", []),
                    "longitude": coords[0] if coords else None,
                    "latitude": coords[1] if len(coords) > 1 else None,
                    "contributors": props.get("contributors", []),
                    "number_of_workers": props.get("number_of_workers", {}).get("max"),
                })

            logger.info("Found %d facilities matching query '%s'", len(facilities), query)
            return facilities

        except Exception as exc:
            logger.error("Open Supply Hub search failed: %s", exc)
            return []

    def get_facility(self, os_id: str) -> dict[str, Any] | None:
        """Get detailed facility information by OS ID."""
        try:
            response = requests.get(
                f"{OSH_API_BASE}/facilities/{os_id}/",
                headers=self._headers(),
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()

            props = data.get("properties", {})
            geometry = data.get("geometry", {})
            coords = geometry.get("coordinates", [None, None])

            return {
                "os_id": data.get("id", ""),
                "name": props.get("name", ""),
                "address": props.get("address", ""),
                "country_code": props.get("country_code", ""),
                "country_name": props.get("country_name", ""),
                "sector": props.get("sector", []),
                "longitude": coords[0] if coords else None,
                "latitude": coords[1] if len(coords) > 1 else None,
                "contributors": props.get("contributors", []),
                "number_of_workers": props.get("number_of_workers", {}).get("max"),
                "parent_company": props.get("extended_fields", {}).get("parent_company", {}).get("value"),
                "facility_type": props.get("extended_fields", {}).get("facility_type", {}).get("value"),
                "processing_types": props.get("extended_fields", {}).get("processing_type", {}).get("value", []),
                "product_types": props.get("extended_fields", {}).get("product_type", {}).get("value", []),
            }

        except Exception as exc:
            logger.error("Open Supply Hub facility lookup failed for %s: %s", os_id, exc)
            return None

    def get_facilities_by_country(self, country_code: str, limit: int = 100) -> list[dict[str, Any]]:
        """Get all facilities in a country."""
        return self.search_facilities(country=country_code, limit=limit)

    def get_facilities_near(
        self,
        latitude: float,
        longitude: float,
        radius_km: float = 50,
    ) -> list[dict[str, Any]]:
        """Get facilities near a geographic point.

        Note: OSH API may not support radius search directly,
        so we filter client-side.
        """
        import math

        # Get facilities in the approximate area
        # Use a bounding box approach
        all_facilities = self.search_facilities(limit=100)

        nearby: list[dict[str, Any]] = []
        for facility in all_facilities:
            f_lat = facility.get("latitude")
            f_lon = facility.get("longitude")
            if f_lat is None or f_lon is None:
                continue

            # Haversine distance
            distance = self._haversine_km(latitude, longitude, f_lat, f_lon)
            if distance <= radius_km:
                facility["distance_km"] = round(distance, 1)
                nearby.append(facility)

        nearby.sort(key=lambda f: f.get("distance_km", 999))
        return nearby

    def _haversine_km(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two points in km."""
        import math
        R = 6371  # Earth radius in km
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
             math.sin(dlon / 2) ** 2)
        return R * 2 * math.asin(math.sqrt(a))


def build_supply_chain_graph_data(
    facilities: list[dict[str, Any]],
) -> dict[str, Any]:
    """Convert OSH facility data into graph nodes and edges.

    Creates a graph structure compatible with app/graph/graph.py.
    """
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    parent_map: dict[str, list[str]] = {}  # parent_company -> [facility_ids]

    for facility in facilities:
        node = {
            "id": facility.get("os_id", ""),
            "name": facility.get("name", ""),
            "type": _infer_node_type(facility),
            "location": f"{facility.get('address', '')}, {facility.get('country_name', '')}",
            "country": facility.get("country_code", ""),
            "latitude": facility.get("latitude"),
            "longitude": facility.get("longitude"),
            "sector": facility.get("sector", []),
            "workers": facility.get("number_of_workers"),
        }
        nodes.append(node)

        # Track parent company relationships
        parent = facility.get("parent_company")
        if parent:
            parent_map.setdefault(parent, []).append(facility["os_id"])

    # Create edges for facilities with same parent company (ownership links)
    for parent, facility_ids in parent_map.items():
        if len(facility_ids) > 1:
            for i in range(len(facility_ids) - 1):
                edges.append({
                    "from_node": facility_ids[i],
                    "to_node": facility_ids[i + 1],
                    "type": "same_owner",
                    "label": f"Parent: {parent}",
                })

    return {
        "nodes": nodes,
        "edges": edges,
        "parent_companies": list(parent_map.keys()),
        "countries": list(set(f.get("country_code", "") for f in facilities)),
        "total_facilities": len(nodes),
    }


def _infer_node_type(facility: dict[str, Any]) -> str:
    """Infer graph node type from facility data."""
    facility_type = str(facility.get("facility_type", "")).lower()
    processing = [str(p).lower() for p in facility.get("processing_types", [])]

    if any(t in facility_type for t in ["warehouse", "distribution", "logistics"]):
        return "warehouse"
    if any(t in facility_type for t in ["manufacturing", "factory", "plant", "assembly"]):
        return "plant"
    if any("warehouse" in p or "storage" in p for p in processing):
        return "warehouse"
    if any("manufacturing" in p or "assembly" in p for p in processing):
        return "plant"

    return "supplier"


def fetch_supply_hub_events(
    countries: list[str] | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Fetch supply hub data as events for the ingestion pipeline.

    Primarily used for graph enrichment rather than risk events.
    """
    client = OpenSupplyHubClient()

    if not client.is_configured:
        logger.info("Open Supply Hub not configured — using fallback data")
        return _fallback_supply_hub_events()[:limit]

    facilities: list[dict[str, Any]] = []
    target_countries = countries or ["CN", "IN", "VN", "BD", "TH"]

    for country in target_countries:
        country_facilities = client.get_facilities_by_country(country, limit=limit // len(target_countries))
        facilities.extend(country_facilities)

    events: list[dict[str, Any]] = []
    for facility in facilities[:limit]:
        events.append(normalize_supply_hub_event(facility))

    if not events:
        events = _fallback_supply_hub_events()[:limit]

    logger.info("Generated %d supply hub events", len(events))
    return events


def normalize_supply_hub_event(facility: dict[str, Any]) -> dict[str, Any]:
    """Convert facility data into advisor event format."""
    name = facility.get("name", "Unknown Facility")
    country = facility.get("country_name", "")
    sector = ", ".join(facility.get("sector", [])) or "General"

    text = (
        f"Supply chain facility: {name} in {country}. "
        f"Sector: {sector}. "
        f"Location: {facility.get('address', 'Unknown')}."
    )

    return {
        "source": "supply_hub",
        "reference_id": f"OSH-{facility.get('os_id', 'unknown')}",
        "supplier": name,
        "event_time": datetime.now(timezone.utc).isoformat(),
        "text": text,
        "metadata": {
            "title": f"Facility: {name} ({country})",
            "summary": text,
            "severity": "low",  # Facility data is informational
            "facility_data": facility,
        },
    }


def _fallback_supply_hub_events() -> list[dict[str, Any]]:
    """Synthetic supply hub events for demo/fallback."""
    now = datetime.now(timezone.utc).isoformat()
    return [
        {
            "source": "supply_hub",
            "reference_id": "OSH-FALLBACK-0",
            "supplier": "Foxconn Zhengzhou",
            "event_time": now,
            "text": "Supply chain facility: Foxconn Zhengzhou Technology Park in China. Sector: Electronics Manufacturing. Workers: 200,000+.",
            "metadata": {
                "title": "Facility: Foxconn Zhengzhou (China)",
                "summary": "Major electronics assembly facility.",
                "severity": "low",
                "facility_data": {
                    "name": "Foxconn Zhengzhou",
                    "country_code": "CN",
                    "sector": ["Electronics"],
                    "latitude": 34.75,
                    "longitude": 113.65,
                },
            },
        },
        {
            "source": "supply_hub",
            "reference_id": "OSH-FALLBACK-1",
            "supplier": "Tata Steel Jamshedpur",
            "event_time": now,
            "text": "Supply chain facility: Tata Steel Jamshedpur in India. Sector: Metals & Mining. Major steel production hub.",
            "metadata": {
                "title": "Facility: Tata Steel Jamshedpur (India)",
                "summary": "Major steel production facility.",
                "severity": "low",
                "facility_data": {
                    "name": "Tata Steel Jamshedpur",
                    "country_code": "IN",
                    "sector": ["Metals"],
                    "latitude": 22.80,
                    "longitude": 86.20,
                },
            },
        },
    ]

"""
Abstract base class for AIS data providers.
Defines the interface that all AIS providers must implement.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any


class AISProviderBase(ABC):
    """Abstract AIS data provider interface."""

    @abstractmethod
    def fetch_vessels(self, bounds: Dict[str, float] = None) -> List[Dict[str, Any]]:
        """
        Fetch vessel data from the AIS provider.
        
        Args:
            bounds: Optional geographic bounds dict with keys:
                    lat_min, lat_max, lon_min, lon_max
        
        Returns:
            List of vessel dictionaries with standardized keys:
            - mmsi, imo, name, vessel_type, callsign, flag
            - latitude, longitude, course, speed, heading
            - destination, eta, nav_status, last_update
        """
        pass

    @abstractmethod
    def get_vessel_details(self, mmsi: str) -> Dict[str, Any]:
        """Fetch detailed information for a specific vessel."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the provider API is reachable and authenticated."""
        pass

    @staticmethod
    def normalize_vessel_data(raw: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize raw provider data to standard format."""
        return {
            "mmsi": str(raw.get("mmsi", "")),
            "imo": str(raw.get("imo", "")),
            "name": str(raw.get("name", "Unknown")).strip(),
            "vessel_type": str(raw.get("vessel_type", "Unknown")),
            "callsign": str(raw.get("callsign", "")),
            "flag": str(raw.get("flag", "")),
            "length": float(raw.get("length", 0) or 0),
            "width": float(raw.get("width", 0) or 0),
            "draught": float(raw.get("draught", 0) or 0),
            "latitude": float(raw.get("latitude", 0) or 0),
            "longitude": float(raw.get("longitude", 0) or 0),
            "course": float(raw.get("course", 0) or 0),
            "speed": float(raw.get("speed", 0) or 0),
            "heading": float(raw.get("heading", 0) or 0),
            "destination": str(raw.get("destination", "")),
            "eta": str(raw.get("eta", "")),
            "nav_status": str(raw.get("nav_status", "")),
            "last_update": str(raw.get("last_update", "")),
        }

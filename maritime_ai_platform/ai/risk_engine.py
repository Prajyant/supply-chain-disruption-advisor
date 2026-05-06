"""
Risk scoring engine for maritime vessel intelligence.
Combines geographic, behavioral, and AI-driven risk factors.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from config.settings import RiskConfig
from database.db_manager import DatabaseManager

logger = logging.getLogger(__name__)


class RiskEngine:
    """
    Weighted risk scoring engine that evaluates vessels based on:
    - Geographic danger zone proximity
    - Speed anomalies
    - AIS silence detection
    - Route deviation indicators
    - AI-generated risk factors
    """

    def __init__(self, config: RiskConfig, db: DatabaseManager):
        self.config = config
        self.db = db

    def calculate_risk(self, vessel: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate comprehensive risk score for a vessel.
        
        Returns dict with:
        - risk_score (0-100)
        - risk_level (LOW/MEDIUM/HIGH)
        - risk_factors (list of contributing factors)
        - danger_zones (list of active zones)
        """
        score = 0
        factors = []
        active_zones = []

        geo_score, geo_factors, zones = self._geographic_risk(vessel)
        score += geo_score
        factors.extend(geo_factors)
        active_zones.extend(zones)

        speed_score, speed_factors = self._speed_anomaly_risk(vessel)
        score += speed_score
        factors.extend(speed_factors)

        ais_score, ais_factors = self._ais_silence_risk(vessel)
        score += ais_score
        factors.extend(ais_factors)

        route_score, route_factors = self._route_deviation_risk(vessel)
        score += route_score
        factors.extend(route_factors)

        behavior_score, behavior_factors = self._behavioral_risk(vessel)
        score += behavior_score
        factors.extend(behavior_factors)

        score = max(0, min(100, score))

        if score <= self.config.low_threshold:
            risk_level = "LOW"
        elif score <= self.config.medium_threshold:
            risk_level = "MEDIUM"
        else:
            risk_level = "HIGH"

        self.db.update_vessel_risk(vessel.get("mmsi", ""), score, risk_level)

        return {
            "risk_score": score,
            "risk_level": risk_level,
            "risk_factors": factors,
            "danger_zones": active_zones,
        }

    def _geographic_risk(self, vessel: Dict[str, Any]) -> tuple:
        """Evaluate geographic danger zone risk."""
        score = 0
        factors = []
        active_zones = []

        lat = vessel.get("latitude", 0)
        lon = vessel.get("longitude", 0)

        for zone in self.config.danger_zones:
            if (zone["lat_min"] <= lat <= zone["lat_max"] and
                    zone["lon_min"] <= lon <= zone["lon_max"]):
                score += zone["weight"]
                factors.append(f"In danger zone: {zone['name']} (+{zone['weight']})")
                active_zones.append(zone["name"])

        return score, factors, active_zones

    def _speed_anomaly_risk(self, vessel: Dict[str, Any]) -> tuple:
        """Detect speed anomalies compared to historical data."""
        score = 0
        factors = []

        current_speed = vessel.get("speed", 0)
        mmsi = vessel.get("mmsi", "")

        history = self.db.get_speed_history(mmsi, hours=24)
        if history and len(history) >= 3:
            avg_speed = sum(h["speed"] for h in history if h["speed"]) / len(history)
            deviation = abs(current_speed - avg_speed)

            if deviation > self.config.speed_anomaly_threshold_knots * 3:
                score += 15
                factors.append(f"Major speed anomaly: {current_speed:.1f}kts vs avg {avg_speed:.1f}kts (+15)")
            elif deviation > self.config.speed_anomaly_threshold_knots:
                score += 8
                factors.append(f"Speed deviation: {current_speed:.1f}kts vs avg {avg_speed:.1f}kts (+8)")

        if current_speed < 1.0 and vessel.get("nav_status") not in ("At anchor", "Moored", "Not under command"):
            score += 12
            factors.append("Near-zero speed while reportedly underway (+12)")

        if current_speed > 28:
            score += 10
            factors.append(f"Excessive speed: {current_speed:.1f}kts (+10)")

        return score, factors

    def _ais_silence_risk(self, vessel: Dict[str, Any]) -> tuple:
        """Detect AIS signal gaps."""
        score = 0
        factors = []

        last_update = vessel.get("last_update", "")
        if last_update:
            try:
                last_time = datetime.fromisoformat(last_update.replace("Z", "+00:00"))
                silence_minutes = (datetime.utcnow() - last_time.replace(tzinfo=None)).total_seconds() / 60

                if silence_minutes > self.config.ais_silence_minutes * 4:
                    score += 25
                    factors.append(f"Extended AIS silence: {silence_minutes:.0f} min (+25)")
                elif silence_minutes > self.config.ais_silence_minutes * 2:
                    score += 15
                    factors.append(f"AIS gap detected: {silence_minutes:.0f} min (+15)")
                elif silence_minutes > self.config.ais_silence_minutes:
                    score += 8
                    factors.append(f"AIS update delay: {silence_minutes:.0f} min (+8)")
            except (ValueError, TypeError):
                pass

        return score, factors

    def _route_deviation_risk(self, vessel: Dict[str, Any]) -> tuple:
        """Assess route deviation indicators."""
        score = 0
        factors = []

        if not vessel.get("destination"):
            score += 5
            factors.append("No destination declared (+5)")

        mmsi = vessel.get("mmsi", "")
        history = self.db.get_vessel_history(mmsi, hours=6)

        if len(history) >= 4:
            courses = [h["course"] for h in history[-4:] if h.get("course") is not None]
            if len(courses) >= 4:
                course_changes = sum(
                    abs(courses[i] - courses[i - 1]) % 360
                    for i in range(1, len(courses))
                )
                if course_changes > 270:
                    score += 15
                    factors.append(f"Erratic course changes detected (+15)")
                elif course_changes > 180:
                    score += 8
                    factors.append(f"Significant course variation (+8)")

        return score, factors

    def _behavioral_risk(self, vessel: Dict[str, Any]) -> tuple:
        """Assess behavioral risk indicators."""
        score = 0
        factors = []

        vessel_type = vessel.get("vessel_type", "").lower()
        lat = vessel.get("latitude", 0)
        lon = vessel.get("longitude", 0)

        if "tanker" in vessel_type:
            for zone in self.config.danger_zones:
                if (zone["lat_min"] <= lat <= zone["lat_max"] and
                        zone["lon_min"] <= lon <= zone["lon_max"]):
                    score += 5
                    factors.append(f"High-value tanker in risk area (+5)")
                    break

        if "fishing" in vessel_type and vessel.get("speed", 0) > 15:
            score += 10
            factors.append("Fishing vessel at unusual speed (+10)")

        if vessel.get("draught", 0) > 15:
            score += 3
            factors.append("Deep draught - restricted maneuverability (+3)")

        return score, factors

    def batch_calculate(self, vessels: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Calculate risk for multiple vessels."""
        results = []
        for vessel in vessels:
            risk = self.calculate_risk(vessel)
            vessel_with_risk = {**vessel, **risk}
            results.append(vessel_with_risk)
        return results

    def get_high_risk_vessels(self, vessels: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter vessels with HIGH risk level."""
        return [v for v in vessels if v.get("risk_level") == "HIGH"]

"""
Alert engine for generating and managing maritime intelligence alerts.
"""

import logging
from typing import Dict, Any, List
from datetime import datetime

from PyQt5.QtCore import QObject, pyqtSignal

from config.settings import RiskConfig
from database.db_manager import DatabaseManager

logger = logging.getLogger(__name__)


class AlertEngine(QObject):
    """Generates alerts based on vessel risk analysis and behavioral patterns."""

    alert_generated = pyqtSignal(dict)

    def __init__(self, config: RiskConfig, db: DatabaseManager):
        super().__init__()
        self.config = config
        self.db = db
        self._previous_states: Dict[str, Dict[str, Any]] = {}

    def evaluate_vessel(self, vessel: Dict[str, Any], risk_data: Dict[str, Any]):
        """Evaluate a vessel and generate alerts if conditions are met."""
        mmsi = vessel.get("mmsi", "")
        name = vessel.get("name", "Unknown")
        prev = self._previous_states.get(mmsi, {})

        if risk_data.get("risk_level") == "HIGH":
            if prev.get("risk_level") != "HIGH":
                self._create_alert(
                    mmsi, name, "HIGH_RISK",
                    "HIGH",
                    f"Vessel {name} (MMSI: {mmsi}) elevated to HIGH risk - Score: {risk_data.get('risk_score', 0)}/100",
                    "; ".join(risk_data.get("risk_factors", []))
                )

        if risk_data.get("danger_zones"):
            prev_zones = set(prev.get("danger_zones", []))
            new_zones = set(risk_data["danger_zones"]) - prev_zones
            for zone in new_zones:
                self._create_alert(
                    mmsi, name, "DANGER_ZONE_ENTRY",
                    "HIGH" if "Aden" in zone or "Somalia" in zone else "MEDIUM",
                    f"Vessel {name} entered danger zone: {zone}",
                    f"Position: {vessel.get('latitude', 0):.4f}N, {vessel.get('longitude', 0):.4f}E"
                )

        current_speed = vessel.get("speed", 0)
        prev_speed = prev.get("speed", current_speed)
        if abs(current_speed - prev_speed) > 10:
            self._create_alert(
                mmsi, name, "SPEED_ANOMALY",
                "MEDIUM",
                f"Vessel {name} speed anomaly: {prev_speed:.1f} → {current_speed:.1f} knots",
                f"Change of {abs(current_speed - prev_speed):.1f} knots detected"
            )

        last_update = vessel.get("last_update", "")
        if last_update:
            try:
                last_time = datetime.fromisoformat(last_update.replace("Z", "+00:00"))
                silence = (datetime.utcnow() - last_time.replace(tzinfo=None)).total_seconds() / 60
                if silence > self.config.ais_silence_minutes and not prev.get("ais_silent"):
                    self._create_alert(
                        mmsi, name, "AIS_SILENCE",
                        "HIGH",
                        f"AIS signal lost for vessel {name} - {silence:.0f} minutes",
                        f"Last known position: {vessel.get('latitude', 0):.4f}N, {vessel.get('longitude', 0):.4f}E"
                    )
                    risk_data["ais_silent"] = True
            except (ValueError, TypeError):
                pass

        self._previous_states[mmsi] = {
            "risk_level": risk_data.get("risk_level"),
            "danger_zones": risk_data.get("danger_zones", []),
            "speed": current_speed,
            "ais_silent": risk_data.get("ais_silent", False),
        }

    def _create_alert(self, mmsi: str, vessel_name: str, alert_type: str,
                      severity: str, message: str, details: str = ""):
        """Create and store an alert."""
        self.db.add_alert(mmsi, vessel_name, alert_type, severity, message, details)
        alert = {
            "mmsi": mmsi,
            "vessel_name": vessel_name,
            "alert_type": alert_type,
            "severity": severity,
            "message": message,
            "details": details,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self.alert_generated.emit(alert)
        logger.warning(f"ALERT [{severity}] {alert_type}: {message}")

    def get_recent_alerts(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent alerts from database."""
        return self.db.get_recent_alerts(limit)

    def get_unacknowledged(self) -> List[Dict[str, Any]]:
        """Get unacknowledged alerts."""
        return self.db.get_unacknowledged_alerts()

    def acknowledge(self, alert_id: int):
        """Acknowledge an alert."""
        self.db.acknowledge_alert(alert_id)

"""Risk service for analyzing and scoring supply chain disruptions."""
import logging
from typing import Optional

from app.services.risk_engine import RiskAnalyzer

logger = logging.getLogger(__name__)


class RiskService:
    """Service for risk analysis and scoring."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.risk_analyzer = RiskAnalyzer()
            cls._instance._risks = []
        return cls._instance

    def __init__(self) -> None:
        pass

    def analyze_events(self, events: list[dict]) -> list[dict]:
        """Analyze events and generate risk assessments.

        Args:
            events: List of event dictionaries

        Returns:
            List of risk assessment dictionaries
        """
        self._risks = [self.risk_analyzer.analyze_event(event).model_dump() for event in events]
        return self._risks

    def get_risks(self) -> list[dict]:
        """Get all current risk assessments."""
        return self._risks

    def get_risk_by_id(self, risk_id: str) -> Optional[dict]:
        """Get a specific risk by ID.

        Args:
            risk_id: The risk ID to look up

        Returns:
            Risk dictionary or None if not found
        """
        for risk in self._risks:
            if risk.get("risk_id") == risk_id:
                return risk
        return None

    def get_risks_by_severity(self, severity: str) -> list[dict]:
        """Get risks filtered by severity.

        Args:
            severity: The severity level to filter by

        Returns:
            List of risk dictionaries
        """
        return [r for r in self._risks if r.get("severity") == severity]

    def get_critical_risks(self) -> list[dict]:
        """Get all critical risks."""
        return self.get_risks_by_severity("critical")

    def get_high_risks(self) -> list[dict]:
        """Get all high risks."""
        return self.get_risks_by_severity("high")

    def update_risk_score(self, risk_id: str, new_score: float) -> Optional[dict]:
        """Update a risk's score.

        Args:
            risk_id: The risk ID to update
            new_score: The new risk score (0.0 to 1.0)

        Returns:
            Updated risk dictionary or None if not found
        """
        for risk in self._risks:
            if risk.get("risk_id") == risk_id:
                risk["confidence"] = new_score
                return risk
        return None

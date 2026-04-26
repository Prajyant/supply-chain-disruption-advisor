"""Risk service for analyzing and scoring supply chain disruptions."""
import logging
from typing import Optional

from app.services.risk_engine import RiskAnalyzer
from app.models.schemas import RiskAssessment

logger = logging.getLogger(__name__)


class RiskService:
    """Service for risk analysis and scoring."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.risk_analyzer = RiskAnalyzer()
            cls._instance._risks = []
            cls._instance._predictions = []  # Predictive cross-reference results
        return cls._instance

    def __init__(self) -> None:
        pass

    def analyze_events(self, events: list[dict]) -> list[dict]:
        """Analyze events individually (reactive layer).

        Args:
            events: List of event dictionaries

        Returns:
            List of risk assessment dictionaries
        """
        self._risks = [self.risk_analyzer.analyze_event(event).model_dump() for event in events]
        return self._risks

    def cross_reference(
        self,
        operations: list[dict],
        news_events: list[dict],
    ) -> list[RiskAssessment]:
        """Run predictive cross-reference analysis.

        Args:
            operations: Normal operational emails (shipment confirmations, etc.)
            news_events: Real-time world news events

        Returns:
            List of predictive RiskAssessment objects
        """
        self._predictions = self.risk_analyzer.cross_reference(operations, news_events)
        logger.info(f"Cross-reference produced {len(self._predictions)} predictions")
        return self._predictions

    def get_risks(self) -> list[dict]:
        """Get all current reactive risk assessments."""
        return self._risks

    def get_predictions(self) -> list[RiskAssessment]:
        """Get all predictive risk assessments."""
        return self._predictions

    def get_risk_by_id(self, risk_id: str) -> Optional[dict]:
        """Get a specific risk by ID."""
        for risk in self._risks:
            if risk.get("risk_id") == risk_id:
                return risk
        return None

    def get_risks_by_severity(self, severity: str) -> list[dict]:
        """Get risks filtered by severity."""
        return [r for r in self._risks if r.get("severity") == severity]

    def get_critical_risks(self) -> list[dict]:
        """Get all critical risks."""
        return self.get_risks_by_severity("critical")

    def get_high_risks(self) -> list[dict]:
        """Get all high risks."""
        return self.get_risks_by_severity("high")

    def update_risk_score(self, risk_id: str, new_score: float) -> Optional[dict]:
        """Update a risk's score."""
        for risk in self._risks:
            if risk.get("risk_id") == risk_id:
                risk["confidence"] = new_score
                return risk
        return None

"""
Analytics overview panel with traffic density and risk distribution charts.
"""

import logging
from typing import List, Dict, Any

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QScrollArea

from analytics.charts import TrafficDensityChart, RiskDistributionChart

logger = logging.getLogger(__name__)


class AnalyticsPanel(QWidget):
    """Panel showing fleet-wide analytics and charts."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        header = QLabel("📊 FLEET ANALYTICS")
        header.setStyleSheet("font-weight: bold; font-size: 13px; color: #4488ff;")
        header.setAlignment(Qt.AlignCenter)
        layout.addWidget(header)

        self.traffic_chart = TrafficDensityChart(parent=self, width=5, height=3)
        layout.addWidget(self.traffic_chart)

        self.risk_dist_chart = RiskDistributionChart(parent=self, width=4, height=3)
        layout.addWidget(self.risk_dist_chart)

        self.stats_label = QLabel("")
        self.stats_label.setAlignment(Qt.AlignCenter)
        self.stats_label.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(self.stats_label)

        layout.addStretch()

    def update_analytics(self, vessels: List[Dict[str, Any]], region_counts: Dict[str, int]):
        """Update all analytics charts."""
        self.traffic_chart.update_chart(region_counts)
        self.risk_dist_chart.update_chart(vessels)

        total = len(vessels)
        high = sum(1 for v in vessels if v.get("risk_level") == "HIGH")
        medium = sum(1 for v in vessels if v.get("risk_level") == "MEDIUM")
        avg_speed = sum(v.get("speed", 0) for v in vessels) / max(total, 1)

        self.stats_label.setText(
            f"Total: {total} | High Risk: {high} | Medium Risk: {medium} | Avg Speed: {avg_speed:.1f}kts"
        )

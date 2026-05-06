"""
Vessel detail and AI analysis panel.
Shows comprehensive vessel information, AI risk analysis, and charts.
"""

import logging
from typing import Dict, Any, Optional

from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTabWidget,
    QTextEdit, QPushButton, QFrame, QScrollArea, QGridLayout,
    QGroupBox, QSizePolicy
)
from PyQt5.QtGui import QFont

from analytics.charts import SpeedHistoryChart, RiskTrendChart

logger = logging.getLogger(__name__)


class DetailPanel(QWidget):
    """Right panel showing vessel details, AI analysis, and charts."""

    analyze_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(380)
        self._current_mmsi: Optional[str] = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self.vessel_name_label = QLabel("Select a vessel")
        self.vessel_name_label.setObjectName("title")
        self.vessel_name_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.vessel_name_label)

        self.risk_badge = QLabel("")
        self.risk_badge.setAlignment(Qt.AlignCenter)
        self.risk_badge.setFixedHeight(24)
        layout.addWidget(self.risk_badge)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        self._create_info_tab()
        self._create_analysis_tab()
        self._create_charts_tab()

        btn_layout = QHBoxLayout()
        self.analyze_btn = QPushButton("🤖 Run AI Analysis")
        self.analyze_btn.setObjectName("primary")
        self.analyze_btn.clicked.connect(self._request_analysis)
        self.analyze_btn.setEnabled(False)
        btn_layout.addWidget(self.analyze_btn)
        layout.addLayout(btn_layout)

    def _create_info_tab(self):
        """Create the vessel information tab."""
        widget = QWidget()
        layout = QGridLayout(widget)
        layout.setSpacing(6)

        self.info_labels = {}
        fields = [
            ("MMSI", "mmsi"), ("IMO", "imo"), ("Type", "vessel_type"),
            ("Flag", "flag"), ("Callsign", "callsign"),
            ("Position", "position"), ("Speed", "speed"), ("Course", "course"),
            ("Heading", "heading"), ("Destination", "destination"),
            ("ETA", "eta"), ("Nav Status", "nav_status"),
            ("Length", "length"), ("Draught", "draught"),
            ("Last Update", "last_update"),
        ]

        for i, (label_text, key) in enumerate(fields):
            label = QLabel(f"{label_text}:")
            label.setStyleSheet("color: #888888; font-weight: bold;")
            value = QLabel("—")
            value.setStyleSheet("color: #e0e0e0;")
            value.setWordWrap(True)
            layout.addWidget(label, i, 0)
            layout.addWidget(value, i, 1)
            self.info_labels[key] = value

        scroll = QScrollArea()
        scroll.setWidget(widget)
        scroll.setWidgetResizable(True)
        self.tabs.addTab(scroll, "📋 Info")

    def _create_analysis_tab(self):
        """Create the AI analysis tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.analysis_text = QTextEdit()
        self.analysis_text.setReadOnly(True)
        self.analysis_text.setPlaceholderText("No AI analysis available.\nClick 'Run AI Analysis' to generate.")
        layout.addWidget(self.analysis_text)

        scroll = QScrollArea()
        scroll.setWidget(widget)
        scroll.setWidgetResizable(True)
        self.tabs.addTab(scroll, "🤖 AI Analysis")

    def _create_charts_tab(self):
        """Create the charts tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.speed_chart = SpeedHistoryChart(parent=widget, width=5, height=2.5)
        layout.addWidget(self.speed_chart)

        self.risk_chart = RiskTrendChart(parent=widget, width=5, height=2.5)
        layout.addWidget(self.risk_chart)

        scroll = QScrollArea()
        scroll.setWidget(widget)
        scroll.setWidgetResizable(True)
        self.tabs.addTab(scroll, "📊 Charts")

    def show_vessel(self, vessel: Dict[str, Any]):
        """Display vessel details."""
        self._current_mmsi = vessel.get("mmsi")
        self.analyze_btn.setEnabled(True)

        name = vessel.get("name", "Unknown")
        self.vessel_name_label.setText(name)

        risk_level = vessel.get("risk_level", "LOW")
        risk_score = vessel.get("risk_score", 0)
        self._update_risk_badge(risk_level, risk_score)

        self.info_labels["mmsi"].setText(str(vessel.get("mmsi", "—")))
        self.info_labels["imo"].setText(str(vessel.get("imo", "—")))
        self.info_labels["vessel_type"].setText(str(vessel.get("vessel_type", "—")))
        self.info_labels["flag"].setText(str(vessel.get("flag", "—")))
        self.info_labels["callsign"].setText(str(vessel.get("callsign", "—")))
        self.info_labels["position"].setText(
            f"{vessel.get('latitude', 0):.4f}°N, {vessel.get('longitude', 0):.4f}°E"
        )
        self.info_labels["speed"].setText(f"{vessel.get('speed', 0):.1f} knots")
        self.info_labels["course"].setText(f"{vessel.get('course', 0):.1f}°")
        self.info_labels["heading"].setText(f"{vessel.get('heading', 0):.1f}°")
        self.info_labels["destination"].setText(str(vessel.get("destination", "—") or "—"))
        self.info_labels["eta"].setText(str(vessel.get("eta", "—") or "—"))
        self.info_labels["nav_status"].setText(str(vessel.get("nav_status", "—") or "—"))
        self.info_labels["length"].setText(f"{vessel.get('length', 0):.0f} m")
        self.info_labels["draught"].setText(f"{vessel.get('draught', 0):.1f} m")
        self.info_labels["last_update"].setText(str(vessel.get("last_update", "—") or "—"))

    def show_analysis(self, analysis: Dict[str, Any]):
        """Display AI analysis results."""
        if not analysis:
            self.analysis_text.setHtml("<p style='color:#888'>No analysis available</p>")
            return

        risk_level = analysis.get("risk_level", "LOW")
        risk_score = analysis.get("risk_score", 0)
        self._update_risk_badge(risk_level, risk_score)

        color_map = {"HIGH": "#ff3355", "MEDIUM": "#ff8800", "LOW": "#00ff88"}
        risk_color = color_map.get(risk_level, "#00ff88")

        html = f"""
        <div style="font-family: Segoe UI; color: #e0e0e0; padding: 8px;">
            <h3 style="color: {risk_color}; margin-bottom: 10px;">
                Risk Assessment: {risk_level} ({risk_score}/100)
            </h3>
            
            <h4 style="color: #4488ff;">📍 Route Analysis</h4>
            <p>{analysis.get('route_analysis', 'N/A')}</p>
            
            <h4 style="color: #4488ff;">🚢 Chokepoint Analysis</h4>
            <p>{analysis.get('chokepoint_analysis', 'N/A')}</p>
            
            <h4 style="color: #ff3355;">⚠️ Piracy Threat</h4>
            <p>{analysis.get('piracy_threat', 'N/A')}</p>
            
            <h4 style="color: #ff8800;">🌊 Weather Concerns</h4>
            <p>{analysis.get('weather_concerns', 'N/A')}</p>
            
            <h4 style="color: #ff8800;">⏱️ ETA Concerns</h4>
            <p>{analysis.get('eta_concerns', 'N/A')}</p>
            
            <h4 style="color: #00ff88;">✅ Recommendations</h4>
            <p>{analysis.get('recommendations', 'N/A')}</p>
            
            <hr style="border-color: #333355; margin: 10px 0;">
            <p style="color: #666; font-size: 10px;">
                Model: {analysis.get('model_used', 'N/A')} | 
                Tokens: {analysis.get('tokens_used', 0)} |
                Time: {analysis.get('timestamp', 'N/A')}
            </p>
        </div>
        """
        self.analysis_text.setHtml(html)

    def update_charts(self, speed_data: list, risk_data: list, vessel_name: str = ""):
        """Update the speed and risk charts."""
        self.speed_chart.update_chart(speed_data, vessel_name)
        self.risk_chart.update_chart(risk_data, vessel_name)

    def _update_risk_badge(self, risk_level: str, risk_score: int):
        """Update the risk badge display."""
        colors = {"HIGH": "#ff3355", "MEDIUM": "#ff8800", "LOW": "#00ff88"}
        color = colors.get(risk_level, "#00ff88")
        self.risk_badge.setText(f"⬤ {risk_level} RISK ({risk_score}/100)")
        self.risk_badge.setStyleSheet(
            f"color: {color}; font-weight: bold; font-size: 13px; "
            f"background: {color}22; border-radius: 4px; padding: 2px;"
        )

    def _request_analysis(self):
        """Request AI analysis for current vessel."""
        if self._current_mmsi:
            self.analyze_requested.emit(self._current_mmsi)
            self.analyze_btn.setEnabled(False)
            self.analyze_btn.setText("⏳ Analyzing...")

    def analysis_complete(self):
        """Re-enable the analyze button after completion."""
        self.analyze_btn.setEnabled(True)
        self.analyze_btn.setText("🤖 Run AI Analysis")

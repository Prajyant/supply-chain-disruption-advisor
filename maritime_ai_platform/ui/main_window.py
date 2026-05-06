"""
Main application window for Maritime AI Risk Intelligence Platform.
Orchestrates all UI components, data flow, and background workers.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from PyQt5.QtCore import Qt, QTimer, pyqtSlot, QThread, pyqtSignal, QObject
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QSplitter,
    QStatusBar, QLabel, QTabWidget, QMessageBox, QApplication
)
from PyQt5.QtGui import QIcon

from ui.styles import DARK_STYLESHEET
from ui.vessel_sidebar import VesselSidebar
from ui.detail_panel import DetailPanel
from ui.alert_panel import AlertPanel
from ui.analytics_panel import AnalyticsPanel
from map.map_widget import MapWidget
from ais.ais_engine import AISEngine, AISDataWorker
from ais.demo_provider import DemoAISProvider
from ai.bedrock_engine import BedrockAIEngine
from ai.risk_engine import RiskEngine
from ai.alert_engine import AlertEngine
from database.db_manager import DatabaseManager
from config.settings import AppConfig

logger = logging.getLogger(__name__)


class AIAnalysisWorker(QObject):
    """Background worker for AI analysis to avoid blocking the UI."""

    analysis_complete = pyqtSignal(str, dict)
    analysis_error = pyqtSignal(str, str)

    def __init__(self, ai_engine: BedrockAIEngine, danger_zones: list):
        super().__init__()
        self.ai_engine = ai_engine
        self.danger_zones = danger_zones
        self._vessel_queue: List[Dict[str, Any]] = []

    @pyqtSlot(dict)
    def analyze(self, vessel: Dict[str, Any]):
        """Run AI analysis on a vessel."""
        mmsi = vessel.get("mmsi", "")
        try:
            result = self.ai_engine.analyze_vessel(vessel, self.danger_zones)
            self.analysis_complete.emit(mmsi, result)
        except Exception as e:
            logger.error(f"AI analysis failed for {mmsi}: {e}")
            self.analysis_error.emit(mmsi, str(e))


class MainWindow(QMainWindow):
    """Main application window."""

    request_analysis = pyqtSignal(dict)

    def __init__(self, config: AppConfig):
        super().__init__()
        self.config = config
        self._vessels: Dict[str, Dict[str, Any]] = {}
        self._use_demo = not config.ais.api_key

        self._init_backend()
        self._init_ui()
        self._init_workers()
        self._connect_signals()
        self._start_data_flow()

    def _init_backend(self):
        """Initialize backend services."""
        self.db = DatabaseManager(self.config.database.db_path)
        self.ai_engine = BedrockAIEngine(self.config.aws)
        self.risk_engine = RiskEngine(self.config.risk, self.db)
        self.alert_engine = AlertEngine(self.config.risk, self.db)

        if self._use_demo:
            logger.info("No AIS API key - using demo data provider")
            self._demo_provider = DemoAISProvider()
        else:
            self._demo_provider = None

        self.ais_engine = AISEngine(self.config.ais, self.db)

    def _init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle(self.config.ui.window_title)
        self.setMinimumSize(1200, 700)
        self.resize(self.config.ui.window_width, self.config.ui.window_height)
        self.setStyleSheet(DARK_STYLESHEET)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        splitter = QSplitter(Qt.Horizontal)

        self.sidebar = VesselSidebar()
        splitter.addWidget(self.sidebar)

        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)

        self.map_widget = MapWidget(
            default_lat=self.config.ui.map_default_lat,
            default_lon=self.config.ui.map_default_lon,
            default_zoom=self.config.ui.map_default_zoom
        )
        center_layout.addWidget(self.map_widget, stretch=7)

        bottom_tabs = QTabWidget()
        self.alert_panel = AlertPanel()
        self.analytics_panel = AnalyticsPanel()
        bottom_tabs.addTab(self.alert_panel, "⚠️ Alerts")
        bottom_tabs.addTab(self.analytics_panel, "📊 Analytics")
        center_layout.addWidget(bottom_tabs, stretch=3)

        splitter.addWidget(center_widget)

        self.detail_panel = DetailPanel()
        splitter.addWidget(self.detail_panel)

        splitter.setSizes([280, 900, 380])
        main_layout.addWidget(splitter)

        self._init_status_bar()

    def _init_status_bar(self):
        """Initialize the status bar."""
        self.statusBar().setStyleSheet(
            "QStatusBar { background: #0a0a15; color: #888; border-top: 1px solid #1a1a2e; }"
        )
        self.status_vessels = QLabel("Vessels: 0")
        self.status_provider = QLabel(f"Provider: {'Demo' if self._use_demo else self.config.ais.provider}")
        self.status_ai = QLabel(f"AI: {'Ready' if self.ai_engine.is_available() else 'Fallback'}")
        self.status_refresh = QLabel("Last refresh: Never")
        self.status_next = QLabel("")

        self.statusBar().addWidget(self.status_vessels)
        self.statusBar().addWidget(self.status_provider)
        self.statusBar().addWidget(self.status_ai)
        self.statusBar().addPermanentWidget(self.status_refresh)
        self.statusBar().addPermanentWidget(self.status_next)

    def _init_workers(self):
        """Initialize background worker threads."""
        self.ai_thread = QThread()
        self.ai_worker = AIAnalysisWorker(self.ai_engine, self.config.risk.danger_zones)
        self.ai_worker.moveToThread(self.ai_thread)
        self.request_analysis.connect(self.ai_worker.analyze)
        self.ai_worker.analysis_complete.connect(self._on_analysis_complete)
        self.ai_worker.analysis_error.connect(self._on_analysis_error)
        self.ai_thread.start()

        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(self.config.ais.poll_interval_seconds * 1000)
        self.refresh_timer.timeout.connect(self._refresh_data)

        self.countdown_timer = QTimer(self)
        self.countdown_timer.setInterval(1000)
        self.countdown_timer.timeout.connect(self._update_countdown)
        self._next_refresh_seconds = self.config.ais.poll_interval_seconds

    def _connect_signals(self):
        """Connect all UI signals."""
        self.sidebar.vessel_selected.connect(self._on_vessel_selected)
        self.sidebar.refresh_requested.connect(self._refresh_data)
        self.map_widget.vessel_selected.connect(self._on_vessel_selected)
        self.detail_panel.analyze_requested.connect(self._on_analyze_requested)
        self.alert_panel.alert_clicked.connect(self._on_vessel_selected)
        self.alert_panel.alert_acknowledged.connect(self.alert_engine.acknowledge)
        self.alert_engine.alert_generated.connect(self._on_alert_generated)

    def _start_data_flow(self):
        """Start the data flow - either demo or real AIS."""
        if self._use_demo:
            QTimer.singleShot(1000, self._refresh_data)
        else:
            # For AISStream, start the WebSocket connection immediately
            # so data accumulates before the first poll
            if self.config.ais.provider == "aisstream":
                from ais.aisstream_provider import AISStreamProvider
                if isinstance(self.ais_engine.provider, AISStreamProvider):
                    self.ais_engine.provider.start_streaming()
                    logger.info("AISStream WebSocket started - data will accumulate")

            self.ais_worker = self.ais_engine.start()
            self.ais_worker.vessels_updated.connect(self._on_vessels_updated)
            self.ais_worker.fetch_error.connect(self._on_fetch_error)
            self.ais_worker.fetch_completed.connect(self._on_fetch_completed)

        self.refresh_timer.start()
        self.countdown_timer.start()

    def _refresh_data(self):
        """Refresh vessel data."""
        self._next_refresh_seconds = self.config.ais.poll_interval_seconds

        if self._use_demo:
            vessels = self._demo_provider.fetch_vessels()
            self._on_vessels_updated(vessels)
        else:
            self.ais_engine.manual_refresh()

    @pyqtSlot(list)
    def _on_vessels_updated(self, vessels: List[Dict[str, Any]]):
        """Handle new vessel data."""
        vessels_with_risk = []
        for vessel in vessels:
            risk_data = self.risk_engine.calculate_risk(vessel)
            vessel_enriched = {**vessel, **risk_data}
            self._vessels[vessel["mmsi"]] = vessel_enriched
            vessels_with_risk.append(vessel_enriched)

            self.alert_engine.evaluate_vessel(vessel, risk_data)

        self.sidebar.update_vessels(vessels_with_risk)
        self.map_widget.update_vessels(vessels_with_risk)

        region_counts = self.db.get_vessel_count_by_region()
        self.analytics_panel.update_analytics(vessels_with_risk, region_counts)

        self.status_vessels.setText(f"Vessels: {len(vessels_with_risk)}")
        self.status_refresh.setText(f"Last refresh: {datetime.utcnow().strftime('%H:%M:%S')} UTC")

        logger.info(f"UI updated with {len(vessels_with_risk)} vessels")

    @pyqtSlot(str)
    def _on_vessel_selected(self, mmsi: str):
        """Handle vessel selection from sidebar or map."""
        vessel = self._vessels.get(mmsi)
        if not vessel:
            vessel = self.db.get_vessel(mmsi)
        if not vessel:
            return

        self.detail_panel.show_vessel(vessel)
        self.map_widget.center_on_vessel(
            vessel.get("latitude", 0), vessel.get("longitude", 0)
        )

        speed_data = self.db.get_speed_history(mmsi)
        risk_data = self.db.get_risk_trend(mmsi)
        self.detail_panel.update_charts(speed_data, risk_data, vessel.get("name", ""))

        report = self.db.get_latest_ai_report(mmsi)
        if report and report.get("report_json"):
            try:
                import json
                analysis = json.loads(report["report_json"])
                self.detail_panel.show_analysis(analysis)
            except Exception:
                pass

    @pyqtSlot(str)
    def _on_analyze_requested(self, mmsi: str):
        """Handle AI analysis request."""
        vessel = self._vessels.get(mmsi)
        if not vessel:
            vessel = self.db.get_vessel(mmsi)
        if vessel:
            self.request_analysis.emit(vessel)
            self.status_ai.setText("AI: Analyzing...")

    @pyqtSlot(str, dict)
    def _on_analysis_complete(self, mmsi: str, result: Dict[str, Any]):
        """Handle completed AI analysis."""
        self.db.add_ai_report(
            mmsi, result,
            result.get("model_used", "unknown"),
            result.get("tokens_used", 0)
        )

        if mmsi in self._vessels:
            self._vessels[mmsi]["risk_score"] = result.get("risk_score", 0)
            self._vessels[mmsi]["risk_level"] = result.get("risk_level", "LOW")
            self._vessels[mmsi]["last_ai_analysis"] = result.get("timestamp", "")

        self.detail_panel.show_analysis(result)
        self.detail_panel.analysis_complete()
        self.status_ai.setText(f"AI: {'Ready' if self.ai_engine.is_available() else 'Fallback'}")

        logger.info(f"AI analysis stored for MMSI {mmsi}: {result.get('risk_level')}")

    @pyqtSlot(str, str)
    def _on_analysis_error(self, mmsi: str, error: str):
        """Handle AI analysis error."""
        self.detail_panel.analysis_complete()
        self.status_ai.setText("AI: Error")
        logger.error(f"AI analysis error for {mmsi}: {error}")

    @pyqtSlot(dict)
    def _on_alert_generated(self, alert: Dict[str, Any]):
        """Handle new alert."""
        self.alert_panel.add_alert(alert)

    @pyqtSlot(str)
    def _on_fetch_error(self, error: str):
        """Handle AIS fetch error."""
        self.status_refresh.setText(f"Fetch error: {error[:50]}")

    @pyqtSlot(int)
    def _on_fetch_completed(self, count: int):
        """Handle AIS fetch completion."""
        self.status_vessels.setText(f"Vessels: {count}")

    def _update_countdown(self):
        """Update the countdown to next refresh."""
        self._next_refresh_seconds -= 1
        if self._next_refresh_seconds < 0:
            self._next_refresh_seconds = self.config.ais.poll_interval_seconds
        minutes = self._next_refresh_seconds // 60
        seconds = self._next_refresh_seconds % 60
        self.status_next.setText(f"Next: {minutes:02d}:{seconds:02d}")

    def closeEvent(self, event):
        """Clean up on window close."""
        logger.info("Application shutting down...")
        self.refresh_timer.stop()
        self.countdown_timer.stop()

        if not self._use_demo:
            self.ais_engine.stop()
            # Stop AISStream WebSocket if running
            if self.config.ais.provider == "aisstream":
                from ais.aisstream_provider import AISStreamProvider
                if isinstance(self.ais_engine.provider, AISStreamProvider):
                    self.ais_engine.provider.stop_streaming()

        self.ai_thread.quit()
        self.ai_thread.wait(3000)

        self.db.cleanup_old_history(days=30)
        event.accept()

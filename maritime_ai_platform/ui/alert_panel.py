"""
Alert notification panel for displaying maritime intelligence alerts.
"""

import logging
from typing import List, Dict, Any

from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QPushButton, QFrame
)
from PyQt5.QtGui import QColor, QFont

logger = logging.getLogger(__name__)


class AlertListItem(QListWidgetItem):
    """Custom list item for alert display."""

    def __init__(self, alert: Dict[str, Any]):
        super().__init__()
        self.alert_data = alert
        self.alert_id = alert.get("id")

        severity = alert.get("severity", "LOW")
        alert_type = alert.get("alert_type", "UNKNOWN")
        message = alert.get("message", "")
        timestamp = alert.get("created_at", alert.get("timestamp", ""))

        icon_map = {
            "HIGH_RISK": "🔴",
            "DANGER_ZONE_ENTRY": "⚠️",
            "SPEED_ANOMALY": "⚡",
            "AIS_SILENCE": "📡",
            "ROUTE_DEVIATION": "↩️",
        }
        icon = icon_map.get(alert_type, "ℹ️")

        display = f"{icon} [{severity}] {message}\n   {timestamp}"
        self.setText(display)

        if severity == "HIGH":
            self.setForeground(QColor("#ff3355"))
        elif severity == "MEDIUM":
            self.setForeground(QColor("#ff8800"))
        else:
            self.setForeground(QColor("#e0e0e0"))

        font = QFont("Segoe UI", 9)
        self.setFont(font)


class AlertPanel(QWidget):
    """Panel displaying maritime intelligence alerts."""

    alert_clicked = pyqtSignal(str)
    alert_acknowledged = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        header_layout = QHBoxLayout()
        header = QLabel("⚠️ ALERTS")
        header.setStyleSheet("font-weight: bold; font-size: 13px; color: #ff8800;")
        header_layout.addWidget(header)

        self.alert_count = QLabel("0")
        self.alert_count.setStyleSheet(
            "background: #ff3355; color: white; border-radius: 8px; "
            "padding: 2px 6px; font-size: 10px; font-weight: bold;"
        )
        header_layout.addWidget(self.alert_count)
        header_layout.addStretch()

        self.ack_all_btn = QPushButton("Acknowledge All")
        self.ack_all_btn.setObjectName("danger")
        self.ack_all_btn.clicked.connect(self._acknowledge_all)
        header_layout.addWidget(self.ack_all_btn)

        layout.addLayout(header_layout)

        self.alert_list = QListWidget()
        self.alert_list.itemClicked.connect(self._on_alert_clicked)
        layout.addWidget(self.alert_list)

    def add_alert(self, alert: Dict[str, Any]):
        """Add a new alert to the panel."""
        item = AlertListItem(alert)
        self.alert_list.insertItem(0, item)
        self._update_count()

    def update_alerts(self, alerts: List[Dict[str, Any]]):
        """Replace all alerts with new list."""
        self.alert_list.clear()
        for alert in alerts:
            item = AlertListItem(alert)
            self.alert_list.addItem(item)
        self._update_count()

    def _on_alert_clicked(self, item: QListWidgetItem):
        """Handle alert click."""
        if isinstance(item, AlertListItem):
            mmsi = item.alert_data.get("mmsi", "")
            if mmsi:
                self.alert_clicked.emit(mmsi)

    def _acknowledge_all(self):
        """Acknowledge all visible alerts."""
        for i in range(self.alert_list.count()):
            item = self.alert_list.item(i)
            if isinstance(item, AlertListItem) and item.alert_id:
                self.alert_acknowledged.emit(item.alert_id)
        self.alert_list.clear()
        self._update_count()

    def _update_count(self):
        """Update the alert count badge."""
        count = self.alert_list.count()
        self.alert_count.setText(str(count))
        if count > 0:
            self.alert_count.setStyleSheet(
                "background: #ff3355; color: white; border-radius: 8px; "
                "padding: 2px 6px; font-size: 10px; font-weight: bold;"
            )
        else:
            self.alert_count.setStyleSheet(
                "background: #333355; color: #888; border-radius: 8px; "
                "padding: 2px 6px; font-size: 10px;"
            )

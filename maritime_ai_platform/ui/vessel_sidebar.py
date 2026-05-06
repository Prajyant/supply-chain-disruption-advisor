"""
Vessel sidebar widget with search, filters, and vessel list.
"""

import logging
from typing import List, Dict, Any

from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QListWidget, QListWidgetItem, QPushButton,
    QFrame, QSizePolicy
)
from PyQt5.QtGui import QColor, QFont

logger = logging.getLogger(__name__)


class VesselListItem(QListWidgetItem):
    """Custom list item for vessel display."""

    def __init__(self, vessel: Dict[str, Any]):
        super().__init__()
        self.vessel_data = vessel
        self.mmsi = vessel.get("mmsi", "")

        name = vessel.get("name", "Unknown")
        risk_level = vessel.get("risk_level", "LOW")
        risk_score = vessel.get("risk_score", 0)
        vessel_type = vessel.get("vessel_type", "Unknown")
        speed = vessel.get("speed", 0)

        display_text = f"{name}\n{vessel_type} | {speed:.1f}kts | Risk: {risk_score}"
        self.setText(display_text)

        if risk_level == "HIGH":
            self.setForeground(QColor("#ff3355"))
        elif risk_level == "MEDIUM":
            self.setForeground(QColor("#ff8800"))
        else:
            self.setForeground(QColor("#00ff88"))

        font = QFont("Segoe UI", 10)
        self.setFont(font)
        self.setSizeHint(self.sizeHint())


class VesselSidebar(QWidget):
    """Left sidebar with vessel search, filters, and list."""

    vessel_selected = pyqtSignal(str)
    refresh_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(280)
        self.setMaximumWidth(350)
        self._all_vessels: List[Dict[str, Any]] = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        header = QLabel("VESSEL TRACKER")
        header.setObjectName("title")
        header.setAlignment(Qt.AlignCenter)
        layout.addWidget(header)

        self.vessel_count_label = QLabel("0 vessels tracked")
        self.vessel_count_label.setObjectName("subtitle")
        self.vessel_count_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.vessel_count_label)

        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setStyleSheet("background-color: #333355;")
        layout.addWidget(separator)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search vessels...")
        self.search_input.textChanged.connect(self._apply_filters)
        layout.addWidget(self.search_input)

        filter_layout = QHBoxLayout()

        self.type_filter = QComboBox()
        self.type_filter.addItems(["All Types", "Cargo", "Tanker", "Passenger", "Military", "Fishing", "Other"])
        self.type_filter.currentTextChanged.connect(self._apply_filters)
        filter_layout.addWidget(self.type_filter)

        self.risk_filter = QComboBox()
        self.risk_filter.addItems(["All Risk", "HIGH", "MEDIUM", "LOW"])
        self.risk_filter.currentTextChanged.connect(self._apply_filters)
        filter_layout.addWidget(self.risk_filter)

        layout.addLayout(filter_layout)

        self.region_filter = QComboBox()
        self.region_filter.addItems([
            "All Regions", "Red Sea", "Gulf of Aden", "Strait of Hormuz",
            "Gulf of Guinea", "South China Sea", "Malacca Strait", "Other"
        ])
        self.region_filter.currentTextChanged.connect(self._apply_filters)
        layout.addWidget(self.region_filter)

        self.vessel_list = QListWidget()
        self.vessel_list.itemClicked.connect(self._on_vessel_clicked)
        self.vessel_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.vessel_list)

        btn_layout = QHBoxLayout()
        self.refresh_btn = QPushButton("⟳ Refresh")
        self.refresh_btn.setObjectName("primary")
        self.refresh_btn.clicked.connect(self.refresh_requested.emit)
        btn_layout.addWidget(self.refresh_btn)

        self.clear_btn = QPushButton("Clear Filters")
        self.clear_btn.clicked.connect(self._clear_filters)
        btn_layout.addWidget(self.clear_btn)

        layout.addLayout(btn_layout)

    def update_vessels(self, vessels: List[Dict[str, Any]]):
        """Update the vessel list with new data."""
        self._all_vessels = vessels
        self.vessel_count_label.setText(f"{len(vessels)} vessels tracked")
        self._apply_filters()

    def _apply_filters(self):
        """Apply search and filter criteria to vessel list."""
        search_text = self.search_input.text().lower()
        type_filter = self.type_filter.currentText()
        risk_filter = self.risk_filter.currentText()
        region_filter = self.region_filter.currentText()

        filtered = self._all_vessels

        if search_text:
            filtered = [
                v for v in filtered
                if search_text in v.get("name", "").lower()
                or search_text in v.get("mmsi", "").lower()
                or search_text in v.get("destination", "").lower()
            ]

        if type_filter != "All Types":
            filtered = [v for v in filtered if v.get("vessel_type", "").lower() == type_filter.lower()]

        if risk_filter != "All Risk":
            filtered = [v for v in filtered if v.get("risk_level", "LOW") == risk_filter]

        if region_filter != "All Regions" and region_filter != "Other":
            filtered = self._filter_by_region(filtered, region_filter)

        self.vessel_list.clear()
        for vessel in filtered:
            item = VesselListItem(vessel)
            self.vessel_list.addItem(item)

    def _filter_by_region(self, vessels: List[Dict[str, Any]], region: str) -> List[Dict[str, Any]]:
        """Filter vessels by geographic region."""
        region_bounds = {
            "Red Sea": (12.0, 30.0, 32.0, 44.0),
            "Gulf of Aden": (10.0, 15.0, 43.0, 54.0),
            "Strait of Hormuz": (24.0, 27.5, 54.0, 58.0),
            "Gulf of Guinea": (-5.0, 8.0, -10.0, 12.0),
            "South China Sea": (0.0, 23.0, 100.0, 121.0),
            "Malacca Strait": (-2.0, 8.0, 98.0, 105.0),
        }
        bounds = region_bounds.get(region)
        if not bounds:
            return vessels
        lat_min, lat_max, lon_min, lon_max = bounds
        return [
            v for v in vessels
            if lat_min <= v.get("latitude", 0) <= lat_max
            and lon_min <= v.get("longitude", 0) <= lon_max
        ]

    def _on_vessel_clicked(self, item: QListWidgetItem):
        """Handle vessel selection."""
        if isinstance(item, VesselListItem):
            self.vessel_selected.emit(item.mmsi)

    def _clear_filters(self):
        """Reset all filters."""
        self.search_input.clear()
        self.type_filter.setCurrentIndex(0)
        self.risk_filter.setCurrentIndex(0)
        self.region_filter.setCurrentIndex(0)

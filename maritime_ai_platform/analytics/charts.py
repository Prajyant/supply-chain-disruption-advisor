"""
Matplotlib-based analytics charts for maritime intelligence.
Generates speed history, risk trends, traffic density, and regional heatmaps.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import io

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import numpy as np

logger = logging.getLogger(__name__)

DARK_BG = "#1a1a2e"
DARK_FG = "#e0e0e0"
GRID_COLOR = "#333355"
ACCENT_GREEN = "#00ff88"
ACCENT_ORANGE = "#ff8800"
ACCENT_RED = "#ff3355"
ACCENT_BLUE = "#4488ff"


def apply_dark_style(fig: Figure, ax):
    """Apply dark theme to matplotlib figure."""
    fig.patch.set_facecolor(DARK_BG)
    ax.set_facecolor(DARK_BG)
    ax.tick_params(colors=DARK_FG)
    ax.xaxis.label.set_color(DARK_FG)
    ax.yaxis.label.set_color(DARK_FG)
    ax.title.set_color(DARK_FG)
    ax.spines["bottom"].set_color(GRID_COLOR)
    ax.spines["top"].set_color(GRID_COLOR)
    ax.spines["left"].set_color(GRID_COLOR)
    ax.spines["right"].set_color(GRID_COLOR)
    ax.grid(True, color=GRID_COLOR, alpha=0.3)


class SpeedHistoryChart(FigureCanvas):
    """Vessel speed history over time."""

    def __init__(self, parent=None, width=6, height=3):
        self.fig, self.ax = plt.subplots(figsize=(width, height))
        super().__init__(self.fig)
        self.setParent(parent)
        apply_dark_style(self.fig, self.ax)

    def update_chart(self, data: List[Dict[str, Any]], vessel_name: str = ""):
        self.ax.clear()
        apply_dark_style(self.fig, self.ax)

        if not data:
            self.ax.text(0.5, 0.5, "No speed data available", ha="center", va="center",
                        color=DARK_FG, fontsize=12, transform=self.ax.transAxes)
            self.draw()
            return

        timestamps = []
        speeds = []
        for point in data:
            try:
                ts = datetime.fromisoformat(point["timestamp"])
                timestamps.append(ts)
                speeds.append(float(point.get("speed", 0) or 0))
            except (ValueError, TypeError):
                continue

        if timestamps:
            self.ax.plot(timestamps, speeds, color=ACCENT_BLUE, linewidth=1.5, marker="o",
                        markersize=3, markerfacecolor=ACCENT_GREEN)
            self.ax.fill_between(timestamps, speeds, alpha=0.1, color=ACCENT_BLUE)
            self.ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
            self.ax.set_xlabel("Time (UTC)")
            self.ax.set_ylabel("Speed (knots)")
            self.ax.set_title(f"Speed History - {vessel_name}" if vessel_name else "Speed History")
            self.fig.autofmt_xdate()

        self.fig.tight_layout()
        self.draw()


class RiskTrendChart(FigureCanvas):
    """Vessel risk score trend over time."""

    def __init__(self, parent=None, width=6, height=3):
        self.fig, self.ax = plt.subplots(figsize=(width, height))
        super().__init__(self.fig)
        self.setParent(parent)
        apply_dark_style(self.fig, self.ax)

    def update_chart(self, data: List[Dict[str, Any]], vessel_name: str = ""):
        self.ax.clear()
        apply_dark_style(self.fig, self.ax)

        if not data:
            self.ax.text(0.5, 0.5, "No risk data available", ha="center", va="center",
                        color=DARK_FG, fontsize=12, transform=self.ax.transAxes)
            self.draw()
            return

        timestamps = []
        scores = []
        for point in data:
            try:
                ts = datetime.fromisoformat(point["timestamp"])
                timestamps.append(ts)
                scores.append(int(point.get("risk_score", 0) or 0))
            except (ValueError, TypeError):
                continue

        if timestamps:
            colors = [ACCENT_GREEN if s <= 30 else ACCENT_ORANGE if s <= 70 else ACCENT_RED for s in scores]
            self.ax.scatter(timestamps, scores, c=colors, s=30, zorder=5)
            self.ax.plot(timestamps, scores, color=DARK_FG, linewidth=0.8, alpha=0.5)

            self.ax.axhspan(0, 30, alpha=0.05, color=ACCENT_GREEN)
            self.ax.axhspan(30, 70, alpha=0.05, color=ACCENT_ORANGE)
            self.ax.axhspan(70, 100, alpha=0.05, color=ACCENT_RED)

            self.ax.axhline(y=30, color=ACCENT_GREEN, linestyle="--", alpha=0.3)
            self.ax.axhline(y=70, color=ACCENT_RED, linestyle="--", alpha=0.3)

            self.ax.set_ylim(0, 100)
            self.ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
            self.ax.set_xlabel("Time (UTC)")
            self.ax.set_ylabel("Risk Score")
            self.ax.set_title(f"Risk Trend - {vessel_name}" if vessel_name else "Risk Trend")
            self.fig.autofmt_xdate()

        self.fig.tight_layout()
        self.draw()


class TrafficDensityChart(FigureCanvas):
    """Regional traffic density bar chart."""

    def __init__(self, parent=None, width=6, height=3):
        self.fig, self.ax = plt.subplots(figsize=(width, height))
        super().__init__(self.fig)
        self.setParent(parent)
        apply_dark_style(self.fig, self.ax)

    def update_chart(self, region_counts: Dict[str, int]):
        self.ax.clear()
        apply_dark_style(self.fig, self.ax)

        if not region_counts:
            self.ax.text(0.5, 0.5, "No traffic data available", ha="center", va="center",
                        color=DARK_FG, fontsize=12, transform=self.ax.transAxes)
            self.draw()
            return

        regions = list(region_counts.keys())
        counts = list(region_counts.values())
        colors = [ACCENT_RED if c > 5 else ACCENT_ORANGE if c > 2 else ACCENT_GREEN for c in counts]

        bars = self.ax.barh(regions, counts, color=colors, alpha=0.8)
        self.ax.set_xlabel("Vessel Count")
        self.ax.set_title("Traffic Density by Region")

        for bar, count in zip(bars, counts):
            self.ax.text(bar.get_width() + 0.1, bar.get_y() + bar.get_height() / 2,
                        str(count), va="center", color=DARK_FG, fontsize=9)

        self.fig.tight_layout()
        self.draw()


class RiskDistributionChart(FigureCanvas):
    """Pie chart showing risk level distribution."""

    def __init__(self, parent=None, width=4, height=3):
        self.fig, self.ax = plt.subplots(figsize=(width, height))
        super().__init__(self.fig)
        self.setParent(parent)
        self.fig.patch.set_facecolor(DARK_BG)

    def update_chart(self, vessels: List[Dict[str, Any]]):
        self.ax.clear()
        self.fig.patch.set_facecolor(DARK_BG)
        self.ax.set_facecolor(DARK_BG)

        if not vessels:
            self.ax.text(0.5, 0.5, "No data", ha="center", va="center",
                        color=DARK_FG, fontsize=12, transform=self.ax.transAxes)
            self.draw()
            return

        low = sum(1 for v in vessels if v.get("risk_level") == "LOW")
        medium = sum(1 for v in vessels if v.get("risk_level") == "MEDIUM")
        high = sum(1 for v in vessels if v.get("risk_level") == "HIGH")

        sizes = [low, medium, high]
        labels = [f"LOW ({low})", f"MEDIUM ({medium})", f"HIGH ({high})"]
        colors_list = [ACCENT_GREEN, ACCENT_ORANGE, ACCENT_RED]
        explode = (0, 0, 0.05)

        non_zero = [(s, l, c, e) for s, l, c, e in zip(sizes, labels, colors_list, explode) if s > 0]
        if non_zero:
            sizes, labels, colors_list, explode = zip(*non_zero)
            self.ax.pie(sizes, labels=labels, colors=colors_list, explode=explode,
                       autopct="%1.0f%%", textprops={"color": DARK_FG, "fontsize": 9},
                       startangle=90)
            self.ax.set_title("Risk Distribution", color=DARK_FG)

        self.fig.tight_layout()
        self.draw()

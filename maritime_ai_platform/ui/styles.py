"""
Dark theme stylesheet for the Maritime AI Risk Intelligence Platform.
"""

DARK_STYLESHEET = """
QMainWindow {
    background-color: #0d0d1a;
}

QWidget {
    background-color: #0d0d1a;
    color: #e0e0e0;
    font-family: 'Segoe UI', 'Roboto', sans-serif;
    font-size: 12px;
}

QLabel {
    color: #e0e0e0;
    background: transparent;
}

QLabel#title {
    font-size: 16px;
    font-weight: bold;
    color: #ffffff;
}

QLabel#subtitle {
    font-size: 11px;
    color: #888888;
}

QPushButton {
    background-color: #1a1a2e;
    color: #e0e0e0;
    border: 1px solid #333355;
    border-radius: 4px;
    padding: 6px 14px;
    font-size: 12px;
}

QPushButton:hover {
    background-color: #252545;
    border-color: #4488ff;
}

QPushButton:pressed {
    background-color: #333355;
}

QPushButton#danger {
    background-color: #3d1020;
    border-color: #ff3355;
    color: #ff3355;
}

QPushButton#danger:hover {
    background-color: #5d1030;
}

QPushButton#primary {
    background-color: #1a3355;
    border-color: #4488ff;
    color: #4488ff;
}

QPushButton#primary:hover {
    background-color: #2a4465;
}

QLineEdit {
    background-color: #1a1a2e;
    color: #e0e0e0;
    border: 1px solid #333355;
    border-radius: 4px;
    padding: 6px 10px;
    selection-background-color: #4488ff;
}

QLineEdit:focus {
    border-color: #4488ff;
}

QComboBox {
    background-color: #1a1a2e;
    color: #e0e0e0;
    border: 1px solid #333355;
    border-radius: 4px;
    padding: 5px 10px;
}

QComboBox::drop-down {
    border: none;
    width: 20px;
}

QComboBox QAbstractItemView {
    background-color: #1a1a2e;
    color: #e0e0e0;
    border: 1px solid #333355;
    selection-background-color: #333355;
}

QListWidget {
    background-color: #0d0d1a;
    color: #e0e0e0;
    border: 1px solid #1a1a2e;
    border-radius: 4px;
    outline: none;
}

QListWidget::item {
    padding: 8px 10px;
    border-bottom: 1px solid #1a1a2e;
}

QListWidget::item:selected {
    background-color: #1a2a4a;
    border-left: 3px solid #4488ff;
}

QListWidget::item:hover {
    background-color: #151530;
}

QTabWidget::pane {
    border: 1px solid #333355;
    background-color: #0d0d1a;
    border-radius: 4px;
}

QTabBar::tab {
    background-color: #1a1a2e;
    color: #888888;
    padding: 8px 16px;
    border: 1px solid #333355;
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background-color: #0d0d1a;
    color: #4488ff;
    border-bottom: 2px solid #4488ff;
}

QTabBar::tab:hover {
    color: #e0e0e0;
}

QScrollBar:vertical {
    background-color: #0d0d1a;
    width: 10px;
    border: none;
}

QScrollBar::handle:vertical {
    background-color: #333355;
    border-radius: 5px;
    min-height: 20px;
}

QScrollBar::handle:vertical:hover {
    background-color: #4488ff;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    background-color: #0d0d1a;
    height: 10px;
    border: none;
}

QScrollBar::handle:horizontal {
    background-color: #333355;
    border-radius: 5px;
    min-width: 20px;
}

QStatusBar {
    background-color: #0a0a15;
    color: #888888;
    border-top: 1px solid #1a1a2e;
    font-size: 11px;
}

QSplitter::handle {
    background-color: #1a1a2e;
    width: 2px;
}

QGroupBox {
    border: 1px solid #333355;
    border-radius: 4px;
    margin-top: 10px;
    padding-top: 10px;
    font-weight: bold;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
    color: #4488ff;
}

QTextEdit {
    background-color: #1a1a2e;
    color: #e0e0e0;
    border: 1px solid #333355;
    border-radius: 4px;
    padding: 8px;
}

QProgressBar {
    background-color: #1a1a2e;
    border: 1px solid #333355;
    border-radius: 4px;
    text-align: center;
    color: #e0e0e0;
    height: 16px;
}

QProgressBar::chunk {
    background-color: #4488ff;
    border-radius: 3px;
}

QToolTip {
    background-color: #1a1a2e;
    color: #e0e0e0;
    border: 1px solid #333355;
    padding: 4px;
}
"""

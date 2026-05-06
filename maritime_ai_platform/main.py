"""
Maritime AI Risk Intelligence Platform - Entry Point
====================================================
Real-time maritime vessel tracking and AI risk analysis system.

Features:
- Live AIS vessel tracking with interactive world map
- AI-powered risk analysis via AWS Bedrock (Claude 3.5 Sonnet)
- Danger zone monitoring and alert generation
- Speed anomaly and AIS silence detection
- Comprehensive analytics and charting

Usage:
    python main.py

Environment Variables:
    AWS_ACCESS_KEY_ID       - AWS credentials for Bedrock
    AWS_SECRET_ACCESS_KEY   - AWS credentials for Bedrock
    AWS_REGION              - AWS region (default: us-east-1)
    AIS_API_KEY             - AISHub or MarineTraffic API key
    AIS_PROVIDER            - 'aishub' or 'marinetraffic' (default: aishub)
"""

import sys
import os
import logging
from pathlib import Path
from datetime import datetime

# Ensure the package root is on the path for both direct execution and module execution
_PACKAGE_DIR = Path(__file__).resolve().parent
_PROJECT_DIR = _PACKAGE_DIR.parent
if str(_PACKAGE_DIR) not in sys.path:
    sys.path.insert(0, str(_PACKAGE_DIR))
if str(_PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(_PROJECT_DIR))

from config.settings import load_config, LOGS_DIR


def setup_logging():
    """Configure application logging."""
    log_file = LOGS_DIR / f"maritime_ai_{datetime.now().strftime('%Y%m%d')}.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ]
    )

    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("matplotlib").setLevel(logging.WARNING)


def main():
    """Application entry point."""
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info("Maritime AI Risk Intelligence Platform v1.0.0")
    logger.info("=" * 60)

    config = load_config()

    logger.info(f"AIS Provider: {config.ais.provider}")
    logger.info(f"AIS API Key: {'Configured' if config.ais.api_key else 'Not set (using demo mode)'}")
    logger.info(f"AWS Region: {config.aws.region}")
    logger.info(f"Bedrock Model: {config.aws.bedrock_model_id}")
    logger.info(f"AI Available: {bool(config.aws.access_key_id)}")
    logger.info(f"Poll Interval: {config.ais.poll_interval_seconds}s")
    logger.info(f"Database: {config.database.db_path}")

    try:
        from PyQt5.QtWidgets import QApplication
        from PyQt5.QtCore import Qt
        from PyQt5 import QtWebEngineWidgets  # Must be imported before QApplication
    except ImportError:
        import subprocess
        print("\nERROR: PyQt5 not found. Installing dependencies now...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r",
                              str(Path(__file__).parent / "requirements.txt")])
        from PyQt5.QtWidgets import QApplication
        from PyQt5.QtCore import Qt
        from PyQt5 import QtWebEngineWidgets

    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("Maritime AI Risk Intelligence Platform")
    app.setOrganizationName("MaritimeAI")

    from ui.main_window import MainWindow
    window = MainWindow(config)
    window.show()

    logger.info("Application window displayed - entering event loop")
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

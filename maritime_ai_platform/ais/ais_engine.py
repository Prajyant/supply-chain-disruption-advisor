"""
AIS Data Engine - manages vessel data fetching with threading, caching, and retry logic.
"""

import logging
import time
import threading
from typing import List, Dict, Any, Optional
from datetime import datetime

from PyQt5.QtCore import QObject, pyqtSignal, QThread

from ais.provider_base import AISProviderBase
from ais.aishub_provider import AISHubProvider
from ais.marinetraffic_provider import MarineTrafficProvider
from ais.aisstream_provider import AISStreamProvider
from config.settings import AISConfig
from database.db_manager import DatabaseManager

logger = logging.getLogger(__name__)


class AISDataWorker(QObject):
    """Background worker for fetching AIS data without blocking the UI."""

    vessels_updated = pyqtSignal(list)
    fetch_error = pyqtSignal(str)
    fetch_started = pyqtSignal()
    fetch_completed = pyqtSignal(int)

    def __init__(self, provider: AISProviderBase, db: DatabaseManager, config: AISConfig):
        super().__init__()
        self.provider = provider
        self.db = db
        self.config = config
        self._running = False
        self._stop_event = threading.Event()

    def start_polling(self):
        """Start the polling loop."""
        self._running = True
        self._stop_event.clear()
        self._poll_loop()

    def stop_polling(self):
        """Stop the polling loop."""
        self._running = False
        self._stop_event.set()

    def _poll_loop(self):
        """Main polling loop with retry logic."""
        while self._running and not self._stop_event.is_set():
            self.fetch_started.emit()
            vessels = self._fetch_with_retry()

            if vessels:
                for vessel in vessels:
                    self.db.upsert_vessel(vessel)
                    self.db.add_vessel_history(
                        vessel["mmsi"], vessel["latitude"], vessel["longitude"],
                        vessel["speed"], vessel["course"], vessel["heading"], 0
                    )
                self.vessels_updated.emit(vessels)
                self.fetch_completed.emit(len(vessels))
                logger.info(f"AIS poll complete: {len(vessels)} vessels updated")
            else:
                self.fetch_error.emit("No vessels returned from AIS provider")

            self._stop_event.wait(timeout=self.config.poll_interval_seconds)

    def _fetch_with_retry(self) -> List[Dict[str, Any]]:
        """Fetch vessels with retry logic."""
        for attempt in range(self.config.max_retries):
            try:
                vessels = self.provider.fetch_vessels()
                if vessels:
                    return vessels
                logger.warning(f"AIS fetch attempt {attempt + 1}: empty response")
            except Exception as e:
                logger.error(f"AIS fetch attempt {attempt + 1} failed: {e}")

            if attempt < self.config.max_retries - 1:
                time.sleep(self.config.retry_delay * (attempt + 1))

        return []

    def fetch_once(self):
        """Perform a single fetch (for manual refresh)."""
        self.fetch_started.emit()
        vessels = self._fetch_with_retry()
        if vessels:
            for vessel in vessels:
                self.db.upsert_vessel(vessel)
            self.vessels_updated.emit(vessels)
            self.fetch_completed.emit(len(vessels))
        else:
            self.fetch_error.emit("Manual fetch returned no vessels")


class AISEngine:
    """
    Main AIS engine that manages providers, workers, and data flow.
    """

    def __init__(self, config: AISConfig, db: DatabaseManager):
        self.config = config
        self.db = db
        self.provider: Optional[AISProviderBase] = None
        self.worker: Optional[AISDataWorker] = None
        self.thread: Optional[QThread] = None
        self._init_provider()

    def _init_provider(self):
        """Initialize the configured AIS provider."""
        if self.config.provider == "aisstream":
            self.provider = AISStreamProvider(
                api_key=self.config.api_key,
            )
        elif self.config.provider == "aishub":
            self.provider = AISHubProvider(
                api_key=self.config.api_key,
                base_url=self.config.aishub_url
            )
        elif self.config.provider == "marinetraffic":
            self.provider = MarineTrafficProvider(
                api_key=self.config.api_key,
                base_url=self.config.marinetraffic_url
            )
        else:
            logger.warning(f"Unknown AIS provider: {self.config.provider}, defaulting to aisstream")
            self.provider = AISStreamProvider(
                api_key=self.config.api_key,
            )

        if self.config.api_key:
            logger.info(f"AIS provider initialized: {self.config.provider}")
        else:
            logger.warning("No AIS API key configured - using demo data")

    def start(self) -> AISDataWorker:
        """Start the AIS data polling in a background thread."""
        self.thread = QThread()
        self.worker = AISDataWorker(self.provider, self.db, self.config)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.start_polling)
        self.thread.start()
        logger.info("AIS engine started")
        return self.worker

    def stop(self):
        """Stop the AIS data polling."""
        if self.worker:
            self.worker.stop_polling()
        if self.thread:
            self.thread.quit()
            self.thread.wait(5000)
        logger.info("AIS engine stopped")

    def manual_refresh(self):
        """Trigger a manual data refresh."""
        if self.worker:
            self.worker.fetch_once()

    def get_cached_vessels(self) -> List[Dict[str, Any]]:
        """Get vessels from database cache."""
        return self.db.get_all_vessels()

    def is_provider_available(self) -> bool:
        """Check if the AIS provider is available."""
        if self.provider:
            return self.provider.is_available()
        return False

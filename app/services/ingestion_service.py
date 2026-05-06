"""Ingestion service for loading and processing supply chain data."""
import logging
from typing import Optional

from app.ingestion.loaders import load_supplier_emails, load_news_feed, load_inventory
from app.ingestion.worldmonitor import fetch_realtime_news
from app.ingestion.email_reader import fetch_live_emails
from app.ingestion.tariff_monitor import fetch_tariff_events
from app.ingestion.port_congestion import fetch_port_congestion_events
from app.ingestion.sanctions_monitor import SanctionsMonitor, normalize_sanctions_event
from app.ingestion.supply_hub import fetch_supply_hub_events
from app.retrieval.index import RetrievalIndex
from app.core.config import get_settings

logger = logging.getLogger(__name__)


class IngestionService:
    """Service for ingesting and indexing supply chain data."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.vector_index = None
        return cls._instance

    def __init__(self) -> None:
        pass

    def ingest(
        self,
        supplier_emails_path: str,
        news_feed_path: str,
        inventory_path: str,
        use_realtime_news: bool = False,
        use_live_emails: bool = False,
        use_tariff_data: bool = True,
        use_port_congestion: bool = True,
        use_sanctions_screening: bool = True,
        use_supply_hub: bool = False,
    ) -> dict[str, int | str]:
        """Ingest data from multiple sources and build search index.

        Args:
            supplier_emails_path: Path to supplier emails CSV
            news_feed_path: Path to news feed CSV
            inventory_path: Path to inventory CSV
            use_realtime_news: Whether to fetch real-time news
            use_tariff_data: Whether to fetch tariff intelligence
            use_port_congestion: Whether to fetch port congestion data
            use_sanctions_screening: Whether to run sanctions screening
            use_supply_hub: Whether to fetch Open Supply Hub data

        Returns:
            Dictionary with ingestion statistics
        """
        events = []
        settings = get_settings()

        # --- Supplier emails: controlled by use_live_emails toggle ---
        if use_live_emails and settings.imap_user and settings.imap_pass:
            live_emails = fetch_live_emails(limit=15)
            if live_emails:
                events.extend(live_emails)
                logger.info(f"Loaded {len(live_emails)} live emails from Gmail inbox")
            else:
                logger.warning("Live email fetch returned nothing — falling back to CSV")
                try:
                    csv_emails = load_supplier_emails(supplier_emails_path)
                    events.extend(csv_emails)
                    logger.info(f"Loaded {len(csv_emails)} emails from CSV fallback")
                except FileNotFoundError:
                    logger.warning(f"Supplier emails CSV not found: {supplier_emails_path}")
        else:
            # Use hardcoded CSV (default / testing mode)
            try:
                csv_emails = load_supplier_emails(supplier_emails_path)
                events.extend(csv_emails)
                logger.info(f"Loaded {len(csv_emails)} supplier emails from CSV")
            except FileNotFoundError:
                logger.warning(f"Supplier emails file not found: {supplier_emails_path}")

        if use_realtime_news:
            try:
                news_events = fetch_realtime_news()
                events.extend(news_events)
                logger.info(f"Fetched {len(news_events)} real-time news events")
            except Exception as e:
                logger.error(f"Failed to fetch real-time news: {e}")
                # Fallback to static file
                try:
                    news_events = load_news_feed(news_feed_path)
                    events.extend(news_events)
                    logger.info(f"Loaded {len(news_events)} static news events as fallback")
                except FileNotFoundError:
                    logger.warning(f"News feed file not found: {news_feed_path}")
        else:
            try:
                news_events = load_news_feed(news_feed_path)
                events.extend(news_events)
                logger.info(f"Loaded {len(news_events)} news events")
            except FileNotFoundError:
                logger.warning(f"News feed file not found: {news_feed_path}")

        # Load inventory data
        try:
            inventory_events = load_inventory(inventory_path)
            events.extend(inventory_events)
            logger.info(f"Loaded {len(inventory_events)} inventory events")
        except FileNotFoundError:
            logger.warning(f"Inventory file not found: {inventory_path}")

        # --- Tariff intelligence ---
        if use_tariff_data:
            try:
                tariff_events = fetch_tariff_events(limit=10)
                events.extend(tariff_events)
                logger.info(f"Loaded {len(tariff_events)} tariff intelligence events")
            except Exception as e:
                logger.warning(f"Tariff data fetch failed: {e}")

        # --- Port congestion monitoring ---
        if use_port_congestion:
            try:
                congestion_events = fetch_port_congestion_events(limit=10)
                events.extend(congestion_events)
                logger.info(f"Loaded {len(congestion_events)} port congestion events")
            except Exception as e:
                logger.warning(f"Port congestion fetch failed: {e}")

        # --- Sanctions screening ---
        if use_sanctions_screening:
            try:
                sanctions_monitor = SanctionsMonitor()
                sanctions_monitor.refresh_if_needed()
                logger.info("Sanctions database refreshed")
            except Exception as e:
                logger.warning(f"Sanctions refresh failed: {e}")

        # --- Open Supply Hub (industry graph) ---
        if use_supply_hub:
            try:
                hub_events = fetch_supply_hub_events(limit=10)
                events.extend(hub_events)
                logger.info(f"Loaded {len(hub_events)} supply hub events")
            except Exception as e:
                logger.warning(f"Supply hub fetch failed: {e}")

        # Build vector index
        self.vector_index = RetrievalIndex()
        self.vector_index.build(events)

        return {
            "ingested_events": len(events),
            "indexed_chunks": self.vector_index.chunk_count,
            "events": events,
            "message": f"Real-time data fetched from WorldMonitor API." if use_realtime_news else "Data loaded from CSV files.",
        }

    def get_index(self) -> Optional[RetrievalIndex]:
        """Get the current vector index."""
        return self.vector_index

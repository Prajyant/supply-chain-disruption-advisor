"""Ingestion service for loading and processing supply chain data."""
import logging
from pathlib import Path
from typing import Optional

from app.ingestion.loaders import load_supplier_emails, load_news_feed, load_inventory
from app.ingestion.worldmonitor import fetch_realtime_news
from app.retrieval.index import RetrievalIndex

logger = logging.getLogger(__name__)


class IngestionService:
    """Service for ingesting and indexing supply chain data."""

    def __init__(self) -> None:
        self.vector_index: Optional[RetrievalIndex] = None

    def ingest(
        self,
        supplier_emails_path: str,
        news_feed_path: str,
        inventory_path: str,
        use_realtime_news: bool = False,
    ) -> dict[str, int | str]:
        """Ingest data from multiple sources and build search index.

        Args:
            supplier_emails_path: Path to supplier emails CSV
            news_feed_path: Path to news feed CSV
            inventory_path: Path to inventory CSV
            use_realtime_news: Whether to fetch real-time news

        Returns:
            Dictionary with ingestion statistics
        """
        events = []

        # Load supplier emails
        try:
            email_events = load_supplier_emails(supplier_emails_path)
            events.extend(email_events)
            logger.info(f"Loaded {len(email_events)} supplier emails")
        except FileNotFoundError:
            logger.warning(f"Supplier emails file not found: {supplier_emails_path}")

        # Load news feed (or fetch real-time)
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

        # Build vector index
        self.vector_index = RetrievalIndex()
        self.vector_index.build(events)

        return {
            "ingested_events": len(events),
            "indexed_chunks": self.vector_index.chunk_count,
            "message": f"Real-time data fetched from WorldMonitor API." if use_realtime_news else "Data loaded from CSV files.",
        }

    def get_index(self) -> Optional[RetrievalIndex]:
        """Get the current vector index."""
        return self.vector_index

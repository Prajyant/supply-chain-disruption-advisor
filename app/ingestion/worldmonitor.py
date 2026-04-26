"""Real-time news ingestion for supply chain disruption detection."""
from __future__ import annotations
import logging
import requests
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# Reliable RSS feeds — Google News is the most consistent
SUPPLY_CHAIN_FEEDS = [
    "https://news.google.com/rss/search?q=supply+chain+disruption&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=shipping+port+logistics&hl=en-US&gl=US&ceid=US:en",
    "https://www.supplychaindive.com/feeds/news/",
]

# Global news feeds — weather, geopolitics, trade
GLOBAL_NEWS_FEEDS = [
    "https://news.google.com/rss/search?q=typhoon+OR+earthquake+OR+flood+OR+trade+war+OR+sanctions&hl=en-US&gl=US&ceid=US:en",
    "https://feeds.bbci.co.uk/news/business/rss.xml",
    "https://feeds.bbci.co.uk/news/world/rss.xml",
]


def fetch_rss_feed(feed_url: str) -> list[dict[str, Any]]:
    """Fetch and parse RSS feed items."""
    try:
        import feedparser
        response = requests.get(
            feed_url,
            headers={"User-Agent": "Mozilla/5.0 (SupplyChainAdvisor/1.0)"},
            timeout=15,
        )
        response.raise_for_status()
        feed = feedparser.parse(response.content)
        items = []
        for entry in feed.entries[:15]:
            items.append({
                "title": entry.get("title", ""),
                "link": entry.get("link", ""),
                "published": entry.get("published", ""),
                "summary": entry.get("summary", entry.get("description", "")),
            })
        logger.info(f"RSS feed {feed_url[:60]}... returned {len(items)} items")
        return items
    except Exception as e:
        logger.warning(f"RSS feed failed: {feed_url[:60]}... — {e}")
        return []


def fetch_supply_chain_news(limit: int = 50) -> list[dict[str, Any]]:
    """Fetch real-time supply chain news from RSS feeds."""
    all_items = []
    for feed_url in SUPPLY_CHAIN_FEEDS:
        items = fetch_rss_feed(feed_url)
        all_items.extend(items)
        if len(all_items) >= limit:
            break
    return all_items[:limit]


def fetch_global_disruption_news(limit: int = 50) -> list[dict[str, Any]]:
    """Fetch global news — we send ALL of it to Gemini to decide relevance."""
    all_items = []
    for feed_url in GLOBAL_NEWS_FEEDS:
        items = fetch_rss_feed(feed_url)
        # No keyword filtering! Gemini will decide what's relevant.
        all_items.extend(items)
        if len(all_items) >= limit:
            break
    return all_items[:limit]


def normalize_news_event(item: dict[str, Any], idx: int, source: str) -> dict[str, Any]:
    """Normalize news item to our internal schema."""
    title = item.get("title", "")
    summary = item.get("summary", item.get("description", ""))
    link = item.get("link", "")
    published = item.get("published", "")

    # Build text field with title and summary
    if summary and summary != title:
        text = f"{title}. {summary}"
    else:
        text = title

    return {
        "source": source,
        "reference_id": f"NEWS-{idx}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "supplier": "Global",
        "event_time": published or datetime.now(timezone.utc).isoformat(),
        "text": text,
        "metadata": {
            "link": link,
            "title": title,
            "summary": summary,
            "published": published,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        },
    }


def fetch_realtime_news() -> list[dict[str, Any]]:
    """Fetch real-time news from all sources.

    Returns:
        List of normalized news events
    """
    all_events = []

    # Fetch supply chain news
    supply_chain_items = fetch_supply_chain_news(limit=30)
    for idx, item in enumerate(supply_chain_items):
        all_events.append(normalize_news_event(item, idx, "news_feed"))

    # Fetch global disruption news
    global_items = fetch_global_disruption_news(limit=30)
    for idx, item in enumerate(global_items):
        all_events.append(normalize_news_event(item, idx + len(supply_chain_items), "global_news"))

    logger.info(f"Total real-time news fetched: {len(all_events)} events")
    return all_events

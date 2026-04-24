"""Real-time news ingestion for supply chain disruption detection."""
from __future__ import annotations
import requests
from datetime import datetime, timezone
from typing import Any

# Free RSS feeds for supply chain news (no API key required)
SUPPLY_CHAIN_NEED_FEEDS = [
    "https://www.supplychaindive.com/feeds/news/",
    "https://www.freightwaves.com/feed",
    "https://www.joc.com/rss",
    "https://www.logisticsmgmt.com/rss",
    "https://www.inboundlogistics.com/cms/rss",
]

# Global news feeds with disruption coverage
GLOBAL_NEWS_FEEDS = [
    "https://feeds.reuters.com/reuters/businessNews",
    "https://feeds.bbci.co.uk/news/business/rss.xml",
    "https://www.sciencedaily.com/rss/environment.xml",
]


def fetch_rss_feed(feed_url: str) -> list[dict[str, Any]]:
    """Fetch and parse RSS feed items."""
    try:
        import feedparser
        response = requests.get(feed_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
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
        return items
    except Exception:
        return []


def fetch_supply_chain_news(limit: int = 50) -> list[dict[str, Any]]:
    """Fetch real-time supply chain news from RSS feeds."""
    all_items = []
    for feed_url in SUPPLY_CHAIN_NEED_FEEDS[:3]:  # Limit to 3 feeds for speed
        items = fetch_rss_feed(feed_url)
        all_items.extend(items)
    return all_items[:limit]


def fetch_global_disruption_news(limit: int = 50) -> list[dict[str, Any]]:
    """Fetch global news with disruption coverage (geopolitical, natural disasters)."""
    all_items = []
    for feed_url in GLOBAL_NEWS_FEEDS[:2]:
        items = fetch_rss_feed(feed_url)
        # Filter for disruption-related content
        disruption_keywords = [
            "supply chain", "disruption", "delay", "strike", "port", "shipping",
            "flood", "earthquake", "hurricane", "wildfire", "cyberattack",
            "sanction", "embargo", "tariff", "shortage", "recall", "bankruptcy",
            "factory", "shutdown", "congestion", "logistics", "freight",
        ]
        for item in items:
            text = f"{item.get('title', '')} {item.get('summary', '')}".lower()
            if any(kw in text for kw in disruption_keywords):
                all_items.append(item)
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
    global_items = fetch_global_disruption_news(limit=20)
    for idx, item in enumerate(global_items):
        all_events.append(normalize_news_event(item, idx + len(supply_chain_items), "global_news"))

    return all_events

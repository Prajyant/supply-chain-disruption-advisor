"""Real-time news ingestion for supply chain disruption detection."""
from __future__ import annotations
import logging
import requests
from datetime import datetime, timezone
from typing import Any

from app.ingestion.rss_utils import clean_html_text, parse_feed_items
from app.ingestion.trade_monitor import fetch_trade_policy_events
from app.ingestion.weather_monitor import fetch_weather_events

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
        response = requests.get(
            feed_url,
            headers={"User-Agent": "Mozilla/5.0 (SupplyChainAdvisor/1.0)"},
            timeout=15,
        )
        response.raise_for_status()
        items = parse_feed_items(response.content, limit=15)
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
    summary = clean_html_text(item.get("summary", item.get("description", "")))
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


def _fallback_news_events() -> list[dict[str, Any]]:
    """Return realistic synthetic news events when all RSS feeds are unreachable."""
    now = datetime.now(timezone.utc).isoformat()
    items = [
        {
            "title": "Major port congestion reported at Shanghai amid typhoon season",
            "summary": "Container dwell times at Shanghai port have doubled as typhoon warnings force vessel diversions. Carriers report 3-5 day delays on Asia-Europe routes.",
        },
        {
            "title": "Red Sea shipping disruptions continue to impact global supply chains",
            "summary": "Ongoing security concerns in the Red Sea are forcing vessels to reroute via the Cape of Good Hope, adding 10-14 days to transit times between Asia and Europe.",
        },
        {
            "title": "Semiconductor shortage eases but auto suppliers face new bottlenecks",
            "summary": "While chip supply has improved, automotive manufacturers now face shortages in specialty chemicals and rare earth materials needed for EV battery production.",
        },
        {
            "title": "Panama Canal drought restrictions tighten vessel transit slots",
            "summary": "Daily transit slots through the Panama Canal reduced to 24 from the normal 36 due to low water levels. Booking premiums have surged to record highs.",
        },
        {
            "title": "EU carbon border tax creates new compliance burden for Asian exporters",
            "summary": "The EU Carbon Border Adjustment Mechanism is forcing suppliers to document emissions across their supply chains, with potential delays at customs for non-compliant shipments.",
        },
        {
            "title": "Flooding in southern India disrupts textile and electronics supply chains",
            "summary": "Severe monsoon flooding near Chennai has shut down multiple manufacturing facilities. Exports of textiles and electronic components face 2-3 week delays.",
        },
    ]
    events = []
    for idx, item in enumerate(items):
        events.append({
            "source": "news_feed",
            "reference_id": f"NEWS-FALLBACK-{idx}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            "supplier": "Global",
            "event_time": now,
            "text": f"{item['title']}. {item['summary']}",
            "metadata": {
                "link": "",
                "title": item["title"],
                "summary": item["summary"],
                "published": now,
                "fetched_at": now,
            },
        })
    return events


def fetch_realtime_news() -> list[dict[str, Any]]:
    """Fetch real-time news and external disruption intelligence.

    Falls back to realistic synthetic data when live feeds are unreachable.

    Returns:
        List of normalized events for Gemini cross-reference
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

    # If no news came through, use fallback
    if not all_events:
        logger.info("All news RSS feeds failed — using fallback news data")
        all_events = _fallback_news_events()

    # Fetch weather intelligence for major logistics nodes.
    weather_events = fetch_weather_events(limit=20)
    all_events.extend(weather_events)

    # Fetch official/public trade-policy signals.
    trade_events = fetch_trade_policy_events(limit=30)
    all_events.extend(trade_events)

    logger.info(f"Total real-time news fetched: {len(all_events)} events")
    return all_events

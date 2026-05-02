"""Trade policy and regulatory intelligence feeds."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import requests

from app.ingestion.rss_utils import parse_feed_items

logger = logging.getLogger(__name__)

TRADE_POLICY_FEEDS = [
    "https://www.wto.org/library/rss/latest_news_e.xml",
    "https://news.google.com/rss/search?q=export+ban+OR+tariff+OR+sanctions+OR+customs+delay+OR+trade+restriction&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=UNCTAD+supply+chain+OR+global+trade+logistics&hl=en-US&gl=US&ceid=US:en",
]

TRADE_KEYWORDS = {
    "critical": ["embargo", "export ban", "border closed", "sanctions", "blockade"],
    "high": ["tariff", "trade restriction", "customs delay", "quota", "anti-dumping", "port restriction"],
    "medium": ["trade dispute", "regulation", "compliance", "inspection", "licensing"],
}


def fetch_trade_policy_events(limit: int = 30) -> list[dict[str, Any]]:
    """Fetch trade-policy news and normalize likely supply-chain events."""
    items: list[dict[str, Any]] = []
    for feed_url in TRADE_POLICY_FEEDS:
        items.extend(fetch_trade_feed(feed_url))
        if len(items) >= limit:
            break

    events = []
    for idx, item in enumerate(items[:limit]):
        event = normalize_trade_event(item, idx)
        if event:
            events.append(event)

    logger.info("Fetched %s trade policy intelligence events", len(events))
    return events


def fetch_trade_feed(feed_url: str) -> list[dict[str, Any]]:
    """Fetch one RSS feed for trade-policy intelligence."""
    try:
        response = requests.get(
            feed_url,
            headers={"User-Agent": "Mozilla/5.0 (SupplyChainAdvisor/1.0)"},
            timeout=15,
        )
        response.raise_for_status()
        items = parse_feed_items(response.content, limit=15)
        for item in items:
            item["feed_url"] = feed_url
        return items
    except Exception as exc:
        logger.warning("Trade feed failed: %s - %s", feed_url, exc)
        return []


def normalize_trade_event(item: dict[str, Any], idx: int) -> dict[str, Any] | None:
    """Normalize a trade-policy feed item into the advisor event format."""
    title = str(item.get("title", ""))
    summary = str(item.get("summary", ""))
    text = f"{title}. {summary}" if summary and summary != title else title
    severity = classify_trade_severity(text)

    if severity == "low":
        return None

    return {
        "source": "trade_policy_monitor",
        "reference_id": f"TRADE-{idx}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "supplier": "Global Trade",
        "event_time": item.get("published") or datetime.now(timezone.utc).isoformat(),
        "text": (
            f"{severity.upper()} trade policy signal: {text}. "
            "Potential shipment impact: customs clearance, tariff exposure, sourcing restrictions, or rerouting."
        ),
        "metadata": {
            "title": title,
            "summary": summary,
            "link": item.get("link", ""),
            "published": item.get("published", ""),
            "feed_url": item.get("feed_url", ""),
            "severity": severity,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        },
    }


def classify_trade_severity(text: str) -> str:
    """Classify a trade-policy item using transparent keyword rules."""
    lowered = text.lower()
    for severity, keywords in TRADE_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            return severity
    return "low"

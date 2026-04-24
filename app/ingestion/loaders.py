from pathlib import Path
from typing import Any
import pandas as pd
from app.ingestion.worldmonitor import (
    fetch_supply_chain_news,
    fetch_global_disruption_news,
    normalize_news_event,
)


def _read_csv(path: str) -> pd.DataFrame:
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")
    return pd.read_csv(csv_path)


def load_supplier_emails(path: str) -> list[dict[str, Any]]:
    df = _read_csv(path).fillna("")
    records: list[dict[str, Any]] = []
    for row in df.to_dict(orient="records"):
        records.append(
            {
                "source": "supplier_email",
                "reference_id": str(row.get("email_id", "")),
                "supplier": str(row.get("supplier", "")),
                "event_time": str(row.get("date", "")),
                "text": str(row.get("subject", "")) + ". " + str(row.get("body", "")),
                "metadata": row,
            }
        )
    return records


def load_news_feed(path: str) -> list[dict[str, Any]]:
    df = _read_csv(path).fillna("")
    records: list[dict[str, Any]] = []
    for row in df.to_dict(orient="records"):
        records.append(
            {
                "source": "news_feed",
                "reference_id": str(row.get("news_id", "")),
                "supplier": str(row.get("region", "")),
                "event_time": str(row.get("date", "")),
                "text": str(row.get("headline", "")) + ". " + str(row.get("content", "")),
                "metadata": row,
            }
        )
    return records


def load_inventory(path: str) -> list[dict[str, Any]]:
    df = _read_csv(path).fillna("")
    records: list[dict[str, Any]] = []
    for row in df.to_dict(orient="records"):
        item_name = str(row.get("item", ""))
        days_of_cover = float(row.get("days_of_cover", 0))
        context = (
            f"Inventory status for {item_name}. "
            f"Current stock: {row.get('current_stock', 0)}. "
            f"Reorder point: {row.get('reorder_point', 0)}. "
            f"Days of cover: {days_of_cover}."
        )
        records.append(
            {
                "source": "inventory",
                "reference_id": str(row.get("item_id", "")),
                "supplier": str(row.get("primary_supplier", "")),
                "event_time": str(row.get("date", "")),
                "text": context,
                "metadata": row,
            }
        )
    return records


def load_realtime_news(limit: int = 50) -> list[dict[str, Any]]:
    """Load real-time news from RSS feeds."""
    all_events = []

    # Fetch supply chain specific news
    sc_items = fetch_supply_chain_news(limit=limit // 2)
    for idx, item in enumerate(sc_items):
        all_events.append(normalize_news_event(item, idx, "supply_chain_news"))

    # Fetch global disruption news
    global_items = fetch_global_disruption_news(limit=limit // 2)
    for idx, item in enumerate(global_items):
        all_events.append(normalize_news_event(item, idx + len(sc_items), "global_news"))

    return all_events


def load_all_data(
    supplier_emails_path: str,
    news_feed_path: str,
    inventory_path: str,
    use_realtime_news: bool = True,
) -> list[dict[str, Any]]:
    """Load all disruption data sources.

    Args:
        supplier_emails_path: Path to supplier emails CSV
        news_feed_path: Path to news feed CSV (used if use_realtime_news=False)
        inventory_path: Path to inventory CSV
        use_realtime_news: If True, fetch real-time data from WorldMonitor API
    """
    data = (
        load_supplier_emails(supplier_emails_path)
        + load_inventory(inventory_path)
    )

    if use_realtime_news:
        data.extend(load_realtime_news(limit=50))
    else:
        data.extend(load_news_feed(news_feed_path))

    return data

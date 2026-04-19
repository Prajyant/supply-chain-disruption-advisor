from pathlib import Path
from typing import Any
import pandas as pd


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


def load_all_data(
    supplier_emails_path: str,
    news_feed_path: str,
    inventory_path: str,
) -> list[dict[str, Any]]:
    return (
        load_supplier_emails(supplier_emails_path)
        + load_news_feed(news_feed_path)
        + load_inventory(inventory_path)
    )

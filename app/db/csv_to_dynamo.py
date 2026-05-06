"""Save CSV data to DynamoDB tables.

Simple one-way sync: reads CSVs and writes rows to DynamoDB.
Each CSV row becomes one DynamoDB item.
"""
import csv
import logging
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.db.dynamo_client import (
    get_dynamodb_resource,
    ensure_tables_exist,
    TABLE_SUPPLIER_EMAILS,
    TABLE_NEWS_FEED,
    TABLE_INVENTORY,
    TABLE_SHIPMENT_UPDATES,
    TABLE_UPLOADED_SHIPMENTS,
)

logger = logging.getLogger(__name__)


def _sanitize_value(value: Any) -> Any:
    """Convert Python values to DynamoDB-compatible types.

    DynamoDB doesn't accept float — use Decimal.
    Empty strings are replaced with None (DynamoDB doesn't allow empty string for keys).
    """
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return value if value else None
    return value


def _read_csv_rows(path: str) -> list[dict[str, str]]:
    """Read a CSV file and return list of row dicts."""
    csv_path = Path(path)
    if not csv_path.exists():
        logger.warning(f"CSV not found: {path}")
        return []
    with open(csv_path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _batch_write(table_name: str, items: list[dict[str, Any]]) -> int:
    """Write items to a DynamoDB table using batch_writer.

    Returns number of items written.
    """
    if not items:
        return 0

    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(table_name)
    written = 0

    with table.batch_writer() as batch:
        for item in items:
            # Remove None values (DynamoDB doesn't store them)
            clean_item = {k: v for k, v in item.items() if v is not None}
            if clean_item:
                batch.put_item(Item=clean_item)
                written += 1

    return written


def save_supplier_emails(path: str = "data/supplier_emails.csv") -> int:
    """Save supplier_emails.csv rows to DynamoDB.

    Returns number of items written.
    """
    rows = _read_csv_rows(path)
    items = []
    for row in rows:
        items.append({
            "email_id": row.get("email_id", ""),
            "date": row.get("date", ""),
            "supplier": row.get("supplier", ""),
            "subject": row.get("subject", ""),
            "body": row.get("body", ""),
            "origin_location": row.get("origin_location", ""),
            "eta_days": int(row["eta_days"]) if row.get("eta_days") else 0,
            "material": row.get("material", ""),
        })

    written = _batch_write(TABLE_SUPPLIER_EMAILS, items)
    logger.info(f"Saved {written} supplier emails to DynamoDB")
    return written


def save_news_feed(path: str = "data/news_feed.csv") -> int:
    """Save news_feed.csv rows to DynamoDB.

    Returns number of items written.
    """
    rows = _read_csv_rows(path)
    items = []
    for row in rows:
        items.append({
            "news_id": row.get("news_id", ""),
            "date": row.get("date", ""),
            "region": row.get("region", ""),
            "headline": row.get("headline", ""),
            "content": row.get("content", ""),
        })

    written = _batch_write(TABLE_NEWS_FEED, items)
    logger.info(f"Saved {written} news feed items to DynamoDB")
    return written


def save_inventory(path: str = "data/inventory.csv") -> int:
    """Save inventory.csv rows to DynamoDB.

    Returns number of items written.
    """
    rows = _read_csv_rows(path)
    items = []
    for row in rows:
        items.append({
            "item_id": row.get("item_id", ""),
            "date": row.get("date", ""),
            "item": row.get("item", ""),
            "current_stock": int(row["current_stock"]) if row.get("current_stock") else 0,
            "reorder_point": int(row["reorder_point"]) if row.get("reorder_point") else 0,
            "days_of_cover": Decimal(row["days_of_cover"]) if row.get("days_of_cover") else Decimal("0"),
            "primary_supplier": row.get("primary_supplier", ""),
        })

    written = _batch_write(TABLE_INVENTORY, items)
    logger.info(f"Saved {written} inventory items to DynamoDB")
    return written


def save_shipment_updates(path: str = "data/shipment_updates.csv") -> int:
    """Save shipment_updates.csv rows to DynamoDB.

    Returns number of items written.
    """
    rows = _read_csv_rows(path)
    items = []
    for row in rows:
        items.append({
            "email_id": row.get("email_id", ""),
            "date": row.get("date", ""),
            "supplier": row.get("supplier", ""),
            "subject": row.get("subject", ""),
            "body": row.get("body", ""),
            "origin_location": row.get("origin_location", ""),
            "eta_days": int(row["eta_days"]) if row.get("eta_days") else 0,
            "material": row.get("material", ""),
            "is_update": row.get("is_update", "false").lower() == "true",
        })

    written = _batch_write(TABLE_SHIPMENT_UPDATES, items)
    logger.info(f"Saved {written} shipment updates to DynamoDB")
    return written


def save_all_csvs() -> dict[str, int]:
    """Save all CSV files to DynamoDB.

    Creates tables if they don't exist, then writes all CSV data.

    Returns dict with counts per table.
    """
    logger.info("Ensuring DynamoDB tables exist...")
    ensure_tables_exist()

    results = {
        "supplier_emails": save_supplier_emails(),
        "news_feed": save_news_feed(),
        "inventory": save_inventory(),
        "shipment_updates": save_shipment_updates(),
    }

    total = sum(results.values())
    logger.info(f"All CSVs saved to DynamoDB: {total} total items")
    return results


def save_uploaded_shipments(shipments: list[dict[str, Any]], filename: str = "") -> int:
    """Save user-uploaded shipment CSV data to DynamoDB.

    Called after the /shipments/upload-csv endpoint parses the file.

    Args:
        shipments: List of parsed shipment dicts from the upload endpoint.
        filename: Original filename for reference.

    Returns:
        Number of items written.
    """
    from datetime import datetime, timezone

    ensure_tables_exist()

    uploaded_at = datetime.now(timezone.utc).isoformat()
    items = []

    for shipment in shipments:
        item: dict[str, Any] = {
            "shipment_id": shipment.get("shipment_id", ""),
            "supplier": shipment.get("supplier", "Unknown"),
            "origin": shipment.get("origin", ""),
            "destination": shipment.get("destination", ""),
            "material": shipment.get("material", ""),
            "imo_number": shipment.get("imo_number") or "",
            "mmsi": shipment.get("mmsi") or "",
            "vessel_name": shipment.get("vessel_name") or "",
            "lead_time_days": Decimal(str(shipment.get("lead_time_days", 0))),
            "inventory_days_cover": Decimal(str(shipment.get("inventory_days_cover", 0))),
            "quantity": Decimal(str(shipment.get("quantity", 0))),
            "declared_value_usd": Decimal(str(shipment.get("declared_value_usd", 0))),
            "supplier_delay_count": int(shipment.get("supplier_delay_count", 0)),
            "priority": str(shipment.get("priority", "1")),
            "departure_date": shipment.get("departure_date") or "",
            "eta_date": shipment.get("eta_date") or "",
            "route_nodes": shipment.get("route_nodes", []),
            "uploaded_at": uploaded_at,
            "source_filename": filename,
        }
        items.append(item)

    written = _batch_write(TABLE_UPLOADED_SHIPMENTS, items)
    logger.info(f"Saved {written} uploaded shipments to DynamoDB (file: {filename})")
    return written

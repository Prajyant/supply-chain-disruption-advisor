"""Load data FROM DynamoDB tables — replaces CSV reads.

Each function mirrors the corresponding loader in app/ingestion/loaders.py
but reads from DynamoDB instead of local CSV files.

Falls back gracefully if tables are empty or credentials fail.
"""
import logging
from decimal import Decimal
from typing import Any

from app.db.dynamo_client import (
    get_dynamodb_resource,
    TABLE_SUPPLIER_EMAILS,
    TABLE_NEWS_FEED,
    TABLE_INVENTORY,
    TABLE_SHIPMENT_UPDATES,
    TABLE_UPLOADED_SHIPMENTS,
)

logger = logging.getLogger(__name__)


def _decimal_to_native(obj: Any) -> Any:
    """Convert DynamoDB Decimal types back to int/float for Python."""
    if isinstance(obj, Decimal):
        if obj % 1 == 0:
            return int(obj)
        return float(obj)
    if isinstance(obj, dict):
        return {k: _decimal_to_native(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_decimal_to_native(i) for i in obj]
    return obj


def _scan_table(table_name: str) -> list[dict[str, Any]]:
    """Scan all items from a DynamoDB table.

    Handles pagination for tables with >1MB of data.
    """
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(table_name)

    items: list[dict[str, Any]] = []
    response = table.scan()
    items.extend(response.get("Items", []))

    # Handle pagination
    while "LastEvaluatedKey" in response:
        response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
        items.extend(response.get("Items", []))

    return [_decimal_to_native(item) for item in items]


def load_supplier_emails_from_dynamo() -> list[dict[str, Any]]:
    """Load supplier emails from DynamoDB.

    Returns events in the same format as loaders.load_supplier_emails().
    """
    rows = _scan_table(TABLE_SUPPLIER_EMAILS)
    if not rows:
        return []

    records: list[dict[str, Any]] = []
    for row in rows:
        records.append({
            "source": "supplier_email",
            "reference_id": str(row.get("email_id", "")),
            "supplier": str(row.get("supplier", "")),
            "event_time": str(row.get("date", "")),
            "text": str(row.get("subject", "")) + ". " + str(row.get("body", "")),
            "metadata": row,
        })

    logger.info(f"Loaded {len(records)} supplier emails from DynamoDB")
    return records


def load_news_feed_from_dynamo() -> list[dict[str, Any]]:
    """Load news feed from DynamoDB.

    Returns events in the same format as loaders.load_news_feed().
    """
    rows = _scan_table(TABLE_NEWS_FEED)
    if not rows:
        return []

    records: list[dict[str, Any]] = []
    for row in rows:
        records.append({
            "source": "news_feed",
            "reference_id": str(row.get("news_id", "")),
            "supplier": str(row.get("region", "")),
            "event_time": str(row.get("date", "")),
            "text": str(row.get("headline", "")) + ". " + str(row.get("content", "")),
            "metadata": row,
        })

    logger.info(f"Loaded {len(records)} news feed items from DynamoDB")
    return records


def load_inventory_from_dynamo() -> list[dict[str, Any]]:
    """Load inventory from DynamoDB.

    Returns events in the same format as loaders.load_inventory().
    """
    rows = _scan_table(TABLE_INVENTORY)
    if not rows:
        return []

    records: list[dict[str, Any]] = []
    for row in rows:
        item_name = str(row.get("item", ""))
        days_of_cover = row.get("days_of_cover", 0)
        context = (
            f"Inventory status for {item_name}. "
            f"Current stock: {row.get('current_stock', 0)}. "
            f"Reorder point: {row.get('reorder_point', 0)}. "
            f"Days of cover: {days_of_cover}."
        )
        records.append({
            "source": "inventory",
            "reference_id": str(row.get("item_id", "")),
            "supplier": str(row.get("primary_supplier", "")),
            "event_time": str(row.get("date", "")),
            "text": context,
            "metadata": row,
        })

    logger.info(f"Loaded {len(records)} inventory items from DynamoDB")
    return records


def load_shipment_updates_from_dynamo() -> list[dict[str, Any]]:
    """Load shipment updates from DynamoDB.

    Returns events in the same format as ShipmentTracker.load_shipment_updates_csv().
    """
    rows = _scan_table(TABLE_SHIPMENT_UPDATES)
    if not rows:
        return []

    events: list[dict[str, Any]] = []
    for row in rows:
        events.append({
            "source": "shipment_update",
            "reference_id": row.get("email_id", ""),
            "supplier": row.get("supplier", ""),
            "event_time": row.get("date", ""),
            "text": f"{row.get('subject', '')}. {row.get('body', '')}",
            "metadata": {
                "subject": row.get("subject", ""),
                "sender_name": row.get("supplier", ""),
                "origin_location": row.get("origin_location", ""),
                "eta_days": row.get("eta_days", ""),
                "material": row.get("material", ""),
                "is_update": row.get("is_update", False),
            },
        })

    logger.info(f"Loaded {len(events)} shipment updates from DynamoDB")
    return events


def load_uploaded_shipments_from_dynamo() -> list[dict[str, Any]]:
    """Load previously uploaded shipments from DynamoDB.

    Returns the raw shipment dicts as they were saved during upload.
    """
    rows = _scan_table(TABLE_UPLOADED_SHIPMENTS)
    logger.info(f"Loaded {len(rows)} uploaded shipments from DynamoDB")
    return rows


def is_dynamo_available() -> bool:
    """Check if DynamoDB is reachable and has data.

    Quick check — tries to describe the supplier emails table.
    Returns False if credentials are bad or tables don't exist.
    """
    try:
        dynamodb = get_dynamodb_resource()
        table = dynamodb.Table(TABLE_SUPPLIER_EMAILS)
        table.load()
        return True
    except Exception:
        return False

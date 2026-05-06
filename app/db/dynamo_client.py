"""DynamoDB client and table management.

Provides a singleton DynamoDB resource and table creation utilities.
Tables are created on first use if they don't exist (for local dev / first deploy).
"""
import logging
from functools import lru_cache
from typing import Any

import boto3
from botocore.exceptions import ClientError

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Table names — override via env vars if needed
TABLE_SUPPLIER_EMAILS = "SupplyChain_SupplierEmails"
TABLE_NEWS_FEED = "SupplyChain_NewsFeed"
TABLE_INVENTORY = "SupplyChain_Inventory"
TABLE_SHIPMENT_UPDATES = "SupplyChain_ShipmentUpdates"
TABLE_UPLOADED_SHIPMENTS = "SupplyChain_UploadedShipments"


@lru_cache(maxsize=1)
def get_dynamodb_resource():
    """Get a boto3 DynamoDB resource using app settings.

    Returns a cached resource instance. Uses DynamoDB Local if
    DYNAMODB_ENDPOINT_URL is set (for local development).
    """
    import os

    settings = get_settings()
    endpoint_url = os.getenv("DYNAMODB_ENDPOINT_URL")  # e.g. http://localhost:8000

    kwargs: dict[str, Any] = {
        "region_name": settings.aws_region,
    }

    # Use explicit credentials if provided (otherwise falls back to IAM role / env)
    if settings.aws_access_key_id and settings.aws_secret_access_key:
        kwargs["aws_access_key_id"] = settings.aws_access_key_id
        kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
        if settings.aws_session_token:
            kwargs["aws_session_token"] = settings.aws_session_token

    if endpoint_url:
        kwargs["endpoint_url"] = endpoint_url
        logger.info(f"Using DynamoDB Local at {endpoint_url}")

    return boto3.resource("dynamodb", **kwargs)


def ensure_tables_exist() -> list[str]:
    """Create DynamoDB tables if they don't already exist.

    Returns list of table names that were created (empty if all existed).
    Safe to call multiple times — idempotent.
    """
    dynamodb = get_dynamodb_resource()
    created: list[str] = []

    table_definitions = [
        {
            "TableName": TABLE_SUPPLIER_EMAILS,
            "KeySchema": [
                {"AttributeName": "email_id", "KeyType": "HASH"},
            ],
            "AttributeDefinitions": [
                {"AttributeName": "email_id", "AttributeType": "S"},
                {"AttributeName": "supplier", "AttributeType": "S"},
                {"AttributeName": "date", "AttributeType": "S"},
            ],
            "GlobalSecondaryIndexes": [
                {
                    "IndexName": "supplier-date-index",
                    "KeySchema": [
                        {"AttributeName": "supplier", "KeyType": "HASH"},
                        {"AttributeName": "date", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
            ],
        },
        {
            "TableName": TABLE_NEWS_FEED,
            "KeySchema": [
                {"AttributeName": "news_id", "KeyType": "HASH"},
            ],
            "AttributeDefinitions": [
                {"AttributeName": "news_id", "AttributeType": "S"},
                {"AttributeName": "region", "AttributeType": "S"},
                {"AttributeName": "date", "AttributeType": "S"},
            ],
            "GlobalSecondaryIndexes": [
                {
                    "IndexName": "region-date-index",
                    "KeySchema": [
                        {"AttributeName": "region", "KeyType": "HASH"},
                        {"AttributeName": "date", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
            ],
        },
        {
            "TableName": TABLE_INVENTORY,
            "KeySchema": [
                {"AttributeName": "item_id", "KeyType": "HASH"},
            ],
            "AttributeDefinitions": [
                {"AttributeName": "item_id", "AttributeType": "S"},
                {"AttributeName": "primary_supplier", "AttributeType": "S"},
                {"AttributeName": "date", "AttributeType": "S"},
            ],
            "GlobalSecondaryIndexes": [
                {
                    "IndexName": "supplier-date-index",
                    "KeySchema": [
                        {"AttributeName": "primary_supplier", "KeyType": "HASH"},
                        {"AttributeName": "date", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
            ],
        },
        {
            "TableName": TABLE_SHIPMENT_UPDATES,
            "KeySchema": [
                {"AttributeName": "email_id", "KeyType": "HASH"},
            ],
            "AttributeDefinitions": [
                {"AttributeName": "email_id", "AttributeType": "S"},
                {"AttributeName": "supplier", "AttributeType": "S"},
                {"AttributeName": "date", "AttributeType": "S"},
            ],
            "GlobalSecondaryIndexes": [
                {
                    "IndexName": "supplier-date-index",
                    "KeySchema": [
                        {"AttributeName": "supplier", "KeyType": "HASH"},
                        {"AttributeName": "date", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
            ],
        },
        {
            "TableName": TABLE_UPLOADED_SHIPMENTS,
            "KeySchema": [
                {"AttributeName": "shipment_id", "KeyType": "HASH"},
            ],
            "AttributeDefinitions": [
                {"AttributeName": "shipment_id", "AttributeType": "S"},
                {"AttributeName": "supplier", "AttributeType": "S"},
                {"AttributeName": "uploaded_at", "AttributeType": "S"},
            ],
            "GlobalSecondaryIndexes": [
                {
                    "IndexName": "supplier-uploaded-index",
                    "KeySchema": [
                        {"AttributeName": "supplier", "KeyType": "HASH"},
                        {"AttributeName": "uploaded_at", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
            ],
        },
    ]

    for table_def in table_definitions:
        table_name = table_def["TableName"]
        try:
            table = dynamodb.Table(table_name)
            table.load()  # Raises if table doesn't exist
            logger.info(f"Table {table_name} already exists")
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                logger.info(f"Creating table {table_name}...")
                create_kwargs: dict[str, Any] = {
                    "TableName": table_name,
                    "KeySchema": table_def["KeySchema"],
                    "AttributeDefinitions": table_def["AttributeDefinitions"],
                    "BillingMode": "PAY_PER_REQUEST",
                }
                if table_def.get("GlobalSecondaryIndexes"):
                    create_kwargs["GlobalSecondaryIndexes"] = table_def[
                        "GlobalSecondaryIndexes"
                    ]
                dynamodb.create_table(**create_kwargs)
                # Wait for table to be active
                table = dynamodb.Table(table_name)
                table.wait_until_exists()
                created.append(table_name)
                logger.info(f"Table {table_name} created successfully")
            else:
                logger.error(f"Error checking table {table_name}: {e}")
                raise

    return created

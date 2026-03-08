"""Lambda entry point — routes API Gateway and SQS events."""

from __future__ import annotations

import json
import logging
import sys
import threading
from typing import Any

from src.handlers.api_gateway_handler import APIGatewayHandler
from src.handlers.sqs_handler import SQSHandler
from src.repositories.dynamodb.provider import DynamoDBStorageProvider

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# Singleton storage provider (reused across Lambda invocations)
_storage: DynamoDBStorageProvider | None = None
_storage_lock = threading.Lock()


def _get_storage() -> DynamoDBStorageProvider:
    """Return the singleton storage provider, initialising it on first call."""
    global _storage
    if _storage is None:
        with _storage_lock:
            if _storage is None:
                _storage = DynamoDBStorageProvider()
    return _storage


def handle_event(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    """Main Lambda handler — routes to API Gateway or SQS handler."""
    logger.info("Incoming event type: %s", _detect_event_type(event))

    storage = _get_storage()

    if _is_api_gateway_event(event):
        try:
            return APIGatewayHandler(storage).handle(event)
        except Exception as e:
            logger.exception("Unhandled error in API Gateway handler")
            return {
                "statusCode": 500,
                "body": json.dumps({"error": str(e)}),
            }

    if _is_sqs_event(event):
        return SQSHandler(storage).handle(event)

    raise RuntimeError(f"Unknown event type: {list(event.keys())}")


def _is_api_gateway_event(event: dict) -> bool:  # noqa: NAMING001
    return "httpMethod" in event or "requestContext" in event


def _is_sqs_event(event: dict) -> bool:  # noqa: NAMING001
    records = event.get("Records", [])
    return bool(records) and records[0].get("eventSource") == "aws:sqs"


def _detect_event_type(event: dict) -> str:
    if _is_api_gateway_event(event):
        return f"API Gateway: {event.get('httpMethod')} {event.get('path')}"
    if _is_sqs_event(event):
        return f"SQS: {len(event.get('Records', []))} records"
    return "Unknown"

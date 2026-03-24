"""Lambda entry point for API Gateway events only.

Separated from the unified handler to avoid the SQS worker Lambda's
long-running AI pipeline blocking API Gateway responses (30s hard limit).
"""

from __future__ import annotations

import logging
import sys
import threading
from typing import Any

from src.handlers.api_gateway_handler import APIGatewayHandler
from src.repositories.dynamodb.provider import DynamoDBStorageProvider
from src.utilities.tracing import setup_tracing

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# setup_tracing() MUST run before _get_storage() creates any boto3 resources.
# DynamoDB tracing requires botocore to be patched before the first boto3.resource() call.
setup_tracing()

_storage: DynamoDBStorageProvider | None = None  # Lazy — initialized on first invocation
_storage_lock = threading.Lock()


def _get_storage() -> DynamoDBStorageProvider:
    """Return the singleton storage provider, initialising it on first call."""
    global _storage
    if _storage is None:
        with _storage_lock:
            if _storage is None:
                _storage = DynamoDBStorageProvider()
    return _storage


def handle_api_event(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    """Lambda handler for API Gateway events."""
    logger.info("API event: %s %s", event.get("httpMethod"), event.get("path"))
    storage = _get_storage()
    return APIGatewayHandler(storage).handle(event)

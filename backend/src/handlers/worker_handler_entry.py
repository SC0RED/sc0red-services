"""Lambda entry point for SQS worker events only.

Separated from the unified handler so API Gateway requests are served
by a dedicated Lambda that is never blocked by long-running AI pipeline work.
"""

from __future__ import annotations

import logging
import sys
import threading
from typing import Any

from src.handlers.sqs_handler import SQSHandler
from src.repositories.dynamodb.provider import DynamoDBStorageProvider
from src.utilities.tracing import configure_tracing

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# configure_tracing() MUST run before _get_storage() creates any boto3 resources.
# DynamoDB tracing requires botocore to be patched before the first boto3.resource() call.
configure_tracing()

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


def handle_worker_event(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    """Lambda handler for SQS worker events."""
    logger.info("SQS event: %d records", len(event.get("Records", [])))
    storage = _get_storage()
    return SQSHandler(storage).handle(event)

"""Lambda entry point for the on-demand strategy-map SQS worker.

Separated from the main `worker_handler_entry` so the strategy-map workload
runs on its own Lambda function with its own concurrency, monitoring, and
failure-isolation envelope (per the strategy-map-on-demand spec, decision §2).
"""

from __future__ import annotations

import logging
import sys
import threading
from typing import TYPE_CHECKING, Any

from src.handlers.strategy_map_handler import StrategyMapSQSHandler
from src.pipeline.factories_factory import _initialize_ai_client_factory
from src.repositories.dynamodb.provider import DynamoDBStorageProvider
from src.utilities.tracing import setup_tracing

if TYPE_CHECKING:
    from signalfield_core.services.ai_client_factory import AIClientFactory

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# `setup_tracing()` patches botocore before any boto3.resource() call. Run
# at module import (cold start) before the storage provider initialises.
setup_tracing()

_storage: DynamoDBStorageProvider | None = None
_ai_client_factory: AIClientFactory | None = None
_storage_lock = threading.Lock()
_ai_factory_lock = threading.Lock()


def _get_storage() -> DynamoDBStorageProvider:
    global _storage
    if _storage is None:
        with _storage_lock:
            if _storage is None:
                _storage = DynamoDBStorageProvider()
    return _storage


def _get_ai_client_factory() -> AIClientFactory:
    """Lazily resolve the AI client factory.

    Uses the same initialiser the analysis pipeline uses
    (`_initialize_ai_client_factory`), so the strategy-map worker sees the same
    provider config (OpenAI vs Anthropic, precision, reasoning effort) as the
    in-pipeline path.
    """
    global _ai_client_factory
    if _ai_client_factory is None:
        with _ai_factory_lock:
            if _ai_client_factory is None:
                _ai_client_factory = _initialize_ai_client_factory()
    return _ai_client_factory


def handle_event(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    """Lambda handler — dispatches an SQS event to the strategy-map worker."""
    logger.info("strategy-map worker invoked: %d records", len(event.get("Records", [])))
    handler = StrategyMapSQSHandler(_get_storage(), _get_ai_client_factory())
    return handler.handle(event)

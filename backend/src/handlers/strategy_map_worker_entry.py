"""Lambda entry point for the on-demand strategy-map SQS worker.

Separated from the main `worker_handler_entry` so the strategy-map workload
runs on its own Lambda function with its own concurrency, monitoring, and
failure-isolation envelope (per the strategy-map-on-demand spec, decision §2).
"""

from __future__ import annotations

import faulthandler
import logging
import sys
import threading
from typing import TYPE_CHECKING, Any

# Diagnostic instrumentation for the silent-worker bug surfaced 2026-05-07
# (CloudWatch logs go dark for ~145s between the boto3 credentials log
# and Lambda END, with no checkpoint logs, no per-AI-call logs, no
# error traceback, and no exception). The ``print(..., flush=True)``
# calls below bypass Python's logging entirely and write to stdout
# directly, so even if the root logger is gagged by a runtime quirk
# they show up in CloudWatch. ``faulthandler.enable()`` dumps a
# traceback on SIGSEGV / SIGABRT / SIGFPE / SIGILL / SIGBUS so a
# C-level crash (e.g. inside a native extension) surfaces a stack
# trace instead of silent process death. Both are diagnostic-only and
# will be reverted once the root cause is identified.
print("[STRATEGY-MAP-DEBUG] worker_entry module import begin", flush=True)  # noqa: T201

faulthandler.enable()

from src.handlers.strategy_map_handler import StrategyMapSQSHandler  # noqa: E402
from src.pipeline.factories_factory import _initialize_ai_client_factory  # noqa: E402
from src.repositories.dynamodb.provider import DynamoDBStorageProvider  # noqa: E402
from src.utilities.tracing import setup_tracing  # noqa: E402

if TYPE_CHECKING:
    from signalfield_core.services.ai_client_factory import AIClientFactory

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

print("[STRATEGY-MAP-DEBUG] worker_entry imports done; calling setup_tracing", flush=True)  # noqa: T201

# `setup_tracing()` patches botocore before any boto3.resource() call. Run
# at module import (cold start) before the storage provider initialises.
setup_tracing()

print("[STRATEGY-MAP-DEBUG] setup_tracing returned; module init complete", flush=True)  # noqa: T201

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
    print("[STRATEGY-MAP-DEBUG] handle_event entered", flush=True)  # noqa: T201
    logger.info("strategy-map worker invoked: %d records", len(event.get("Records", [])))
    print("[STRATEGY-MAP-DEBUG] before _get_storage()", flush=True)  # noqa: T201
    storage = _get_storage()
    print("[STRATEGY-MAP-DEBUG] after _get_storage(); before _get_ai_client_factory()", flush=True)  # noqa: T201
    factory = _get_ai_client_factory()
    print(  # noqa: T201
        "[STRATEGY-MAP-DEBUG] after _get_ai_client_factory(); before handler.handle",
        flush=True,
    )
    handler = StrategyMapSQSHandler(storage, factory)
    result = handler.handle(event)
    print("[STRATEGY-MAP-DEBUG] handler.handle returned", flush=True)  # noqa: T201
    return result

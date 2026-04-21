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
from src.utilities.tracing import setup_tracing

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# setup_tracing() MUST run before _get_storage() creates any boto3 resources.
# DynamoDB tracing requires botocore to be patched before the first boto3.resource() call.
setup_tracing()

_storage: DynamoDBStorageProvider | None = None  # Lazy — initialized on first invocation
_storage_lock = threading.Lock()


_TRANSIENT_BOTO_CODES = {
    "ThrottlingException",
    "ProvisionedThroughputExceededException",
    "RequestLimitExceeded",
    "InternalServerError",
    "ServiceUnavailable",
}


def _is_transient_infrastructure_error(error: BaseException) -> bool:
    """Walk the exception chain looking for retryable infrastructure errors.

    Returns True for: botocore throttle/5xx, httpx connection/timeout errors.
    Returns False for everything else (programming errors, unknown exceptions).
    """
    current: BaseException | None = error
    while current is not None:
        # botocore ClientError with a transient error code
        class_name = type(current).__name__
        if class_name == "ClientError":
            error_code = getattr(current, "response", {}).get("Error", {}).get("Code", "")
            if error_code in _TRANSIENT_BOTO_CODES:
                return True

        # httpx connection and timeout errors
        module = type(current).__module__ or ""
        if module.startswith("httpx") and class_name in (
            "ConnectError",
            "ConnectTimeout",
            "ReadTimeout",
            "PoolTimeout",
        ):
            return True

        current = current.__cause__ or current.__context__
        # Prevent infinite loop on self-referencing chains
        if current is error:
            break

    return False


def _get_storage() -> DynamoDBStorageProvider:
    """Return the singleton storage provider, initialising it on first call."""
    global _storage
    if _storage is None:
        with _storage_lock:
            if _storage is None:
                _storage = DynamoDBStorageProvider()
    return _storage


def handle_worker_event(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    """Lambda handler for SQS worker events AND direct Step Function invocations.

    Event shape detection:
    - SQS: {"Records": [...]} → existing SQSHandler path
    - Step Functions: {"source": "step_functions", "url": ..., ...} → direct analysis
    """
    storage = _get_storage()

    if event.get("source") == "step_functions":
        # Direct invocation from Step Functions. Domain errors (EngineError,
        # ValueError, RuntimeError) are recorded on the company and the Lambda
        # returns success — the check_wave poll sees the error field and
        # considers the company resolved. Programming errors PROPAGATE so the
        # Lambda returns a non-200 → Step Functions retries the invocation.
        from signalfield_core.exceptions.base import EngineError

        from src.handlers.factory_manager import FactoryManager
        from src.pipeline.appsync_notifier import notify_progress

        logger.info(
            "Step Functions invocation: %s (%s)",
            event.get("company_name") or event.get("url"),
            event.get("scan_id"),
        )

        request_id = event["request_id"]
        scan_id = event["scan_id"]

        # Identity-at-start write (idempotent on re-dispatch)
        company_repo = storage.create_company_repository()
        company_repo.update(
            request_id,
            {
                "id": request_id,
                "company_name": event.get("company_name", ""),
                "company_url": event["url"],
                "scan_id": scan_id,
                "org_id": event["org_id"],
            },
        )

        factory_manager = FactoryManager(storage)
        try:
            factory_manager.run_company_analysis(
                url=event["url"],
                org_id=event["org_id"],
                user_id=event["user_id"],
                scan_id=scan_id,
                company_name=event.get("company_name", ""),
                request_id=request_id,
            )
        except (EngineError, ValueError, RuntimeError) as error:
            # Domain error — record failure, return success so Step Functions
            # doesn't retry (the company is resolved with an error).
            logger.exception("Pipeline failed for %s (step_functions)", request_id)
            company_repo.update(request_id, {"id": request_id, "error": str(error)})
            notify_progress(
                scan_id=scan_id,
                progress=0,
                label=f"Analysis failed: {error}",
                status="failed",
                company_id=request_id,
            )
            return {"status": "failed", "error": str(error)}
        except Exception as error:
            # Check if the root cause is a transient infrastructure error
            # (DynamoDB throttle, connection reset, etc.) — worth retrying.
            if _is_transient_infrastructure_error(error):
                logger.warning(
                    "Transient error for %s — re-raising for Step Functions retry",
                    request_id,
                )
                raise
            # Permanent/unknown error — record and move on.
            logger.exception("Unexpected error for %s (step_functions)", request_id)
            company_repo.update(request_id, {"id": request_id, "error": str(error)})
            notify_progress(
                scan_id=scan_id,
                progress=0,
                label=f"Analysis failed: {error}",
                status="failed",
                company_id=request_id,
            )
            return {"status": "failed", "error": str(error)}

        notify_progress(
            scan_id=scan_id,
            progress=100,
            label="Analysis complete!",
            status="complete",
            company_id=request_id,
        )
        return {"status": "processed"}

    logger.info("SQS event: %d records", len(event.get("Records", [])))
    return SQSHandler(storage).handle(event)

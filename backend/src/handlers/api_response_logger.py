"""Response logging + correlation-id helper for API Gateway handlers.

Extracted from `api_gateway_handler` so the gateway module stays focused
on routing/dispatch and the logging contract has a single home.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.handlers.api_gateway_handler import LambdaResponse

logger = logging.getLogger(__name__)


def finalize_response(
    response: LambdaResponse,
    *,
    method: str,
    path: str,
    request_id: str,
    start_time: float,
) -> LambdaResponse:
    """Add the correlation-id header to the response and log the request.

    `start_time` is a `time.monotonic()` reading captured at the start of
    request processing.
    """
    duration_ms = int((time.monotonic() - start_time) * 1000)
    status = response.get("statusCode", 0)

    response_headers = response.get("headers") or {}
    response_headers["X-Request-Id"] = request_id
    response["headers"] = response_headers

    logger.info(
        "%s %s → %d (%dms) request_id=%s",
        method,
        path,
        status,
        duration_ms,
        request_id,
    )
    return response

"""Push progress updates to AppSync for real-time client subscriptions."""

from __future__ import annotations

import json
import logging
import os
from urllib.error import URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

_HTTP_OK = 200
# Read at module level — standard for Lambda where env is fixed per cold start.
# In tests, patch these module-level values with @patch.
_APPSYNC_ENDPOINT = os.environ.get("APPSYNC_ENDPOINT", "")
_APPSYNC_API_KEY = os.environ.get("APPSYNC_API_KEY", "")

_MUTATION = """
mutation PublishProgress($input: ScanProgressInput!) {
    publishProgress(input: $input) {
        scanId companyId progress progressLabel status
    }
}
"""


def notify_progress(
    *,
    scan_id: str,
    progress: int,
    label: str,
    status: str = "running",
    company_id: str = "",
) -> None:
    """Push a progress update to AppSync (fire-and-forget).

    Silently returns if AppSync is not configured (local dev, tests).
    On network errors, logs a warning and returns — DynamoDB polling
    is the fallback and always has the canonical progress.
    """
    if not _APPSYNC_ENDPOINT or not _APPSYNC_API_KEY:
        return

    payload = json.dumps(
        {
            "query": _MUTATION,
            "variables": {
                "input": {
                    "scanId": scan_id,
                    "companyId": company_id,
                    "progress": progress,
                    "progressLabel": label,
                    "status": status,
                }
            },
        }
    ).encode()

    request = Request(  # noqa: S310 — URL is from a trusted env var, not user input
        _APPSYNC_ENDPOINT,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "x-api-key": _APPSYNC_API_KEY,
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=5) as response:  # noqa: S310  # nosec B310 — URL is from env var, not user input
            if response.status != _HTTP_OK:
                logger.warning("AppSync notify failed: status=%d", response.status)
    except (URLError, OSError):
        logger.warning("AppSync notify failed for scan=%s", scan_id, exc_info=True)



"""Per-org rate limiting for MCP-initiated scans.

Scans trigger paid AI pipeline runs; an LLM client can loop where a human
would not, so MCP scan tools are capped per organization (the web UI is
deliberately unlimited — human-paced). Fixed UTC windows, with one counter row
per window on the existing single-table:

    pk=RATE_LIMIT#{org_id}  sk=SCAN#HOUR#2026-06-11T14   counter, ttl
    pk=RATE_LIMIT#{org_id}  sk=SCAN#DAY#2026-06-11       counter, ttl

Both windows are consumed in a single DynamoDB transaction (two conditional
``ADD counter 1`` updates) — either both slots are taken or neither is, so
concurrent calls cannot admit past a limit and a refused call can never leak a
slot in the other window. Rows expire via the table's TTL attribute.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from typing import Any

import boto3
from botocore.exceptions import ClientError

HOURLY_SCAN_LIMIT = 5
DAILY_SCAN_LIMIT = 30


class ScanRateLimitedError(Exception):
    """Raised when an org has exhausted a scan window; message is client-ready."""


class ScanRateLimiter:
    """Transactional conditional counters for MCP scan calls, per org per window."""

    def __init__(self, table_name: str, endpoint_url: str | None = None) -> None:
        """Initialize against the single-table (same table as OAuthRepository)."""
        kwargs: dict[str, Any] = {}
        if endpoint_url:
            kwargs["endpoint_url"] = endpoint_url
        # Low-level client: transact_write_items isn't exposed on the resource
        # Table abstraction the other repositories use.
        self._client = boto3.client("dynamodb", **kwargs)  # type: ignore[reportUnknownMemberType]
        self._table_name = table_name

    def check_and_increment(self, org_id: str) -> None:
        """Consume one scan slot in BOTH windows atomically, or raise.

        Raises:
            ScanRateLimitedError: When either window is exhausted. Neither
                counter is incremented in that case (single transaction).
        """
        now = datetime.now(UTC)
        hour_key = f"SCAN#HOUR#{now.strftime('%Y-%m-%dT%H')}"
        day_key = f"SCAN#DAY#{now.strftime('%Y-%m-%d')}"

        transact_items: list[Any] = [
            self._consume_window(org_id, hour_key, HOURLY_SCAN_LIMIT, ttl_seconds=2 * 3600),
            self._consume_window(org_id, day_key, DAILY_SCAN_LIMIT, ttl_seconds=2 * 86400),
        ]
        try:
            self._client.transact_write_items(TransactItems=transact_items)
        except ClientError as error:
            if error.response["Error"]["Code"] != "TransactionCanceledException":  # type: ignore[reportTypedDictNotRequiredAccess]
                raise
            # CancellationReasons align positionally with TransactItems:
            # [0] = hour window, [1] = day window.
            reasons: list[dict[str, Any]] = error.response.get("CancellationReasons", [])  # type: ignore[reportUnknownMemberType]
            next_hour = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
            next_day = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            if _is_condition_failed(reasons, 0):
                raise ScanRateLimitedError(
                    f"Scan rate limit reached: {HOURLY_SCAN_LIMIT} scans/hour per organization. "
                    f"Try again after {next_hour.isoformat()}."
                ) from None
            if _is_condition_failed(reasons, 1):
                raise ScanRateLimitedError(
                    f"Scan rate limit reached: {DAILY_SCAN_LIMIT} scans/day per organization. "
                    f"Try again after {next_day.isoformat()}."
                ) from None
            # Cancelled for another reason (e.g. transaction conflict) — a
            # transient infrastructure condition, not a limit. Propagate.
            raise

    def _consume_window(
        self, org_id: str, window_key: str, limit: int, *, ttl_seconds: int
    ) -> dict[str, Any]:
        """Build the conditional one-slot Update for a window (low-level format)."""
        return {
            "Update": {
                "TableName": self._table_name,
                "Key": {"pk": {"S": f"RATE_LIMIT#{org_id}"}, "sk": {"S": window_key}},
                "UpdateExpression": "ADD #counter :one SET #ttl = if_not_exists(#ttl, :ttl)",
                "ConditionExpression": "attribute_not_exists(#counter) OR #counter < :limit",
                "ExpressionAttributeNames": {"#counter": "counter", "#ttl": "ttl"},
                "ExpressionAttributeValues": {
                    ":one": {"N": "1"},
                    ":limit": {"N": str(limit)},
                    ":ttl": {"N": str(int(time.time()) + ttl_seconds)},
                },
            }
        }


def _is_condition_failed(reasons: list[dict[str, Any]], index: int) -> bool:  # noqa: NAMING001  is_ predicate; checker mis-flags leading-underscore
    return len(reasons) > index and reasons[index].get("Code") == "ConditionalCheckFailed"

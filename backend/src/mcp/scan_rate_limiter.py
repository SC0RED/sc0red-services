"""Per-org rate limiting for MCP-initiated scans.

Scans trigger paid AI pipeline runs; an LLM client can loop where a human
would not, so MCP scan tools are capped per organization (the web UI is
deliberately unlimited — human-paced). Fixed UTC windows, enforced with one
conditional atomic counter write per window on the existing single-table:

    pk=RATE_LIMIT#{org_id}  sk=SCAN#HOUR#2026-06-11T14   counter, ttl
    pk=RATE_LIMIT#{org_id}  sk=SCAN#DAY#2026-06-11       counter, ttl

``ADD counter 1`` guarded by ``counter < limit`` is atomic — concurrent calls
cannot admit past the limit. Rows expire via the table's TTL attribute.
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
    """Conditional atomic counters for MCP scan calls, per org per window."""

    def __init__(self, table_name: str, endpoint_url: str | None = None) -> None:
        """Initialize against the single-table (same pattern as OAuthRepository)."""
        kwargs: dict[str, Any] = {}
        if endpoint_url:
            kwargs["endpoint_url"] = endpoint_url
        self._table = boto3.resource("dynamodb", **kwargs).Table(table_name)  # type: ignore[reportUnknownMemberType]

    def check_and_increment(self, org_id: str) -> None:
        """Consume one scan slot for the org, or raise ``ScanRateLimitedError``.

        The hour window is consumed first (it trips far more often at 5 vs 30);
        if the day window then refuses, the hour slot is handed back so rejected
        attempts never eat the budget a later legitimate call needs.
        """
        now = datetime.now(UTC)
        hour_key = f"SCAN#HOUR#{now.strftime('%Y-%m-%dT%H')}"
        day_key = f"SCAN#DAY#{now.strftime('%Y-%m-%d')}"
        next_hour = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
        next_day = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

        if not self._try_consume(org_id, hour_key, HOURLY_SCAN_LIMIT, ttl_seconds=2 * 3600):
            raise ScanRateLimitedError(
                f"Scan rate limit reached: {HOURLY_SCAN_LIMIT} scans/hour per organization. "
                f"Try again after {next_hour.isoformat()}."
            )
        if not self._try_consume(org_id, day_key, DAILY_SCAN_LIMIT, ttl_seconds=2 * 86400):
            self._release(org_id, hour_key)
            raise ScanRateLimitedError(
                f"Scan rate limit reached: {DAILY_SCAN_LIMIT} scans/day per organization. "
                f"Try again after {next_day.isoformat()}."
            )

    def _try_consume(  # noqa: NAMING001  action verb; bool is success/failure, not a predicate
        self, org_id: str, window_key: str, limit: int, *, ttl_seconds: int
    ) -> bool:
        """Atomically take one slot in the window; False when the window is full."""
        try:
            self._table.update_item(
                Key={"pk": f"RATE_LIMIT#{org_id}", "sk": window_key},
                UpdateExpression="ADD #counter :one SET #ttl = if_not_exists(#ttl, :ttl)",
                ConditionExpression="attribute_not_exists(#counter) OR #counter < :limit",
                ExpressionAttributeNames={"#counter": "counter", "#ttl": "ttl"},
                ExpressionAttributeValues={
                    ":one": 1,
                    ":limit": limit,
                    ":ttl": int(time.time()) + ttl_seconds,
                },
            )
        except ClientError as error:
            if error.response["Error"]["Code"] == "ConditionalCheckFailedException":  # type: ignore[reportTypedDictNotRequiredAccess]
                return False
            raise
        return True

    def _release(self, org_id: str, window_key: str) -> None:
        """Hand back a slot consumed by a call another window then refused."""
        self._table.update_item(
            Key={"pk": f"RATE_LIMIT#{org_id}", "sk": window_key},
            UpdateExpression="ADD #counter :minus_one",
            ExpressionAttributeNames={"#counter": "counter"},
            ExpressionAttributeValues={":minus_one": -1},
        )

"""Tombstone primitives for soft-delete with recovery.

The `soft-delete-recovery` change replaces hard `DELETE` semantics on
analyses, scans, and assessments with a marker-based soft delete:

- A `deleted_at` ISO 8601 string is set on the item when it's deleted
- A `ttl` epoch-seconds attribute is set 90 days into the future so
  DynamoDB TTL evicts the row automatically
- All read paths in the repositories filter out items where
  `deleted_at` is set (or absent — backward-compatible with legacy
  pre-tombstone records)

Centralising the helpers here keeps the field names + TTL window in
one place and makes the soft-delete contract grep-able. Per the
design doc D4, repository read methods filter tombstones by default;
recovery-aware methods opt in via a `_with_deleted` suffix.

See `openspec/changes/soft-delete-recovery/design.md` for the full
design decisions.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

# Field names — single source of truth for grep + refactor.
DELETED_AT_FIELD = "deleted_at"
TTL_FIELD = "ttl"

# 90 days matches the analytics-events log retention pattern. After
# this window DynamoDB TTL hard-evicts the record automatically;
# recovery is not possible past this point.
TOMBSTONE_TTL_DAYS = 90


def is_live(item: dict[str, Any] | None) -> bool:
    """True if the item exists and is not tombstoned.

    Treats "not found" (``None``) and "tombstoned" identically — the
    typical posture for live-traffic reads, where callers want a
    single ``if not is_live(item): return None`` check. Recovery
    paths that need to distinguish the two cases call
    ``get_*_with_deleted`` and inspect ``deleted_at`` directly.
    """
    return item is not None and not item.get(DELETED_AT_FIELD)


def filter_live(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return only items that are not tombstoned.

    Items missing the `deleted_at` field are considered live (covers
    legacy records written before this change shipped — they have no
    `deleted_at` attribute at all, which is fine).
    """
    return [item for item in items if not item.get(DELETED_AT_FIELD)]


def tombstone_attributes(now: datetime | None = None) -> dict[str, Any]:
    """Return the `{deleted_at, ttl}` attribute pair for marking a record deleted.

    `deleted_at`: ISO 8601 string (timezone-aware UTC) for the
    timestamp. Human-readable; sortable lexicographically.

    `ttl`: epoch seconds for `now + TOMBSTONE_TTL_DAYS`. DynamoDB TTL
    expects a numeric epoch value, not an ISO string, so this is a
    paired attribute.

    `now` parameter exists only for tests that want a deterministic
    timestamp; production calls omit it.
    """
    when = now or datetime.now(UTC)
    expires_at = when + timedelta(days=TOMBSTONE_TTL_DAYS)
    return {
        DELETED_AT_FIELD: when.isoformat(),
        TTL_FIELD: int(expires_at.timestamp()),
    }

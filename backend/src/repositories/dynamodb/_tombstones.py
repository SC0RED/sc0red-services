"""Tombstone primitives for soft-delete with recovery.

The `soft-delete-recovery` change replaces hard `DELETE` semantics on
analyses, scans, and assessments with a marker-based soft delete:

- A `deleted_at` ISO 8601 string is set on the item when it's deleted
- A `ttl` epoch-seconds attribute is set 95 days into the future so
  DynamoDB TTL evicts the row automatically. The 5-day buffer over
  the 90-day user-facing recovery window eliminates the same-session
  eviction race in the Phase 2 admin UI — see
  `openspec/changes/recently-deleted-admin-ui/design.md` D9.
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
DELETED_BY_FIELD = "deleted_by"

# Internal TTL window. Set to 5 days longer than the user-facing
# 90-day recovery window so a record at the edge of the UI's 90d
# chip can never be TTL-evicted between the recovery flow's read
# and write within a single user session — eliminates the eviction
# race for the common case (user clicks Restore within a few hours
# of opening the page).
#
# 5 days is enough to cover a Friday-evening tab left open until
# Monday morning. Rare residual race (tab open >5 days) is still
# caught by the `require_exists=True` guard on every restore call
# site — see `_tombstones.tombstone_attributes` and
# `client.remove_attributes`. Belt-and-braces.
#
# Storage cost: ~5.5% over a flat 90-day TTL. Negligible at sc0red Services
# volumes. User-facing copy stays "90 days recoverable" — the 5
# extra days are internal margin only.
TOMBSTONE_TTL_DAYS = 95


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


def tombstone_attributes(
    now: datetime | None = None, actor_id: str | None = None
) -> dict[str, Any]:
    """Return the `{deleted_at, ttl, [deleted_by]}` attribute set for marking a record deleted.

    `deleted_at`: ISO 8601 string (timezone-aware UTC) for the
    timestamp. Human-readable; sortable lexicographically.

    `ttl`: epoch seconds for `now + TOMBSTONE_TTL_DAYS` (95 days).
    DynamoDB TTL expects a numeric epoch value, not an ISO string, so
    this is a paired attribute. The 5-day buffer over the 90-day
    user-facing recovery window is intentional — see the constant's
    comment and `recently-deleted-admin-ui/design.md` D9.

    `deleted_by`: optional actor user_id. Set when the delete was
    initiated by an authenticated user — the Phase 2 admin recovery UI
    surfaces this as "Deleted by Alice" on each row. Omitted (key not
    written) when the deleter is unknown — engineer-assisted recovery
    or scripts that don't carry an actor identity. Read-side fallback
    in `admin_handlers._resolve_actor` renders missing/unknown actors
    as null → "Unknown" in the column.

    `now` parameter exists only for tests that want a deterministic
    timestamp; production calls omit it.
    """
    when = now or datetime.now(UTC)
    expires_at = when + timedelta(days=TOMBSTONE_TTL_DAYS)
    attributes: dict[str, Any] = {
        DELETED_AT_FIELD: when.isoformat(),
        TTL_FIELD: int(expires_at.timestamp()),
    }
    if actor_id:
        attributes[DELETED_BY_FIELD] = actor_id
    return attributes

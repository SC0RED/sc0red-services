"""Tests for the admin handlers — `/api/admin/recently-deleted` and
`/api/admin/restore`.

Covers role gating, org isolation, time-window filtering, mixed
record-type restore dispatch, and the eviction-race translation
from `ConditionalCheckFailedException` → `ttl_expired`.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

from botocore.exceptions import ClientError

from src.handlers.admin_handlers import (
    handle_admin_restore,
    handle_get_recently_deleted,
)
from src.handlers.auth_middleware import AuthContext


def _admin(org_id: str = "org-1") -> AuthContext:
    return AuthContext(user_id="user-admin", org_id=org_id, email="admin@org.com", role="admin")


def _analyst(org_id: str = "org-1") -> AuthContext:
    return AuthContext(
        user_id="user-analyst", org_id=org_id, email="analyst@org.com", role="analyst"
    )


def _make_storage(
    *,
    tombstoned_companies: list[dict[str, Any]] | None = None,
    tombstoned_scans: list[dict[str, Any]] | None = None,
    users: list[dict[str, Any]] | None = None,
    company_lookup: dict[str, dict[str, Any]] | None = None,
    scan_lookup: dict[str, dict[str, Any]] | None = None,
    company_restore_raises: ClientError | None = None,
    scan_restore_raises: ClientError | None = None,
) -> MagicMock:
    """Mock storage provider for admin-handler tests."""
    storage = MagicMock()

    resolved_company_lookup: dict[str, dict[str, Any]] = company_lookup or {}
    resolved_scan_lookup: dict[str, dict[str, Any]] = scan_lookup or {}

    def lookup_company(cid: str) -> dict[str, Any] | None:
        return resolved_company_lookup.get(cid)

    def lookup_scan(sid: str) -> dict[str, Any] | None:
        return resolved_scan_lookup.get(sid)

    company_repo = MagicMock()
    company_repo.find_tombstoned_by_org.return_value = tombstoned_companies or []
    company_repo.get_by_id_with_deleted.side_effect = lookup_company
    if company_restore_raises is not None:
        company_repo.restore.side_effect = company_restore_raises
    storage.create_company_repository.return_value = company_repo

    scan_repo = MagicMock()
    scan_repo.find_tombstoned_by_org.return_value = tombstoned_scans or []
    scan_repo.get_by_id_with_deleted.side_effect = lookup_scan
    if scan_restore_raises is not None:
        scan_repo.restore.side_effect = scan_restore_raises
    storage.create_scan_repository.return_value = scan_repo

    user_repo = MagicMock()
    user_repo.find_by_org.return_value = users or []
    storage.create_user_repository.return_value = user_repo
    return storage


def _body(result: dict[str, Any]) -> dict[str, Any]:
    return json.loads(result["body"])


def _ttl_error() -> ClientError:
    """boto3 ClientError shape that the restore guards translate."""
    return ClientError(
        {"Error": {"Code": "ConditionalCheckFailedException", "Message": "Conditional failed"}},
        "UpdateItem",
    )


# ── handle_get_recently_deleted ──────────────────────────────────────


def test_admin_recently_deleted_lists_org_tombstones() -> None:
    """Both companies and scans are returned, sorted newest-first."""
    storage = _make_storage(
        tombstoned_companies=[
            {
                "id": "c-1",
                "company_name": "Acme Corp",
                "scan_id": "scan-1",
                "deleted_at": "2026-04-20T12:00:00+00:00",
                "deleted_by": "user-1",
            }
        ],
        tombstoned_scans=[
            {
                "id": "scan-2",
                "source_url": "https://otherco.com",
                "deleted_at": "2026-04-25T12:00:00+00:00",
                "deleted_by": "user-1",
            }
        ],
        users=[{"id": "user-1", "name": "Alice", "email": "alice@org.com"}],
    )
    result = handle_get_recently_deleted({}, _admin(), storage)
    assert result["statusCode"] == 200
    body = _body(result)
    # Sort by deletedAt descending — scan (Apr 25) before analysis (Apr 20).
    assert [r["id"] for r in body["records"]] == ["scan-2", "c-1"]
    scan_record, analysis_record = body["records"]
    assert scan_record["type"] == "scan"
    assert scan_record["displayName"] == "https://otherco.com"
    assert scan_record["deletedBy"] == {"id": "user-1", "name": "Alice"}
    assert scan_record["scanId"] is None
    assert scan_record["parentTombstoned"] is False
    assert analysis_record["type"] == "analysis"
    assert analysis_record["displayName"] == "Acme Corp"
    assert analysis_record["scanId"] == "scan-1"
    assert analysis_record["deletedBy"] == {"id": "user-1", "name": "Alice"}


def test_admin_recently_deleted_respects_window() -> None:
    """Window query param flows through to the repo's `window_start`."""
    storage = _make_storage()
    handle_get_recently_deleted(
        {"queryStringParameters": {"window": "7d"}}, _admin(), storage
    )

    # Repo received a window_start ~ now - 7d (within 5s).
    company_call = storage.create_company_repository.return_value.find_tombstoned_by_org.call_args
    scan_call = storage.create_scan_repository.return_value.find_tombstoned_by_org.call_args
    from datetime import UTC, datetime, timedelta

    expected = datetime.now(UTC) - timedelta(days=7)
    for call in (company_call, scan_call):
        assert call.kwargs["window_start"] is not None
        delta = abs((call.kwargs["window_start"] - expected).total_seconds())
        assert delta < 5, f"window_start too far from expected: delta={delta}s"


def test_admin_recently_deleted_default_window_30d() -> None:
    """Missing `?window=` defaults to 30 days."""
    storage = _make_storage()
    handle_get_recently_deleted({}, _admin(), storage)
    from datetime import UTC, datetime, timedelta

    expected = datetime.now(UTC) - timedelta(days=30)
    call = storage.create_company_repository.return_value.find_tombstoned_by_org.call_args
    delta = abs((call.kwargs["window_start"] - expected).total_seconds())
    assert delta < 5


def test_admin_recently_deleted_unknown_window_falls_back_to_default() -> None:
    """A malformed/unknown window value defaults to 30d rather than 400-ing."""
    storage = _make_storage()
    handle_get_recently_deleted(
        {"queryStringParameters": {"window": "bogus"}}, _admin(), storage
    )
    from datetime import UTC, datetime, timedelta

    expected = datetime.now(UTC) - timedelta(days=30)
    call = storage.create_company_repository.return_value.find_tombstoned_by_org.call_args
    delta = abs((call.kwargs["window_start"] - expected).total_seconds())
    assert delta < 5


def test_admin_recently_deleted_clamps_window_to_90d_max() -> None:
    """`?window=90d` is the largest accepted; matches the TTL ceiling."""
    storage = _make_storage()
    handle_get_recently_deleted(
        {"queryStringParameters": {"window": "90d"}}, _admin(), storage
    )
    from datetime import UTC, datetime, timedelta

    expected = datetime.now(UTC) - timedelta(days=90)
    call = storage.create_company_repository.return_value.find_tombstoned_by_org.call_args
    delta = abs((call.kwargs["window_start"] - expected).total_seconds())
    assert delta < 5


def test_admin_recently_deleted_resolves_actor_names() -> None:
    """`deletedBy` carries the user's name when found, else attribution by id."""
    storage = _make_storage(
        tombstoned_companies=[
            {
                "id": "c-known",
                "company_name": "Known",
                "deleted_at": "2026-04-25T12:00:00+00:00",
                "deleted_by": "user-1",
            },
            {
                "id": "c-unknown-actor",
                "company_name": "Unknown Actor",
                "deleted_at": "2026-04-24T12:00:00+00:00",
                "deleted_by": "user-MISSING",
            },
            {
                "id": "c-no-actor",
                "company_name": "No Actor",
                "deleted_at": "2026-04-23T12:00:00+00:00",
                "deleted_by": None,
            },
        ],
        users=[{"id": "user-1", "name": "Alice", "email": "alice@org.com"}],
    )
    body = _body(handle_get_recently_deleted({}, _admin(), storage))
    by_id = {r["id"]: r for r in body["records"]}
    assert by_id["c-known"]["deletedBy"] == {"id": "user-1", "name": "Alice"}
    # Off-boarded user — id surfaces, name falls back to the id so the
    # UI can still attribute the action.
    assert by_id["c-unknown-actor"]["deletedBy"] == {"id": "user-MISSING", "name": "user-MISSING"}
    # Pre-tombstone records (no `deleted_by`) surface as null.
    assert by_id["c-no-actor"]["deletedBy"] is None


def test_admin_recently_deleted_flags_parent_tombstoned() -> None:
    """When an analysis's parent scan is also tombstoned, flag it."""
    storage = _make_storage(
        tombstoned_companies=[
            {
                "id": "c-orphan",
                "company_name": "Orphaned",
                "scan_id": "scan-DEAD",
                "deleted_at": "2026-04-25T12:00:00+00:00",
            },
            {
                "id": "c-standalone",
                "company_name": "Standalone",
                "scan_id": "",
                "deleted_at": "2026-04-25T11:00:00+00:00",
            },
        ],
        tombstoned_scans=[
            {
                "id": "scan-DEAD",
                "source_url": "https://dead.com",
                "deleted_at": "2026-04-25T12:00:00+00:00",
            }
        ],
    )
    body = _body(handle_get_recently_deleted({}, _admin(), storage))
    by_id = {r["id"]: r for r in body["records"]}
    assert by_id["c-orphan"]["parentTombstoned"] is True
    assert by_id["c-standalone"]["parentTombstoned"] is False


def test_admin_recently_deleted_returns_403_for_analyst_role() -> None:
    """Analysts can't see the page or hit the API."""
    storage = _make_storage()
    result = handle_get_recently_deleted({}, _analyst(), storage)
    assert result["statusCode"] == 403
    body = _body(result)
    assert body.get("code") == "FORBIDDEN"
    # Critically, no record reads happened — the gate fires before
    # touching the storage layer.
    storage.create_company_repository.return_value.find_tombstoned_by_org.assert_not_called()
    storage.create_scan_repository.return_value.find_tombstoned_by_org.assert_not_called()


# ── handle_admin_restore ─────────────────────────────────────────────


def test_admin_restore_clears_tombstone_for_analysis() -> None:
    """Single-id restore on a known company calls `company_repo.restore`."""
    storage = _make_storage(
        company_lookup={
            "c-1": {"id": "c-1", "org_id": "org-1", "deleted_at": "2026-04-20T12:00:00+00:00"}
        },
    )
    result = handle_admin_restore(
        {"body": json.dumps({"ids": ["c-1"]})}, _admin(), storage
    )
    assert result["statusCode"] == 200
    body = _body(result)
    assert body == {"restored": ["c-1"], "failed": []}
    storage.create_company_repository.return_value.restore.assert_called_once_with("c-1")


def test_admin_restore_handles_mixed_record_types() -> None:
    """Mixed batch: a company id and a scan id both restore in one call."""
    storage = _make_storage(
        company_lookup={"c-1": {"id": "c-1", "org_id": "org-1"}},
        scan_lookup={"scan-2": {"id": "scan-2", "org_id": "org-1"}},
    )
    result = handle_admin_restore(
        {"body": json.dumps({"ids": ["c-1", "scan-2"]})}, _admin(), storage
    )
    body = _body(result)
    assert sorted(body["restored"]) == ["c-1", "scan-2"]
    assert body["failed"] == []
    storage.create_company_repository.return_value.restore.assert_called_once_with("c-1")
    storage.create_scan_repository.return_value.restore.assert_called_once_with("scan-2")


def test_admin_restore_partial_failure_returns_failed_array() -> None:
    """One id restores, another is unknown — `failed` carries the unknown."""
    storage = _make_storage(
        company_lookup={"c-known": {"id": "c-known", "org_id": "org-1"}},
    )
    result = handle_admin_restore(
        {"body": json.dumps({"ids": ["c-known", "c-missing"]})},
        _admin(),
        storage,
    )
    body = _body(result)
    assert body["restored"] == ["c-known"]
    assert body["failed"] == [{"id": "c-missing", "reason": "not_found"}]


def test_admin_restore_returns_403_for_analyst_role() -> None:
    storage = _make_storage()
    result = handle_admin_restore(
        {"body": json.dumps({"ids": ["c-1"]})}, _analyst(), storage
    )
    assert result["statusCode"] == 403


def test_admin_restore_org_isolation_cross_org_id_surfaces_as_not_found() -> None:
    """An id pointing to another org's record looks identical to missing."""
    storage = _make_storage(
        company_lookup={
            "c-other-org": {"id": "c-other-org", "org_id": "org-OTHER"}
        },
    )
    result = handle_admin_restore(
        {"body": json.dumps({"ids": ["c-other-org"]})}, _admin(), storage
    )
    body = _body(result)
    assert body["restored"] == []
    assert body["failed"] == [{"id": "c-other-org", "reason": "not_found"}]
    # Critically, restore() was never called on the cross-org record.
    storage.create_company_repository.return_value.restore.assert_not_called()


def test_admin_restore_idempotent_on_live_record() -> None:
    """Restoring an already-live record is a no-op success — no 4xx noise."""
    storage = _make_storage(
        company_lookup={
            "c-live": {
                "id": "c-live",
                "org_id": "org-1",
                # No `deleted_at` — record is live. The handler still
                # accepts it; `restore()` is a no-op REMOVE on attrs
                # that aren't there.
            }
        },
    )
    result = handle_admin_restore(
        {"body": json.dumps({"ids": ["c-live"]})}, _admin(), storage
    )
    body = _body(result)
    assert body == {"restored": ["c-live"], "failed": []}


def test_admin_restore_translates_ttl_evicted_to_ttl_expired() -> None:
    """Eviction race: `restore()` raises `ConditionalCheckFailedException`,
    handler translates to `ttl_expired` in the failed array."""
    storage = _make_storage(
        company_lookup={"c-ghost": {"id": "c-ghost", "org_id": "org-1"}},
        company_restore_raises=_ttl_error(),
    )
    result = handle_admin_restore(
        {"body": json.dumps({"ids": ["c-ghost"]})}, _admin(), storage
    )
    body = _body(result)
    assert body["restored"] == []
    assert body["failed"] == [{"id": "c-ghost", "reason": "ttl_expired"}]


def test_admin_restore_rejects_missing_ids() -> None:
    storage = _make_storage()
    result = handle_admin_restore({"body": json.dumps({})}, _admin(), storage)
    assert result["statusCode"] == 400


def test_admin_restore_rejects_empty_id_list() -> None:
    storage = _make_storage()
    result = handle_admin_restore(
        {"body": json.dumps({"ids": []})}, _admin(), storage
    )
    assert result["statusCode"] == 400


def test_admin_restore_rejects_non_string_ids() -> None:
    storage = _make_storage()
    result = handle_admin_restore(
        {"body": json.dumps({"ids": ["c-1", 42, None]})}, _admin(), storage
    )
    assert result["statusCode"] == 400


def test_admin_restore_rejects_invalid_json() -> None:
    storage = _make_storage()
    result = handle_admin_restore({"body": "not-json"}, _admin(), storage)
    assert result["statusCode"] == 400

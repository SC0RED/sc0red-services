"""Admin-only handlers (`/api/admin/*`).

Phase 2 of the soft-delete recovery work — see
`openspec/changes/recently-deleted-admin-ui/proposal.md`.

Two endpoints:

- ``GET /api/admin/recently-deleted?window=24h|7d|30d|90d`` — lists
  tombstoned scans + analyses for the caller's org within the window.
  Default window: 30 days. Max window: 90 days (matches the TTL ceiling).

- ``POST /api/admin/restore`` — body ``{"ids": [...]}`` (mixed scans
  and analyses; the backend infers each id's type). Restores each
  tombstoned record by clearing ``deleted_at`` and ``ttl``.

Both handlers gate on ``authentication.role == "admin"`` and return
403 to analysts. Org isolation is enforced at the record level — an
admin can only see / restore tombstones in their own org.

Frontend lives at `/settings/recently-deleted`. Sidebar entry is
hidden for non-admins.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from botocore.exceptions import ClientError

from src.handlers.api_gateway_handler import (
    FORBIDDEN,
    VALIDATION_ERROR,
    build_error,
    build_json_response,
)

if TYPE_CHECKING:
    from src.handlers.api_gateway_handler import LambdaResponse
    from src.handlers.auth_middleware import AuthContext
    from src.handlers.router import Router
    from src.repositories.dynamodb.provider import DynamoDBStorageProvider

logger = logging.getLogger(__name__)

# Window literal → days. Max window matches the 90-day tombstone TTL
# from `_tombstones.TOMBSTONE_TTL_DAYS`. Anything beyond that is
# guaranteed already TTL-evicted and unrecoverable.
_WINDOW_DAYS: dict[str, int] = {
    "24h": 1,
    "7d": 7,
    "30d": 30,
    "90d": 90,
}
_DEFAULT_WINDOW = "30d"


def _ensure_admin(authentication: AuthContext) -> LambdaResponse | None:
    """Gate the handler on admin role; return a 403 response if not.

    Returning the response (rather than raising) matches the existing
    pattern where handlers return error tuples; the caller threads it
    back to the API Gateway response without unwinding.
    """
    if authentication.role != "admin":
        return build_error("Admin role required", 403, FORBIDDEN)
    return None


def _parse_window(value: str | None) -> int:
    """Resolve the `?window=` query param to a number of days.

    Unknown values fall back to the default rather than 400-ing — the
    UI sources values from a fixed chip set, so a malformed value here
    is almost certainly a stale frontend talking to a newer backend
    (or vice versa). Defaulting is the user-friendly choice.
    """
    if value is None:
        return _WINDOW_DAYS[_DEFAULT_WINDOW]
    return _WINDOW_DAYS.get(value, _WINDOW_DAYS[_DEFAULT_WINDOW])


def handle_get_recently_deleted(
    event: dict[str, Any],
    authentication: AuthContext,
    storage: DynamoDBStorageProvider,
) -> LambdaResponse:
    """Handle GET /api/admin/recently-deleted.

    Returns a flat list of tombstoned scans + companies (analyses) for
    the org, sorted by ``deletedAt`` descending. Each record includes
    enough metadata that the UI can render the list without a follow-up
    request — denormalises the actor name, parent-tombstone status,
    and the type-specific display name at read time.
    """
    if error := _ensure_admin(authentication):
        return error

    query_params: dict[str, Any] = event.get("queryStringParameters") or {}
    window_days = _parse_window(query_params.get("window"))
    window_start = datetime.now(UTC) - timedelta(days=window_days)

    company_repo = storage.create_company_repository()
    scan_repo = storage.create_scan_repository()
    user_repo = storage.create_user_repository()

    tombstoned_companies = company_repo.find_tombstoned_by_org(
        authentication.org_id, window_start=window_start
    )
    tombstoned_scans = scan_repo.find_tombstoned_by_org(
        authentication.org_id, window_start=window_start
    )

    # Build the actor-name lookup once. Users are bounded by org size
    # (handful per org), so the single GSI query is cheap. Skipping the
    # lookup when no records would benefit just makes the handler more
    # branchy without saving real time.
    # Hard `user["id"]` access matches `activity_handlers.py` —
    # `id` is required on every user record per the schema, and a
    # missing one is a data-corruption bug we want to surface, not
    # silently swallow.
    user_by_id: dict[str, dict[str, Any]] = {
        user["id"]: user for user in user_repo.find_by_org(authentication.org_id)
    }

    # Pre-compute the set of tombstoned scan ids so each analysis row
    # can flag `parentTombstoned` in O(1). The cardinality is bounded
    # by the number of tombstoned scans in the window.
    tombstoned_scan_ids = {scan["id"] for scan in tombstoned_scans if scan.get("id")}

    records: list[dict[str, Any]] = []

    for company in tombstoned_companies:
        scan_id = company.get("scan_id", "") or None
        records.append(
            {
                "id": company["id"],
                "type": "analysis",
                "displayName": company.get("company_name", "") or company.get("company_url", ""),
                "scanId": scan_id,
                "deletedAt": company["deleted_at"],
                "deletedBy": _resolve_actor(company.get("deleted_by"), user_by_id),
                "parentTombstoned": bool(scan_id and scan_id in tombstoned_scan_ids),
            }
        )

    records.extend(
        {
            "id": scan["id"],
            "type": "scan",
            "displayName": scan.get("source_url", "") or scan.get("type", "scan"),
            "scanId": None,
            "deletedAt": scan["deleted_at"],
            "deletedBy": _resolve_actor(scan.get("deleted_by"), user_by_id),
            "parentTombstoned": False,
        }
        for scan in tombstoned_scans
    )

    # ISO-8601 strings sort lexically; reverse for newest-first.
    records.sort(key=lambda r: r["deletedAt"], reverse=True)

    logger.info(
        "recently_deleted org_id=%s window_days=%d count=%d",
        authentication.org_id,
        window_days,
        len(records),
    )

    return build_json_response({"records": records})


def _resolve_actor(
    actor_id: str | None, user_by_id: dict[str, dict[str, Any]]
) -> dict[str, str] | None:
    """Look up the actor's display name; return None when no actor id.

    Pre-tombstone records (deleted before `deleted_by` was tracked) and
    deletes initiated outside the user surface (engineer-assisted
    recovery, scripts) won't have an actor id. The frontend renders
    "Unknown actor" for `null`.

    When an actor id is present but no matching user record is in the
    org (off-boarded user, or — pre-fix — a Cognito sub stored on the
    record), surface the id with `name = "Unknown"`. Pre-fix this path
    rendered the raw id as the name, leaking a UUID into the UI. See
    `openspec/changes/fix-actor-attribution/` D3.
    """
    if not actor_id:
        return None
    user = user_by_id.get(actor_id)
    if not user:
        return {"id": actor_id, "name": "Unknown"}
    return {"id": actor_id, "name": user.get("name", "") or user.get("email", "") or "Unknown"}


def handle_admin_restore(
    event: dict[str, Any],
    authentication: AuthContext,
    storage: DynamoDBStorageProvider,
) -> LambdaResponse:
    """Handle POST /api/admin/restore.

    Body: ``{"ids": [...]}`` (mixed scans + analyses). For each id we
    try the company repo first, then the scan repo — whichever returns
    a record (live or tombstoned) determines the type. Org isolation
    is enforced at the record level: a record from a different org
    surfaces as ``not_found`` (same opacity as a missing record).

    Restoring an already-live record is a no-op (idempotent) — we
    short-circuit with a `restored` outcome so the UI's flow remains
    "Restore N → success" without 4xx noise on retries.
    """
    if error := _ensure_admin(authentication):
        return error

    raw_body = event.get("body") or "{}"
    try:
        parsed: Any = json.loads(raw_body)
    except json.JSONDecodeError as error:
        return build_error(f"Invalid JSON: {error}", 400, VALIDATION_ERROR)
    if not isinstance(parsed, dict):
        return build_error("Body must be a JSON object", 400, VALIDATION_ERROR)

    raw_ids = parsed.get("ids")
    if not isinstance(raw_ids, list) or not all(isinstance(item, str) for item in raw_ids):
        return build_error("Body must include `ids: string[]`", 400, VALIDATION_ERROR)
    if not raw_ids:
        return build_error("`ids` must not be empty", 400, VALIDATION_ERROR)
    ids: list[str] = list(raw_ids)

    company_repo = storage.create_company_repository()
    scan_repo = storage.create_scan_repository()

    restored: list[str] = []
    failed: list[dict[str, str]] = []

    for record_id in ids:
        # Try the company first (analyses are the more common case),
        # then fall back to the scan repo. Both reads use the recovery-
        # aware variant so tombstoned records are visible.
        company = company_repo.get_by_id_with_deleted(record_id)
        if company and company.get("org_id") == authentication.org_id:
            outcome = _attempt_restore(company_repo, record_id, kind="analysis")
        else:
            scan = scan_repo.get_by_id_with_deleted(record_id)
            if scan and scan.get("org_id") == authentication.org_id:
                outcome = _attempt_restore(scan_repo, record_id, kind="scan")
            else:
                # Neither repo returned a record we own. "not_found"
                # covers missing records, cross-org records, and ids of
                # types we haven't extended this endpoint to (e.g.
                # assessments). Same opacity posture as `check_org_access`.
                outcome = "not_found"

        if outcome == "restored":
            restored.append(record_id)
        else:
            failed.append({"id": record_id, "reason": outcome})

    logger.info(
        "admin_restore org_id=%s requested=%d restored=%d failed=%d",
        authentication.org_id,
        len(ids),
        len(restored),
        len(failed),
    )

    return build_json_response({"restored": restored, "failed": failed})


def _attempt_restore(repo: Any, record_id: str, *, kind: str) -> str:
    """Call ``repo.restore(record_id)`` and translate eviction-race failures.

    Phase 1 added ``require_exists=True`` on every restore call site so
    a TTL-evicted row surfaces as ``ConditionalCheckFailedException``
    instead of silently writing an empty shell. Re-translating that
    here keeps the boto3 error shape from leaking past the handler;
    callers see a clean ``ttl_expired`` outcome string.
    """
    try:
        repo.restore(record_id)
    except ClientError as error:
        code = error.response.get("Error", {}).get("Code", "")
        if code == "ConditionalCheckFailedException":
            logger.info(
                "admin_restore ttl_expired record_id=%s kind=%s",
                record_id,
                kind,
            )
            return "ttl_expired"
        raise
    return "restored"


def register_routes(router: Router, storage: DynamoDBStorageProvider) -> None:
    """Wire `/api/admin/*` onto the gateway router.

    Co-locating route registration with the handlers keeps the gateway
    module under the 400-line limit and means future admin routes don't
    require a gateway edit.
    """
    router.protected(
        "GET",
        "/api/admin/recently-deleted",
        lambda event, authentication: handle_get_recently_deleted(event, authentication, storage),
    )
    router.protected(
        "POST",
        "/api/admin/restore",
        lambda event, authentication: handle_admin_restore(event, authentication, storage),
    )

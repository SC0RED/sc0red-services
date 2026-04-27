"""Activity-feed handler — projects org-level events from existing DynamoDB records.

This is `webapp-ux-foundations-tier2` §5. The endpoint surfaces a feed of
"what's happening across my org" for the in-app activity panel — Bob ran a
scan, Alice's analysis completed, Charlie was invited, etc.

Design choice: **read-time projection, no persistent events table** (per the
spec's D6 decision). At today's volumes — handful of design-partner orgs,
thousands of records per org max — projecting on-demand from the existing
operational records is well under the 500ms p95 budget. Once projection
becomes too slow, we add an events table and a write-side projection. For
now, the implementation is intentionally simple.

What can be projected:
    - **scan_started** — from each scan record's `created_at`
    - **analysis_completed** — from each company record where `analyzed_at`
      is non-null
    - **member_invited** — from each invitation record's `created_at`
    - **member_joined** — from each user record's `created_at`

What CANNOT be projected (no source-of-truth timestamp on existing records):
    - **scan_completed** — scans don't store a `completed_at` field; the
      status flips from "running" → "complete" but the time isn't recorded.
    - **scan_failed / analysis_failed** — same gap; failures are recorded
      but not timestamped distinctly from creation.
    - **deletes** — DynamoDB doesn't keep tombstones. Projecting deletes
      would require either an audit-log-on-write or a separate events
      table — both deferred.

The omitted event types are tracked for the future events-table iteration.

Output shape (per `tasks.md` §5.2):
    {
        "id": str,           # deterministic per event ("scan_started:{id}")
        "type": str,         # one of the four event-type literals above
        "actor": {"id": str, "name": str},   # who triggered the event
        "target": {"id": str, "name": str, "type": str},  # what was acted on
        "timestamp": str,    # ISO 8601, used by the UI for relative-time
        "summary": str,      # human-readable one-liner for screen readers
    }

Hard-cap: 100 events per response. The UI does not paginate beyond that
in v1; older events fall off the feed. When the events-table migration
lands, swap this to real cursor pagination.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Literal

from src.handlers.api_gateway_handler import build_json_response

if TYPE_CHECKING:
    from src.handlers.api_gateway_handler import LambdaResponse
    from src.handlers.auth_middleware import AuthContext
    from src.repositories.dynamodb.provider import DynamoDBStorageProvider

logger = logging.getLogger(__name__)

# Cap matches the design.md risk-mitigation note: "Add a hard limit (last
# 100 events shown)". Smaller values are fine for the UI; a higher value
# would balloon projection cost linearly with org size.
_MAX_EVENTS = 100

EventType = Literal[
    "scan_started",
    "analysis_completed",
    "member_invited",
    "member_joined",
]


def handle_get_activity(
    _event: dict[str, Any],
    authentication: AuthContext,
    storage: DynamoDBStorageProvider,
) -> LambdaResponse:
    """Handle GET /api/activity — return up to 100 recent org-scoped events."""
    org_id = authentication.org_id

    scan_repo = storage.create_scan_repository()
    company_repo = storage.create_company_repository()
    user_repo = storage.create_user_repository()
    invitation_repo = storage.create_invitation_repository()

    # Fetch all org-scoped records once. Each repository already filters by
    # org via GSI. The user list doubles as the actor-id → name lookup
    # below, so we always materialise it.
    #
    # KNOWN v1 LIMIT: `find_by_org` is page-capped at `_MAX_EVENTS=100` and
    # we discard the cursor. Orgs with >100 companies will silently miss
    # `analysis_completed` events for any company beyond the first GSI
    # page. Acceptable today (no design partner has approached this); the
    # fix lands when we move to a real events table and stop projecting
    # at read time. See architecture-review §5 finding #4.
    scans = scan_repo.find_recent_by_org(org_id, limit=_MAX_EVENTS)
    companies, _company_cursor = company_repo.find_by_org(org_id, limit=_MAX_EVENTS)
    users = user_repo.find_by_org(org_id)
    invitations = invitation_repo.find_by_org(org_id)

    # Observability: when an org maxes out the company page, recent
    # `analysis_completed` events for companies beyond the page boundary
    # are silently absent. A Logs Insights query on this field flags
    # affected orgs before users notice. (Architecture-review §5
    # finding #2 — fix at events-table migration time.)
    if len(companies) >= _MAX_EVENTS:
        logger.warning(
            "activity_feed.company_page_capped org_id=%s limit=%d "
            "— analysis_completed events for companies beyond the GSI page "
            "boundary are not projected; consider events-table migration",
            org_id,
            _MAX_EVENTS,
        )

    actor_names = {user["id"]: user.get("name") or user.get("email", "") for user in users}

    events: list[dict[str, Any]] = []
    for scan in scans:
        event = _project_scan_started(scan, actor_names)
        if event is not None:
            events.append(event)
    for company in companies:
        event = _project_analysis_completed(company, actor_names)
        if event is not None:
            events.append(event)
    for invitation in invitations:
        event = _project_member_invited(invitation, actor_names)
        if event is not None:
            events.append(event)
    for user in users:
        event = _project_member_joined(user)
        if event is not None:
            events.append(event)

    # Sort newest-first then truncate. Records without a timestamp sort to
    # the bottom (rare; happens for legacy users created before
    # `created_at` was added in §5).
    events.sort(key=lambda e: e["timestamp"], reverse=True)
    truncated = events[:_MAX_EVENTS]

    return build_json_response({"events": truncated})


def _project_scan_started(
    scan: dict[str, Any],
    actor_names: dict[str, str],
) -> dict[str, Any] | None:
    """Project a scan record into a `scan_started` event, or skip if malformed."""
    timestamp = scan.get("created_at") or ""
    if not timestamp:
        return None
    scan_id = scan.get("id", "")
    actor_id = scan.get("created_by", "")
    actor_name = actor_names.get(actor_id, "") or "Someone"
    target_name = scan.get("source_url") or "a scan"
    target_type = scan.get("type") or "scan"
    return {
        "id": f"scan_started:{scan_id}",
        "type": "scan_started",
        "actor": {"id": actor_id, "name": actor_name},
        "target": {"id": scan_id, "name": target_name, "type": "scan"},
        "timestamp": timestamp,
        "summary": f"{actor_name} started a {target_type} scan",
    }


def _project_analysis_completed(
    company: dict[str, Any],
    actor_names: dict[str, str],
) -> dict[str, Any] | None:
    """Project a company record into an `analysis_completed` event.

    Only fires when `analyzed_at` is present — pending or in-flight analyses
    are skipped (their event is "scan started", not "analysis completed").
    """
    analyzed_at = company.get("analyzed_at")
    if not analyzed_at:
        return None
    company_id = company.get("id", "")
    company_name = company.get("company_name") or company.get("name") or "an analysis"
    # Companies don't carry an `actor` — the analysis runs server-side.
    # Use the scan creator as a proxy if we can; otherwise fall back to a
    # neutral label so consumers never see an empty `actor.name` (the
    # server-side attribution case). Matches the fallback shape used by
    # `scan_started` ("Someone") and `member_invited` ("An admin").
    actor_id = company.get("created_by", "")
    resolved_name = actor_names.get(actor_id, "") if actor_id else ""
    actor_name = resolved_name or "An analyst"
    return {
        "id": f"analysis_completed:{company_id}",
        "type": "analysis_completed",
        "actor": {"id": actor_id, "name": actor_name},
        "target": {"id": company_id, "name": company_name, "type": "analysis"},
        "timestamp": analyzed_at,
        "summary": f"Analysis completed for {company_name}",
    }


def _project_member_invited(
    invitation: dict[str, Any],
    actor_names: dict[str, str],
) -> dict[str, Any] | None:
    """Project an invitation record into a `member_invited` event."""
    timestamp = invitation.get("created_at") or ""
    if not timestamp:
        return None
    invite_id = invitation.get("id", "")
    actor_id = invitation.get("invited_by", "")
    actor_name = actor_names.get(actor_id, "") or "An admin"
    invitee_email = invitation.get("email", "someone")
    return {
        "id": f"member_invited:{invite_id}",
        "type": "member_invited",
        "actor": {"id": actor_id, "name": actor_name},
        "target": {"id": invite_id, "name": invitee_email, "type": "invitation"},
        "timestamp": timestamp,
        "summary": f"{actor_name} invited {invitee_email}",
    }


def _project_member_joined(user: dict[str, Any]) -> dict[str, Any] | None:
    """Project a user record into a `member_joined` event.

    Skips users without `created_at` (legacy users created before the
    field was added). For new signups the field is always present.
    """
    timestamp = user.get("created_at") or ""
    if not timestamp:
        return None
    # `id` is required on every user record (the actor_names dict-build
    # at the call site uses `user["id"]` and would already have raised
    # for a missing id). Hard access here matches and keeps the failure
    # mode loud — a user record without an id is a schema violation,
    # not a legacy gap to silently absorb.
    user_id = user["id"]
    name = user.get("name") or user.get("email") or "A new member"
    return {
        "id": f"member_joined:{user_id}",
        "type": "member_joined",
        # The user IS both actor and target here.
        "actor": {"id": user_id, "name": name},
        "target": {"id": user_id, "name": name, "type": "user"},
        "timestamp": timestamp,
        "summary": f"{name} joined the team",
    }

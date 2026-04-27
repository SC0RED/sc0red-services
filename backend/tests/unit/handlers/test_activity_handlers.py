"""Tests for the activity-feed handler.

Covers projection from each of the four event sources, org isolation,
the 100-event hard cap, the newest-first sort, and graceful handling
of records with missing timestamps.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

from src.handlers.activity_handlers import handle_get_activity
from src.handlers.auth_middleware import AuthContext


def _auth(user_id: str = "user-1", org_id: str = "org-1") -> AuthContext:
    return AuthContext(user_id=user_id, org_id=org_id, email="a@b.com", role="analyst")


def _make_storage(
    *,
    scans: list[dict[str, Any]] | None = None,
    companies: list[dict[str, Any]] | None = None,
    users: list[dict[str, Any]] | None = None,
    invitations: list[dict[str, Any]] | None = None,
) -> MagicMock:
    """Build a MagicMock storage provider whose repositories return the given lists."""
    storage = MagicMock()
    scan_repo = MagicMock()
    scan_repo.find_recent_by_org.return_value = scans or []
    storage.create_scan_repository.return_value = scan_repo

    company_repo = MagicMock()
    company_repo.find_by_org.return_value = (companies or [], None)
    storage.create_company_repository.return_value = company_repo

    user_repo = MagicMock()
    user_repo.find_by_org.return_value = users or []
    storage.create_user_repository.return_value = user_repo

    invitation_repo = MagicMock()
    invitation_repo.find_by_org.return_value = invitations or []
    storage.create_invitation_repository.return_value = invitation_repo
    return storage


def _body(result: dict[str, Any]) -> dict[str, Any]:
    return json.loads(result["body"])


# ── projection tests ──────────────────────────────────────────────────


def test_returns_empty_events_when_org_has_no_records() -> None:
    storage = _make_storage()
    result = handle_get_activity({}, _auth(), storage)
    assert result["statusCode"] == 200
    assert _body(result) == {"events": []}


def test_projects_scan_started_from_scan_record() -> None:
    storage = _make_storage(
        scans=[
            {
                "id": "scan-1",
                "created_by": "user-1",
                "created_at": "2026-04-26T12:00:00Z",
                "type": "portfolio",
                "source_url": "https://acme.com",
            }
        ],
        users=[{"id": "user-1", "name": "Alice", "email": "alice@org.com"}],
    )
    body = _body(handle_get_activity({}, _auth(), storage))
    assert len(body["events"]) == 1
    event = body["events"][0]
    assert event["type"] == "scan_started"
    assert event["actor"] == {"id": "user-1", "name": "Alice"}
    assert event["target"] == {"id": "scan-1", "name": "https://acme.com", "type": "scan"}
    assert event["timestamp"] == "2026-04-26T12:00:00Z"
    assert "Alice started a portfolio scan" == event["summary"]
    assert event["id"] == "scan_started:scan-1"


def test_projects_analysis_completed_only_when_analyzed_at_set() -> None:
    storage = _make_storage(
        companies=[
            {
                "id": "company-1",
                "company_name": "Acme Corp",
                "analyzed_at": "2026-04-26T13:00:00Z",
            },
            {
                "id": "company-2",
                "company_name": "Beta Inc",
                # No analyzed_at — pending or in-flight, must be skipped.
            },
        ],
    )
    body = _body(handle_get_activity({}, _auth(), storage))
    types = [event["type"] for event in body["events"]]
    assert types == ["analysis_completed"]
    event = body["events"][0]
    assert event["target"]["name"] == "Acme Corp"
    assert event["summary"] == "Analysis completed for Acme Corp"


def test_projects_member_invited_with_inviter_name() -> None:
    storage = _make_storage(
        invitations=[
            {
                "id": "inv-1",
                "email": "newhire@org.com",
                "invited_by": "user-1",
                "created_at": "2026-04-26T14:00:00Z",
            }
        ],
        users=[{"id": "user-1", "name": "Alice", "email": "alice@org.com"}],
    )
    body = _body(handle_get_activity({}, _auth(), storage))
    event = body["events"][0]
    assert event["type"] == "member_invited"
    assert event["actor"] == {"id": "user-1", "name": "Alice"}
    assert event["target"]["name"] == "newhire@org.com"
    assert event["summary"] == "Alice invited newhire@org.com"


def test_projects_member_joined_from_user_created_at() -> None:
    storage = _make_storage(
        users=[
            {
                "id": "user-2",
                "name": "Bob",
                "email": "bob@org.com",
                "created_at": "2026-04-26T15:00:00Z",
            }
        ],
    )
    body = _body(handle_get_activity({}, _auth(), storage))
    event = body["events"][0]
    assert event["type"] == "member_joined"
    # The user is both actor and target — same id, same display name —
    # but `target` carries a `type` field the actor doesn't, so we
    # assert the shared identity directly rather than full equality.
    assert event["actor"]["id"] == event["target"]["id"] == "user-2"
    assert event["actor"]["name"] == event["target"]["name"] == "Bob"
    assert event["target"]["type"] == "user"
    assert event["summary"] == "Bob joined the team"


def test_skips_legacy_user_without_created_at() -> None:
    """A user record predating the §5 schema addition must not crash projection.

    It just doesn't surface a `member_joined` event — that's the documented
    behaviour for legacy users.
    """
    storage = _make_storage(
        users=[{"id": "user-legacy", "name": "Legacy", "email": "legacy@org.com"}],
    )
    body = _body(handle_get_activity({}, _auth(), storage))
    assert body["events"] == []


# ── ordering and capping ──────────────────────────────────────────────


def test_events_are_sorted_newest_first() -> None:
    storage = _make_storage(
        scans=[
            {
                "id": "scan-old",
                "created_by": "user-1",
                "created_at": "2026-04-20T00:00:00Z",
                "type": "single",
                "source_url": "old.com",
            },
            {
                "id": "scan-new",
                "created_by": "user-1",
                "created_at": "2026-04-26T00:00:00Z",
                "type": "single",
                "source_url": "new.com",
            },
        ],
        users=[{"id": "user-1", "name": "Alice"}],
    )
    body = _body(handle_get_activity({}, _auth(), storage))
    assert [e["target"]["name"] for e in body["events"]] == ["new.com", "old.com"]


def test_response_is_capped_at_100_events() -> None:
    """Hard-cap matches the design.md risk-mitigation cap."""
    scans = [
        {
            "id": f"scan-{index}",
            "created_by": "user-1",
            "created_at": f"2026-04-{1 + (index % 28):02d}T00:00:00Z",
            "type": "single",
            "source_url": f"site-{index}.com",
        }
        for index in range(150)
    ]
    storage = _make_storage(scans=scans, users=[{"id": "user-1", "name": "Alice"}])
    body = _body(handle_get_activity({}, _auth(), storage))
    assert len(body["events"]) == 100


def test_logs_warning_when_company_page_is_capped(caplog) -> None:
    """Cap-hit observability — a Logs Insights query on this warning flags
    orgs that may be silently missing recent `analysis_completed` events.

    Architecture-review #2 mitigation: a one-line log gives us a way to
    detect the silent-truncation regression class before the events-table
    migration replaces read-time projection.
    """
    import logging as _logging

    companies = [
        {"id": f"company-{index}", "company_name": f"Co {index}", "analyzed_at": "2026-04-26T00:00:00Z"}
        for index in range(100)  # exactly _MAX_EVENTS — boundary triggers the warning
    ]
    storage = _make_storage(companies=companies)
    with caplog.at_level(_logging.WARNING, logger="src.handlers.activity_handlers"):
        handle_get_activity({}, _auth(org_id="org-at-cap"), storage)

    cap_warnings = [r for r in caplog.records if "company_page_capped" in r.getMessage()]
    assert len(cap_warnings) == 1
    assert "org-at-cap" in cap_warnings[0].getMessage()


def test_does_not_log_warning_below_cap(caplog) -> None:
    """The cap-hit log is rate-limited to actual cap hits — no log when
    the page returns fewer than `_MAX_EVENTS` companies."""
    import logging as _logging

    storage = _make_storage(
        companies=[
            {"id": "c-1", "company_name": "C", "analyzed_at": "2026-04-26T00:00:00Z"}
        ],
    )
    with caplog.at_level(_logging.WARNING, logger="src.handlers.activity_handlers"):
        handle_get_activity({}, _auth(), storage)

    cap_warnings = [r for r in caplog.records if "company_page_capped" in r.getMessage()]
    assert cap_warnings == []


# ── org isolation ─────────────────────────────────────────────────────


def test_org_isolation_repositories_are_called_with_jwt_org_id() -> None:
    """Every repo call uses `authentication.org_id`, not anything from the request."""
    storage = _make_storage()
    handle_get_activity({}, _auth(org_id="org-the-correct-one"), storage)

    storage.create_scan_repository.return_value.find_recent_by_org.assert_called_once()
    scan_call_args = storage.create_scan_repository.return_value.find_recent_by_org.call_args
    assert scan_call_args[0][0] == "org-the-correct-one"

    storage.create_company_repository.return_value.find_by_org.assert_called_once()
    company_call_args = storage.create_company_repository.return_value.find_by_org.call_args
    assert company_call_args[0][0] == "org-the-correct-one"

    storage.create_user_repository.return_value.find_by_org.assert_called_once_with(
        "org-the-correct-one"
    )
    storage.create_invitation_repository.return_value.find_by_org.assert_called_once_with(
        "org-the-correct-one"
    )


# ── graceful degradation ──────────────────────────────────────────────


def test_scan_without_created_by_uses_someone_placeholder() -> None:
    """Records that lost their `created_by` (legacy / corruption) shouldn't crash."""
    storage = _make_storage(
        scans=[
            {
                "id": "scan-x",
                "created_by": "",
                "created_at": "2026-04-26T12:00:00Z",
                "type": "single",
                "source_url": "x.com",
            }
        ],
    )
    body = _body(handle_get_activity({}, _auth(), storage))
    assert body["events"][0]["actor"]["name"] == "Someone"


def test_scan_without_created_at_is_skipped() -> None:
    storage = _make_storage(scans=[{"id": "scan-y", "created_by": "user-1"}])
    body = _body(handle_get_activity({}, _auth(), storage))
    assert body["events"] == []


def test_analysis_completed_without_actor_falls_back_to_analyst_label() -> None:
    """Server-side completed analyses (no resolvable creator) get a placeholder.

    Without the fallback, the actor.name would be an empty string —
    a UX defect surfaced by the architecture-review §5 finding #2.
    """
    storage = _make_storage(
        companies=[
            {
                "id": "company-orphan",
                "company_name": "Orphan Co",
                "analyzed_at": "2026-04-26T13:00:00Z",
                # No `created_by` — server-side or legacy record.
            },
        ],
    )
    body = _body(handle_get_activity({}, _auth(), storage))
    assert body["events"][0]["actor"]["name"] == "An analyst"


def test_invitation_without_inviter_name_falls_back_to_admin_label() -> None:
    storage = _make_storage(
        invitations=[
            {
                "id": "inv-1",
                "email": "x@org.com",
                "invited_by": "unknown-user",
                "created_at": "2026-04-26T14:00:00Z",
            }
        ],
    )
    body = _body(handle_get_activity({}, _auth(), storage))
    assert body["events"][0]["actor"]["name"] == "An admin"


# ── full mixed scenario ───────────────────────────────────────────────


def test_mixed_event_types_all_appear_sorted_newest_first() -> None:
    storage = _make_storage(
        scans=[
            {
                "id": "scan-1",
                "created_by": "user-1",
                "created_at": "2026-04-26T08:00:00Z",
                "type": "single",
                "source_url": "scan.com",
            }
        ],
        companies=[
            {
                "id": "company-1",
                "company_name": "Acme",
                "analyzed_at": "2026-04-26T09:00:00Z",
            }
        ],
        invitations=[
            {
                "id": "inv-1",
                "email": "n@x.com",
                "invited_by": "user-1",
                "created_at": "2026-04-26T10:00:00Z",
            }
        ],
        users=[
            {
                "id": "user-1",
                "name": "Alice",
                "email": "alice@org.com",
                "created_at": "2026-04-26T11:00:00Z",
            }
        ],
    )
    body = _body(handle_get_activity({}, _auth(), storage))
    types = [event["type"] for event in body["events"]]
    # Newest first: member_joined (11:00) → member_invited (10:00) →
    # analysis_completed (09:00) → scan_started (08:00).
    assert types == ["member_joined", "member_invited", "analysis_completed", "scan_started"]

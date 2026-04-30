"""Tests for the cascade-aware restore helpers.

Covers the bug fix that surfaced in production: restoring an analysis
via the Recently Deleted UI was leaving the company's assessments
tombstoned, so the detail page rendered with name/score/tier visible
but empty risk-scores / opportunities / EBITDA / value-chain. Cascade
restore is now exercised end-to-end here so a future refactor can't
regress without a test failure.

Same coverage for the scan-level cascade (scan → links → companies →
assessments).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from botocore.exceptions import ClientError

from src.handlers.admin_restore import (
    restore_analysis,
    restore_scan,
    translate_restore_error,
)


def _ttl_expired_error() -> ClientError:
    return ClientError(
        {"Error": {"Code": "ConditionalCheckFailedException", "Message": "expired"}},
        "UpdateItem",
    )


def _other_aws_error() -> ClientError:
    return ClientError(
        {"Error": {"Code": "ProvisionedThroughputExceededException", "Message": "throttled"}},
        "UpdateItem",
    )


# ── translate_restore_error ─────────────────────────────────────────


def test_translate_returns_ttl_expired_for_conditional_check_failed() -> None:
    assert translate_restore_error(_ttl_expired_error(), "c-1", kind="analysis") == "ttl_expired"


def test_translate_reraises_other_aws_errors() -> None:
    error = _other_aws_error()
    try:
        translate_restore_error(error, "c-1", kind="analysis")
    except ClientError as raised:
        assert raised is error
    else:
        msg = "translate_restore_error should re-raise non-TTL errors"
        raise AssertionError(msg)


# ── restore_analysis ────────────────────────────────────────────────


def test_restore_analysis_cascades_to_tombstoned_assessments() -> None:
    """The bug this PR fixes: assessments must be restored alongside the company."""
    company_repo = MagicMock()
    assessment_repo = MagicMock()
    assessment_repo.find_by_company_with_deleted.return_value = [
        {"id": "a-1", "deleted_at": "2026-04-20T10:00:00+00:00"},
        {"id": "a-2", "deleted_at": "2026-04-20T10:00:00+00:00"},
    ]

    outcome = restore_analysis(company_repo, assessment_repo, "c-1")

    assert outcome == "restored"
    company_repo.restore.assert_called_once_with("c-1")
    # All tombstoned assessments restored — pre-delete state.
    assert assessment_repo.restore.call_count == 2
    restored_ids = {call.args[0] for call in assessment_repo.restore.call_args_list}
    assert restored_ids == {"a-1", "a-2"}


def test_restore_analysis_skips_already_live_assessments() -> None:
    """An assessment without deleted_at is already live — don't redundantly restore."""
    company_repo = MagicMock()
    assessment_repo = MagicMock()
    assessment_repo.find_by_company_with_deleted.return_value = [
        {"id": "a-1", "deleted_at": "2026-04-20T10:00:00+00:00"},  # tombstoned
        {"id": "a-2"},  # live (no deleted_at)
    ]

    outcome = restore_analysis(company_repo, assessment_repo, "c-1")

    assert outcome == "restored"
    company_repo.restore.assert_called_once_with("c-1")
    assessment_repo.restore.assert_called_once_with("a-1")


def test_restore_analysis_continues_on_per_assessment_ttl_eviction() -> None:
    """A single TTL-evicted assessment doesn't fail the whole restore."""
    company_repo = MagicMock()
    assessment_repo = MagicMock()
    assessment_repo.find_by_company_with_deleted.return_value = [
        {"id": "a-evicted", "deleted_at": "2026-01-01T00:00:00+00:00"},
        {"id": "a-recent", "deleted_at": "2026-04-20T10:00:00+00:00"},
    ]
    # First call (a-evicted) raises; second (a-recent) succeeds.
    assessment_repo.restore.side_effect = [_ttl_expired_error(), None]

    outcome = restore_analysis(company_repo, assessment_repo, "c-1")

    assert outcome == "restored"
    assert assessment_repo.restore.call_count == 2


def test_restore_analysis_doesnt_touch_assessments_when_company_ttl_expired() -> None:
    """Don't half-restore: if the company itself is gone, leave the cascade alone."""
    company_repo = MagicMock()
    company_repo.restore.side_effect = _ttl_expired_error()
    assessment_repo = MagicMock()

    outcome = restore_analysis(company_repo, assessment_repo, "c-1")

    assert outcome == "ttl_expired"
    assessment_repo.find_by_company_with_deleted.assert_not_called()
    assessment_repo.restore.assert_not_called()


def test_restore_analysis_with_no_assessments_just_restores_company() -> None:
    company_repo = MagicMock()
    assessment_repo = MagicMock()
    assessment_repo.find_by_company_with_deleted.return_value = []

    outcome = restore_analysis(company_repo, assessment_repo, "c-1")

    assert outcome == "restored"
    company_repo.restore.assert_called_once_with("c-1")
    assessment_repo.restore.assert_not_called()


def test_restore_analysis_per_assessment_non_ttl_error_propagates() -> None:
    """A non-TTL AWS error on an assessment surfaces — we don't swallow real failures."""
    company_repo = MagicMock()
    assessment_repo = MagicMock()
    assessment_repo.find_by_company_with_deleted.return_value = [
        {"id": "a-1", "deleted_at": "2026-04-20T10:00:00+00:00"},
    ]
    assessment_repo.restore.side_effect = _other_aws_error()

    try:
        restore_analysis(company_repo, assessment_repo, "c-1")
    except ClientError as error:
        assert error.response["Error"]["Code"] == "ProvisionedThroughputExceededException"
    else:
        msg = "non-TTL ClientError should propagate"
        raise AssertionError(msg)


# ── restore_scan ────────────────────────────────────────────────────


def test_restore_scan_cascades_links_companies_and_assessments() -> None:
    """Full scan-restore cascade: scan → each link → each company → its assessments."""
    scan_repo = MagicMock()
    company_repo = MagicMock()
    assessment_repo = MagicMock()

    scan_repo.get_scan_companies_with_deleted.return_value = [
        {"company_id": "c-1", "deleted_at": "2026-04-20T10:00:00+00:00"},
        {"company_id": "c-2", "deleted_at": "2026-04-20T10:00:00+00:00"},
    ]

    def assessments_for(company_id: str) -> list[dict[str, Any]]:
        return [{"id": f"a-{company_id}", "deleted_at": "2026-04-20T10:00:00+00:00"}]

    assessment_repo.find_by_company_with_deleted.side_effect = assessments_for

    outcome = restore_scan(scan_repo, company_repo, assessment_repo, "scan-1")

    assert outcome == "restored"
    scan_repo.restore.assert_called_once_with("scan-1")
    # Both links restored.
    assert scan_repo.restore_link.call_count == 2
    # Both companies restored.
    assert company_repo.restore.call_count == 2
    # Each company's assessment restored.
    assert assessment_repo.restore.call_count == 2


def test_restore_scan_skips_link_restore_when_link_is_already_live() -> None:
    """A live link (no deleted_at) doesn't need restoring."""
    scan_repo = MagicMock()
    company_repo = MagicMock()
    assessment_repo = MagicMock()

    scan_repo.get_scan_companies_with_deleted.return_value = [
        {"company_id": "c-1"},  # live link
    ]
    assessment_repo.find_by_company_with_deleted.return_value = []

    restore_scan(scan_repo, company_repo, assessment_repo, "scan-1")

    scan_repo.restore.assert_called_once_with("scan-1")
    scan_repo.restore_link.assert_not_called()
    # Cascade still runs to make the company live + its assessments —
    # the user might have manually deleted just the company before the
    # scan was deleted.
    company_repo.restore.assert_called_once_with("c-1")


def test_restore_scan_doesnt_touch_cascade_when_scan_ttl_expired() -> None:
    scan_repo = MagicMock()
    scan_repo.restore.side_effect = _ttl_expired_error()
    company_repo = MagicMock()
    assessment_repo = MagicMock()

    outcome = restore_scan(scan_repo, company_repo, assessment_repo, "scan-1")

    assert outcome == "ttl_expired"
    scan_repo.get_scan_companies_with_deleted.assert_not_called()
    scan_repo.restore_link.assert_not_called()
    company_repo.restore.assert_not_called()


def test_restore_scan_continues_when_a_single_link_ttl_expired() -> None:
    scan_repo = MagicMock()
    company_repo = MagicMock()
    assessment_repo = MagicMock()

    scan_repo.get_scan_companies_with_deleted.return_value = [
        {"company_id": "c-evicted", "deleted_at": "2026-01-01T00:00:00+00:00"},
        {"company_id": "c-recent", "deleted_at": "2026-04-20T10:00:00+00:00"},
    ]
    scan_repo.restore_link.side_effect = [_ttl_expired_error(), None]
    assessment_repo.find_by_company_with_deleted.return_value = []

    outcome = restore_scan(scan_repo, company_repo, assessment_repo, "scan-1")

    assert outcome == "restored"
    # One link evicted → skipped; the other link restored.
    assert scan_repo.restore_link.call_count == 2
    # The evicted-link branch `continue`s before reaching company_repo.restore,
    # so only the recent company is restored.
    company_repo.restore.assert_called_once_with("c-recent")


def test_restore_scan_continues_when_a_company_ttl_expired() -> None:
    """Per-company TTL expiry during the scan cascade is logged + skipped."""
    scan_repo = MagicMock()
    company_repo = MagicMock()
    assessment_repo = MagicMock()

    scan_repo.get_scan_companies_with_deleted.return_value = [
        {"company_id": "c-evicted", "deleted_at": "2026-01-01T00:00:00+00:00"},
        {"company_id": "c-recent", "deleted_at": "2026-04-20T10:00:00+00:00"},
    ]
    company_repo.restore.side_effect = [_ttl_expired_error(), None]
    assessment_repo.find_by_company_with_deleted.return_value = []

    outcome = restore_scan(scan_repo, company_repo, assessment_repo, "scan-1")

    assert outcome == "restored"
    assert company_repo.restore.call_count == 2

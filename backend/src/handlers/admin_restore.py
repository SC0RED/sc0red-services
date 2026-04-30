"""Cascade-aware restore helpers for the admin Recently Deleted UI.

Extracted from ``admin_handlers.py`` to keep both files under the
400-line limit and isolate the cascade behaviour for unit testing.

The delete cascade in `analysis_handlers.handle_delete_analysis` and
`scan_handlers.handle_delete_scan` tombstones MULTIPLE records per
top-level delete:

  - Delete analysis: company + its assessments
  - Delete scan: scan + each scan→company link + each linked company
                 + each linked company's assessments

The restore must reverse the same cascade. Without this, restoring an
analysis leaves its assessments tombstoned — the detail page renders
with companyName/score/tier visible (from the live company record)
but empty riskScores/opportunities/ebitdaTree (from still-tombstoned
assessments filtered out by `find_by_company`). Silent data loss
visible only when the user opens the restored record.

See `openspec/changes/recently-deleted-admin-ui/` for the original
delete/restore design and `openspec/changes/restore-cascade-fix/`
for the bug fix that introduced this module.
"""

from __future__ import annotations

import logging
from typing import Any

from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


def translate_restore_error(error: ClientError, record_id: str, *, kind: str) -> str:
    """Translate ``ConditionalCheckFailedException`` to ``ttl_expired``.

    Phase 1 added ``require_exists=True`` on every restore call site so
    a TTL-evicted row surfaces as ``ConditionalCheckFailedException``
    instead of silently writing an empty shell. Re-translating that
    here keeps the boto3 error shape from leaking past the handler;
    callers see a clean ``ttl_expired`` outcome string.

    Re-raises any other ClientError so unexpected failures are loud.
    """
    code = error.response.get("Error", {}).get("Code", "")
    if code == "ConditionalCheckFailedException":
        logger.info(
            "admin_restore ttl_expired record_id=%s kind=%s",
            record_id,
            kind,
        )
        return "ttl_expired"
    raise error


def restore_analysis(company_repo: Any, assessment_repo: Any, analysis_id: str) -> str:
    """Restore a tombstoned analysis AND its cascaded assessments.

    Restores ALL tombstoned assessments for the company, not just the
    most recent — re-analysis creates additional assessment metadata
    rows over time, and we want the post-restore state to match the
    pre-delete state. The only path that tombstones an assessment is
    the delete-analysis cascade (verified via grep), so an existing
    tombstoned assessment for a now-live company is by definition
    orphan data from the same delete event.

    If the company restore fails (TTL evicted), we don't attempt the
    assessments — better to leave them coherent with the company's
    missing state than half-restore.

    Per-assessment TTL evictions are logged + skipped so a single
    evicted row doesn't fail the entire restore.
    """
    try:
        company_repo.restore(analysis_id)
    except ClientError as error:
        return translate_restore_error(error, analysis_id, kind="analysis")

    assessments = assessment_repo.find_by_company_with_deleted(analysis_id)
    for assessment in assessments:
        if not assessment.get("deleted_at"):
            continue
        try:
            assessment_repo.restore(assessment["id"])
        except ClientError as error:
            code = error.response.get("Error", {}).get("Code", "")
            if code == "ConditionalCheckFailedException":
                logger.warning(
                    "admin_restore assessment_ttl_expired analysis_id=%s assessment_id=%s",
                    analysis_id,
                    assessment["id"],
                )
                continue
            raise
    return "restored"


def restore_scan(
    scan_repo: Any,
    company_repo: Any,
    assessment_repo: Any,
    scan_id: str,
) -> str:
    """Restore a tombstoned scan AND its cascaded links + companies + assessments.

    `handle_delete_scan` cascades scan → links → companies → assessments;
    the restore reverses the full chain. Without this, restoring a scan
    would leave the linked analyses showing as deleted in the listing
    (companies still tombstoned) — visible regression of the original
    delete operation's reach.

    If the scan restore fails (TTL evicted), we don't touch downstream
    records. Per-cascade-step TTL evictions are logged + skipped so a
    single evicted assessment doesn't fail the entire scan-level restore.
    """
    try:
        scan_repo.restore(scan_id)
    except ClientError as error:
        return translate_restore_error(error, scan_id, kind="scan")

    links = scan_repo.get_scan_companies_with_deleted(scan_id)
    for link in links:
        company_id = link.get("company_id", "")
        if not company_id:
            continue
        # Restore the link first so the scan-companies query reads correctly.
        if link.get("deleted_at"):
            try:
                scan_repo.restore_link(scan_id, company_id)
            except ClientError as error:
                code = error.response.get("Error", {}).get("Code", "")
                if code == "ConditionalCheckFailedException":
                    logger.warning(
                        "admin_restore link_ttl_expired scan_id=%s company_id=%s",
                        scan_id,
                        company_id,
                    )
                    continue
                raise
        # Cascade the company + its assessments. Reuse `restore_analysis` —
        # it carries the same per-step TTL handling we want here.
        outcome = restore_analysis(company_repo, assessment_repo, company_id)
        if outcome == "ttl_expired":
            logger.warning(
                "admin_restore company_ttl_expired_during_scan_cascade scan_id=%s company_id=%s",
                scan_id,
                company_id,
            )
    return "restored"

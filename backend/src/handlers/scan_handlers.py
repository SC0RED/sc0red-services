"""Scan handlers — start, status, confirm, delete.

The start/confirm business logic lives in ``scan_core`` (shared with the MCP
write tools); these handlers own only the HTTP envelope — body parsing,
presence validation, org access, and response shapes.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from src.handlers.api_gateway_handler import (
    NOT_FOUND,
    VALIDATION_ERROR,
    build_error,
    build_json_response,
    check_org_access,
)
from src.handlers.scan_core import ScanInputError, confirm_scan, start_scan
from src.utilities.scan_summary import build_unified_analyses

if TYPE_CHECKING:
    from src.handlers.api_gateway_handler import LambdaResponse
    from src.handlers.auth_middleware import AuthContext
    from src.repositories.dynamodb.provider import DynamoDBStorageProvider

logger = logging.getLogger(__name__)


def handle_scan_start(
    event: dict[str, Any],
    authentication: AuthContext,
    storage: DynamoDBStorageProvider,
    sqs: Any,
    queue_url: str,
) -> LambdaResponse:
    """Handle POST /api/scan/start."""
    body = json.loads(event.get("body") or "{}")
    url = body.get("url", "")
    scan_type = body.get("type", "")

    if not url or not scan_type:
        return build_error("url and type required", code=VALIDATION_ERROR)

    result = start_scan(
        storage.create_scan_repository(),
        url=url,
        scan_type=scan_type,
        authentication=authentication,
        sqs=sqs,
        queue_url=queue_url,
    )
    response: dict[str, Any] = {"scanId": result["scan_id"], "status": result["status"]}
    if "analysis_id" in result:
        response["analysisId"] = result["analysis_id"]
    return build_json_response(response)


def _compute_scan_progress(
    analyses: list[dict[str, Any]],
    scan_progress: int,
    total_companies: int = 0,
) -> tuple[int, int]:
    """Return (done_count, computed_progress) from per-company pipeline progress.

    Uses ``total_companies`` (from the scan record, set at confirm time) as the
    denominator. Drives terminal-state detection off the explicit ``state``
    field set by ``build_unified_analyses`` rather than re-deriving from
    ``analyzedAt``/``error`` — the contract that ``state`` is authoritative
    means downstream logic should not duplicate the derivation.
    """
    if not analyses:
        return 0, scan_progress
    # Use the true total; fall back to len(analyses) for standalone scans
    # where total_companies may be 0 or absent.
    total = max(total_companies, len(analyses))
    done_count = sum(1 for a in analyses if a.get("state") in ("done", "failed"))
    company_progress_sum = sum(
        100 if a.get("state") in ("done", "failed") else a.get("pipelineProgress", 0)
        for a in analyses
    )
    return done_count, company_progress_sum // total


def _derive_progress_label(
    analyses: list[dict[str, Any]],
    fallback_label: str,
) -> str:
    """Return the progress label from the most advanced in-progress company."""
    in_progress = [a for a in analyses if a.get("state") == "scanning"]
    if in_progress:
        furthest = max(in_progress, key=lambda a: a.get("pipelineProgress", 0))
        return str(furthest.get("pipelineLabel", fallback_label))
    return fallback_label


def handle_scan_status(
    _event: dict[str, Any],
    authentication: AuthContext,
    storage: DynamoDBStorageProvider,
    scan_id: str,
) -> LambdaResponse:
    """Handle GET /api/scan/{scan_id}."""
    scan_repo = storage.create_scan_repository()
    scan = scan_repo.get_by_id(scan_id)
    if error := check_org_access(scan, authentication):
        return error
    # check_org_access returns an error response when scan is None; this
    # is defensive narrowing for type checkers — unreachable at runtime.
    if scan is None:
        raise RuntimeError(f"scan {scan_id} vanished between access check and read")

    company_repo = storage.create_company_repository()
    scan_companies = scan_repo.get_scan_companies(scan_id)
    company_ids = [link["company_id"] for link in scan_companies if link.get("company_id")]
    companies_batch = company_repo.get_by_ids(company_ids) if company_ids else []
    # Build one analysis entry per scan_company link — pending entries
    # are synthesized from links for companies that have not yet been
    # picked up by a worker. The frontend renders state-driven cards
    # off the explicit `state` field on each entry.
    analyses = build_unified_analyses(scan_companies, companies_batch)

    status = scan.get("status")
    total_companies = scan.get("total_companies", 0)

    done_count, computed_progress = _compute_scan_progress(
        analyses, scan.get("progress", 0), total_companies
    )

    # Detect completion from company data even if scan record is stale.
    # Handles race conditions where _update_scan_progress hasn't run yet.
    if status == "running" and total_companies and done_count >= total_companies:
        scan_repo.update(scan_id, {"status": "complete", "progress": 100})
        status = "complete"
        computed_progress = 100

    # Use the higher of scan-level or computed progress
    progress = max(scan.get("progress", 0), computed_progress)

    progress_label = _derive_progress_label(analyses, scan.get("progress_label", ""))

    logger.info(
        "[poll] scan=%s status=%s progress=%s analyses=%d",
        scan_id,
        status,
        progress,
        len(analyses),
    )

    return build_json_response(
        {
            "status": status,
            "progress": progress,
            "progressLabel": progress_label,
            "type": scan.get("type"),
            "totalCompanies": total_companies,
            "portfolioCompanies": scan.get("portfolio_companies", []),
            "analyses": analyses,
            "error": scan.get("error", ""),
        }
    )


def handle_scan_confirm(
    event: dict[str, Any],
    authentication: AuthContext,
    storage: DynamoDBStorageProvider,
    sqs: Any,
    queue_url: str,
    scan_id: str,
) -> LambdaResponse:
    """Handle POST /api/scan/{scan_id}/confirm.

    Creates scan→company links and dispatches analyses via Step Functions
    (portfolio scans with multiple companies) or SQS (single company) — see
    ``scan_core.confirm_scan``.
    """
    body = json.loads(event.get("body") or "{}")
    companies = body.get("companies", [])
    if not companies:
        return build_error("No companies provided", code=VALIDATION_ERROR)

    scan_repo = storage.create_scan_repository()
    scan = scan_repo.get_by_id(scan_id)
    if not scan or scan.get("org_id") != authentication.org_id:
        return build_error("Scan not found", 404, NOT_FOUND)

    try:
        result = confirm_scan(
            scan_repo,
            scan_id=scan_id,
            companies=companies,
            authentication=authentication,
            sqs=sqs,
            queue_url=queue_url,
        )
    except ScanInputError as error:
        return build_error(str(error), code=VALIDATION_ERROR)

    return build_json_response({"ok": True, "queued": result["queued"]}, 202)


def handle_delete_scan(
    _event: dict[str, Any],
    authentication: AuthContext,
    storage: DynamoDBStorageProvider,
    scan_id: str,
) -> LambdaResponse:
    """Handle DELETE /api/scan/{scan_id}.

    Soft-deletes (tombstones) the scan, every linked company, every
    company's assessments, and every scan→company link record. Records
    become invisible to live reads immediately and are hard-evicted by
    DynamoDB TTL after 90 days. Recovery within that window goes through
    the engineer-assisted path (Phase 1) or the admin Recently Deleted
    UI (Phase 2).
    """
    scan_repo = storage.create_scan_repository()
    scan = scan_repo.get_by_id(scan_id)
    if error := check_org_access(scan, authentication):
        return error

    company_repo = storage.create_company_repository()
    assessment_repo = storage.create_assessment_repository()
    actor_id = authentication.user_id

    scan_companies = scan_repo.get_scan_companies(scan_id)
    for link in scan_companies:
        company_id = link.get("company_id", "")
        if company_id:
            assessments = assessment_repo.find_by_company(company_id)
            for assessment in assessments:
                assessment_repo.tombstone(assessment["id"], actor_id=actor_id)
            company_repo.tombstone(company_id, actor_id=actor_id)
            scan_repo.tombstone_link(scan_id, company_id, actor_id=actor_id)

    scan_repo.tombstone(scan_id, actor_id=actor_id)
    return build_json_response({"ok": True})

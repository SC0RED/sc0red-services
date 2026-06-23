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
from src.handlers.scan_core import ScanInputError, confirm_scan, deepen_scan, start_scan
from src.utilities.scan_summary import (
    build_unified_analyses,
    compute_scan_progress,
    derive_progress_label,
)

if TYPE_CHECKING:
    from src.handlers.api_gateway_handler import LambdaResponse
    from src.handlers.auth_middleware import AuthContext
    from src.handlers.router import Router
    from src.repositories.dynamodb.provider import DynamoDBStorageProvider

logger = logging.getLogger(__name__)


def register_routes(
    router: Router,
    storage: DynamoDBStorageProvider,
    sqs: Any,
    queue_url: str,
) -> None:
    """Register scan routes (start / status / confirm / deepen / delete)."""
    router.protected(
        "POST",
        "/api/scan/start",
        lambda event, authentication: handle_scan_start(
            event, authentication, storage, sqs, queue_url
        ),
    )
    router.protected(
        "GET",
        "/api/scan/{scan_id}",
        lambda event, authentication, scan_id: handle_scan_status(
            event, authentication, storage, scan_id
        ),
    )
    router.protected(
        "POST",
        "/api/scan/{scan_id}/confirm",
        lambda event, authentication, scan_id: handle_scan_confirm(
            event, authentication, storage, sqs, queue_url, scan_id
        ),
    )
    router.protected(
        "POST",
        "/api/scan/{scan_id}/deepen",
        lambda event, authentication, scan_id: handle_scan_deepen(
            event, authentication, storage, sqs, queue_url, scan_id
        ),
    )
    router.protected(
        "DELETE",
        "/api/scan/{scan_id}",
        lambda event, authentication, scan_id: handle_delete_scan(
            event, authentication, storage, scan_id
        ),
    )


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

    done_count, computed_progress = compute_scan_progress(
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

    progress_label = derive_progress_label(analyses, scan.get("progress_label", ""))

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
            "discoveryVerdict": _verdict_response(scan.get("discovery_verdict")),
            "analyses": analyses,
            "error": scan.get("error", ""),
        }
    )


def _verdict_response(verdict: dict[str, Any] | None) -> dict[str, Any] | None:
    """Map the persisted discovery verdict to the camelCase API shape.

    Returns ``None`` for scans created before the verdict existed. The first
    four keys are guaranteed by ``portfolio_merge.build_verdict``, so they are
    accessed directly — a missing key is a bug, not a default-to-empty case.
    ``site_source_url`` is newer, so it is read with a default for verdicts
    persisted before it existed.
    """
    if not verdict:
        return None
    return {
        "method": verdict["method"],
        "count": verdict["count"],
        "completeness": verdict["completeness"],
        "availableActions": verdict["available_actions"],
        "siteSourceUrl": verdict.get("site_source_url", ""),
    }


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


def handle_scan_deepen(
    _event: dict[str, Any],
    authentication: AuthContext,
    storage: DynamoDBStorageProvider,
    sqs: Any,
    queue_url: str,
    scan_id: str,
) -> LambdaResponse:
    """Handle POST /api/scan/{scan_id}/deepen.

    Customer-triggered escalation: re-run discovery deeper for a scan that is
    awaiting confirmation, seeded with its current companies. Only valid while
    the scan is in ``awaiting_confirmation`` — see ``scan_core.deepen_scan``.
    """
    scan_repo = storage.create_scan_repository()
    scan = scan_repo.get_by_id(scan_id)
    if not scan or scan.get("org_id") != authentication.org_id:
        return build_error("Scan not found", 404, NOT_FOUND)
    if scan.get("status") != "awaiting_confirmation":
        return build_error("Scan is not awaiting confirmation", code=VALIDATION_ERROR)

    result = deepen_scan(
        scan_repo,
        scan_id=scan_id,
        source_url=scan["source_url"],
        authentication=authentication,
        sqs=sqs,
        queue_url=queue_url,
    )
    return build_json_response({"scanId": result["scan_id"], "status": result["status"]}, 202)


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

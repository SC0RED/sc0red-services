"""Scan handlers — start, status, confirm, delete."""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import boto3

from src.handlers.api_gateway_handler import (
    NOT_FOUND,
    VALIDATION_ERROR,
    build_company_summary,
    build_error,
    build_json_response,
    check_org_access,
)
from src.handlers.sqs_messages import (
    build_analysis_message,
    build_portfolio_discovery_message,
)

if TYPE_CHECKING:
    from src.handlers.api_gateway_handler import LambdaResponse
    from src.handlers.auth_middleware import AuthContext
    from src.repositories.dynamodb.provider import DynamoDBStorageProvider
    from src.repositories.dynamodb.scan_repository import DynamoDBScanRepository

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

    scan_repo = storage.create_scan_repository()
    scan_id = _create_scan_record(scan_repo, url, scan_type, authentication)

    if scan_type == "portfolio":
        return _start_portfolio_scan(scan_id, url, authentication, sqs, queue_url)
    return _start_single_scan(scan_repo, scan_id, url, authentication, sqs, queue_url)


def _create_scan_record(
    scan_repo: DynamoDBScanRepository,
    url: str,
    scan_type: str,
    authentication: AuthContext,
) -> str:
    scan_id = str(uuid.uuid4())
    # Portfolio scans are created in "discovering" so the DB record matches
    # the API response the client receives. The worker is idempotent — it
    # re-asserts "discovering" on entry, then transitions to
    # "awaiting_confirmation" (success) or "failed" (domain error). Single
    # scans are "running" since they dispatch per-company work to SQS.
    initial_status = "discovering" if scan_type == "portfolio" else "running"
    scan_repo.create(
        {
            "id": scan_id,
            "org_id": authentication.org_id,
            "created_by": authentication.user_id,
            "type": scan_type,
            "source_url": url,
            "status": initial_status,
            "progress": 0,
            "created_at": datetime.now(UTC).isoformat(),
        }
    )
    return scan_id


def _start_portfolio_scan(
    scan_id: str,
    url: str,
    authentication: AuthContext,
    sqs: Any,
    queue_url: str,
) -> LambdaResponse:
    """Dispatch portfolio discovery to the SQS worker and return immediately.

    The worker runs ``DiscoverPortfolio`` → ``ValidatePortfolioCompanies`` and
    writes results to the scan record. Clients poll GET /api/scan/{id} to
    observe the status transition through ``discovering`` to
    ``awaiting_confirmation`` (or ``failed``).
    """
    sqs.send_message(
        QueueUrl=queue_url,
        MessageBody=build_portfolio_discovery_message(
            url=url,
            org_id=authentication.org_id,
            user_id=authentication.user_id,
            scan_id=scan_id,
        ),
    )
    return build_json_response(
        {
            "scanId": scan_id,
            "status": "discovering",
        }
    )


def _start_single_scan(
    scan_repo: DynamoDBScanRepository,
    scan_id: str,
    url: str,
    authentication: AuthContext,
    sqs: Any,
    queue_url: str,
) -> LambdaResponse:
    analysis_id = str(uuid.uuid4())
    scan_repo.update(scan_id, {"status": "running", "progress": 10, "total_companies": 1})
    scan_repo.link_company(scan_id, analysis_id, "")

    sqs.send_message(
        QueueUrl=queue_url,
        MessageBody=build_analysis_message(
            url=url,
            org_id=authentication.org_id,
            user_id=authentication.user_id,
            scan_id=scan_id,
            request_id=analysis_id,
        ),
    )

    return build_json_response(
        {
            "scanId": scan_id,
            "status": "running",
            "analysisId": analysis_id,
        }
    )


def _compute_scan_progress(
    analyses: list[dict[str, Any]],
    scan_progress: int,
    total_companies: int = 0,
) -> tuple[int, int]:
    """Return (done_count, computed_progress) from per-company pipeline progress.

    Uses ``total_companies`` (from the scan record, set at confirm time) as the
    denominator — not ``len(analyses)``, which only counts companies that have
    DynamoDB records. Companies still queued in SQS have no record yet and would
    be invisible, making progress appear 100% prematurely.
    """
    if not analyses:
        return 0, scan_progress
    # Use the true total; fall back to len(analyses) for standalone scans
    # where total_companies may be 0 or absent.
    total = max(total_companies, len(analyses))
    done_count = sum(1 for a in analyses if a.get("analyzedAt") or a.get("error"))
    company_progress_sum = sum(
        100 if (a.get("analyzedAt") or a.get("error")) else a.get("pipelineProgress", 0)
        for a in analyses
    )
    return done_count, company_progress_sum // total


def _derive_progress_label(
    analyses: list[dict[str, Any]],
    fallback_label: str,
) -> str:
    """Return the progress label from the most advanced in-progress company."""
    in_progress = [
        a
        for a in analyses
        if not a.get("analyzedAt") and not a.get("error") and a.get("pipelineProgress")
    ]
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
    analyses = [build_company_summary(c) for c in companies_batch]

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
    (portfolio scans with multiple companies) or SQS (single company).
    """
    body = json.loads(event.get("body") or "{}")
    companies = body.get("companies", [])
    if not companies:
        return build_error("No companies provided", code=VALIDATION_ERROR)

    scan_repo = storage.create_scan_repository()
    scan = scan_repo.get_by_id(scan_id)
    if not scan or scan.get("org_id") != authentication.org_id:
        return build_error("Scan not found", 404, NOT_FOUND)

    valid_companies = [c for c in companies if c.get("url", "").startswith(("http://", "https://"))]
    if not valid_companies:
        return build_error("At least one company with a url is required", code=VALIDATION_ERROR)

    scan_repo.update(
        scan_id,
        {"status": "running", "progress": 10, "total_companies": len(valid_companies)},
    )

    # Create scan→company links and build the company list for dispatch
    queued = []
    company_payloads = []
    for company in valid_companies:
        company_name = company.get("name", "")
        company_url = company["url"]
        analysis_id = str(uuid.uuid4())
        scan_repo.link_company(scan_id, analysis_id, company_name)
        queued.append({"name": company_name, "analysisId": analysis_id})
        company_payloads.append(
            {
                "name": company_name,
                "url": company_url,
                "analysis_id": analysis_id,
            }
        )

    # Dispatch via Step Functions for portfolio scans (multiple companies).
    # Step Functions dispatches in waves matching worker concurrency,
    # avoiding SQS poller throttle that causes messages to land in DLQ.
    state_machine_arn = os.environ.get("PORTFOLIO_STATE_MACHINE_ARN", "")
    if state_machine_arn and len(valid_companies) > 1:
        wave_size = int(os.environ.get("WAVE_SIZE", "4"))
        sfn_client = boto3.client("stepfunctions")
        sfn_client.start_execution(
            stateMachineArn=state_machine_arn,
            input=json.dumps(
                {
                    "companies": company_payloads,
                    "wave_size": wave_size,
                    "scan_id": scan_id,
                    "org_id": authentication.org_id,
                    "user_id": authentication.user_id,
                }
            ),
        )
    else:
        # Fallback: single company or no state machine configured (local dev).
        # Send directly to SQS as before.
        for index, company in enumerate(valid_companies):
            sqs.send_message(
                QueueUrl=queue_url,
                MessageBody=build_analysis_message(
                    url=company["url"],
                    org_id=authentication.org_id,
                    user_id=authentication.user_id,
                    scan_id=scan_id,
                    request_id=queued[index]["analysisId"],
                    company_name=company.get("name", ""),
                ),
            )

    return build_json_response({"ok": True, "queued": queued}, 202)


def handle_delete_scan(
    _event: dict[str, Any],
    authentication: AuthContext,
    storage: DynamoDBStorageProvider,
    scan_id: str,
) -> LambdaResponse:
    """Handle DELETE /api/scan/{scan_id}."""
    scan_repo = storage.create_scan_repository()
    scan = scan_repo.get_by_id(scan_id)
    if error := check_org_access(scan, authentication):
        return error

    company_repo = storage.create_company_repository()
    assessment_repo = storage.create_assessment_repository()

    scan_companies = scan_repo.get_scan_companies(scan_id)
    for link in scan_companies:
        company_id = link.get("company_id", "")
        if company_id:
            assessments = assessment_repo.find_by_company(company_id)
            for assessment in assessments:
                assessment_repo.delete(assessment["id"])
            company_repo.delete(company_id)

    scan_repo.delete_all_company_links(scan_id)
    scan_repo.delete(scan_id)
    return build_json_response({"ok": True})

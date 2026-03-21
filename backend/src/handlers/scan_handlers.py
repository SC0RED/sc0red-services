"""Scan handlers — start, status, confirm, delete."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from src.handlers.api_gateway_handler import (
    _build_company_summary,
    _error,
    _json_response,
)

if TYPE_CHECKING:
    from src.handlers.api_gateway_handler import LambdaResponse
    from src.handlers.auth_middleware import AuthContext
    from src.handlers.factory_manager import FactoryManager
    from src.repositories.dynamodb.provider import DynamoDBStorageProvider
    from src.repositories.dynamodb.scan_repository import DynamoDBScanRepository

logger = logging.getLogger(__name__)


def handle_scan_start(
    event: dict[str, Any],
    authentication: AuthContext,
    storage: DynamoDBStorageProvider,
    factory_manager: FactoryManager,
    sqs: Any,
    queue_url: str,
) -> LambdaResponse:
    """Handle POST /api/scan/start."""
    body = json.loads(event.get("body") or "{}")
    url = body.get("url", "")
    scan_type = body.get("type", "")

    if not url or not scan_type:
        return _error("url and type required")

    scan_repo = storage.create_scan_repository()
    scan_id = _create_scan_record(scan_repo, url, scan_type, authentication)

    if scan_type == "portfolio":
        return _start_portfolio_scan(scan_repo, scan_id, url, authentication, factory_manager)
    return _start_single_scan(scan_repo, scan_id, url, authentication, sqs, queue_url)


def _create_scan_record(
    scan_repo: DynamoDBScanRepository,
    url: str,
    scan_type: str,
    authentication: AuthContext,
) -> str:
    scan_id = str(uuid.uuid4())
    scan_repo.create(
        {
            "id": scan_id,
            "org_id": authentication.org_id,
            "created_by": authentication.user_id,
            "type": scan_type,
            "source_url": url,
            "status": "running",
            "progress": 0,
            "created_at": datetime.now(UTC).isoformat(),
        }
    )
    return scan_id


def _start_portfolio_scan(
    scan_repo: DynamoDBScanRepository,
    scan_id: str,
    url: str,
    authentication: AuthContext,
    factory_manager: FactoryManager,
) -> LambdaResponse:
    scan_repo.update(scan_id, {"progress": 5})
    result = factory_manager.run_portfolio_discovery(
        url=url,
        org_id=authentication.org_id,
        user_id=authentication.user_id,
        scan_id=scan_id,
    )
    companies = result["details"]["portfolio_companies"]
    scan_repo.update(
        scan_id,
        {
            "status": "awaiting_confirmation",
            "progress": 20,
            "portfolio_companies": companies,
        },
    )
    return _json_response(
        {
            "scanId": scan_id,
            "status": "awaiting_confirmation",
            "portfolioCompanies": companies,
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
        MessageBody=json.dumps(
            {
                "url": url,
                "org_id": authentication.org_id,
                "user_id": authentication.user_id,
                "scan_id": scan_id,
                "company_name": "",
                "request_id": analysis_id,
            }
        ),
    )

    return _json_response(
        {
            "scanId": scan_id,
            "status": "running",
            "analysisId": analysis_id,
        }
    )


def handle_scan_status(
    _event: dict[str, Any],
    authentication: AuthContext,
    storage: DynamoDBStorageProvider,
    scan_id: str,
) -> LambdaResponse:
    """Handle GET /api/scan/{scan_id}."""
    scan_repo = storage.create_scan_repository()
    scan = scan_repo.get_by_id(scan_id)
    if not scan or scan.get("org_id") != authentication.org_id:
        return _error("Not found", 404)

    company_repo = storage.create_company_repository()
    scan_companies = scan_repo.get_scan_companies(scan_id)
    company_ids = [link["company_id"] for link in scan_companies if link.get("company_id")]
    companies_batch = company_repo.get_by_ids(company_ids) if company_ids else []
    analyses = [_build_company_summary(c) for c in companies_batch]

    status = scan.get("status")
    total_companies = scan.get("total_companies", 0)

    # Compute progress from per-company pipeline_progress
    if analyses:
        total = len(analyses)
        done_count = sum(1 for a in analyses if a.get("analyzedAt") or a.get("error"))
        company_progress_sum = sum(
            100 if (a.get("analyzedAt") or a.get("error")) else a.get("pipelineProgress", 0)
            for a in analyses
        )
        computed_progress = company_progress_sum // total
    else:
        done_count = 0
        computed_progress = scan.get("progress", 0)

    # Detect completion from company data even if scan record is stale.
    # Handles race conditions where _update_scan_progress hasn't run yet.
    if status == "running" and total_companies and done_count >= total_companies:
        scan_repo.update(scan_id, {"status": "complete", "progress": 100})
        status = "complete"
        computed_progress = 100

    # Use the higher of scan-level or computed progress
    progress = max(scan.get("progress", 0), computed_progress)

    # Build label from the most advanced in-progress company
    progress_label = scan.get("progress_label", "")
    in_progress = [
        a
        for a in analyses
        if not a.get("analyzedAt") and not a.get("error") and a.get("pipelineProgress")
    ]
    if in_progress:
        furthest = max(in_progress, key=lambda a: a.get("pipelineProgress", 0))
        progress_label = furthest.get("pipelineLabel", progress_label)

    logger.info(
        "[poll] scan=%s status=%s progress=%s analyses=%d",
        scan_id,
        status,
        progress,
        len(analyses),
    )

    return _json_response(
        {
            "status": status,
            "progress": progress,
            "progressLabel": progress_label,
            "type": scan.get("type"),
            "portfolioCompanies": scan.get("portfolio_companies", []),
            "analyses": analyses,
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
    """Handle POST /api/scan/{scan_id}/confirm."""
    body = json.loads(event.get("body") or "{}")
    companies = body.get("companies", [])
    if not companies:
        return _error("No companies provided")

    scan_repo = storage.create_scan_repository()
    scan = scan_repo.get_by_id(scan_id)
    if not scan or scan.get("org_id") != authentication.org_id:
        return _error("Scan not found", 404)

    valid_companies = [c for c in companies if c.get("url")]
    if not valid_companies:
        return _error("At least one company with a url is required")

    scan_repo.update(
        scan_id,
        {"status": "running", "progress": 10, "total_companies": len(valid_companies)},
    )

    queued = []
    for company in valid_companies:
        company_name = company.get("name", "")
        company_url = company["url"]
        analysis_id = str(uuid.uuid4())
        scan_repo.link_company(scan_id, analysis_id, company_name)

        sqs.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps(
                {
                    "url": company_url,
                    "org_id": authentication.org_id,
                    "user_id": authentication.user_id,
                    "scan_id": scan_id,
                    "company_name": company_name,
                    "request_id": analysis_id,
                }
            ),
        )
        queued.append({"name": company_name, "analysisId": analysis_id})

    return _json_response({"ok": True, "queued": queued}, 202)


def handle_delete_scan(
    _event: dict[str, Any],
    authentication: AuthContext,
    storage: DynamoDBStorageProvider,
    scan_id: str,
) -> LambdaResponse:
    """Handle DELETE /api/scan/{scan_id}."""
    scan_repo = storage.create_scan_repository()
    scan = scan_repo.get_by_id(scan_id)
    if not scan or scan.get("org_id") != authentication.org_id:
        return _error("Not found", 404)

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
    return _json_response({"ok": True})

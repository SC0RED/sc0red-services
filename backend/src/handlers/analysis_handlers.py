"""Analysis handlers — get, delete, list, dashboard, reanalyze."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from src.handlers.api_gateway_handler import (
    build_company_summary,
    build_error,
    build_json_response,
)
from src.handlers.sqs_messages import build_reanalysis_message

if TYPE_CHECKING:
    from src.handlers.api_gateway_handler import LambdaResponse
    from src.handlers.auth_middleware import AuthContext
    from src.repositories.dynamodb.provider import DynamoDBStorageProvider

logger = logging.getLogger(__name__)


def handle_get_analysis(
    _event: dict[str, Any],
    authentication: AuthContext,
    storage: DynamoDBStorageProvider,
    analysis_id: str,
) -> LambdaResponse:
    """Handle GET /api/analysis/{analysis_id}."""
    company_repo = storage.create_company_repository()
    company = company_repo.get_by_id(analysis_id)
    if not company or company.get("org_id") != authentication.org_id:
        return build_error("Not found", 404)

    assessment_repo = storage.create_assessment_repository()
    assessments = assessment_repo.find_by_company(analysis_id)

    risk_scores = []
    opportunities = []
    analysis_summary = ""
    top_actions: list[str] = []
    ebitda_tree = None

    documents: list[dict[str, Any]] = []

    if assessments:
        # Take the most recent assessment — during re-analysis, both old and new
        # assessments exist briefly until the old one is deleted. Sort by created_at
        # descending to always pick the newest. Legacy assessments without created_at
        # sort last (empty string).
        assessments.sort(key=lambda a: a.get("created_at", ""), reverse=True)
        assessment = assessments[0]
        assessment_id = assessment["id"]
        risk_scores = assessment_repo.get_risk_scores(assessment_id)
        opportunities = assessment_repo.get_opportunities(assessment_id)
        ebitda_tree = assessment_repo.get_ebitda_tree(assessment_id)
        documents = assessment_repo.get_documents(assessment_id)

    metadata_json = company.get("metadata_json", "")
    if metadata_json:
        # DynamoDB may return string (json.dumps'd) or dict (Map type from legacy records)
        meta = json.loads(metadata_json) if isinstance(metadata_json, str) else metadata_json
        analysis_summary = meta.get("analysis_summary", "")
        top_actions = meta.get("top_actions", [])

    return build_json_response(
        {
            "companyName": company.get("company_name", ""),
            "companyUrl": company.get("company_url", ""),
            "industry": company.get("industry", ""),
            "overallRiskScore": company.get("overall_risk_score"),
            "riskTier": company.get("risk_tier"),
            "analysisSummary": analysis_summary,
            "topActions": top_actions,
            "riskScores": risk_scores,
            "opportunities": opportunities,
            "ebitdaTree": ebitda_tree,
            "documents": documents,
            "pipelineProgress": company.get("pipeline_progress", 0),
            "pipelineLabel": company.get("pipeline_label", ""),
            "analyzedAt": company.get("analyzed_at"),
            "scanId": company.get("scan_id", ""),
        }
    )


def handle_delete_analysis(
    _event: dict[str, Any],
    authentication: AuthContext,
    storage: DynamoDBStorageProvider,
    analysis_id: str,
) -> LambdaResponse:
    """Handle DELETE /api/analysis/{analysis_id}."""
    company_repo = storage.create_company_repository()
    company = company_repo.get_by_id(analysis_id)
    if not company or company.get("org_id") != authentication.org_id:
        return build_error("Not found", 404)

    assessment_repo = storage.create_assessment_repository()
    assessments = assessment_repo.find_by_company(analysis_id)
    for assessment in assessments:
        assessment_repo.delete(assessment["id"])

    company_repo.delete(analysis_id)

    scan_id = company.get("scan_id", "")
    if scan_id:
        scan_repo = storage.create_scan_repository()
        scan_repo.unlink_company(scan_id, analysis_id)
        remaining = scan_repo.get_scan_companies(scan_id)
        if not remaining:
            scan_repo.delete(scan_id)

    return build_json_response({"ok": True})


def handle_list_analyses(
    _event: dict[str, Any],
    authentication: AuthContext,
    storage: DynamoDBStorageProvider,
) -> LambdaResponse:
    """Handle GET /api/analyses."""
    company_repo = storage.create_company_repository()
    companies = company_repo.find_by_org(authentication.org_id)
    return build_json_response({"analyses": [build_company_summary(c) for c in companies]})


def handle_dashboard(
    _event: dict[str, Any],
    authentication: AuthContext,
    storage: DynamoDBStorageProvider,
) -> LambdaResponse:
    """Handle GET /api/dashboard."""
    company_repo = storage.create_company_repository()
    scan_repo = storage.create_scan_repository()

    companies = company_repo.find_by_org(authentication.org_id)
    analyzed = [c for c in companies if c.get("overall_risk_score") is not None]

    total_analyses = len(analyzed)
    avg_risk_score = (
        round(sum(float(c["overall_risk_score"]) for c in analyzed) / total_analyses, 1)
        if total_analyses
        else 0
    )
    critical_count = sum(1 for c in analyzed if c.get("risk_tier") == "critical")

    all_scans = scan_repo.find_recent_by_org(authentication.org_id, limit=None)
    scan_count = len(all_scans)
    recent_scans = all_scans[:10]

    scan_type_map = {s["id"]: s.get("type", "") for s in all_scans}

    # Build fallback date map: scan_id -> earliest analyzed_at from linked companies
    scan_date_fallback: dict[str, str] = {}
    for company in companies:
        scan_id = company.get("scan_id", "")
        analyzed_at = company.get("analyzed_at", "")
        if scan_id and analyzed_at:
            existing = scan_date_fallback.get(scan_id, "")
            if not existing or analyzed_at < existing:
                scan_date_fallback[scan_id] = analyzed_at

    analyzed.sort(key=lambda c: c.get("analyzed_at", ""), reverse=True)
    recent_analyses = [
        {
            "id": c.get("id"),
            "companyName": c.get("company_name", ""),
            "companyUrl": c.get("company_url", ""),
            "overallRiskScore": c.get("overall_risk_score"),
            "riskTier": c.get("risk_tier"),
            "analyzedAt": c.get("analyzed_at"),
            "scanType": scan_type_map.get(c.get("scan_id", ""), ""),
        }
        for c in analyzed[:8]
    ]

    recent_scan_list = [
        {
            "id": s.get("id"),
            "sourceUrl": s.get("source_url", ""),
            "type": s.get("type", ""),
            "status": s.get("status", ""),
            "progress": s.get("progress", 0),
            "completedCount": s.get("completed_count", 0),
            "createdAt": s.get("created_at") or scan_date_fallback.get(s.get("id", ""), ""),
        }
        for s in recent_scans
    ]

    return build_json_response(
        {
            "totalAnalyses": total_analyses,
            "avgRiskScore": avg_risk_score,
            "criticalCount": critical_count,
            "scanCount": scan_count,
            "recentAnalyses": recent_analyses,
            "recentScans": recent_scan_list,
        }
    )


def handle_reanalyze(
    _event: dict[str, Any],
    authentication: AuthContext,
    storage: DynamoDBStorageProvider,
    sqs: Any,
    queue_url: str,
    analysis_id: str,
) -> LambdaResponse:
    """Handle POST /api/analysis/{analysis_id}/reanalyze."""
    company_repo = storage.create_company_repository()
    company = company_repo.get_by_id(analysis_id)
    if not company or company.get("org_id") != authentication.org_id:
        return build_error("Not found", 404)

    company_url = company.get("company_url", "")
    if not company_url:
        return build_error("Analysis has no company URL — cannot re-analyze")

    scan_id = company.get("scan_id", "")

    sqs.send_message(
        QueueUrl=queue_url,
        MessageBody=build_reanalysis_message(
            analysis_id=analysis_id,
            url=company_url,
            org_id=authentication.org_id,
            user_id=authentication.user_id,
            scan_id=scan_id,
        ),
    )

    return build_json_response({"status": "queued", "scanId": scan_id}, 202)

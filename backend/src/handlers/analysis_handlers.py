"""Analysis handlers — get, delete, list, dashboard, reanalyze."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from src.handlers.analysis_payload import build_analysis_payload
from src.handlers.api_gateway_handler import (
    VALIDATION_ERROR,
    build_error,
    build_json_response,
    check_org_access,
)
from src.handlers.sqs_messages import (
    build_reanalysis_message,
    build_strategy_map_message,
)
from src.utilities.scan_summary import build_company_summary

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
    if error := check_org_access(company, authentication):
        return error
    return build_json_response(build_analysis_payload(storage, company, analysis_id))


def handle_delete_analysis(
    _event: dict[str, Any],
    authentication: AuthContext,
    storage: DynamoDBStorageProvider,
    analysis_id: str,
) -> LambdaResponse:
    """Handle DELETE /api/analysis/{analysis_id}.

    Soft-deletes (tombstones) the analysis, its assessments, and the
    scan→company link. Cascades to the parent scan when this was its
    last live link. Records become invisible to live reads immediately
    and are hard-evicted by DynamoDB TTL after 90 days. Recovery within
    that window goes through the engineer-assisted path (Phase 1) or
    the admin Recently Deleted UI (Phase 2).
    """
    company_repo = storage.create_company_repository()
    company = company_repo.get_by_id(analysis_id)
    if error := check_org_access(company, authentication):
        return error

    assessment_repo = storage.create_assessment_repository()
    assessments = assessment_repo.find_by_company(analysis_id)
    for assessment in assessments:
        assessment_repo.tombstone(assessment["id"], actor_id=authentication.user_id)

    company_repo.tombstone(analysis_id, actor_id=authentication.user_id)

    scan_id = company.get("scan_id", "")
    if scan_id:
        scan_repo = storage.create_scan_repository()
        scan_repo.tombstone_link(scan_id, analysis_id, actor_id=authentication.user_id)
        remaining = scan_repo.get_scan_companies(scan_id)
        if not remaining:
            scan_repo.tombstone(scan_id, actor_id=authentication.user_id)

    return build_json_response({"ok": True})


def handle_bulk_delete_analyses(
    event: dict[str, Any],
    authentication: AuthContext,
    storage: DynamoDBStorageProvider,
) -> LambdaResponse:
    """Handle POST /api/analyses/bulk-delete — delete N analyses in one call.

    Race-immune cascade: the single-delete endpoint cascades to the scan
    when the deleted analysis was its last linked company, but parallel
    DELETEs on the same scan can each read the post-unlink state before
    peers' writes commit and ALL conclude "links remain" — leaving an
    orphan scan. This handler unlinks every analysis first, then makes
    the cascade decision over each affected scan in a single post-delete
    pass. One handler run = no race.

    Body: ``{"ids": [...]}``. Response: ``{"deleted", "failed", "deletedScans"}``.
    """
    raw_body = event.get("body") or "{}"
    try:
        body = json.loads(raw_body)
    except json.JSONDecodeError as error:
        return build_error(f"Invalid JSON: {error}", 400, VALIDATION_ERROR)

    ids = body.get("ids")
    if not isinstance(ids, list) or not all(isinstance(item, str) for item in ids):
        return build_error("Body must include `ids: string[]`", 400, VALIDATION_ERROR)
    if not ids:
        return build_error("`ids` must not be empty", 400, VALIDATION_ERROR)

    company_repo = storage.create_company_repository()
    assessment_repo = storage.create_assessment_repository()
    scan_repo = storage.create_scan_repository()

    # Single BatchGetItem instead of N GetItem calls (CLAUDE.md
    # DynamoDB pattern). The result preserves only IDs that exist; we
    # build a lookup so the loop below can branch on missing/cross-org
    # cases without re-querying.
    fetched = company_repo.get_by_ids(ids)
    company_by_id: dict[str, dict[str, Any]] = {
        company["id"]: company for company in fetched if company.get("id")
    }

    actor_id = authentication.user_id

    deleted: list[str] = []
    failed: list[dict[str, str]] = []
    affected_scan_ids: set[str] = set()

    for analysis_id in ids:
        company = company_by_id.get(analysis_id)
        if not company or company.get("org_id") != authentication.org_id:
            # Org-mismatch and missing-record both surface as the same
            # opaque "not found" — same posture as `check_org_access`.
            failed.append({"id": analysis_id, "reason": "not_found"})
            continue

        # `assessment_repo.find_by_company` is a per-company GSI query;
        # there's no batch equivalent today. The N queries are bounded by
        # the user's selection size (typically 1-12) so this is
        # acceptable for v1; revisit if bulk-delete starts handling
        # hundreds of rows per call.
        assessments = assessment_repo.find_by_company(analysis_id)
        for assessment in assessments:
            assessment_repo.tombstone(assessment["id"], actor_id=actor_id)
        company_repo.tombstone(analysis_id, actor_id=actor_id)

        scan_id = company.get("scan_id", "")
        if scan_id:
            scan_repo.tombstone_link(scan_id, analysis_id, actor_id=actor_id)
            affected_scan_ids.add(scan_id)

        deleted.append(analysis_id)

    # Cascade pass: every requested analysis is tombstoned (link records
    # included), so `get_scan_companies` returns the post-delete truth.
    # Race-immune in the happy path; transient exceptions are picked up
    # by `cleanup_orphan_scans.py` on the next sweep.
    deleted_scans: list[str] = []
    for scan_id in affected_scan_ids:
        if not scan_repo.get_scan_companies(scan_id):
            scan_repo.tombstone(scan_id, actor_id=actor_id)
            deleted_scans.append(scan_id)

    logger.info(
        "bulk_delete_analyses org_id=%s requested=%d deleted=%d failed=%d scans_cascaded=%d",
        authentication.org_id,
        len(ids),
        len(deleted),
        len(failed),
        len(deleted_scans),
    )

    return build_json_response(
        {
            "deleted": deleted,
            "failed": failed,
            "deletedScans": deleted_scans,
        }
    )


def handle_list_analyses(
    event: dict[str, Any],
    authentication: AuthContext,
    storage: DynamoDBStorageProvider,
) -> LambdaResponse:
    """Handle GET /api/analyses — supports ?limit=N&cursor=JSON pagination."""
    query_params = event.get("queryStringParameters") or {}
    limit = int(query_params["limit"]) if query_params.get("limit") else None
    cursor = json.loads(query_params["cursor"]) if query_params.get("cursor") else None

    company_repo = storage.create_company_repository()
    scan_repo = storage.create_scan_repository()
    companies, next_cursor = company_repo.find_by_org(
        authentication.org_id,
        limit=limit,
        cursor=cursor,
    )

    all_scans = scan_repo.find_recent_by_org(authentication.org_id, limit=None)
    scan_type_map = {s["id"]: s.get("type", "") for s in all_scans}

    analyses = []
    for company in companies:
        summary = build_company_summary(company)
        company_scan_id = company.get("scan_id", "")
        # Surface scan provenance so the analyses table can link the
        # "Portfolio" badge through to /portfolio/{scanId}.
        summary["scanId"] = company_scan_id
        summary["scanType"] = scan_type_map.get(company_scan_id, "")
        analyses.append(summary)

    response: dict[str, Any] = {"analyses": analyses}
    if next_cursor:
        response["cursor"] = json.dumps(next_cursor)
    return build_json_response(response)


def handle_dashboard(
    _event: dict[str, Any],
    authentication: AuthContext,
    storage: DynamoDBStorageProvider,
) -> LambdaResponse:
    """Handle GET /api/dashboard — aggregates stats from all companies + recent items."""
    company_repo = storage.create_company_repository()
    scan_repo = storage.create_scan_repository()

    # Load all companies for stats (no limit — need totals)
    companies, _cursor = company_repo.find_by_org(authentication.org_id)
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
            # Total linked companies at confirm time. Used by the dashboard's
            # delete-scan toast to spell out the full cascade scope (deletion
            # touches every linked company, not just the completed ones).
            "totalCompanies": s.get("total_companies", 0),
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
    if error := check_org_access(company, authentication):
        return error

    company_url = company.get("company_url", "")
    if not company_url:
        return build_error("Analysis has no company URL — cannot re-analyze", code=VALIDATION_ERROR)

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


def handle_generate_strategy_map(
    _event: dict[str, Any],
    authentication: AuthContext,
    storage: DynamoDBStorageProvider,
    sqs: Any,
    queue_url: str,
    analysis_id: str,
) -> LambdaResponse:
    """Handle POST /api/analysis/{analysis_id}/strategy-map.

    Per the strategy-map-on-demand spec: validate access, mark generation
    in-flight on the company record, enqueue an SQS message on the dedicated
    ``janus-strategy-map-queue``, and return 202 Accepted immediately. The
    SQS worker (``strategy_map_handler``) picks up the message, runs
    ``GenerateStrategyMap`` against the persisted analysis, persists the
    result, and pushes an AppSync ``strategy_map_complete`` event.

    Returns 503 ``STRATEGY_MAP_FEATURE_DISABLED`` when ``queue_url`` is empty
    — the API Lambda's CDK env var is unset (e.g., environment hasn't
    deployed Phase A2 yet), and we'd rather fail cleanly than ParamValidationError
    out of boto3 below.
    """
    if not queue_url:
        return build_error(
            "Strategy-map generation queue not configured for this environment",
            status=503,
            code="STRATEGY_MAP_FEATURE_DISABLED",
        )

    company_repo = storage.create_company_repository()
    company = company_repo.get_by_id(analysis_id)
    if error := check_org_access(company, authentication):
        return error

    scan_id = company.get("scan_id", "")

    # Mark generation in-flight BEFORE enqueueing so a refresh during the
    # narrow window between SQS send and worker pickup still shows the
    # generating placeholder rather than the CTA. The worker clears the
    # field on success or failure.
    company_repo.set_strategy_map_generation_state(analysis_id, "generating")

    sqs.send_message(
        QueueUrl=queue_url,
        MessageBody=build_strategy_map_message(
            analysis_id=analysis_id,
            scan_id=scan_id,
        ),
    )

    return build_json_response({"status": "queued", "analysisId": analysis_id}, 202)

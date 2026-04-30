"""Assemble the analysis JSON payload from DynamoDB records.

Lives in its own module so two callers can share it without a tight
coupling to `analysis_handlers`:
  - `analysis_handlers.handle_get_analysis` — Cognito-auth `/api/analysis/{id}`
  - `internal_handlers.handle_internal_get_analysis` — internal-API-key
    `/api/internal/analysis/{id}` (powers the headless PDF render path)

Caller is responsible for the org-scoping check before invoking
`build_analysis_payload` — this module trusts that the `company` dict
passed in is the right one for the caller's auth context.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.repositories.dynamodb.provider import DynamoDBStorageProvider


def build_analysis_payload(
    storage: DynamoDBStorageProvider,
    company: dict[str, Any],
    analysis_id: str,
) -> dict[str, Any]:
    """Assemble the JSON payload for a fully-loaded analysis."""
    # Look up the parent scan to surface scan provenance (type + source URL)
    # on the analysis detail page. Used by the frontend to render the
    # "Part of: {scan}" cross-reference for portfolio analyses, and to
    # avoid showing portfolio-only navigation on standalone analyses.
    scan_type = ""
    scan_source_url = ""
    scan_id = company.get("scan_id", "")
    if scan_id:
        scan_repo = storage.create_scan_repository()
        scan = scan_repo.get_by_id(scan_id)
        if scan is not None:
            scan_type = scan.get("type", "")
            scan_source_url = scan.get("source_url", "")

    assessment_repo = storage.create_assessment_repository()
    assessments = assessment_repo.find_by_company(analysis_id)

    risk_scores: list[dict[str, Any]] = []
    opportunities: list[dict[str, Any]] = []
    analysis_summary = ""
    top_actions: list[str] = []
    ebitda_tree: dict[str, Any] | None = None
    value_chain: dict[str, Any] | None = None
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
        value_chain = assessment_repo.get_value_chain(assessment_id)
        documents = assessment_repo.get_documents(assessment_id)

    metadata_json = company.get("metadata_json", "")
    if metadata_json:
        # DynamoDB may return string (json.dumps'd) or dict (Map type from legacy records)
        meta = json.loads(metadata_json) if isinstance(metadata_json, str) else metadata_json
        analysis_summary = meta.get("analysis_summary", "")
        top_actions = meta.get("top_actions", [])

    return {
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
        "valueChain": value_chain,
        "documents": documents,
        "pipelineProgress": company.get("pipeline_progress", 0),
        "pipelineLabel": company.get("pipeline_label", ""),
        "analyzedAt": company.get("analyzed_at"),
        "error": company.get("error"),
        "scanId": scan_id,
        "scanType": scan_type,
        "scanSourceUrl": scan_source_url,
    }

"""Stage 6: Persist analysis results to DynamoDB.

Ports the DB write logic from pe-scan/src/app/api/scan/start/route.ts.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

from signalfield_core.pipeline.step import RequestStep

from src.pipeline.step_timer import StepTimer

if TYPE_CHECKING:
    from src.facades.company_accessor import CompanyAccessor
    from src.repositories.dynamodb.assessment_repository import DynamoDBAssessmentRepository
    from src.repositories.dynamodb.company_repository import DynamoDBCompanyRepository

logger = logging.getLogger(__name__)


class PersistResults(RequestStep):
    """Persists the full analysis (company, assessment, risk scores, opportunities) to DynamoDB."""

    def __init__(
        self,
        company_repo: DynamoDBCompanyRepository,
        assessment_repo: DynamoDBAssessmentRepository,
    ) -> None:
        super().__init__()
        self._company_repo = company_repo
        self._assessment_repo = assessment_repo

    def execute(self) -> None:
        """Persist company, assessment, risk scores, and opportunities to DynamoDB."""
        timer = StepTimer("PersistResults")
        accessor = cast("CompanyAccessor", self.entity_accessor)
        company = accessor.company

        if not company.id:
            raise RuntimeError("Company ID must be set before persisting results")
        company_id = company.id
        accessor.set_id(company_id)

        profile = company.profile
        risk_assessment = company.risk_assessment
        opportunity_result = company.opportunity_result

        company_doc: dict[str, Any] = {
            "company_name": profile.company_name if profile else "",
            "company_url": company.actual_url or company.url,
            "industry": profile.industry if profile else "",
            "description": profile.description if profile else "",
            "overall_risk_score": risk_assessment.overall_score if risk_assessment else None,
            "risk_tier": risk_assessment.tier if risk_assessment else None,
            "scan_id": company.scan_id,
            "org_id": company.org_id,
            "analyzed_at": datetime.now(UTC).isoformat(),
        }
        # `created_by` attributes the analysis to the user who triggered
        # the scan/re-analyze. Read by the activity-feed handler for
        # `analysis_completed` events. See
        # `openspec/changes/fix-actor-attribution/`.
        if company.user_id:
            company_doc["created_by"] = company.user_id
        company_doc["id"] = company_id
        self._company_repo.save(company_doc)

        # Persist assessment with risk scores
        assessment_id = ""
        if risk_assessment:
            assessment_id = str(uuid.uuid4())
            assessment_doc = {
                "company_id": company_id,
                "overall_score": risk_assessment.overall_score,
                "tier": risk_assessment.tier,
                "top_risks": risk_assessment.top_risks,
                "analysis_summary": risk_assessment.analysis_summary,
                "created_at": datetime.now(UTC).isoformat(),
            }
            assessment_doc["id"] = assessment_id
            self._assessment_repo.save(assessment_doc)

            # Persist risk scores in batch
            self._assessment_repo.batch_save_risk_scores(
                assessment_id,
                [
                    {
                        "category": rs.category,
                        "score": rs.score,
                        "rationale": rs.rationale,
                    }
                    for rs in risk_assessment.risk_scores
                ],
            )

        # Persist opportunities in batch (only if we have a valid assessment).
        # ``model_dump()`` carries every field defined on the Opportunity
        # Pydantic model — so when the model grows new fields (Phase 14
        # added ``investment_value_usd`` and ``roi_estimate_pct`` for the
        # ROI x Investment matrix), they flow through automatically.
        # Previously this was a hand-rolled dict literal that silently
        # dropped any field not listed by name; that bug shipped the
        # matrix as a blank chart until production telemetry caught it.
        if opportunity_result and risk_assessment:
            self._assessment_repo.batch_save_opportunities(
                assessment_id,
                [opp.model_dump() for opp in opportunity_result.opportunities],
            )

            # Save top actions as part of company metadata
            self._company_repo.update_company_metadata(
                company_id,
                {
                    "top_actions": opportunity_result.top_three_immediate_actions,
                },
            )

        # Persist value chain (only if we have a valid assessment to attach it to)
        value_chain = company.value_chain
        if value_chain and assessment_id:
            self._assessment_repo.save_value_chain(
                assessment_id,
                {
                    "steps": [step.model_dump() for step in value_chain.steps],
                    "summary": value_chain.summary,
                    "grounded": value_chain.grounded,
                    "insufficient_data_reason": value_chain.insufficient_data_reason,
                    "provenance_basis": value_chain.provenance_basis,
                },
            )

        # Persist EBITDA tree (only if we have a valid assessment to attach it to)
        ebitda_tree = company.ebitda_tree
        if ebitda_tree and assessment_id:
            self._assessment_repo.save_ebitda_tree(
                assessment_id,
                {
                    "tree_data": [node.model_dump() for node in ebitda_tree.nodes],
                    "revenue_estimate": ebitda_tree.revenue_estimate,
                    "ebitda_estimate": ebitda_tree.ebitda_estimate,
                    "business_model_summary": ebitda_tree.summary,
                    "grounded": ebitda_tree.grounded,
                    "insufficient_data_reason": ebitda_tree.insufficient_data_reason,
                },
            )

        # Persist the AI-generated Balanced Scorecard strategy map.
        # Serialised by Pydantic with by_alias=True so the on-disk +
        # API-visible payload uses camelCase keys (matching the JSON
        # schema and the frontend `AnalysisData.strategyMap` shape).
        strategy_map = company.strategy_map
        if strategy_map and assessment_id:
            self._assessment_repo.save_strategy_map(
                assessment_id,
                strategy_map.model_dump(by_alias=True),
            )

        self.request_executor.add_details(timer.to_details())
        self.request_executor.mark_question_complete("persist_results")

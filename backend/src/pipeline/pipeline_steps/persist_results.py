"""Stage 4: Persist analysis results to DynamoDB.

Ports the DB write logic from pe-scan/src/app/api/scan/start/route.ts.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast

from signalfield_core.pipeline.step import RequestStep

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
        accessor = cast("CompanyAccessor", self.entity_accessor)
        company = accessor.company

        if not company.id:
            raise RuntimeError("Company ID must be set before persisting results")
        company_id = company.id
        accessor.set_id(company_id)

        profile = company.profile
        risk_assessment = company.risk_assessment
        opportunity_result = company.opportunity_result

        company_doc = {
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
        self._company_repo.save_company(company_id, company_doc)

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
            }
            self._assessment_repo.save_assessment(assessment_id, assessment_doc)

            # Persist individual risk scores
            for rs in risk_assessment.risk_scores:
                self._assessment_repo.save_risk_score(
                    assessment_id,
                    rs.category,
                    {
                        "score": rs.score,
                        "explanation": rs.explanation,
                        "evidence": rs.evidence,
                    },
                )

        # Persist opportunities (only if we have a valid assessment to attach them to)
        if opportunity_result and risk_assessment:
            for i, opp in enumerate(opportunity_result.opportunities):
                self._assessment_repo.save_opportunity(
                    assessment_id,
                    i,
                    {
                        "title": opp.title,
                        "risk_mitigated": opp.risk_mitigated,
                        "impact_rating": opp.impact_rating,
                        "strategic_category": opp.strategic_category,
                        "description": opp.description,
                        "implementation_steps": opp.implementation_steps,
                        "timeline": opp.timeline,
                        "investment_range": opp.investment_range,
                        "roi_estimate": opp.roi_estimate,
                        "related_services": opp.related_services,
                    },
                )

            # Save top actions as part of company metadata
            self._company_repo.update_company_metadata(
                company_id,
                {
                    "top_actions": opportunity_result.top_three_immediate_actions,
                },
            )

        self.request_executor.mark_question_complete("persist_results")

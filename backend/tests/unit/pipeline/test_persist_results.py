"""Tests for PersistResults pipeline step."""

from unittest.mock import MagicMock

import pytest

from src.facades.company_accessor import CompanyAccessor
from src.models.model_company import (
    Company,
    CompanyProfile,
    Opportunity,
    OpportunityResult,
    RiskAssessment,
    RiskScore,
)
from src.pipeline.pipeline_steps.persist_results import PersistResults


class TestPersistResults:
    def _make_full_company(self):
        return Company(
            id="comp-1",
            url="https://example.com",
            org_id="org-1",
            profile=CompanyProfile(
                company_name="Test Corp",
                industry="SaaS",
                industry_sector="Technology",
            ),
            risk_assessment=RiskAssessment(
                risk_scores=[
                    RiskScore(category="competitive_displacement", score=7),
                    RiskScore(category="data_ip", score=3),
                ],
                overall_score=5.0,
                tier="moderate",
                top_risks=["competitive_displacement"],
                analysis_summary="Moderate risk",
            ),
            opportunity_result=OpportunityResult(
                opportunities=[
                    Opportunity(title="Deploy AI", risk_mitigated="competitive_displacement"),
                ],
                top_three_immediate_actions=["Action 1"],
            ),
        )

    def test_persist_with_repos(self):
        company = self._make_full_company()
        accessor = CompanyAccessor(company)

        mock_company_repo = MagicMock()
        mock_assessment_repo = MagicMock()
        mock_assessment_repo.save_assessment.return_value = "assess-new"

        step = PersistResults(
            company_repo=mock_company_repo,
            assessment_repo=mock_assessment_repo,
        )
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        step.execute()

        mock_company_repo.save_company.assert_called_once()
        mock_assessment_repo.save_assessment.assert_called_once()
        assert mock_assessment_repo.save_risk_score.call_count == 2
        assert mock_assessment_repo.save_opportunity.call_count == 1
        step._request_executor.mark_question_complete.assert_called_with("persist_results")

    def test_persist_company_id_none_raises(self):
        company = Company(
            id="",
            url="https://example.com",
            profile=CompanyProfile(company_name="Test", industry="Tech"),
        )
        accessor = CompanyAccessor(company)

        step = PersistResults(
            company_repo=MagicMock(),
            assessment_repo=MagicMock(),
        )
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        with pytest.raises(RuntimeError, match="Company ID must be set"):
            step.execute()

    def test_persist_without_risk_assessment_skips_opportunities(self):
        company = Company(
            id="comp-1",
            url="https://example.com",
            profile=CompanyProfile(company_name="Test", industry="Tech"),
            opportunity_result=OpportunityResult(
                opportunities=[Opportunity(title="Opp")],
                top_three_immediate_actions=[],
            ),
        )
        accessor = CompanyAccessor(company)

        mock_company_repo = MagicMock()
        mock_assessment_repo = MagicMock()

        step = PersistResults(
            company_repo=mock_company_repo,
            assessment_repo=mock_assessment_repo,
        )
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        step.execute()

        mock_assessment_repo.save_assessment.assert_not_called()
        mock_assessment_repo.save_opportunity.assert_not_called()

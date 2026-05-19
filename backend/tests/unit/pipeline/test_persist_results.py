"""Tests for PersistResults pipeline step."""

from unittest.mock import MagicMock

import pytest

from src.facades.company_accessor import CompanyAccessor
from src.models.model_company import (
    Company,
    CompanyProfile,
    EbitdaNode,
    EbitdaTreeResult,
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
                    Opportunity(title="Deploy AI", value_lever="Revenue Side"),
                ],
                top_three_immediate_actions=["Action 1"],
            ),
        )

    def test_persist_with_repos(self):
        company = self._make_full_company()
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

        mock_company_repo.save.assert_called_once()
        mock_assessment_repo.save.assert_called_once()
        mock_assessment_repo.batch_save_risk_scores.assert_called_once()
        mock_assessment_repo.batch_save_opportunities.assert_called_once()

        # Verify risk scores batch call content
        risk_call_args = mock_assessment_repo.batch_save_risk_scores.call_args[0]
        assert len(risk_call_args[1]) == 2  # 2 risk scores

        # Verify opportunities batch call content
        opp_call_args = mock_assessment_repo.batch_save_opportunities.call_args[0]
        assert len(opp_call_args[1]) == 1  # 1 opportunity
        assert opp_call_args[1][0]["value_lever"] == "Revenue Side"

        step._request_executor.mark_question_complete.assert_called_with("persist_results")

    def test_persist_writes_created_by_when_user_id_present(self):
        """`created_by` is written on the company doc when the Sc0redServicesEvent
        carried a user_id through to the pipeline. Read by the activity
        feed for `analysis_completed` events. See
        `openspec/changes/fix-actor-attribution/`.
        """
        company = self._make_full_company()
        company.user_id = "u-alice"
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

        saved_doc = mock_company_repo.save.call_args[0][0]
        assert saved_doc.get("created_by") == "u-alice"

    def test_persist_skips_created_by_when_user_id_absent(self):
        """Defensive: pipelines triggered without a user context (e.g.
        engineer-run scripts) do not write a `created_by` field. The
        activity feed renders "An analyst" for these records, which is
        the right placeholder.
        """
        company = self._make_full_company()
        # company.user_id stays at its default ""
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

        saved_doc = mock_company_repo.save.call_args[0][0]
        assert "created_by" not in saved_doc

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

    def test_persist_with_ebitda_tree(self):
        company = self._make_full_company()
        company.ebitda_tree = EbitdaTreeResult(
            summary="SaaS economics overview",
            revenue_estimate="$10M-$50M",
            ebitda_estimate="$2M-$8M",
            nodes=[
                EbitdaNode(
                    id="revenue",
                    label="Total Revenue",
                    type="revenue",
                    description="All revenue",
                    linked_opportunity_indices=[0],
                ),
            ],
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

        mock_assessment_repo.save_ebitda_tree.assert_called_once()
        call_args = mock_assessment_repo.save_ebitda_tree.call_args[0]
        ebitda_data = call_args[1]
        assert ebitda_data["revenue_estimate"] == "$10M-$50M"
        assert ebitda_data["ebitda_estimate"] == "$2M-$8M"
        assert ebitda_data["business_model_summary"] == "SaaS economics overview"
        assert len(ebitda_data["tree_data"]) == 1

    def test_persist_without_ebitda_tree_skips(self):
        company = self._make_full_company()
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

        mock_assessment_repo.save_ebitda_tree.assert_not_called()

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

        mock_assessment_repo.save.assert_not_called()
        mock_assessment_repo.batch_save_opportunities.assert_not_called()

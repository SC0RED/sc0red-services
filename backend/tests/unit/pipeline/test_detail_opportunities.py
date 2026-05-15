"""Tests for DetailOpportunities pipeline step."""

from unittest.mock import MagicMock

import pytest

from src.facades.company_accessor import CompanyAccessor
from src.models.model_company import (
    Company,
    CompanyProfile,
    RiskAssessment,
    RiskScore,
)
from src.pipeline.pipeline_steps.detail_opportunities import DetailOpportunities


def _make_ranked_ideation(
    title: str = "Deploy AI Chatbot",
    value_lever: str = "Both",
    risk_category: str = "competitive_displacement",
    impact_rating: str = "High",
    top_actions: list[str] | None = None,
) -> dict:
    return {
        "title": title,
        "description": "Build a customer-facing AI chatbot",
        "value_lever": value_lever,
        "strategic_category": "Competitive Moat",
        "impact_rating": impact_rating,
        "risk_category": risk_category,
        "top_three_immediate_actions": top_actions or ["Action 1", "Action 2", "Action 3"],
    }


def _make_detail_response() -> dict:
    return {
        "implementation_steps": ["Step 1", "Step 2", "Step 3"],
        "timeline": "Medium-term (3-9 months)",
        "investment_range": "$100K-$500K",
        "roi_estimate": "30% improvement in support efficiency",
    }


def _make_company(ideation_count: int = 3) -> Company:
    company = Company(url="https://example.com")
    company.profile = CompanyProfile(
        company_name="Test Corp",
        industry="SaaS",
        industry_sector="Technology",
        business_model="SaaS",
        company_size="Mid-market 200-1000",
    )
    company.risk_assessment = RiskAssessment(
        risk_scores=[RiskScore(category="competitive_displacement", score=8)],
        overall_score=7.0,
        tier="high",
        top_risks=["competitive_displacement"],
        analysis_summary="High competitive risk",
    )
    company.ranked_ideations = [
        _make_ranked_ideation(
            title=f"AI Opportunity {i + 1}",
            value_lever=["Revenue Side", "Cost Side", "Both"][i % 3],
        )
        for i in range(ideation_count)
    ]
    return company


def _make_mock_factory() -> MagicMock:
    mock_factory = MagicMock()
    mock_client = MagicMock()
    mock_factory.get_client.return_value = mock_client

    detail_response = MagicMock()
    detail_response.content = _make_detail_response()
    detail_response.metadata = {"tokens": 80}
    mock_client.query_structured.return_value = detail_response

    return mock_factory


class TestDetailOpportunities:
    def test_successful_with_three_ideations(self):
        mock_factory = _make_mock_factory()
        company = _make_company(ideation_count=3)
        accessor = CompanyAccessor(company)

        step = DetailOpportunities(ai_client_factory=mock_factory)
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        step.execute()

        result = accessor.company.opportunity_result
        assert result is not None
        assert len(result.opportunities) == 3
        assert result.opportunities[0].title == "AI Opportunity 1"

        for opp in result.opportunities:
            assert len(opp.implementation_steps) == 3
            assert opp.timeline == "Medium-term (3-9 months)"

        assert result.top_three_immediate_actions == ["Action 1", "Action 2", "Action 3"]
        assert mock_factory.get_client.call_count == 3

        calls = step._request_executor.mark_question_complete.call_args_list
        completed = {c[0][0] for c in calls}
        assert "generate_opportunities" in completed

    def test_all_calls_use_standard_precision(self):
        """Every DetailOpportunities AI call runs on Precision.STANDARD (gpt-5.4-mini).

        Initial draft of the 2026-05-15 migration pinned this step to
        ``Precision.ADVANCED``, but a re-read of the benchmark outputs
        showed mini's roi_estimate is structurally complete (lever,
        financial impact, payback period, driving action). The verbose
        gpt-5.1 ROI adds supporting math PE users can re-derive, and
        gpt-5.1 hits recurring ~3-minute tail-latency spikes on this
        call site (e.g., ``detail_3`` ran 201s in production on
        2026-05-15).

        If real PE users surface quality complaints post-deploy, the
        revert is one line in ``_run_ai_call``. This test pins the
        current routing so the revert is intentional, not accidental.
        """
        from signalfield_core.models.enums import Precision

        mock_factory = _make_mock_factory()
        company = _make_company(ideation_count=3)
        accessor = CompanyAccessor(company)
        step = DetailOpportunities(ai_client_factory=mock_factory)
        step._entity_accessor = accessor
        step._request_executor = MagicMock()
        step.execute()

        calls = mock_factory.get_client.call_args_list
        precisions = [c.kwargs["precision"] for c in calls]
        assert all(p == Precision.STANDARD for p in precisions), (
            f"DetailOpportunities must use Precision.STANDARD; got {precisions}"
        )

    def test_missing_profile_raises(self):
        company = Company(url="https://example.com")
        company.risk_assessment = RiskAssessment(overall_score=5.0)
        accessor = CompanyAccessor(company)

        step = DetailOpportunities(ai_client_factory=MagicMock())
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        with pytest.raises(ValueError, match="profile or risk assessment missing"):
            step.execute()

    def test_missing_factory_raises(self):
        company = _make_company()
        accessor = CompanyAccessor(company)

        step = DetailOpportunities(ai_client_factory=None)
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        with pytest.raises(RuntimeError, match="AI client factory not configured"):
            step.execute()

    def test_no_ranked_ideations_raises(self):
        company = _make_company()
        company.ranked_ideations = []
        accessor = CompanyAccessor(company)

        step = DetailOpportunities(ai_client_factory=MagicMock())
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        with pytest.raises(ValueError, match="No ranked ideations"):
            step.execute()

    def test_ai_call_failure_propagates(self):
        from signalfield_core.utilities.future_manager import FutureManagerError

        mock_factory = MagicMock()
        mock_client = MagicMock()
        mock_factory.get_client.return_value = mock_client
        mock_client.query_structured.side_effect = RuntimeError("AI service unavailable")

        company = _make_company()
        accessor = CompanyAccessor(company)

        step = DetailOpportunities(ai_client_factory=mock_factory)
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        with pytest.raises(FutureManagerError):
            step.execute()

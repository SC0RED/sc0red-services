"""Tests for GenerateOpportunities pipeline step."""

from unittest.mock import MagicMock

import pytest
from signalfield_core.models.enums import Precision, ReasoningEffort, Verbosity

from src.facades.company_accessor import CompanyAccessor
from src.models.model_company import Company, CompanyProfile, RiskAssessment, RiskScore
from src.pipeline.pipeline_steps.generate_opportunities import (
    _SYSTEM_PROMPT,
    GenerateOpportunities,
    _build_context_block,
    _build_high_priority_prompt,
    _build_strategic_prompt,
)


def _make_opportunity_data(
    title: str = "Deploy AI Chatbot",
    risk_mitigated: str = "competitive_displacement",
    value_lever: str = "Both",
) -> dict:
    return {
        "title": title,
        "risk_mitigated": risk_mitigated,
        "impact_rating": "High",
        "strategic_category": "Competitive Moat",
        "description": "Build a customer-facing AI chatbot",
        "implementation_steps": ["Step 1", "Step 2", "Step 3"],
        "timeline": "Medium-term (3-9 months)",
        "investment_range": "$100K-$500K",
        "roi_estimate": "30% improvement in support efficiency",
        "related_services": ["Accenture - AI strategy"],
        "value_lever": value_lever,
    }


class TestGenerateOpportunities:
    def _make_mock_factory(self, high_priority_data: dict, strategic_data: dict):
        """Create a mock AIClientFactory that dispatches by schema.

        Routes responses based on whether the schema requires top_three_immediate_actions
        (high-priority) or not (strategic), making the mock independent of call order.
        """
        mock_factory = MagicMock()
        mock_client = MagicMock()
        mock_factory.get_client.return_value = mock_client

        response_high = MagicMock()
        response_high.content = high_priority_data
        response_strategic = MagicMock()
        response_strategic.content = strategic_data

        def dispatch_by_schema(*, input_text, json_schema):
            if "top_three_immediate_actions" in json_schema.get("required", []):
                return response_high
            return response_strategic

        mock_client.query_structured.side_effect = dispatch_by_schema
        return mock_factory

    def _make_company_with_profile_and_risk(self) -> Company:
        company = Company(url="https://example.com")
        company.profile = CompanyProfile(
            company_name="Test Corp",
            industry="SaaS",
            industry_sector="Technology",
            business_model="SaaS",
        )
        company.risk_assessment = RiskAssessment(
            risk_scores=[
                RiskScore(category="competitive_displacement", score=8),
                RiskScore(category="technology_obsolescence", score=7),
                RiskScore(category="talent_workforce", score=6),
            ],
            overall_score=7.0,
            tier="high",
            top_risks=[
                "competitive_displacement",
                "technology_obsolescence",
                "talent_workforce",
            ],
            analysis_summary="High competitive risk",
        )
        return company

    def test_successful_parallel_generation(self):
        high_priority_data = {
            "opportunities": [
                _make_opportunity_data("AI Chatbot", "competitive_displacement"),
                _make_opportunity_data("Tech Upgrade", "technology_obsolescence"),
            ],
            "top_three_immediate_actions": ["Action 1", "Action 2", "Action 3"],
        }
        strategic_data = {
            "opportunities": [
                _make_opportunity_data("Compliance Bot", "regulatory_compliance", "Cost Side"),
            ],
        }
        mock_factory = self._make_mock_factory(high_priority_data, strategic_data)

        company = self._make_company_with_profile_and_risk()
        accessor = CompanyAccessor(company)

        step = GenerateOpportunities(ai_client_factory=mock_factory)
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        step.execute()

        result = accessor.company.opportunity_result
        assert result is not None
        assert len(result.opportunities) == 3
        assert result.opportunities[0].title == "AI Chatbot"
        assert result.opportunities[1].title == "Tech Upgrade"
        assert result.opportunities[2].title == "Compliance Bot"
        assert result.opportunities[2].value_lever == "Cost Side"
        assert result.top_three_immediate_actions == ["Action 1", "Action 2", "Action 3"]

        # Two AI calls should have been made (parallel), both with instructions
        assert mock_factory.get_client.call_count == 2
        mock_factory.get_client.assert_called_with(
            verbosity=Verbosity.MEDIUM,
            reasoning_effort=ReasoningEffort.LOW,
            precision=Precision.STANDARD,
            instructions=_SYSTEM_PROMPT,
        )
        assert mock_client_query_count(mock_factory) == 2

    def test_top_actions_come_from_high_priority_call(self):
        """top_three_immediate_actions must come from the high-priority call only."""
        high_priority_data = {
            "opportunities": [_make_opportunity_data()],
            "top_three_immediate_actions": ["Urgent 1", "Urgent 2", "Urgent 3"],
        }
        strategic_data = {
            "opportunities": [_make_opportunity_data("Strategic Opp", "data_ip")],
        }
        mock_factory = self._make_mock_factory(high_priority_data, strategic_data)

        company = self._make_company_with_profile_and_risk()
        accessor = CompanyAccessor(company)

        step = GenerateOpportunities(ai_client_factory=mock_factory)
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        step.execute()

        result = accessor.company.opportunity_result
        assert result is not None
        assert result.top_three_immediate_actions == ["Urgent 1", "Urgent 2", "Urgent 3"]

    def test_missing_profile_raises(self):
        company = Company(url="https://example.com")
        company.risk_assessment = RiskAssessment(overall_score=5.0)
        accessor = CompanyAccessor(company)

        step = GenerateOpportunities(ai_client_factory=MagicMock())
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        with pytest.raises(ValueError, match="profile or risk assessment missing"):
            step.execute()

    def test_missing_risk_assessment_raises(self):
        company = Company(url="https://example.com")
        company.profile = CompanyProfile(company_name="Test", industry="Tech")
        accessor = CompanyAccessor(company)

        step = GenerateOpportunities(ai_client_factory=MagicMock())
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        with pytest.raises(ValueError, match="profile or risk assessment missing"):
            step.execute()

    def test_missing_factory_raises(self):
        company = self._make_company_with_profile_and_risk()
        accessor = CompanyAccessor(company)

        step = GenerateOpportunities(ai_client_factory=None)
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        with pytest.raises(RuntimeError, match="AI client factory not configured"):
            step.execute()

    def test_ai_call_failure_propagates(self):
        """If one AI call fails, the exception should propagate."""
        mock_factory = MagicMock()
        mock_client = MagicMock()
        mock_factory.get_client.return_value = mock_client
        mock_client.query_structured.side_effect = RuntimeError("AI service unavailable")

        company = self._make_company_with_profile_and_risk()
        accessor = CompanyAccessor(company)

        step = GenerateOpportunities(ai_client_factory=mock_factory)
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        with pytest.raises(RuntimeError, match="AI service unavailable"):
            step.execute()

    def test_category_split_uses_top_risks(self):
        """High-priority prompt should target top_risks, strategic prompt the rest."""
        company = self._make_company_with_profile_and_risk()
        profile_dict = company.profile.model_dump()
        assessment_dict = company.risk_assessment.model_dump()
        top_risks = company.risk_assessment.top_risks[:3]

        high_prompt = _build_high_priority_prompt(profile_dict, assessment_dict, top_risks)
        assert "competitive_displacement" in high_prompt
        assert "technology_obsolescence" in high_prompt
        assert "highest-priority" in high_prompt.lower()

        other_categories = [
            "margin_compression", "customer_behavior",
            "regulatory_compliance", "supply_chain", "data_ip",
        ]
        strategic_prompt = _build_strategic_prompt(profile_dict, assessment_dict, other_categories)
        assert "margin_compression" in strategic_prompt
        assert "strategic" in strategic_prompt.lower()


class TestPromptBuilders:
    def test_context_block_includes_profile_and_scores(self):
        profile = {"company_name": "Acme", "industry": "Tech"}
        assessment = {
            "risk_scores": [{"category": "data_ip", "score": 5}],
            "overall_score": 5.0,
            "tier": "moderate",
            "top_risks": ["data_ip"],
            "analysis_summary": "Moderate risk",
        }
        context = _build_context_block(profile, assessment)
        assert "Acme" in context
        assert "data_ip" in context
        assert "5.0/10" in context

    def test_high_priority_prompt_includes_actions_instruction(self):
        assessment = {
            "risk_scores": [],
            "overall_score": 5.0,
            "tier": "moderate",
            "top_risks": ["data_ip"],
            "analysis_summary": "Test summary",
        }
        prompt = _build_high_priority_prompt({}, assessment, ["data_ip"])
        assert "top_three_immediate_actions" in prompt
        assert "2-3 high-priority" in prompt

    def test_strategic_prompt_excludes_actions_instruction(self):
        assessment = {
            "risk_scores": [],
            "overall_score": 5.0,
            "tier": "moderate",
            "top_risks": ["data_ip"],
            "analysis_summary": "Test summary",
        }
        prompt = _build_strategic_prompt({}, assessment, ["data_ip"])
        assert "Do NOT include top_three_immediate_actions" in prompt
        assert "1-2 strategic" in prompt


def mock_client_query_count(mock_factory: MagicMock) -> int:
    """Count total query_structured calls across all clients from the factory."""
    mock_client = mock_factory.get_client.return_value
    return mock_client.query_structured.call_count

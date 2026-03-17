"""Tests for ParallelProfileAndRisk composite pipeline step."""

from unittest.mock import MagicMock, call

import pytest
from signalfield_core.models.enums import Precision, ReasoningEffort, Verbosity

from src.facades.company_accessor import CompanyAccessor
from src.models.model_company import Company
from src.pipeline.pipeline_steps.assess_risk import RISK_SYSTEM_PROMPT
from src.pipeline.pipeline_steps.extract_profile import PROFILE_SYSTEM_PROMPT
from src.pipeline.pipeline_steps.parallel_profile_risk import ParallelProfileAndRisk


_PROFILE_RESPONSE = {
    "company_name": "Acme Corp",
    "industry": "B2B SaaS - HR Technology",
    "industry_sector": "Technology",
    "business_model": "SaaS",
    "description": "HR platform for mid-market",
    "products_services": ["ATS", "Payroll"],
    "target_market": "Mid-market companies",
    "company_size": "Mid-market 200-1000",
    "revenue_model": "subscription",
    "tech_signals": ["React", "AWS"],
    "competitive_positioning": "AI-first HR",
    "ai_maturity": "Partial adoption",
    "key_risks_visible": [],
}

_RISK_RESPONSE = {
    "risk_scores": [
        {
            "category": "competitive_displacement",
            "score": 7,
            "rationale": "High competition in the space",
        },
        {
            "category": "technology_obsolescence",
            "score": 4,
            "rationale": "Moderate risk due to some legacy systems",
        },
    ],
    "overall_score": 5.5,
    "tier": "moderate",
    "top_risks": ["competitive_displacement"],
    "analysis_summary": "Moderate overall risk",
}


class TestParallelProfileAndRisk:
    def _make_mock_factory(
        self,
        profile_data: dict = _PROFILE_RESPONSE,
        risk_data: dict = _RISK_RESPONSE,
    ) -> MagicMock:
        """Create a mock AIClientFactory returning different data per call.

        The composite step calls get_client() twice (once per thread) with different
        system prompts. We use side_effect to return separate mock clients.
        """
        mock_factory = MagicMock()

        profile_client = MagicMock()
        profile_response = MagicMock()
        profile_response.content = profile_data
        profile_client.query_structured.return_value = profile_response

        risk_client = MagicMock()
        risk_response = MagicMock()
        risk_response.content = risk_data
        risk_client.query_structured.return_value = risk_response

        def get_client_side_effect(**kwargs):
            if kwargs.get("instructions") == PROFILE_SYSTEM_PROMPT:
                return profile_client
            return risk_client

        mock_factory.get_client.side_effect = get_client_side_effect
        return mock_factory

    def _make_accessor(
        self,
        scraped_text: str = "Acme Corp is an HR technology company...",
        url: str = "https://acme.com",
        document_text: str | None = None,
    ) -> CompanyAccessor:
        company = Company(url=url)
        company.scraped_text = scraped_text
        if document_text:
            company.document_text = document_text
        return CompanyAccessor(company)

    def test_successful_parallel_execution(self):
        mock_factory = self._make_mock_factory()
        accessor = self._make_accessor()

        step = ParallelProfileAndRisk(ai_client_factory=mock_factory)
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        step.execute()

        # Both results are set on accessor
        assert accessor.company.profile is not None
        assert accessor.company.profile.company_name == "Acme Corp"
        assert accessor.company.profile.industry == "B2B SaaS - HR Technology"

        assert accessor.company.risk_assessment is not None
        assert accessor.company.risk_assessment.overall_score == 5.5
        assert len(accessor.company.risk_assessment.risk_scores) == 2

        # Both questions marked complete
        step._request_executor.mark_question_complete.assert_any_call("extract_profile")
        step._request_executor.mark_question_complete.assert_any_call("assess_risk")

        # Details added (timings)
        step._request_executor.add_details.assert_called_once()
        details = step._request_executor.add_details.call_args[0][0]
        assert "ParallelProfileAndRisk.timings" in details

    def test_two_ai_clients_created_with_correct_system_prompts(self):
        mock_factory = self._make_mock_factory()
        accessor = self._make_accessor()

        step = ParallelProfileAndRisk(ai_client_factory=mock_factory)
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        step.execute()

        # get_client called twice — once per thread
        assert mock_factory.get_client.call_count == 2
        expected_calls = [
            call(
                verbosity=Verbosity.MEDIUM,
                reasoning_effort=ReasoningEffort.LOW,
                precision=Precision.STANDARD,
                instructions=PROFILE_SYSTEM_PROMPT,
            ),
            call(
                verbosity=Verbosity.MEDIUM,
                reasoning_effort=ReasoningEffort.LOW,
                precision=Precision.STANDARD,
                instructions=RISK_SYSTEM_PROMPT,
            ),
        ]
        mock_factory.get_client.assert_has_calls(expected_calls, any_order=True)

    def test_includes_document_text_in_prompts(self):
        mock_factory = self._make_mock_factory()
        accessor = self._make_accessor(document_text="Investment memo: Revenue is $50M annually.")

        step = ParallelProfileAndRisk(ai_client_factory=mock_factory)
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        step.execute()

        # Check both AI calls received prompts with document text
        profile_client = mock_factory.get_client(instructions=PROFILE_SYSTEM_PROMPT)
        risk_client = mock_factory.get_client(instructions=RISK_SYSTEM_PROMPT)

        profile_prompt = profile_client.query_structured.call_args[1]["input_text"]
        risk_prompt = risk_client.query_structured.call_args[1]["input_text"]

        assert "SUPPLEMENTARY DOCUMENTS" in profile_prompt
        assert "Investment memo" in profile_prompt
        assert "SUPPLEMENTARY DOCUMENTS" in risk_prompt
        assert "Investment memo" in risk_prompt

    def test_incomplete_profile_raises(self):
        mock_factory = self._make_mock_factory(
            profile_data={
                "company_name": "",
                "industry": "",
            }
        )
        accessor = self._make_accessor()

        step = ParallelProfileAndRisk(ai_client_factory=mock_factory)
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        with pytest.raises(ValueError, match="incomplete data"):
            step.execute()

    def test_empty_risk_scores_raises(self):
        mock_factory = self._make_mock_factory(
            risk_data={
                "risk_scores": [],
                "overall_score": 0,
                "tier": "low",
                "top_risks": [],
                "analysis_summary": "No risks",
            }
        )
        accessor = self._make_accessor()

        step = ParallelProfileAndRisk(ai_client_factory=mock_factory)
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        with pytest.raises(ValueError, match="no risk scores"):
            step.execute()

    def test_no_ai_factory_raises(self):
        accessor = self._make_accessor()

        step = ParallelProfileAndRisk(ai_client_factory=None)
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        with pytest.raises(RuntimeError, match="AI client factory not configured"):
            step.execute()

    def test_ai_call_failure_propagates(self):
        mock_factory = MagicMock()
        mock_client = MagicMock()
        mock_factory.get_client.return_value = mock_client
        mock_client.query_structured.side_effect = RuntimeError("API down")

        accessor = self._make_accessor()

        step = ParallelProfileAndRisk(ai_client_factory=mock_factory)
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        with pytest.raises(RuntimeError, match="API down"):
            step.execute()

    def test_uses_actual_url_when_available(self):
        mock_factory = self._make_mock_factory()
        company = Company(url="https://original.com")
        company.scraped_text = "Some content"
        company.actual_url = "https://resolved.com"
        accessor = CompanyAccessor(company)

        step = ParallelProfileAndRisk(ai_client_factory=mock_factory)
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        step.execute()

        # The profile prompt should contain the resolved URL
        profile_client = mock_factory.get_client(instructions=PROFILE_SYSTEM_PROMPT)
        profile_prompt = profile_client.query_structured.call_args[1]["input_text"]
        assert "https://resolved.com" in profile_prompt

    def test_risk_prompt_contains_scraped_text(self):
        mock_factory = self._make_mock_factory()
        accessor = self._make_accessor(scraped_text="Unique website content for testing")

        step = ParallelProfileAndRisk(ai_client_factory=mock_factory)
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        step.execute()

        risk_client = mock_factory.get_client(instructions=RISK_SYSTEM_PROMPT)
        risk_prompt = risk_client.query_structured.call_args[1]["input_text"]
        assert "Unique website content for testing" in risk_prompt
        assert "RISK CATEGORIES TO ASSESS" in risk_prompt

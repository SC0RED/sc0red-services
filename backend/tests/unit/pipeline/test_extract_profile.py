"""Tests for ExtractProfile pipeline step."""

from unittest.mock import MagicMock

import pytest
from signalfield_core.models.enums import Precision, ReasoningEffort, Verbosity

from src.facades.company_accessor import CompanyAccessor
from src.models.model_company import Company
from src.pipeline.pipeline_steps.extract_profile import ExtractProfile


class TestExtractProfile:
    def _make_mock_factory(self, response_data):
        """Create a mock AIClientFactory that returns structured response data."""
        mock_factory = MagicMock()
        mock_client = MagicMock()
        mock_factory.get_client.return_value = mock_client
        mock_response = MagicMock()
        mock_response.content = response_data
        mock_client.query_structured.return_value = mock_response
        return mock_factory

    def test_successful_extraction(self):
        profile_data = {
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
        mock_factory = self._make_mock_factory(profile_data)

        company = Company(url="https://acme.com")
        company.scraped_text = "Acme Corp is an HR technology company..."
        accessor = CompanyAccessor(company)

        step = ExtractProfile(ai_client_factory=mock_factory)
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        step.execute()

        assert accessor.company.profile is not None
        assert accessor.company.profile.company_name == "Acme Corp"
        assert accessor.company.profile.industry == "B2B SaaS - HR Technology"
        step._request_executor.mark_question_complete.assert_called_with("extract_profile")

        from src.pipeline.pipeline_steps.extract_profile import _SYSTEM_PROMPT

        mock_factory.get_client.assert_called_once_with(
            verbosity=Verbosity.MEDIUM,
            reasoning_effort=ReasoningEffort.LOW,
            precision=Precision.STANDARD,
            instructions=_SYSTEM_PROMPT,
        )

    def test_incomplete_profile_raises(self):
        mock_factory = self._make_mock_factory(
            {
                "company_name": "",
                "industry": "",
            }
        )

        company = Company(url="https://example.com")
        company.scraped_text = "Some content here"
        accessor = CompanyAccessor(company)

        step = ExtractProfile(ai_client_factory=mock_factory)
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        with pytest.raises(ValueError, match="incomplete data"):
            step.execute()

    def test_includes_document_text_in_prompt(self):
        profile_data = {
            "company_name": "Acme Corp",
            "industry": "B2B SaaS",
            "industry_sector": "Technology",
            "business_model": "SaaS",
            "description": "Test",
            "products_services": [],
            "target_market": "Enterprise",
            "company_size": "Mid-market 200-1000",
            "revenue_model": "subscription",
            "tech_signals": [],
            "competitive_positioning": "AI-first",
            "ai_maturity": "Early exploration",
            "key_risks_visible": [],
        }
        mock_factory = self._make_mock_factory(profile_data)
        mock_client = mock_factory.get_client.return_value

        company = Company(url="https://acme.com")
        company.scraped_text = "Acme Corp website content"
        company.document_text = "Investment memo: Revenue is $50M annually."
        accessor = CompanyAccessor(company)

        step = ExtractProfile(ai_client_factory=mock_factory)
        step._entity_accessor = accessor
        step._request_executor = MagicMock()
        step.execute()

        prompt_sent = mock_client.query_structured.call_args[1]["input_text"]
        assert "SUPPLEMENTARY DOCUMENTS" in prompt_sent
        assert "Investment memo: Revenue is $50M annually." in prompt_sent
        # System prompt should NOT be in user prompt — it goes via instructions param
        assert "senior business intelligence analyst" not in prompt_sent

    def test_omits_document_section_when_no_documents(self):
        profile_data = {
            "company_name": "Acme Corp",
            "industry": "B2B SaaS",
            "industry_sector": "Technology",
            "business_model": "SaaS",
            "description": "Test",
            "products_services": [],
            "target_market": "Enterprise",
            "company_size": "Mid-market 200-1000",
            "revenue_model": "subscription",
            "tech_signals": [],
            "competitive_positioning": "AI-first",
            "ai_maturity": "Early exploration",
            "key_risks_visible": [],
        }
        mock_factory = self._make_mock_factory(profile_data)
        mock_client = mock_factory.get_client.return_value

        company = Company(url="https://acme.com")
        company.scraped_text = "Acme Corp website content"
        accessor = CompanyAccessor(company)

        step = ExtractProfile(ai_client_factory=mock_factory)
        step._entity_accessor = accessor
        step._request_executor = MagicMock()
        step.execute()

        prompt_sent = mock_client.query_structured.call_args[1]["input_text"]
        assert "SUPPLEMENTARY DOCUMENTS" not in prompt_sent
        assert "senior business intelligence analyst" not in prompt_sent

"""Tests for ExtractProfile pipeline step."""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.facades.company_accessor import CompanyAccessor
from src.models.model_company import Company
from src.pipeline.pipeline_steps.extract_profile import ExtractProfile


class TestExtractProfile:
    def _make_mock_response(self, data):
        """Create a mock OpenAI response."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps(data)
        return mock_response

    @patch("src.pipeline.pipeline_steps.extract_profile.openai.OpenAI")
    def test_successful_extraction(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

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
        mock_client.chat.completions.create.return_value = self._make_mock_response(profile_data)

        company = Company(url="https://acme.com")
        company.scraped_text = "Acme Corp is an HR technology company..."
        accessor = CompanyAccessor(company)

        step = ExtractProfile(openai_api_key="test-key")
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        step.execute()

        assert accessor.company.profile is not None
        assert accessor.company.profile.company_name == "Acme Corp"
        assert accessor.company.profile.industry == "B2B SaaS - HR Technology"
        step._request_executor.mark_question_complete.assert_called_with("extract_profile")

    @patch("src.pipeline.pipeline_steps.extract_profile.openai.OpenAI")
    def test_incomplete_profile_raises(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        mock_client.chat.completions.create.return_value = self._make_mock_response({
            "company_name": "",
            "industry": "",
        })

        company = Company(url="https://example.com")
        company.scraped_text = "Some content here"
        accessor = CompanyAccessor(company)

        step = ExtractProfile(openai_api_key="test-key")
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        with pytest.raises(ValueError, match="incomplete data"):
            step.execute()

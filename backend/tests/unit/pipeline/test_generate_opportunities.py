"""Tests for GenerateOpportunities pipeline step."""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.facades.company_accessor import CompanyAccessor
from src.models.model_company import Company, CompanyProfile, RiskAssessment, RiskScore
from src.pipeline.pipeline_steps.generate_opportunities import GenerateOpportunities


class TestGenerateOpportunities:
    def _make_mock_response(self, data):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps(data)
        return mock_response

    def _make_company_with_profile_and_risk(self):
        company = Company(url="https://example.com")
        company.profile = CompanyProfile(
            company_name="Test Corp",
            industry="SaaS",
            industry_sector="Technology",
            business_model="SaaS",
        )
        company.risk_assessment = RiskAssessment(
            risk_scores=[RiskScore(category="competitive_displacement", score=7)],
            overall_score=7.0,
            tier="high",
            top_risks=["competitive_displacement"],
            analysis_summary="High competitive risk",
        )
        return company

    @patch("src.pipeline.pipeline_steps.generate_opportunities.openai.OpenAI")
    def test_successful_generation(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        opp_data = {
            "opportunities": [
                {
                    "title": "Deploy AI Chatbot",
                    "risk_mitigated": "competitive_displacement",
                    "impact_rating": "High",
                    "strategic_category": "Competitive Moat",
                    "description": "Build a customer-facing AI chatbot",
                    "implementation_steps": ["Step 1", "Step 2"],
                    "timeline": "Medium-term (3-9 months)",
                    "investment_range": "$100K-$500K",
                    "roi_estimate": "30% improvement in support efficiency",
                    "related_services": [
                        {
                            "service_type": "AI Consulting",
                            "vendors": [
                                {
                                    "name": "Accenture",
                                    "url": "https://accenture.com",
                                    "specialty": "AI strategy",
                                }
                            ],
                        }
                    ],
                }
            ],
            "top_three_immediate_actions": ["Action 1", "Action 2", "Action 3"],
        }
        mock_client.chat.completions.create.return_value = self._make_mock_response(opp_data)

        company = self._make_company_with_profile_and_risk()
        accessor = CompanyAccessor(company)

        step = GenerateOpportunities(openai_api_key="test-key")
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        step.execute()

        result = accessor.company.opportunity_result
        assert result is not None
        assert len(result.opportunities) == 1
        assert result.opportunities[0].title == "Deploy AI Chatbot"
        assert len(result.opportunities[0].related_services) == 1
        assert len(result.top_three_immediate_actions) == 3

    @patch("src.pipeline.pipeline_steps.generate_opportunities.openai.OpenAI")
    def test_missing_profile_raises(self, mock_openai_cls):
        company = Company(url="https://example.com")
        company.risk_assessment = RiskAssessment(overall_score=5.0)
        accessor = CompanyAccessor(company)

        step = GenerateOpportunities(openai_api_key="test-key")
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        with pytest.raises(ValueError, match="profile or risk assessment missing"):
            step.execute()

    @patch("src.pipeline.pipeline_steps.generate_opportunities.openai.OpenAI")
    def test_missing_risk_assessment_raises(self, mock_openai_cls):
        company = Company(url="https://example.com")
        company.profile = CompanyProfile(company_name="Test", industry="Tech")
        accessor = CompanyAccessor(company)

        step = GenerateOpportunities(openai_api_key="test-key")
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        with pytest.raises(ValueError, match="profile or risk assessment missing"):
            step.execute()

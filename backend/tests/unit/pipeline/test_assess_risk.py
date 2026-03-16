"""Tests for AssessRisk pipeline step."""

from unittest.mock import MagicMock

import pytest
from signalfield_core.models.enums import Precision, ReasoningEffort, Verbosity

from src.facades.company_accessor import CompanyAccessor
from src.models.model_company import Company, CompanyProfile
from src.pipeline.pipeline_steps.assess_risk import AssessRisk


class TestAssessRisk:
    def _make_mock_factory(self, response_data):
        """Create a mock AIClientFactory that returns structured response data."""
        mock_factory = MagicMock()
        mock_client = MagicMock()
        mock_factory.get_client.return_value = mock_client
        mock_response = MagicMock()
        mock_response.content = response_data
        mock_client.query_structured.return_value = mock_response
        return mock_factory

    def test_successful_assessment(self):
        assessment_data = {
            "risk_scores": [
                {
                    "category": "competitive_displacement",
                    "score": 7,
                    "explanation": "High competition",
                    "evidence": "many competitors in the space",
                },
                {
                    "category": "technology_obsolescence",
                    "score": 4,
                    "explanation": "Moderate risk",
                    "evidence": "some legacy systems",
                },
            ],
            "overall_score": 5.5,
            "tier": "moderate",
            "top_risks": ["competitive_displacement"],
            "analysis_summary": "Moderate overall risk",
        }
        mock_factory = self._make_mock_factory(assessment_data)

        company = Company(url="https://example.com")
        company.scraped_text = "Content about the company"
        company.profile = CompanyProfile(
            company_name="Test Co",
            industry="SaaS",
            industry_sector="Technology",
        )
        accessor = CompanyAccessor(company)

        step = AssessRisk(ai_client_factory=mock_factory)
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        step.execute()

        assert accessor.company.risk_assessment is not None
        assert accessor.company.risk_assessment.overall_score == 5.5
        assert len(accessor.company.risk_assessment.risk_scores) == 2
        step._request_executor.mark_question_complete.assert_called_with("assess_risk")
        mock_factory.get_client.assert_called_once_with(
            verbosity=Verbosity.MEDIUM,
            reasoning_effort=ReasoningEffort.LOW,
            precision=Precision.STANDARD,
        )

    def test_missing_profile_raises(self):
        company = Company(url="https://example.com")
        company.scraped_text = "content"
        accessor = CompanyAccessor(company)

        step = AssessRisk(ai_client_factory=MagicMock())
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        with pytest.raises(ValueError, match="no company profile"):
            step.execute()

    def test_empty_risk_scores_raises(self):
        mock_factory = self._make_mock_factory(
            {
                "risk_scores": [],
                "overall_score": 0,
                "tier": "low",
            }
        )

        company = Company(url="https://example.com")
        company.scraped_text = "content"
        company.profile = CompanyProfile(company_name="Test", industry="Tech")
        accessor = CompanyAccessor(company)

        step = AssessRisk(ai_client_factory=mock_factory)
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        with pytest.raises(ValueError, match="no risk scores"):
            step.execute()

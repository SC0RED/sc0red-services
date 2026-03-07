"""Tests for CompanyAnalysisFactory."""

from unittest.mock import MagicMock

from src.facades.company_accessor import CompanyAccessor
from src.models.model_company import Company
from src.pipeline.pipeline_factories.company_analysis_factory import CompanyAnalysisFactory
from src.pipeline.pipeline_steps.assess_risk import AssessRisk
from src.pipeline.pipeline_steps.extract_profile import ExtractProfile
from src.pipeline.pipeline_steps.generate_opportunities import GenerateOpportunities
from src.pipeline.pipeline_steps.persist_results import PersistResults
from src.pipeline.pipeline_steps.scrape_and_resolve import ScrapeAndResolveURL


class TestCompanyAnalysisFactory:
    def _make_factory(self):
        accessor = CompanyAccessor(Company(url="https://example.com"))
        mock_ai_factory = MagicMock()
        return CompanyAnalysisFactory(
            entity_accessor=accessor,
            ai_client_factory=mock_ai_factory,
            tenant_id="t-1",
            request_id="r-1",
        )

    def test_get_pipeline_returns_five_steps(self):
        factory = self._make_factory()
        pipeline = factory.get_pipeline()
        assert len(pipeline) == 5
        assert isinstance(pipeline[0], ScrapeAndResolveURL)
        assert isinstance(pipeline[1], ExtractProfile)
        assert isinstance(pipeline[2], AssessRisk)
        assert isinstance(pipeline[3], GenerateOpportunities)
        assert isinstance(pipeline[4], PersistResults)

    def test_build_executor_wires_accessor(self):
        factory = self._make_factory()
        executor = factory.build_executor()
        assert executor.tenant_id == "t-1"
        assert executor.request_id == "r-1"

    def test_execute_pipeline_runs_all_steps(self):
        factory = self._make_factory()
        # Mock the steps so they don't hit real APIs
        mock_steps = [MagicMock() for _ in range(5)]
        for i, step in enumerate(mock_steps):
            step.step_name.return_value = f"Step{i}"
        factory.get_pipeline = MagicMock(return_value=mock_steps)

        _executor = factory.execute_pipeline()
        for step in mock_steps:
            step.execute.assert_called_once()

    def test_factory_with_repos(self):
        accessor = CompanyAccessor(Company(url="https://example.com"))
        company_repo = MagicMock()
        assessment_repo = MagicMock()
        mock_ai_factory = MagicMock()
        factory = CompanyAnalysisFactory(
            entity_accessor=accessor,
            ai_client_factory=mock_ai_factory,
            company_repo=company_repo,
            assessment_repo=assessment_repo,
        )
        pipeline = factory.get_pipeline()
        persist_step = pipeline[4]
        assert isinstance(persist_step, PersistResults)

"""Tests for CompanyAnalysisFactory."""

from unittest.mock import MagicMock

from src.facades.company_accessor import CompanyAccessor
from src.models.model_company import Company
from src.pipeline.pipeline_factories.company_analysis_factory import CompanyAnalysisFactory
from src.pipeline.pipeline_steps.compute_ebitda_tree import ComputeEbitdaTree
from src.pipeline.pipeline_steps.compute_value_chain import ComputeValueChain
from src.pipeline.pipeline_steps.detail_opportunities import DetailOpportunities
from src.pipeline.pipeline_steps.generate_strategy_map import GenerateStrategyMap
from src.pipeline.pipeline_steps.parallel_profile_risk import ParallelProfileRiskAndIdeation
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

    def test_get_pipeline_returns_six_steps(self):
        # Per `strategy-map-on-demand` Phase C the auto-gen
        # `GenerateStrategyMap` step was lifted from this pipeline to a
        # dedicated SQS worker. The persisted analysis pipeline is now 6
        # steps (was 7) and the strategy-map artifact is generated
        # on-demand via the "Generate strategy map" button.
        factory = self._make_factory()
        pipeline = factory.get_pipeline()
        assert len(pipeline) == 6
        assert isinstance(pipeline[0], ScrapeAndResolveURL)
        assert isinstance(pipeline[1], ParallelProfileRiskAndIdeation)
        assert isinstance(pipeline[2], DetailOpportunities)
        assert isinstance(pipeline[3], ComputeEbitdaTree)
        assert isinstance(pipeline[4], ComputeValueChain)
        assert isinstance(pipeline[5], PersistResults)

    def test_pipeline_does_not_contain_generate_strategy_map(self):
        # Defends against an accidental re-introduction of the auto-gen
        # step. The strategy-map worker uses the same `GenerateStrategyMap`
        # class, so the import isn't dead — only the wiring into THIS
        # pipeline must stay removed.
        factory = self._make_factory()
        pipeline = factory.get_pipeline()
        assert not any(isinstance(step, GenerateStrategyMap) for step in pipeline)

    def test_build_executor_wires_accessor(self):
        factory = self._make_factory()
        executor = factory.build_executor()
        assert executor.tenant_id == "t-1"
        assert executor.request_id == "r-1"

    def test_execute_pipeline_runs_all_steps(self):
        factory = self._make_factory()
        mock_steps = [MagicMock() for _ in range(6)]
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
        persist_step = pipeline[5]
        assert isinstance(persist_step, PersistResults)

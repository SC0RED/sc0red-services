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

    def test_get_pipeline_returns_seven_steps(self):
        # Per `redesign-strategy-map` Phase 4 the strategy-map step is
        # back in the auto-pipeline (and the on-demand SQS worker that
        # ran it in isolation was deleted in the same change). The
        # pipeline runs every analysis end-to-end through to a persisted
        # strategy map without any user-driven trigger.
        factory = self._make_factory()
        pipeline = factory.get_pipeline()
        assert len(pipeline) == 7
        assert isinstance(pipeline[0], ScrapeAndResolveURL)
        assert isinstance(pipeline[1], ParallelProfileRiskAndIdeation)
        assert isinstance(pipeline[2], DetailOpportunities)
        assert isinstance(pipeline[3], ComputeEbitdaTree)
        assert isinstance(pipeline[4], ComputeValueChain)
        assert isinstance(pipeline[5], GenerateStrategyMap)
        assert isinstance(pipeline[6], PersistResults)

    def test_generate_strategy_map_sits_between_value_chain_and_persist(self):
        # Order matters: ``GenerateStrategyMap`` consumes the profile,
        # risk assessment, opportunities, EBITDA tree, and value chain
        # produced by the upstream steps, then ``PersistResults`` writes
        # the assembled map to DynamoDB alongside the other artifacts.
        factory = self._make_factory()
        pipeline = factory.get_pipeline()
        value_chain_index = next(
            i for i, step in enumerate(pipeline) if isinstance(step, ComputeValueChain)
        )
        strategy_index = next(
            i for i, step in enumerate(pipeline) if isinstance(step, GenerateStrategyMap)
        )
        persist_index = next(
            i for i, step in enumerate(pipeline) if isinstance(step, PersistResults)
        )
        assert value_chain_index < strategy_index < persist_index

    def test_build_executor_wires_accessor(self):
        factory = self._make_factory()
        executor = factory.build_executor()
        assert executor.tenant_id == "t-1"
        assert executor.request_id == "r-1"

    def test_execute_pipeline_runs_all_steps(self):
        factory = self._make_factory()
        mock_steps = [MagicMock() for _ in range(7)]
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
        persist_step = pipeline[6]
        assert isinstance(persist_step, PersistResults)

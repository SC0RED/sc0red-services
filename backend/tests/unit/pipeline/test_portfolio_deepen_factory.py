"""Tests for PortfolioDeepenFactory."""

from unittest.mock import MagicMock

from src.facades.company_accessor import CompanyAccessor
from src.models.model_company import Company
from src.pipeline.pipeline_factories.portfolio_deepen_factory import PortfolioDeepenFactory
from src.pipeline.pipeline_steps.deepen_portfolio import DeepenPortfolio
from src.pipeline.pipeline_steps.validate_portfolio import ValidatePortfolioCompanies

_SEED = [{"name": "Known", "url": "https://known.com"}]


class TestPortfolioDeepenFactory:
    def _make_factory(self):
        accessor = CompanyAccessor(Company(url="https://pefirm.com"))
        return PortfolioDeepenFactory(
            entity_accessor=accessor,
            tenant_id="t-1",
            request_id="r-1",
            seed_companies=_SEED,
        )

    def test_get_pipeline_returns_deepen_and_validate_steps(self):
        pipeline = self._make_factory().get_pipeline()
        assert len(pipeline) == 2
        assert isinstance(pipeline[0], DeepenPortfolio)
        assert isinstance(pipeline[1], ValidatePortfolioCompanies)
        # The seed is threaded into the deepen step.
        assert pipeline[0]._seed_companies == _SEED

    def test_build_executor(self):
        executor = self._make_factory().build_executor()
        assert executor.tenant_id == "t-1"
        assert executor.request_id == "r-1"

    def test_execute_pipeline(self):
        factory = self._make_factory()
        mock_step = MagicMock()
        mock_step.step_name.return_value = "DeepenPortfolio"
        factory.get_pipeline = MagicMock(return_value=[mock_step])

        factory.execute_pipeline()
        mock_step.execute.assert_called_once()

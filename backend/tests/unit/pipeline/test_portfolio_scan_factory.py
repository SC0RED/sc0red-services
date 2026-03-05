"""Tests for PortfolioScanFactory."""

from unittest.mock import MagicMock

from src.facades.company_accessor import CompanyAccessor
from src.models.model_company import Company
from src.pipeline.pipeline_factories.portfolio_scan_factory import PortfolioScanFactory
from src.pipeline.pipeline_steps.discover_portfolio import DiscoverPortfolio


class TestPortfolioScanFactory:
    def _make_factory(self):
        accessor = CompanyAccessor(Company(url="https://pefirm.com"))
        return PortfolioScanFactory(
            entity_accessor=accessor,
            tenant_id="t-1",
            request_id="r-1",
        )

    def test_get_pipeline_returns_single_step(self):
        factory = self._make_factory()
        pipeline = factory.get_pipeline()
        assert len(pipeline) == 1
        assert isinstance(pipeline[0], DiscoverPortfolio)

    def test_build_executor(self):
        factory = self._make_factory()
        executor = factory.build_executor()
        assert executor.tenant_id == "t-1"
        assert executor.request_id == "r-1"

    def test_execute_pipeline(self):
        factory = self._make_factory()
        mock_step = MagicMock()
        mock_step.step_name.return_value = "DiscoverPortfolio"
        factory.get_pipeline = MagicMock(return_value=[mock_step])

        _executor = factory.execute_pipeline()
        mock_step.execute.assert_called_once()

"""Tests for DiscoverPortfolio pipeline step."""

from unittest.mock import MagicMock, patch

import pytest

from src.facades.company_accessor import CompanyAccessor
from src.models.model_company import Company
from src.pipeline.pipeline_steps.discover_portfolio import DiscoverPortfolio


class TestDiscoverPortfolio:
    @patch("src.pipeline.pipeline_steps.discover_portfolio.PortfolioDiscoveryStrategy")
    def test_execute_success(self, mock_strategy_cls):
        mock_strategy = MagicMock()
        mock_strategy.execute.return_value = (
            '[{"name": "Co1", "url": "https://co1.com"}]',
            {"companies": [{"name": "Co1", "url": "https://co1.com"}]},
        )
        mock_strategy_cls.return_value = mock_strategy

        company = Company(url="https://pefirm.com/portfolio")
        accessor = CompanyAccessor(company)

        step = DiscoverPortfolio()
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        step.execute()

        step._request_executor.add_details.assert_called_once()
        details = step._request_executor.add_details.call_args[0][0]
        assert details["portfolio_count"] == 1
        assert len(details["portfolio_companies"]) == 1
        step._request_executor.mark_question_complete.assert_called_with("discover_portfolio")

    def test_execute_no_url_raises(self):
        company = Company(url="")
        accessor = CompanyAccessor(company)

        step = DiscoverPortfolio()
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        with pytest.raises(ValueError, match="No URL"):
            step.execute()

    @patch("src.pipeline.pipeline_steps.discover_portfolio.PortfolioDiscoveryStrategy")
    def test_execute_empty_results(self, mock_strategy_cls):
        mock_strategy = MagicMock()
        mock_strategy.execute.return_value = ("[]", {"companies": []})
        mock_strategy_cls.return_value = mock_strategy

        company = Company(url="https://pefirm.com")
        accessor = CompanyAccessor(company)

        step = DiscoverPortfolio()
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        step.execute()

        details = step._request_executor.add_details.call_args[0][0]
        assert details["portfolio_count"] == 0

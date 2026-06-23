"""Tests for DiscoverPortfolio pipeline step."""

from unittest.mock import MagicMock, patch

import pytest

from src.pipeline.pipeline_steps.ai_call import TokenCounts
from src.pipeline.pipeline_steps.discover_portfolio import DiscoverPortfolio
from src.pipeline.pipeline_steps.portfolio_extract import extract_companies_from_scrape


def _make_mock_executor():
    executor = MagicMock()
    executor.details = {}
    return executor


def _make_mock_accessor(url="https://firm.com"):
    accessor = MagicMock()
    accessor.company.url = url
    return accessor


def _heuristic_result(companies, page_text="page text", all_links=None, script_text=""):
    return (
        "[]",
        {
            "companies": companies,
            "count": len(companies),
            "page_text": page_text,
            "script_text": script_text,
            "all_links": all_links or [],
        },
    )


class TestRunAIExtraction:
    def test_returns_companies(self):
        mock_ai = MagicMock()

        with patch(
            "src.pipeline.pipeline_steps.portfolio_extract.run_structured_ai_call"
        ) as mock_call:
            mock_call.return_value = (
                "extract_portfolio",
                {"companies": [{"name": "X", "url": "https://x.com"}], "is_pe_firm": True},
                1.0,
                TokenCounts(input_tokens=100, output_tokens=50, cached_input_tokens=0),
            )
            result = extract_companies_from_scrape(
                mock_ai,
                "https://firm.com",
                "page text",
                "",
                [{"text": "link", "href": "https://x.com"}],
                step_name="DiscoverPortfolio",
            )
            assert len(result["companies"]) == 1

    def test_propagates_error(self):
        mock_ai = MagicMock()

        with (
            patch(
                "src.pipeline.pipeline_steps.portfolio_extract.run_structured_ai_call",
                side_effect=RuntimeError("AI error"),
            ),
            pytest.raises(RuntimeError, match="AI error"),
        ):
            extract_companies_from_scrape(
                mock_ai,
                "https://firm.com",
                "page text",
                "",
                [{"text": "a", "href": "b"}],
                step_name="DiscoverPortfolio",
            )


class TestDiscoverPortfolioStep:
    def test_heuristic_only_no_ai(self):
        step = DiscoverPortfolio(ai_client_factory=None)
        step.request_executor = _make_mock_executor()
        step.entity_accessor = _make_mock_accessor()

        with patch(
            "src.pipeline.pipeline_steps.discover_portfolio.PortfolioDiscoveryStrategy"
        ) as mock_strategy:
            mock_strategy.return_value.execute.return_value = _heuristic_result(
                [{"name": "Acme", "url": "https://acme.com"}]
            )
            step.execute()

        call_args = step.request_executor.add_details.call_args[0][0]
        assert call_args["portfolio_count"] == 1
        assert call_args["portfolio_companies"][0]["name"] == "Acme"

    def test_with_ai_extraction(self):
        mock_ai = MagicMock()
        step = DiscoverPortfolio(ai_client_factory=mock_ai)
        step.request_executor = _make_mock_executor()
        step.entity_accessor = _make_mock_accessor()

        ai_result = {
            "companies": [
                {"name": "Acme Corp", "url": "https://www.acme.com"},
                {"name": "Beta", "url": "https://beta.com"},
            ],
            "is_pe_firm": True,
        }

        with (
            patch(
                "src.pipeline.pipeline_steps.discover_portfolio.extract_companies_from_scrape",
                return_value=ai_result,
            ),
            patch(
                "src.pipeline.pipeline_steps.discover_portfolio.PortfolioDiscoveryStrategy"
            ) as mock_strategy,
        ):
            mock_strategy.return_value.execute.return_value = _heuristic_result(
                [
                    {"name": "Acme", "url": "https://acme.com"},
                    {"name": "Gamma", "url": "https://gamma.com"},
                ],
            )
            step.execute()

        call_args = step.request_executor.add_details.call_args[0][0]
        assert call_args["portfolio_count"] == 3

    def test_non_pe_firm_message(self):
        mock_ai = MagicMock()
        step = DiscoverPortfolio(ai_client_factory=mock_ai)
        step.request_executor = _make_mock_executor()
        step.entity_accessor = _make_mock_accessor()

        ai_result = {
            "companies": [],
            "is_pe_firm": False,
            "firm_type_description": "This is an accounting firm.",
        }

        with (
            patch(
                "src.pipeline.pipeline_steps.discover_portfolio.extract_companies_from_scrape",
                return_value=ai_result,
            ),
            patch(
                "src.pipeline.pipeline_steps.discover_portfolio.run_web_search_discovery",
                return_value=[],
            ),
            patch(
                "src.pipeline.pipeline_steps.discover_portfolio.PortfolioDiscoveryStrategy"
            ) as mock_strategy,
        ):
            mock_strategy.return_value.execute.return_value = _heuristic_result(
                [], page_text="text"
            )
            step.execute()

        call_args = step.request_executor.add_details.call_args[0][0]
        assert call_args["portfolio_count"] == 0
        assert "accounting firm" in call_args["portfolio_diagnostic"]

    def test_no_url_raises(self):
        step = DiscoverPortfolio()
        step.request_executor = _make_mock_executor()
        step.entity_accessor = _make_mock_accessor(url="")

        with pytest.raises(ValueError, match="No URL provided"):
            step.execute()

    def test_both_paths_empty_returns_diagnostic(self):
        mock_ai = MagicMock()
        step = DiscoverPortfolio(ai_client_factory=mock_ai)
        step.request_executor = _make_mock_executor()
        step.entity_accessor = _make_mock_accessor()

        ai_result = {"companies": [], "is_pe_firm": True}

        with (
            patch(
                "src.pipeline.pipeline_steps.discover_portfolio.extract_companies_from_scrape",
                return_value=ai_result,
            ),
            patch(
                "src.pipeline.pipeline_steps.discover_portfolio.run_web_search_discovery",
                return_value=[],
            ),
            patch(
                "src.pipeline.pipeline_steps.discover_portfolio.PortfolioDiscoveryStrategy"
            ) as mock_strategy,
        ):
            mock_strategy.return_value.execute.return_value = _heuristic_result(
                [], page_text="text"
            )
            step.execute()

        call_args = step.request_executor.add_details.call_args[0][0]
        assert call_args["portfolio_count"] == 0
        assert "Could not identify" in call_args["portfolio_diagnostic"]

    def test_empty_page_and_script_text_skips_ai(self):
        mock_ai = MagicMock()
        step = DiscoverPortfolio(ai_client_factory=mock_ai)
        step.request_executor = _make_mock_executor()
        step.entity_accessor = _make_mock_accessor()

        with (
            patch(
                "src.pipeline.pipeline_steps.discover_portfolio.extract_companies_from_scrape"
            ) as mock_extract,
            patch(
                "src.pipeline.pipeline_steps.discover_portfolio.PortfolioDiscoveryStrategy"
            ) as mock_strategy,
        ):
            # Both page_text and script_text empty → AI extraction is skipped.
            mock_strategy.return_value.execute.return_value = _heuristic_result(
                [{"name": "X", "url": "https://x.com"}], page_text="", script_text=""
            )
            step.execute()

        mock_extract.assert_not_called()
        call_args = step.request_executor.add_details.call_args[0][0]
        assert call_args["portfolio_count"] == 1

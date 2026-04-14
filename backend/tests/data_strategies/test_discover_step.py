"""Tests for DiscoverPortfolio pipeline step."""

from unittest.mock import MagicMock, patch

import pytest

from src.pipeline.pipeline_steps.discover_portfolio import DiscoverPortfolio


def _make_mock_executor():
    executor = MagicMock()
    executor.details = {}
    return executor


def _make_mock_accessor(url="https://firm.com"):
    accessor = MagicMock()
    accessor.company.url = url
    return accessor


class TestScrapeForAI:
    def test_combines_text_from_paths(self):
        step = DiscoverPortfolio()
        mock_result = {"title": "", "description": "", "text": "page text", "links": [{"text": "a", "href": "b", "context_name": ""}], "meta_keywords": ""}

        with patch("src.pipeline.pipeline_steps.discover_portfolio.scrape_url", return_value=mock_result):
            text, links = step._scrape_for_ai("https://firm.com")  # noqa: SLF001
            assert "page text" in text
            assert len(links) > 0

    def test_handles_scrape_errors(self):
        step = DiscoverPortfolio()
        call_count = 0

        def side_effect(url):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                return {"title": "", "description": "", "text": "ok", "links": [], "meta_keywords": ""}
            msg = "404"
            raise Exception(msg)  # noqa: TRY002

        with patch("src.pipeline.pipeline_steps.discover_portfolio.scrape_url", side_effect=side_effect):
            text, links = step._scrape_for_ai("https://firm.com")  # noqa: SLF001
            assert "ok" in text


class TestRunAIExtraction:
    def test_returns_companies(self):
        mock_ai = MagicMock()
        step = DiscoverPortfolio(ai_client_factory=mock_ai)

        with patch("src.pipeline.pipeline_steps.discover_portfolio.run_structured_ai_call") as mock_call:
            mock_call.return_value = ("extract_portfolio", {"companies": [{"name": "X", "url": "https://x.com"}], "is_pe_firm": True}, 1.0)
            result = step._run_ai_extraction("https://firm.com", "page text", [{"text": "link", "href": "https://x.com"}])  # noqa: SLF001
            assert len(result["companies"]) == 1

    def test_returns_empty_on_error(self):
        mock_ai = MagicMock()
        step = DiscoverPortfolio(ai_client_factory=mock_ai)

        with patch("src.pipeline.pipeline_steps.discover_portfolio.run_structured_ai_call", side_effect=Exception("AI error")):
            result = step._run_ai_extraction("https://firm.com", "page text", [])  # noqa: SLF001
            assert result["companies"] == []
            assert result["is_pe_firm"] is True


class TestDiscoverPortfolioStep:
    def test_heuristic_only_no_ai(self):
        """Without ai_client_factory, only heuristic runs."""
        step = DiscoverPortfolio(ai_client_factory=None)
        step.request_executor = _make_mock_executor()
        step.entity_accessor = _make_mock_accessor()

        heuristic_result = (
            "[]",
            {"companies": [{"name": "Acme", "url": "https://acme.com"}], "count": 1},
        )
        with patch.object(
            step, "_scrape_for_ai", return_value=("page text", [])
        ), patch(
            "src.pipeline.pipeline_steps.discover_portfolio.PortfolioDiscoveryStrategy"
        ) as mock_strategy:
            mock_strategy.return_value.execute.return_value = heuristic_result
            step.execute()

        call_args = step.request_executor.add_details.call_args[0][0]
        assert call_args["portfolio_count"] == 1
        assert call_args["portfolio_companies"][0]["name"] == "Acme"

    def test_with_ai_extraction(self):
        """With ai_client_factory, both paths run and merge."""
        mock_ai = MagicMock()
        step = DiscoverPortfolio(ai_client_factory=mock_ai)
        step.request_executor = _make_mock_executor()
        step.entity_accessor = _make_mock_accessor()

        heuristic_result = (
            "[]",
            {"companies": [
                {"name": "Acme", "url": "https://acme.com"},
                {"name": "Gamma", "url": "https://gamma.com"},
            ], "count": 2},
        )
        ai_result = {
            "companies": [
                {"name": "Acme Corp", "url": "https://www.acme.com"},
                {"name": "Beta", "url": "https://beta.com"},
            ],
            "is_pe_firm": True,
        }

        with patch.object(
            step, "_scrape_for_ai", return_value=("page text", [])
        ), patch.object(
            step, "_run_ai_extraction", return_value=ai_result
        ), patch(
            "src.pipeline.pipeline_steps.discover_portfolio.PortfolioDiscoveryStrategy"
        ) as mock_strategy:
            mock_strategy.return_value.execute.return_value = heuristic_result
            step.execute()

        call_args = step.request_executor.add_details.call_args[0][0]
        assert call_args["portfolio_count"] == 3  # acme (intersection) + gamma + beta

    def test_non_pe_firm_message(self):
        """AI identifies non-PE firm and returns diagnostic."""
        mock_ai = MagicMock()
        step = DiscoverPortfolio(ai_client_factory=mock_ai)
        step.request_executor = _make_mock_executor()
        step.entity_accessor = _make_mock_accessor()

        heuristic_result = ("[]", {"companies": [], "count": 0})
        ai_result = {
            "companies": [],
            "is_pe_firm": False,
            "firm_type_description": "This is an accounting firm.",
        }

        with patch.object(
            step, "_scrape_for_ai", return_value=("page text", [])
        ), patch.object(
            step, "_run_ai_extraction", return_value=ai_result
        ), patch(
            "src.pipeline.pipeline_steps.discover_portfolio.PortfolioDiscoveryStrategy"
        ) as mock_strategy:
            mock_strategy.return_value.execute.return_value = heuristic_result
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

        heuristic_result = ("[]", {"companies": [], "count": 0})
        ai_result = {"companies": [], "is_pe_firm": True}

        with patch.object(
            step, "_scrape_for_ai", return_value=("page text", [])
        ), patch.object(
            step, "_run_ai_extraction", return_value=ai_result
        ), patch(
            "src.pipeline.pipeline_steps.discover_portfolio.PortfolioDiscoveryStrategy"
        ) as mock_strategy:
            mock_strategy.return_value.execute.return_value = heuristic_result
            step.execute()

        call_args = step.request_executor.add_details.call_args[0][0]
        assert call_args["portfolio_count"] == 0
        assert "Could not identify" in call_args["portfolio_diagnostic"]

    def test_empty_page_text_skips_ai(self):
        mock_ai = MagicMock()
        step = DiscoverPortfolio(ai_client_factory=mock_ai)
        step.request_executor = _make_mock_executor()
        step.entity_accessor = _make_mock_accessor()

        heuristic_result = ("[]", {"companies": [{"name": "X", "url": "https://x.com"}], "count": 1})

        with patch.object(
            step, "_scrape_for_ai", return_value=("", [])
        ), patch(
            "src.pipeline.pipeline_steps.discover_portfolio.PortfolioDiscoveryStrategy"
        ) as mock_strategy:
            mock_strategy.return_value.execute.return_value = heuristic_result
            step.execute()

        call_args = step.request_executor.add_details.call_args[0][0]
        assert call_args["portfolio_count"] == 1

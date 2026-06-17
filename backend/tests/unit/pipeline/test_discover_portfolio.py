"""Tests for DiscoverPortfolio pipeline step."""

from unittest.mock import MagicMock, patch

import pytest

from src.facades.company_accessor import CompanyAccessor
from src.models.model_company import Company
from src.pipeline.pipeline_steps.ai_call import TokenCounts
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
        # Heuristic-only company (no AI intersection) → goes to validation candidates
        assert len(details["portfolio_companies"]) == 1
        assert details["portfolio_auto_included"] == []
        step._request_executor.mark_question_complete.assert_called_with("discover_portfolio")

    @patch("src.pipeline.pipeline_steps.discover_portfolio.PortfolioDiscoveryStrategy")
    def test_script_json_is_fed_to_ai_extraction(self, mock_strategy_cls):
        """Embedded-JSON portfolios: script_text reaches the AI extractor, prioritised."""
        script_text = '{"companies":[{"name":"Sophos","url":"https://sophos.com"}]}'
        mock_strategy = MagicMock()
        mock_strategy.execute.return_value = (
            "ignored",
            {"companies": [], "page_text": "skeleton", "script_text": script_text, "all_links": []},
        )
        mock_strategy_cls.return_value = mock_strategy

        accessor = CompanyAccessor(Company(url="https://pefirm.com/portfolio"))
        step = DiscoverPortfolio(ai_client_factory=MagicMock())
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        captured: dict[str, str] = {}

        def _fake_call(*, user_prompt: str, **_: object):
            captured["prompt"] = user_prompt
            return (
                "extract_portfolio",
                {"is_pe_firm": True, "companies": [{"name": "Sophos", "url": "https://sophos.com"}]},
                0.0,
                TokenCounts(input_tokens=10, output_tokens=5, cached_input_tokens=0),
            )

        with patch(
            "src.pipeline.pipeline_steps.discover_portfolio.run_structured_ai_call",
            side_effect=_fake_call,
        ):
            step.execute()

        # The script JSON (where the companies live) is in the extraction prompt,
        # ahead of the visible skeleton.
        assert "Sophos" in captured["prompt"]
        assert captured["prompt"].index("Sophos") < captured["prompt"].index("skeleton")
        details = step._request_executor.add_details.call_args[0][0]
        assert details["portfolio_count"] == 1

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
        assert details["portfolio_companies"] == []
        assert details["portfolio_auto_included"] == []

    @patch("src.pipeline.pipeline_steps.discover_portfolio.PortfolioDiscoveryStrategy")
    def test_intersection_auto_included_remainder_to_validate(self, mock_strategy_cls):
        """Companies found by BOTH heuristic and AI skip validation; others go to candidates."""
        heuristic = [
            {"name": "Both Co", "url": "https://both.com"},
            {"name": "Heuristic Only", "url": "https://heur.com"},
        ]
        page_text = "Our portfolio includes Both Co and AI Only Co."
        mock_strategy = MagicMock()
        mock_strategy.execute.return_value = (
            "ignored",
            {"companies": heuristic, "page_text": page_text, "all_links": []},
        )
        mock_strategy_cls.return_value = mock_strategy

        company = Company(url="https://pefirm.com/portfolio")
        accessor = CompanyAccessor(company)

        ai_factory = MagicMock()
        step = DiscoverPortfolio(ai_client_factory=ai_factory)
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        ai_result = {
            "is_pe_firm": True,
            "companies": [
                {"name": "Both Co", "url": "https://both.com"},
                {"name": "AI Only", "url": "https://aionly.com"},
            ],
        }
        with patch(
            "src.pipeline.pipeline_steps.discover_portfolio.run_structured_ai_call",
            return_value=(
                "extract_portfolio",
                ai_result,
                0.0,
                TokenCounts(input_tokens=100, output_tokens=50, cached_input_tokens=0),
            ),
        ):
            step.execute()

        details = step._request_executor.add_details.call_args[0][0]
        auto_urls = {c["url"] for c in details["portfolio_auto_included"]}
        candidate_urls = {c["url"] for c in details["portfolio_companies"]}

        assert auto_urls == {"https://both.com"}
        assert candidate_urls == {"https://heur.com", "https://aionly.com"}
        assert details["portfolio_count"] == 3

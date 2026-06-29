"""Tests for the FetchProvidedSource step."""

from unittest.mock import MagicMock, patch

import pytest

from src.facades.company_accessor import CompanyAccessor
from src.models.model_company import Company
from src.pipeline.pipeline_steps.fetch_provided_source import FetchProvidedSource

_STRATEGY = "src.pipeline.pipeline_steps.fetch_provided_source.PortfolioDiscoveryStrategy"
_EXTRACT = "src.pipeline.pipeline_steps.fetch_provided_source.extract_companies_from_scrape"


_DEFAULT_AI = object()


def _make_step(seed, *, url="https://firm.com/portfolio", ai_factory=_DEFAULT_AI):
    step = FetchProvidedSource(
        ai_client_factory=MagicMock() if ai_factory is _DEFAULT_AI else ai_factory,
        seed_companies=seed,
    )
    step._entity_accessor = CompanyAccessor(Company(url=url))
    step._request_executor = MagicMock()
    return step


def _scrape(companies, *, page_text="page text", script_text="", all_links=None):
    """Build a (raw, metadata) PortfolioDiscoveryStrategy result."""
    return (
        "[]",
        {
            "companies": companies,
            "page_text": page_text,
            "script_text": script_text,
            "all_links": all_links or [],
        },
    )


class TestFetchProvidedSource:
    def test_merges_page_companies_with_seed_tagged_provided_url(self):
        seed = [{"name": "Known", "url": "https://known.com", "description": ""}]
        step = _make_step(seed)
        with (
            patch(_STRATEGY) as mock_strategy,
            patch(
                _EXTRACT,
                return_value={
                    "companies": [{"name": "Fresh", "url": "https://fresh.com"}],
                    "is_pe_firm": True,
                },
            ),
        ):
            mock_strategy.return_value.execute.return_value = _scrape([])
            step.execute()

        details = step._request_executor.add_details.call_args[0][0]
        assert details["portfolio_auto_included"] == seed
        assert details["portfolio_companies"] == [
            {
                "name": "Fresh",
                "url": "https://fresh.com",
                "description": "",
                "source": "provided_url",
                "status": "",
            }
        ]
        assert details["portfolio_count"] == 2
        verdict = details["discovery_verdict"]
        # Provided-page companies are reliable → partial_site_list (never claimed full).
        assert verdict["completeness"] == "partial_site_list"
        assert verdict["method"] == "site"
        # The provided page is the trust anchor when it contributed companies.
        assert verdict["site_source_url"] == "https://firm.com/portfolio"

    def test_dedupes_page_company_already_on_scan(self):
        seed = [{"name": "Known", "url": "https://known.com", "description": ""}]
        step = _make_step(seed)
        with (
            patch(_STRATEGY) as mock_strategy,
            patch(
                _EXTRACT,
                return_value={
                    "companies": [{"name": "Known, Inc.", "url": "https://known.com"}],
                    "is_pe_firm": True,
                },
            ),
        ):
            mock_strategy.return_value.execute.return_value = _scrape([])
            step.execute()

        details = step._request_executor.add_details.call_args[0][0]
        assert details["portfolio_companies"] == []
        assert details["portfolio_count"] == 1
        # Nothing fresh from the page → leave the scan's existing verdict
        # untouched rather than relabelling the unchanged list as site-derived.
        assert "discovery_verdict" not in details

    def test_uses_heuristic_companies_without_ai_factory(self):
        step = _make_step([], ai_factory=None)
        with patch(_STRATEGY) as mock_strategy:
            mock_strategy.return_value.execute.return_value = _scrape(
                [{"name": "Acme", "url": "https://acme.com"}]
            )
            step.execute()

        details = step._request_executor.add_details.call_args[0][0]
        assert details["portfolio_companies"] == [
            {
                "name": "Acme",
                "url": "https://acme.com",
                "description": "",
                "source": "provided_url",
                "status": "",
            }
        ]
        assert details["portfolio_count"] == 1

    def test_empty_page_keeps_seed(self):
        seed = [{"name": "Known", "url": "https://known.com", "description": ""}]
        step = _make_step(seed)
        with (
            patch(_STRATEGY) as mock_strategy,
            patch(_EXTRACT, return_value={"companies": [], "is_pe_firm": True}),
        ):
            mock_strategy.return_value.execute.return_value = _scrape([])
            step.execute()

        details = step._request_executor.add_details.call_args[0][0]
        assert details["portfolio_companies"] == []
        assert details["portfolio_auto_included"] == seed
        assert details["portfolio_count"] == 1
        # No new companies → prior verdict preserved (no overwrite).
        assert "discovery_verdict" not in details

    def test_no_url_raises(self):
        step = _make_step([], url="")
        with pytest.raises(ValueError, match="No URL"):
            step.execute()

    def test_skips_ai_when_no_text_scraped(self):
        step = _make_step([])
        with (
            patch(_STRATEGY) as mock_strategy,
            patch(_EXTRACT) as mock_extract,
        ):
            mock_strategy.return_value.execute.return_value = _scrape(
                [], page_text="", script_text=""
            )
            step.execute()

        # No text and no script → AI extraction is never called.
        mock_extract.assert_not_called()

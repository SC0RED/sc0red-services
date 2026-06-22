"""Tests for the DeepenPortfolio step."""

from unittest.mock import MagicMock, patch

import pytest

from src.facades.company_accessor import CompanyAccessor
from src.models.model_company import Company
from src.pipeline.pipeline_steps.deepen_portfolio import DeepenPortfolio

_PATCH = "src.pipeline.pipeline_steps.deepen_portfolio.run_deep_web_search_discovery"


def _make_step(seed, url="https://firm.com"):
    step = DeepenPortfolio(ai_client_factory=MagicMock(), seed_companies=seed)
    step._entity_accessor = CompanyAccessor(Company(url=url))
    step._request_executor = MagicMock()
    return step


class TestDeepenPortfolio:
    def test_merges_new_candidates_with_seed(self):
        seed = [{"name": "Known", "url": "https://known.com", "description": ""}]
        new = [
            {"name": "Fresh", "url": "https://fresh.com"},
            {"name": "Known", "url": "https://known.com"},  # dup of seed → dropped
        ]
        step = _make_step(seed)
        with patch(_PATCH, return_value=new):
            step.execute()

        details = step._request_executor.add_details.call_args[0][0]
        # Existing list is trusted (auto_included); only the fresh one validates.
        assert details["portfolio_auto_included"] == seed
        assert details["portfolio_companies"] == [
            {"name": "Fresh", "url": "https://fresh.com", "description": ""}
        ]
        assert details["portfolio_count"] == 2
        assert details["discovery_verdict"]["completeness"] == "web_search_subset"
        assert "search_deeper" in details["discovery_verdict"]["available_actions"]

    def test_seed_names_passed_to_search(self):
        seed = [{"name": "Known", "url": "https://known.com"}]
        step = _make_step(seed)
        with patch(_PATCH, return_value=[]) as mock_search:
            step.execute()
        # The deep search is seeded with the existing company names.
        assert mock_search.call_args.args[2] == ["Known"]

    def test_no_new_candidates_keeps_seed(self):
        seed = [{"name": "Known", "url": "https://known.com", "description": ""}]
        step = _make_step(seed)
        with patch(_PATCH, return_value=[]):
            step.execute()
        details = step._request_executor.add_details.call_args[0][0]
        assert details["portfolio_companies"] == []
        assert details["portfolio_auto_included"] == seed
        assert details["portfolio_count"] == 1
        # Adding nothing new → web search exhausted → point to upload only.
        verdict = details["discovery_verdict"]
        assert verdict["completeness"] == "web_search_exhausted"
        assert verdict["available_actions"] == ["upload_list"]

    def test_no_url_raises(self):
        step = _make_step([], url="")
        with pytest.raises(ValueError, match="No URL"):
            step.execute()

    def test_requires_ai_factory(self):
        step = DeepenPortfolio(ai_client_factory=None, seed_companies=[])
        step._entity_accessor = CompanyAccessor(Company(url="https://firm.com"))
        step._request_executor = MagicMock()
        with pytest.raises(RuntimeError, match="AI client factory"):
            step.execute()

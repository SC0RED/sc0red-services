"""Tests for DiscoverPortfolio pipeline step."""

from unittest.mock import MagicMock, patch

import pytest

from src.facades.company_accessor import CompanyAccessor
from src.models.model_company import Company
from src.pipeline.pipeline_steps.ai_call import TokenCounts
from src.pipeline.pipeline_steps.discover_portfolio import DiscoverPortfolio
from src.pipeline.pipeline_steps.portfolio_merge import (
    build_verdict,
    find_new_candidates,
    merge_fallback,
)


def _grounded(companies: list[dict[str, str]]):
    return (
        "portfolio_web_fallback",
        {"companies": companies},
        0.0,
        TokenCounts(input_tokens=10, output_tokens=5, cached_input_tokens=0),
        [],
    )


class TestMergeFallback:
    def test_adds_new_candidates_to_needs_validation(self):
        out = merge_fallback(
            auto_included=[{"name": "A", "url": "https://a.com"}],
            needs_validation=[{"name": "B", "url": "https://b.com"}],
            fallback=[{"name": "C", "url": "https://c.com"}],
        )
        urls = {c["url"] for c in out}
        assert urls == {"https://b.com", "https://c.com"}  # A stays auto-included, C added

    def test_dedupes_against_site_results_by_domain(self):
        out = merge_fallback(
            auto_included=[{"name": "A", "url": "https://a.com"}],
            needs_validation=[],
            fallback=[
                {"name": "A dup", "url": "https://www.a.com/"},
                {"name": "New", "url": "https://new.com"},
            ],
        )
        assert {c["url"] for c in out} == {"https://new.com"}

    def test_skips_candidates_without_a_domain(self):
        out = merge_fallback([], [], [{"name": "X", "url": ""}])
        assert out == []

    def test_site_company_not_repeated_by_web_search_different_tld(self):
        # The firm's site has Acme(acme.com); web search returns Acme(acme.in) —
        # the trusted site entry wins, the web-search twin is dropped.
        out = merge_fallback(
            auto_included=[{"name": "Acme", "url": "https://acme.com"}],
            needs_validation=[],
            fallback=[
                {"name": "Acme, Inc.", "url": "https://acme.in"},
                {"name": "Beta", "url": "https://beta.com"},
            ],
        )
        assert {c["url"] for c in out} == {"https://beta.com"}

    def test_web_search_tld_duplicates_collapse_by_name(self):
        out = merge_fallback(
            auto_included=[],
            needs_validation=[],
            fallback=[
                {"name": "Acme", "url": "https://acme.com"},
                {"name": "Acme LLC", "url": "https://acme.in"},
            ],
        )
        assert len(out) == 1
        assert out[0]["name"] == "Acme"  # first-encountered wins

    def test_distinct_names_preserved(self):
        out = merge_fallback(
            auto_included=[{"name": "Acme", "url": "https://acme.com"}],
            needs_validation=[],
            fallback=[{"name": "Acme Health", "url": "https://acmehealth.com"}],
        )
        assert {c["url"] for c in out} == {"https://acmehealth.com"}


class TestNormalizeCompanyName:
    def test_strips_suffixes_and_punctuation(self):
        from src.pipeline.pipeline_steps.portfolio_merge import normalize_company_name

        assert normalize_company_name("Acme, Inc.") == "acme"
        assert normalize_company_name("Acme LLC") == "acme"
        assert normalize_company_name("Acme Corp") == "acme"
        assert normalize_company_name("Acme Health") == "acme health"

    def test_keeps_tokens_when_all_suffixes(self):
        from src.pipeline.pipeline_steps.portfolio_merge import normalize_company_name

        # Stripping everything would empty it → keep the un-stripped tokens.
        assert normalize_company_name("Holdings Group") == "holdings group"


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
                {
                    "is_pe_firm": True,
                    "companies": [{"name": "Sophos", "url": "https://sophos.com"}],
                },
                0.0,
                TokenCounts(input_tokens=10, output_tokens=5, cached_input_tokens=0),
            )

        with patch(
            "src.pipeline.pipeline_steps.portfolio_extract.run_structured_ai_call",
            side_effect=_fake_call,
        ):
            step.execute()

        # The script JSON (where the companies live) is in the extraction prompt,
        # ahead of the visible skeleton.
        assert "Sophos" in captured["prompt"]
        assert captured["prompt"].index("Sophos") < captured["prompt"].index("skeleton")
        details = step._request_executor.add_details.call_args[0][0]
        assert details["portfolio_count"] == 1

    @patch("src.pipeline.pipeline_steps.portfolio_websearch.run_grounded_ai_call")
    @patch("src.pipeline.pipeline_steps.discover_portfolio.PortfolioDiscoveryStrategy")
    def test_low_yield_triggers_web_search_fallback(self, mock_strategy_cls, mock_grounded):
        # Opaque site: no companies, no embedded data → fallback fires.
        mock_strategy = MagicMock()
        mock_strategy.execute.return_value = (
            "[]",
            {"companies": [], "page_text": "", "script_text": "", "all_links": []},
        )
        mock_strategy_cls.return_value = mock_strategy
        mock_grounded.return_value = _grounded([{"name": "Jamf", "url": "https://jamf.com"}])

        step = DiscoverPortfolio(ai_client_factory=MagicMock())
        step._entity_accessor = CompanyAccessor(Company(url="https://vista.com"))
        step._request_executor = MagicMock()
        step.execute()

        mock_grounded.assert_called_once()
        details = step._request_executor.add_details.call_args[0][0]
        assert details["portfolio_count"] == 1
        # Fallback candidate is validation-tier, never auto-included.
        assert {c["url"] for c in details["portfolio_companies"]} == {"https://jamf.com"}
        assert details["portfolio_auto_included"] == []

    @patch("src.pipeline.pipeline_steps.portfolio_websearch.run_grounded_ai_call")
    @patch("src.pipeline.pipeline_steps.discover_portfolio.PortfolioDiscoveryStrategy")
    def test_fallback_after_fetch_failure_still_recovers(self, mock_strategy_cls, mock_grounded):
        # Site fetch failed (block) → 0 site companies → fallback fires as recovery
        # (and logs the fetch-failure cause). Result is still populated.
        mock_strategy = MagicMock()
        mock_strategy.execute.return_value = (
            "[]",
            {
                "companies": [],
                "page_text": "",
                "script_text": "",
                "all_links": [],
                "site_fetch_failed": True,
            },
        )
        mock_strategy_cls.return_value = mock_strategy
        mock_grounded.return_value = _grounded([{"name": "Jamf", "url": "https://jamf.com"}])

        step = DiscoverPortfolio(ai_client_factory=MagicMock())
        step._entity_accessor = CompanyAccessor(Company(url="https://firm.com"))
        step._request_executor = MagicMock()
        step.execute()

        mock_grounded.assert_called_once()
        details = step._request_executor.add_details.call_args[0][0]
        assert details["portfolio_count"] == 1

    @patch("src.pipeline.pipeline_steps.portfolio_websearch.run_grounded_ai_call")
    @patch("src.pipeline.pipeline_steps.discover_portfolio.PortfolioDiscoveryStrategy")
    def test_fallback_seeded_with_logo_names(self, mock_strategy_cls, mock_grounded):
        # Logo-grid site (Vista): site yields 0 companies but logo names exist →
        # the fallback is seeded with those names to resolve their URLs.
        mock_strategy = MagicMock()
        mock_strategy.execute.return_value = (
            "[]",
            {
                "companies": [],
                "page_text": "",
                "script_text": "",
                "all_links": [],
                "logo_company_names": ["Jamf", "Datto"],
            },
        )
        mock_strategy_cls.return_value = mock_strategy

        captured: dict[str, str] = {}

        def _capture(*, user_prompt: str, **_: object):
            captured["prompt"] = user_prompt
            return _grounded(
                [
                    {"name": "Jamf", "url": "https://jamf.com"},
                    {"name": "Datto", "url": "https://datto.com"},
                ]
            )

        mock_grounded.side_effect = _capture
        step = DiscoverPortfolio(ai_client_factory=MagicMock())
        step._entity_accessor = CompanyAccessor(Company(url="https://vista.com"))
        step._request_executor = MagicMock()
        step.execute()

        assert "Jamf" in captured["prompt"] and "Datto" in captured["prompt"]
        assert "known to include" in captured["prompt"].lower()
        details = step._request_executor.add_details.call_args[0][0]
        assert {c["url"] for c in details["portfolio_companies"]} == {
            "https://jamf.com",
            "https://datto.com",
        }

    @patch("src.pipeline.pipeline_steps.portfolio_websearch.run_grounded_ai_call")
    @patch("src.pipeline.pipeline_steps.discover_portfolio.PortfolioDiscoveryStrategy")
    def test_fallback_unseeded_when_no_logo_names(self, mock_strategy_cls, mock_grounded):
        # Opaque site with no logo grid → comprehensive (unseeded) prompt.
        mock_strategy = MagicMock()
        mock_strategy.execute.return_value = (
            "[]",
            {"companies": [], "page_text": "", "script_text": "", "all_links": []},
        )
        mock_strategy_cls.return_value = mock_strategy

        captured: dict[str, str] = {}

        def _capture(*, user_prompt: str, **_: object):
            captured["prompt"] = user_prompt
            return _grounded([{"name": "Acme", "url": "https://acme.com"}])

        mock_grounded.side_effect = _capture
        step = DiscoverPortfolio(ai_client_factory=MagicMock())
        step._entity_accessor = CompanyAccessor(Company(url="https://opaque.com"))
        step._request_executor = MagicMock()
        step.execute()

        assert "known to include" not in captured["prompt"].lower()

    @patch("src.pipeline.pipeline_steps.portfolio_websearch.run_grounded_ai_call")
    @patch("src.pipeline.pipeline_steps.discover_portfolio.PortfolioDiscoveryStrategy")
    def test_healthy_site_skips_fallback(self, mock_strategy_cls, mock_grounded):
        # A "healthy" site must exceed _FALLBACK_THRESHOLD (5) to skip the
        # web-search fallback — thin scrapes (≤5) now auto-augment.
        companies = [{"name": f"Co{i}", "url": f"https://co{i}.com"} for i in range(6)]
        mock_strategy = MagicMock()
        mock_strategy.execute.return_value = (
            "x",
            {
                "companies": companies,
                "page_text": "",
                "script_text": "",
                "all_links": [],
            },
        )
        mock_strategy_cls.return_value = mock_strategy

        step = DiscoverPortfolio(ai_client_factory=MagicMock())
        step._entity_accessor = CompanyAccessor(Company(url="https://firm.com"))
        step._request_executor = MagicMock()
        step.execute()

        mock_grounded.assert_not_called()
        assert step._request_executor.add_details.call_args[0][0]["portfolio_count"] == 6

    @patch("src.pipeline.pipeline_steps.portfolio_websearch.run_grounded_ai_call")
    @patch("src.pipeline.pipeline_steps.discover_portfolio.PortfolioDiscoveryStrategy")
    def test_fallback_fails_soft(self, mock_strategy_cls, mock_grounded):
        from signalfield_core.exceptions.base import EngineError

        mock_strategy = MagicMock()
        mock_strategy.execute.return_value = (
            "[]",
            {"companies": [], "page_text": "", "script_text": "", "all_links": []},
        )
        mock_strategy_cls.return_value = mock_strategy
        mock_grounded.side_effect = EngineError("search down")

        step = DiscoverPortfolio(ai_client_factory=MagicMock())
        step._entity_accessor = CompanyAccessor(Company(url="https://firm.com"))
        step._request_executor = MagicMock()
        step.execute()  # must not raise

        details = step._request_executor.add_details.call_args[0][0]
        assert details["portfolio_count"] == 0
        assert details["portfolio_diagnostic"]

    @patch("src.pipeline.pipeline_steps.portfolio_websearch.run_grounded_ai_call")
    @patch("src.pipeline.pipeline_steps.discover_portfolio.PortfolioDiscoveryStrategy")
    def test_fallback_fails_soft_on_schema_violation(self, mock_strategy_cls, mock_grounded):
        # A malformed (schema-invalid) AI response must NOT crash the scan —
        # run_grounded_ai_call re-raises jsonschema.ValidationError.
        import jsonschema

        mock_strategy = MagicMock()
        mock_strategy.execute.return_value = (
            "[]",
            {"companies": [], "page_text": "", "script_text": "", "all_links": []},
        )
        mock_strategy_cls.return_value = mock_strategy
        mock_grounded.side_effect = jsonschema.ValidationError("bad response shape")

        step = DiscoverPortfolio(ai_client_factory=MagicMock())
        step._entity_accessor = CompanyAccessor(Company(url="https://firm.com"))
        step._request_executor = MagicMock()
        step.execute()  # must not raise

        details = step._request_executor.add_details.call_args[0][0]
        assert details["portfolio_count"] == 0
        assert details["portfolio_diagnostic"]

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
            "src.pipeline.pipeline_steps.portfolio_extract.run_structured_ai_call",
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


class TestBuildVerdict:
    def test_non_zero_site_is_partial_not_full(self):
        # A non-zero site scrape is NOT inferred complete — even a large count is
        # partial_site_list, and escalation stays available.
        v = build_verdict(site_total=151, total=151, site_fetch_failed=False, fallback_ran=False)
        assert v["completeness"] == "partial_site_list"
        assert v["method"] == "site"
        assert "search_deeper" in v["available_actions"]
        assert "upload_list" in v["available_actions"]

    def test_web_search_subset(self):

        v = build_verdict(site_total=0, total=3, site_fetch_failed=False, fallback_ran=True)
        assert v["completeness"] == "web_search_subset"
        assert "search_deeper" in v["available_actions"] and "upload_list" in v["available_actions"]

    def test_web_search_exhausted_when_deepen_adds_nothing(self):
        # A deepen round that added 0 new → exhausted; point to upload only.
        v = build_verdict(
            site_total=0, total=10, site_fetch_failed=False, fallback_ran=True, deepen_added=0
        )
        assert v["completeness"] == "web_search_exhausted"
        assert v["available_actions"] == ["upload_list"]

    def test_deepen_with_new_companies_stays_subset(self):
        v = build_verdict(
            site_total=0, total=12, site_fetch_failed=False, fallback_ran=True, deepen_added=2
        )
        assert v["completeness"] == "web_search_subset"
        assert "search_deeper" in v["available_actions"]

    def test_site_blocked(self):

        v = build_verdict(site_total=0, total=2, site_fetch_failed=True, fallback_ran=True)
        assert v["completeness"] == "site_blocked"

    def test_partial_when_fetch_failed_but_no_fallback(self):
        # Fetch partially failed and no fallback ran (e.g. non-PE firm) but the
        # site still yielded links → partial, not blocked (blocked needs fallback).
        v = build_verdict(site_total=8, total=8, site_fetch_failed=True, fallback_ran=False)
        assert v["completeness"] == "partial_site_list"
        assert "search_deeper" in v["available_actions"]

    def test_genuinely_empty(self):

        v = build_verdict(site_total=0, total=0, site_fetch_failed=False, fallback_ran=True)
        assert v["completeness"] == "genuinely_empty"
        assert v["count"] == 0


class TestDiscoveryVerdictEmitted:
    @patch("src.pipeline.pipeline_steps.discover_portfolio.PortfolioDiscoveryStrategy")
    def test_execute_emits_verdict(self, mock_strategy_cls):
        mock_strategy = MagicMock()
        mock_strategy.execute.return_value = (
            "[]",
            {"companies": [{"name": "Co", "url": "https://co.com"}]},
        )
        mock_strategy_cls.return_value = mock_strategy

        step = DiscoverPortfolio()  # no AI → heuristic only, no fallback
        step._entity_accessor = CompanyAccessor(Company(url="https://firm.com"))
        step._request_executor = MagicMock()
        step.execute()

        details = step._request_executor.add_details.call_args[0][0]
        # Non-zero site scrape is partial (never inferred complete).
        assert details["discovery_verdict"]["completeness"] == "partial_site_list"
        assert details["discovery_verdict"]["count"] == 1
        # Provenance: site-derived companies are tagged `site`, and the verdict
        # anchors to the page we read.
        assert details["portfolio_companies"][0]["source"] == "site"
        assert details["discovery_verdict"]["site_source_url"] == "https://firm.com"

    @patch("src.pipeline.pipeline_steps.discover_portfolio.run_web_search_discovery")
    @patch("src.pipeline.pipeline_steps.discover_portfolio.PortfolioDiscoveryStrategy")
    def test_fallback_companies_tagged_web_search(self, mock_strategy_cls, mock_fallback):
        # Empty site → web-search fallback; recovered companies are tagged
        # `web_search` and the verdict has no site source.
        mock_strategy = MagicMock()
        mock_strategy.execute.return_value = (
            "[]",
            {"companies": [], "page_text": "", "script_text": "", "all_links": []},
        )
        mock_strategy_cls.return_value = mock_strategy
        mock_fallback.return_value = [{"name": "WebCo", "url": "https://webco.com"}]

        step = DiscoverPortfolio(ai_client_factory=MagicMock())
        step._entity_accessor = CompanyAccessor(Company(url="https://firm.com"))
        step._request_executor = MagicMock()
        step.execute()

        details = step._request_executor.add_details.call_args[0][0]
        assert details["portfolio_companies"][0]["source"] == "web_search"
        assert details["discovery_verdict"]["site_source_url"] == ""


def _empty_strategy():
    """A PortfolioDiscoveryStrategy mock whose scrape yields no companies."""
    strategy = MagicMock()
    strategy.execute.return_value = (
        "[]",
        {"companies": [], "page_text": "", "script_text": "", "all_links": []},
    )
    return strategy


def _company(name: str, url: str) -> dict[str, str]:
    return {"name": name, "url": url, "description": "", "source": "site"}


class TestDeterministicRungs:
    """wp-json + sitemap rungs run additively before the web-search fallback."""

    @patch("src.pipeline.pipeline_steps.discover_portfolio.discover_via_sitemap")
    @patch("src.pipeline.pipeline_steps.discover_portfolio.discover_via_wp_json")
    @patch("src.pipeline.pipeline_steps.discover_portfolio.PortfolioDiscoveryStrategy")
    def test_rungs_run_when_in_html_thin_no_ai(self, mock_strategy_cls, mock_wpjson, mock_sitemap):
        # In-HTML scrape finds nothing AND there's no AI factory — the deterministic
        # rungs must still run (they're browser-free and AI-free) and populate the list.
        mock_strategy_cls.return_value = _empty_strategy()
        mock_wpjson.return_value = [_company("Acme", "https://acme.com")]
        mock_sitemap.return_value = [_company("Beta", "https://beta.com")]

        step = DiscoverPortfolio()  # no AI factory
        step._entity_accessor = CompanyAccessor(Company(url="https://firm.com/portfolio"))
        step._request_executor = MagicMock()
        step.execute()

        mock_wpjson.assert_called_once_with("https://firm.com")
        mock_sitemap.assert_called_once_with("https://firm.com")
        details = step._request_executor.add_details.call_args[0][0]
        assert {c["name"] for c in details["portfolio_companies"]} == {"Acme", "Beta"}
        assert details["portfolio_count"] == 2
        # Site-derived → verdict anchors to the firm page.
        assert details["discovery_verdict"]["site_source_url"] == "https://firm.com/portfolio"
        # Recovered by the deterministic rungs (no heuristic/AI) → structured_endpoint.
        assert details["discovery_verdict"]["delivery_mechanism"] == "structured_endpoint"

    @patch("src.pipeline.pipeline_steps.discover_portfolio.discover_via_sitemap")
    @patch("src.pipeline.pipeline_steps.discover_portfolio.discover_via_wp_json")
    @patch("src.pipeline.pipeline_steps.discover_portfolio.PortfolioDiscoveryStrategy")
    def test_rungs_skipped_when_in_html_rich(self, mock_strategy_cls, mock_wpjson, mock_sitemap):
        # Scrape already found a real list (> threshold) → don't pay for the rungs.
        rich = [_company(f"Co{i}", f"https://co{i}.com") for i in range(6)]
        strategy = MagicMock()
        strategy.execute.return_value = ("x", {"companies": rich})
        mock_strategy_cls.return_value = strategy

        step = DiscoverPortfolio()
        step._entity_accessor = CompanyAccessor(Company(url="https://firm.com/portfolio"))
        step._request_executor = MagicMock()
        step.execute()

        mock_wpjson.assert_not_called()
        mock_sitemap.assert_not_called()

    @patch("src.pipeline.pipeline_steps.discover_portfolio.discover_via_sitemap")
    @patch("src.pipeline.pipeline_steps.discover_portfolio.discover_via_wp_json")
    @patch("src.pipeline.pipeline_steps.discover_portfolio.PortfolioDiscoveryStrategy")
    def test_rung_results_deduped_against_scrape(
        self, mock_strategy_cls, mock_wpjson, mock_sitemap
    ):
        # Scrape found Acme; wp-json returns Acme (dup) + Gamma → only Gamma is added.
        strategy = MagicMock()
        strategy.execute.return_value = (
            "x",
            {"companies": [_company("Acme", "https://acme.com")]},
        )
        mock_strategy_cls.return_value = strategy
        mock_wpjson.return_value = [
            _company("Acme", "https://acme.com"),
            _company("Gamma", "https://gamma.com"),
        ]
        mock_sitemap.return_value = []

        step = DiscoverPortfolio()
        step._entity_accessor = CompanyAccessor(Company(url="https://firm.com/portfolio"))
        step._request_executor = MagicMock()
        step.execute()

        details = step._request_executor.add_details.call_args[0][0]
        names = [c["name"] for c in details["portfolio_companies"]]
        assert names.count("Acme") == 1
        assert "Gamma" in names
        assert details["portfolio_count"] == 2

    @patch("src.pipeline.pipeline_steps.discover_portfolio.discover_via_sitemap")
    @patch("src.pipeline.pipeline_steps.discover_portfolio.discover_via_wp_json")
    @patch("src.pipeline.pipeline_steps.discover_portfolio.PortfolioDiscoveryStrategy")
    def test_rungs_skipped_for_non_pe_firm(self, mock_strategy_cls, mock_wpjson, mock_sitemap):
        # Thin scrape but the AI extractor says it's not a PE/VC firm → don't probe
        # its structured sources (a law firm's wp-json isn't a portfolio).
        strategy = MagicMock()
        strategy.execute.return_value = (
            "x",
            {"companies": [], "page_text": "skeleton", "script_text": "", "all_links": []},
        )
        mock_strategy_cls.return_value = strategy

        def _not_pe(*, user_prompt: str, **_: object):
            return (
                "extract_portfolio",
                {"is_pe_firm": False, "firm_type_description": "law firm", "companies": []},
                0.0,
                TokenCounts(input_tokens=1, output_tokens=1, cached_input_tokens=0),
            )

        step = DiscoverPortfolio(ai_client_factory=MagicMock())
        step._entity_accessor = CompanyAccessor(Company(url="https://lawfirm.com"))
        step._request_executor = MagicMock()
        with patch(
            "src.pipeline.pipeline_steps.portfolio_extract.run_structured_ai_call",
            side_effect=_not_pe,
        ):
            step.execute()

        mock_wpjson.assert_not_called()
        mock_sitemap.assert_not_called()


class TestFindNewCandidatesStatus:
    """find_new_candidates carries the current/realized status the wp-json rung sets."""

    def test_preserves_status_when_present(self):
        fresh = find_new_candidates(
            [{"name": "OldCo", "url": "https://oldco.com", "status": "realized"}],
            [],
            source="site",
        )
        assert fresh[0]["status"] == "realized"

    def test_defaults_status_empty_when_absent(self):
        fresh = find_new_candidates(
            [{"name": "Acme", "url": "https://acme.com"}], [], source="web_search"
        )
        assert fresh[0]["status"] == ""

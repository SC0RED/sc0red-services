"""Tests for portfolio discovery strategy."""

import json
from unittest.mock import patch

import pytest
from curl_cffi.requests.exceptions import ConnectionError as CurlConnectionError
from curl_cffi.requests.exceptions import HTTPError, ImpersonateError

from src.data_strategies.portfolio_discovery_strategy import (
    _GENERIC_CTA_PATTERNS,
    _SOCIAL_DOMAINS,
    PORTFOLIO_PATHS,
    PortfolioDiscoveryStrategy,
)


class TestPortfolioDiscoveryConstants:
    def test_social_domains_includes_common(self):
        assert "linkedin.com" in _SOCIAL_DOMAINS
        assert "twitter.com" in _SOCIAL_DOMAINS
        assert "facebook.com" in _SOCIAL_DOMAINS

    def test_portfolio_paths_includes_common(self):
        assert "/portfolio" in PORTFOLIO_PATHS
        assert "/companies" in PORTFOLIO_PATHS
        assert "/investments" in PORTFOLIO_PATHS

    def test_cta_patterns_are_strings(self):
        assert len(_GENERIC_CTA_PATTERNS) > 0
        for pattern in _GENERIC_CTA_PATTERNS:
            assert isinstance(pattern, str)


class TestPortfolioDiscoveryStrategy:
    def test_execute_no_url(self):
        strategy = PortfolioDiscoveryStrategy(config={})
        raw_json, meta = strategy.execute()
        assert raw_json == ""
        assert meta["companies"] == []

    @patch("src.data_strategies.portfolio_discovery_strategy.scrape_url")
    def test_execute_finds_external_links(self, mock_scrape):
        mock_scrape.return_value = {
            "text": "Portfolio page",
            "title": "Our Portfolio",
            "description": "",
            "links": [
                {"text": "DataCorp Inc", "href": "https://datacorp.com"},
                {"text": "Beta Inc", "href": "https://beta.com"},
            ],
            "meta_keywords": "",
        }

        strategy = PortfolioDiscoveryStrategy(config={"url": "https://pefirm.com"})
        _raw_json, meta = strategy.execute()

        companies = meta["companies"]
        assert len(companies) >= 1
        urls = [c["url"] for c in companies]
        assert any("datacorp.com" in u for u in urls)

    @patch("src.data_strategies.portfolio_discovery_strategy.scrape_url")
    def test_execute_filters_social_links(self, mock_scrape):
        mock_scrape.return_value = {
            "text": "content",
            "title": "title",
            "description": "",
            "links": [
                {"text": "Follow us", "href": "https://linkedin.com/company/pefirm"},
                {"text": "Twitter", "href": "https://twitter.com/pefirm"},
                {"text": "Real Company", "href": "https://realcompany.com"},
            ],
            "meta_keywords": "",
        }

        strategy = PortfolioDiscoveryStrategy(config={"url": "https://pefirm.com"})
        _, meta = strategy.execute()

        company_urls = [c["url"] for c in meta["companies"]]
        assert not any("linkedin" in u for u in company_urls)
        assert not any("twitter" in u for u in company_urls)

    @patch("src.data_strategies.portfolio_discovery_strategy.scrape_url")
    def test_execute_filters_generic_ctas(self, mock_scrape):
        mock_scrape.return_value = {
            "text": "content",
            "title": "title",
            "description": "",
            "links": [
                {"text": "Learn More", "href": "https://company.com"},
                {"text": "Click Here", "href": "https://company2.com"},
                {"text": "Valid Company", "href": "https://valid.com"},
            ],
            "meta_keywords": "",
        }

        strategy = PortfolioDiscoveryStrategy(config={"url": "https://pefirm.com"})
        _, meta = strategy.execute()

        names = [c["name"] for c in meta["companies"]]
        assert "Learn More" not in names
        assert "Click Here" not in names

    @patch("src.data_strategies.portfolio_discovery_strategy.scrape_url")
    def test_execute_filters_short_and_long_text(self, mock_scrape):
        mock_scrape.return_value = {
            "text": "content",
            "title": "title",
            "description": "",
            "links": [
                {"text": "AB", "href": "https://short.com"},
                {"text": "A" * 61, "href": "https://long.com"},
                {"text": "Good Name", "href": "https://good.com"},
            ],
            "meta_keywords": "",
        }

        strategy = PortfolioDiscoveryStrategy(config={"url": "https://pefirm.com"})
        _, meta = strategy.execute()

        names = [c["name"] for c in meta["companies"]]
        assert "AB" not in names
        assert "Good Name" in names

    @patch("src.data_strategies.portfolio_discovery_strategy.scrape_url")
    def test_execute_deduplicates_urls(self, mock_scrape):
        mock_scrape.return_value = {
            "text": "content",
            "title": "title",
            "description": "",
            "links": [
                {"text": "Company A", "href": "https://company.com"},
                {"text": "Company A Again", "href": "https://company.com"},
            ],
            "meta_keywords": "",
        }

        strategy = PortfolioDiscoveryStrategy(config={"url": "https://pefirm.com"})
        _, meta = strategy.execute()

        urls = [c["url"] for c in meta["companies"]]
        assert len(urls) == len(set(urls))

    @patch("src.data_strategies.portfolio_discovery_strategy.scrape_url")
    def test_execute_scrape_failure_skips_page(self, mock_scrape):
        # Transport/HTTP errors are the fail-soft contract — skip the page.
        mock_scrape.side_effect = CurlConnectionError("Connection error")

        strategy = PortfolioDiscoveryStrategy(config={"url": "https://pefirm.com"})
        _raw_json, meta = strategy.execute()

        # Should not raise, just returns empty — and it kept trying every path
        # rather than aborting on the first transport error.
        assert meta["companies"] == []
        assert mock_scrape.call_count == len(PORTFOLIO_PATHS)

    @patch("src.data_strategies.portfolio_discovery_strategy.scrape_url")
    def test_impersonation_misconfig_propagates(self, mock_scrape):
        # A bad _IMPERSONATE_TARGET is a programming error — it must NOT be
        # swallowed by the fail-soft transport handler as "no companies".
        mock_scrape.side_effect = ImpersonateError("bad target")

        strategy = PortfolioDiscoveryStrategy(config={"url": "https://pefirm.com"})
        with pytest.raises(ImpersonateError):
            strategy.execute()

    @patch("src.data_strategies.portfolio_discovery_strategy.scrape_url")
    def test_execute_internal_portfolio_links(self, mock_scrape):
        mock_scrape.return_value = {
            "text": "content",
            "title": "title",
            "description": "",
            "links": [
                {"text": "Mega Corp", "href": "https://pefirm.com/portfolio/mega-corp"},
                {"text": "Beta Labs", "href": "https://pefirm.com/companies/beta-labs"},
            ],
            "meta_keywords": "",
        }

        strategy = PortfolioDiscoveryStrategy(config={"url": "https://pefirm.com"})
        _, meta = strategy.execute()

        names = [c["name"] for c in meta["companies"]]
        assert "Mega Corp" in names
        assert "Beta Labs" in names

    def test_execute_adds_https_if_missing(self):
        with patch("src.data_strategies.portfolio_discovery_strategy.scrape_url") as mock_scrape:
            mock_scrape.return_value = {
                "text": "content",
                "title": "title",
                "description": "",
                "links": [],
                "meta_keywords": "",
            }
            strategy = PortfolioDiscoveryStrategy(config={"url": "pefirm.com"})
            strategy.execute()
            # The first call should be to the root URL with https
            first_call_url = mock_scrape.call_args_list[0][0][0]
            assert first_call_url.startswith("https://")

    @patch("src.data_strategies.portfolio_discovery_strategy.scrape_url")
    def test_execute_returns_json_string(self, mock_scrape):
        mock_scrape.return_value = {
            "text": "content",
            "title": "title",
            "description": "",
            "links": [{"text": "Test Co", "href": "https://testco.com"}],
            "meta_keywords": "",
        }

        strategy = PortfolioDiscoveryStrategy(config={"url": "https://pefirm.com"})
        raw_json, meta = strategy.execute()

        parsed = json.loads(raw_json)
        assert isinstance(parsed, list)
        assert meta["count"] == len(parsed)

    @patch("src.data_strategies.portfolio_discovery_strategy.scrape_url")
    def test_relative_url_without_leading_slash(self, mock_scrape):
        """href="portfolio/company" gets resolved to base_origin/portfolio/company."""
        mock_scrape.return_value = {
            "text": "content",
            "title": "title",
            "description": "",
            "links": [
                {"text": "Zeta Corp", "href": "portfolio/zeta"},
            ],
            "meta_keywords": "",
        }

        strategy = PortfolioDiscoveryStrategy(config={"url": "https://pefirm.com"})
        _, meta = strategy.execute()

        # Relative link to same domain with /portfolio/ path → treated as internal portfolio
        urls = [c["url"] for c in meta["companies"]]
        assert any("pefirm.com/portfolio/zeta" in u for u in urls)

    @patch("src.data_strategies.portfolio_discovery_strategy.scrape_url")
    def test_same_domain_non_portfolio_links_filtered(self, mock_scrape):
        """Same-domain non-portfolio/companies/investments links are filtered."""
        mock_scrape.return_value = {
            "text": "content",
            "title": "title",
            "description": "",
            "links": [
                {"text": "About Us Page", "href": "https://pefirm.com/about"},
                {"text": "Contact Info", "href": "https://pefirm.com/contact-us"},
            ],
            "meta_keywords": "",
        }

        strategy = PortfolioDiscoveryStrategy(config={"url": "https://pefirm.com"})
        _, meta = strategy.execute()

        assert meta["companies"] == []

    @patch("src.data_strategies.portfolio_discovery_strategy.scrape_url")
    def test_link_text_matching_skip_patterns(self, mock_scrape):
        """Links starting with 'The', 'Login', etc. are skipped."""
        mock_scrape.return_value = {
            "text": "content",
            "title": "title",
            "description": "",
            "links": [
                {"text": "The Company", "href": "https://thecompany.com"},
                {"text": "Login Here", "href": "https://login.com"},
                {"text": "Contact Support", "href": "https://contact.com"},
                {"text": "Valid Corp", "href": "https://validcorp.com"},
            ],
            "meta_keywords": "",
        }

        strategy = PortfolioDiscoveryStrategy(config={"url": "https://pefirm.com"})
        _, meta = strategy.execute()

        names = [c["name"] for c in meta["companies"]]
        assert "The Company" not in names
        assert "Login Here" not in names
        assert "Contact Support" not in names
        assert "Valid Corp" in names

    @patch("src.data_strategies.portfolio_discovery_strategy.scrape_url")
    def test_malformed_link_causes_graceful_skip(self, mock_scrape):
        """A link dict missing 'href' key causes exception → graceful skip."""
        mock_scrape.return_value = {
            "text": "content",
            "title": "title",
            "description": "",
            "links": [
                {"text": "Bad Link"},  # missing 'href'
                {"text": "Good Link", "href": "https://good.com"},
            ],
            "meta_keywords": "",
        }

        strategy = PortfolioDiscoveryStrategy(config={"url": "https://pefirm.com"})
        _, meta = strategy.execute()

        names = [c["name"] for c in meta["companies"]]
        assert "Good Link" in names

    @patch("src.data_strategies.portfolio_discovery_strategy.scrape_url")
    def test_no_hardcoded_company_cap(self, mock_scrape):
        """Heuristic returns all valid candidates — no silent truncation.

        Regression: heuristic path previously truncated at 30 companies
        (cap since removed); must return all valid candidates regardless
        of page size. Customer-facing symptom was perotjain.com returning
        30-38 companies when the page contains 70+.
        """
        links = [{"text": f"Company {i:02d}", "href": f"https://company{i}.com"} for i in range(50)]
        mock_scrape.return_value = {
            "text": "content",
            "title": "title",
            "description": "",
            "links": links,
            "meta_keywords": "",
        }

        strategy = PortfolioDiscoveryStrategy(config={"url": "https://pefirm.com"})
        _, meta = strategy.execute()

        # Every valid candidate is returned — no longer capped at 30.
        # scrape_url is called once per PORTFOLIO_PATHS entry, so the same
        # 50 links are seen multiple times; dedup by URL leaves exactly 50.
        assert len(meta["companies"]) == 50

    @patch("src.data_strategies.portfolio_discovery_strategy.scrape_url")
    @patch("src.data_strategies.portfolio_discovery_strategy.fetch_page_html")
    def test_fallback_data_attributes(self, mock_fetch, mock_scrape):
        """When no links found, fallback to data-company-name/data-company-link attributes."""
        mock_scrape.return_value = {
            "text": "content",
            "title": "title",
            "description": "",
            "links": [],
            "meta_keywords": "",
        }

        mock_fetch.return_value = """
        <html><body>
            <div data-company-name="DataCo" data-company-link="https://dataco.com"></div>
            <div data-company-name="BetaInc" data-company-link="https://betainc.com"></div>
        </body></html>
        """

        strategy = PortfolioDiscoveryStrategy(config={"url": "https://pefirm.com"})
        _, meta = strategy.execute()

        names = [c["name"] for c in meta["companies"]]
        assert "DataCo" in names
        assert "BetaInc" in names

    @patch("src.data_strategies.portfolio_discovery_strategy.scrape_url")
    @patch("src.data_strategies.portfolio_discovery_strategy.fetch_page_html")
    def test_fallback_invalid_data_attributes(self, mock_fetch, mock_scrape):
        """Fallback skips: empty name, non-http URL, duplicate URLs."""
        mock_scrape.return_value = {
            "text": "content",
            "title": "title",
            "description": "",
            "links": [],
            "meta_keywords": "",
        }

        mock_fetch.return_value = """
        <html><body>
            <div data-company-name="" data-company-link="https://empty.com"></div>
            <div data-company-name="NoHttp" data-company-link="ftp://nohttp.com"></div>
            <div data-company-name="ValidCo" data-company-link="https://valid.com"></div>
            <div data-company-name="DupeCo" data-company-link="https://valid.com"></div>
        </body></html>
        """

        strategy = PortfolioDiscoveryStrategy(config={"url": "https://pefirm.com"})
        _, meta = strategy.execute()

        names = [c["name"] for c in meta["companies"]]
        assert "ValidCo" in names
        assert "" not in names
        assert "NoHttp" not in names
        # Duplicate URL should not produce a second entry
        assert len([c for c in meta["companies"] if c["url"] == "https://valid.com"]) == 1

    @patch("src.data_strategies.portfolio_discovery_strategy.scrape_url")
    @patch("src.data_strategies.portfolio_discovery_strategy.fetch_page_html")
    def test_fallback_http_error(self, mock_fetch, mock_scrape):
        """HTTP error during fallback path is handled gracefully (fail-soft)."""
        mock_scrape.return_value = {
            "text": "content",
            "title": "title",
            "description": "",
            "links": [],
            "meta_keywords": "",
        }

        # The impersonating transport raises HTTPError on a bad status (e.g. 500).
        mock_fetch.side_effect = HTTPError("HTTP Error 500")

        strategy = PortfolioDiscoveryStrategy(config={"url": "https://pefirm.com"})
        _, meta = strategy.execute()

        assert meta["companies"] == []


def _empty_scrape_result():
    return {
        "title": "",
        "description": "",
        "text": "",
        "links": [],
        "meta_keywords": "",
        "script_text": "",
        "embedded_companies": [],
        "logo_company_names": [],
    }


class TestEmbeddedStructuredCandidates:
    @patch("src.data_strategies.portfolio_discovery_strategy.scrape_url")
    def test_embedded_records_become_detail_page_candidates(self, mock_scrape):
        def fake(url):
            result = _empty_scrape_result()
            if url.rstrip("/").endswith("/portfolio"):
                result["embedded_companies"] = [
                    {"name": "Calabrio", "slug": "calabrio"},
                    {"name": "Dynatrace", "slug": "dynatrace"},
                ]
            return result

        mock_scrape.side_effect = fake
        _raw, meta = PortfolioDiscoveryStrategy({"url": "https://www.thomabravo.com"}).execute()

        urls = {c["url"] for c in meta["companies"]}
        assert "https://www.thomabravo.com/portfolio/calabrio" in urls
        assert "https://www.thomabravo.com/portfolio/dynatrace" in urls
        assert {"Calabrio", "Dynatrace"} <= {c["name"] for c in meta["companies"]}

    @patch("src.data_strategies.portfolio_discovery_strategy.scrape_url")
    def test_root_only_records_do_not_create_root_urls(self, mock_scrape):
        def fake(url):
            result = _empty_scrape_result()
            if url.rstrip("/") == "https://www.thomabravo.com":  # root only
                result["embedded_companies"] = [{"name": "Acme", "slug": "acme"}]
            return result

        mock_scrape.side_effect = fake
        _raw, meta = PortfolioDiscoveryStrategy({"url": "https://www.thomabravo.com"}).execute()

        # No detail-page parent for the root, so no candidate is fabricated.
        urls = {c["url"] for c in meta["companies"]}
        assert not any(u.endswith("/acme") for u in urls)

    @patch("src.data_strategies.portfolio_discovery_strategy.scrape_url")
    def test_dedupes_structured_against_heuristic_link(self, mock_scrape):
        def fake(url):
            result = _empty_scrape_result()
            if url.rstrip("/").endswith("/portfolio"):
                result["links"] = [
                    {"text": "Calabrio", "href": "https://www.thomabravo.com/portfolio/calabrio"}
                ]
                result["embedded_companies"] = [{"name": "Calabrio", "slug": "calabrio"}]
            return result

        mock_scrape.side_effect = fake
        _raw, meta = PortfolioDiscoveryStrategy({"url": "https://www.thomabravo.com"}).execute()

        calabrio = [
            c
            for c in meta["companies"]
            if c["url"] == "https://www.thomabravo.com/portfolio/calabrio"
        ]
        assert len(calabrio) == 1


class TestLogoGridSeeds:
    @patch("src.data_strategies.portfolio_discovery_strategy.scrape_url")
    def test_logo_names_collected_and_firm_excluded(self, mock_scrape):
        def fake(url):
            result = _empty_scrape_result()
            if url.rstrip("/").endswith("/companies"):
                # last entry contains the firm's domain stem → a self-reference
                result["logo_company_names"] = ["Jamf", "Datto", "VistaEquityPartners"]
            return result

        mock_scrape.side_effect = fake
        _raw, meta = PortfolioDiscoveryStrategy(
            {"url": "https://www.vistaequitypartners.com"}
        ).execute()
        # logo names surface as seeds; site companies stay 0 (names have no URL)
        assert meta["count"] == 0
        seeds = meta["logo_company_names"]
        assert "Jamf" in seeds and "Datto" in seeds
        # firm self-reference (contains the domain stem) filtered out
        assert "VistaEquityPartners" not in seeds

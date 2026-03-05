"""Tests for portfolio discovery strategy."""

import json
from unittest.mock import MagicMock, patch

from src.data_strategies.portfolio_discovery_strategy import (
    PortfolioDiscoveryStrategy,
    _GENERIC_CTA_PATTERNS,
    _MAX_COMPANIES,
    _PORTFOLIO_PATHS,
    _SOCIAL_DOMAINS,
)


class TestPortfolioDiscoveryConstants:
    def test_social_domains_includes_common(self):
        assert "linkedin.com" in _SOCIAL_DOMAINS
        assert "twitter.com" in _SOCIAL_DOMAINS
        assert "facebook.com" in _SOCIAL_DOMAINS

    def test_portfolio_paths_includes_common(self):
        assert "/portfolio" in _PORTFOLIO_PATHS
        assert "/companies" in _PORTFOLIO_PATHS
        assert "/investments" in _PORTFOLIO_PATHS

    def test_max_companies_is_reasonable(self):
        assert _MAX_COMPANIES == 30

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
        raw_json, meta = strategy.execute()

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
        mock_scrape.side_effect = RuntimeError("Connection error")

        strategy = PortfolioDiscoveryStrategy(config={"url": "https://pefirm.com"})
        raw_json, meta = strategy.execute()

        # Should not raise, just returns empty
        assert meta["companies"] == []

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

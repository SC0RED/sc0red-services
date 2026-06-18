"""Tests for portfolio discovery heuristic improvements."""

from unittest.mock import patch

from curl_cffi.requests.exceptions import ConnectionError as CurlConnectionError

from src.data_strategies.portfolio_discovery_strategy import PortfolioDiscoveryStrategy


def _mock_scrape(links):
    """Create a mock scrape_url that returns given links."""
    return {
        "title": "Test",
        "description": "",
        "text": "Portfolio page",
        "links": links,
        "meta_keywords": "",
        "script_text": "",
        "embedded_companies": [],
        "logo_company_names": [],
    }


class TestCTAContextHandling:
    def test_learn_more_with_context_name_passes(self):
        links = [
            {"text": "LEARN MORE", "href": "https://acme.com", "context_name": "Acme Corp"},
        ]
        with patch(
            "src.data_strategies.portfolio_discovery_strategy.scrape_url",
            return_value=_mock_scrape(links),
        ):
            strategy = PortfolioDiscoveryStrategy({"url": "https://firm.com"})
            _, result = strategy.execute()
            companies = result["companies"]
            assert len(companies) == 1
            assert companies[0]["name"] == "Acme Corp"
            assert companies[0]["url"] == "https://acme.com"

    def test_learn_more_without_context_falls_back_to_url_domain(self):
        """CTA link with no context is kept; name is derived from the URL domain.

        Prior behavior dropped these links entirely. That cost us ~9 cards on
        perotjain.com (empty alt + no heading). Deriving ``Acme`` from
        ``acme.com`` is imperfect but strictly better than losing the URL —
        the AI validation step confirms whether the candidate is real.
        """
        links = [
            {"text": "LEARN MORE", "href": "https://acme.com", "context_name": ""},
        ]
        with patch(
            "src.data_strategies.portfolio_discovery_strategy.scrape_url",
            return_value=_mock_scrape(links),
        ):
            strategy = PortfolioDiscoveryStrategy({"url": "https://firm.com"})
            _, result = strategy.execute()
            companies = result["companies"]
            assert len(companies) == 1
            assert companies[0]["name"] == "Acme"
            assert companies[0]["url"] == "https://acme.com"

    def test_normal_link_text_used_directly(self):
        links = [
            {"text": "Acme Corp", "href": "https://acme.com", "context_name": ""},
        ]
        with patch(
            "src.data_strategies.portfolio_discovery_strategy.scrape_url",
            return_value=_mock_scrape(links),
        ):
            strategy = PortfolioDiscoveryStrategy({"url": "https://firm.com"})
            _, result = strategy.execute()
            assert len(result["companies"]) == 1
            assert result["companies"][0]["name"] == "Acme Corp"

    def test_same_domain_links_filtered(self):
        links = [
            {"text": "About Us", "href": "https://firm.com/about", "context_name": ""},
        ]
        with patch(
            "src.data_strategies.portfolio_discovery_strategy.scrape_url",
            return_value=_mock_scrape(links),
        ):
            strategy = PortfolioDiscoveryStrategy({"url": "https://firm.com"})
            _, result = strategy.execute()
            assert len(result["companies"]) == 0

    def test_social_links_filtered(self):
        links = [
            {"text": "Follow Us", "href": "https://twitter.com/firm", "context_name": ""},
        ]
        with patch(
            "src.data_strategies.portfolio_discovery_strategy.scrape_url",
            return_value=_mock_scrape(links),
        ):
            strategy = PortfolioDiscoveryStrategy({"url": "https://firm.com"})
            _, result = strategy.execute()
            assert len(result["companies"]) == 0

    def test_multiple_cta_links_with_mixed_context(self):
        """Links with context keep their rich names; links without fall back to the URL domain."""
        links = [
            {"text": "Learn More", "href": "https://acme.com", "context_name": "Acme Corp"},
            {"text": "Learn More", "href": "https://beta.com", "context_name": "Beta Inc"},
            {"text": "Learn More", "href": "https://gamma.com", "context_name": ""},
        ]
        with patch(
            "src.data_strategies.portfolio_discovery_strategy.scrape_url",
            return_value=_mock_scrape(links),
        ):
            strategy = PortfolioDiscoveryStrategy({"url": "https://firm.com"})
            _, result = strategy.execute()
            assert len(result["companies"]) == 3
            names = {c["name"] for c in result["companies"]}
            assert names == {"Acme Corp", "Beta Inc", "Gamma"}

    def test_empty_link_text_with_context(self):
        links = [
            {"text": "", "href": "https://acme.com", "context_name": "Acme Corp"},
        ]
        with patch(
            "src.data_strategies.portfolio_discovery_strategy.scrape_url",
            return_value=_mock_scrape(links),
        ):
            strategy = PortfolioDiscoveryStrategy({"url": "https://firm.com"})
            _, result = strategy.execute()
            assert len(result["companies"]) == 1

    def test_no_url_returns_empty(self):
        strategy = PortfolioDiscoveryStrategy({"url": ""})
        _, result = strategy.execute()
        assert result["companies"] == []


class TestScrapeFailSoft:
    def test_transport_error_skips_page_without_raising(self):
        """A transport/HTTP error on a portfolio page is skipped, not fatal."""
        strategy = PortfolioDiscoveryStrategy({"url": "https://firm.com"})
        with (
            patch(
                "src.data_strategies.portfolio_discovery_strategy.scrape_url",
                side_effect=CurlConnectionError("blocked"),
            ),
            patch(
                "src.data_strategies.portfolio_discovery_strategy.PortfolioDiscoveryStrategy._fallback_data_attributes",
                return_value=[],
            ),
        ):
            _, result = strategy.execute()
        assert result["companies"] == []


class TestDetailLinkSlugNames:
    def test_descriptive_text_uses_slug_name(self):
        links = [
            {
                "text": "Integrated cloud communications platform for businesses worldwide today",
                "href": "https://firm.com/investments/8x8",
                "context_name": "",
            },
        ]
        with patch(
            "src.data_strategies.portfolio_discovery_strategy.scrape_url",
            return_value=_mock_scrape(links),
        ):
            _, result = PortfolioDiscoveryStrategy({"url": "https://firm.com"}).execute()
        companies = result["companies"]
        assert any(
            c["name"] == "8x8" and c["url"] == "https://firm.com/investments/8x8"
            for c in companies
        )

    def test_slug_with_separators_title_cased(self):
        links = [
            {
                "text": "K-12 student information system for school districts across the country",
                "href": "https://firm.com/investments/aeries-software",
                "context_name": "",
            },
        ]
        with patch(
            "src.data_strategies.portfolio_discovery_strategy.scrape_url",
            return_value=_mock_scrape(links),
        ):
            _, result = PortfolioDiscoveryStrategy({"url": "https://firm.com"}).execute()
        assert any(c["name"] == "Aeries Software" for c in result["companies"])

    def test_clean_anchor_text_preserved(self):
        # Short, valid anchor name on a detail link is kept (slug does not override).
        links = [
            {"text": "Accela", "href": "https://firm.com/investments/accela", "context_name": ""},
        ]
        with patch(
            "src.data_strategies.portfolio_discovery_strategy.scrape_url",
            return_value=_mock_scrape(links),
        ):
            _, result = PortfolioDiscoveryStrategy({"url": "https://firm.com"}).execute()
        names = [c["name"] for c in result["companies"]]
        assert "Accela" in names

    def test_non_detail_same_domain_link_not_a_candidate(self):
        links = [
            {"text": "About Us", "href": "https://firm.com/about", "context_name": ""},
        ]
        with patch(
            "src.data_strategies.portfolio_discovery_strategy.scrape_url",
            return_value=_mock_scrape(links),
        ):
            _, result = PortfolioDiscoveryStrategy({"url": "https://firm.com"}).execute()
        assert result["companies"] == []

    def test_unusable_text_and_unusable_slug_dropped(self):
        # Internal detail link, descriptive text (out of bounds) AND a 1-char slug
        # (slug name also out of bounds) → no derivable name → dropped.
        links = [
            {
                "text": "A very long descriptive sentence exceeding the name length cap",
                "href": "https://firm.com/investments/a",
                "context_name": "",
            },
        ]
        with patch(
            "src.data_strategies.portfolio_discovery_strategy.scrape_url",
            return_value=_mock_scrape(links),
        ):
            _, result = PortfolioDiscoveryStrategy({"url": "https://firm.com"}).execute()
        assert result["companies"] == []

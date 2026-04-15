"""Tests for portfolio discovery heuristic improvements."""

from unittest.mock import patch

from src.data_strategies.portfolio_discovery_strategy import PortfolioDiscoveryStrategy


def _mock_scrape(links):
    """Create a mock scrape_url that returns given links."""
    return {
        "title": "Test",
        "description": "",
        "text": "Portfolio page",
        "links": links,
        "meta_keywords": "",
    }


class TestCTAContextHandling:
    def test_learn_more_with_context_name_passes(self):
        links = [
            {"text": "LEARN MORE", "href": "https://acme.com", "context_name": "Acme Corp"},
        ]
        with patch("src.data_strategies.portfolio_discovery_strategy.scrape_url", return_value=_mock_scrape(links)):
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
        with patch("src.data_strategies.portfolio_discovery_strategy.scrape_url", return_value=_mock_scrape(links)):
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
        with patch("src.data_strategies.portfolio_discovery_strategy.scrape_url", return_value=_mock_scrape(links)):
            strategy = PortfolioDiscoveryStrategy({"url": "https://firm.com"})
            _, result = strategy.execute()
            assert len(result["companies"]) == 1
            assert result["companies"][0]["name"] == "Acme Corp"

    def test_same_domain_links_filtered(self):
        links = [
            {"text": "About Us", "href": "https://firm.com/about", "context_name": ""},
        ]
        with patch("src.data_strategies.portfolio_discovery_strategy.scrape_url", return_value=_mock_scrape(links)):
            strategy = PortfolioDiscoveryStrategy({"url": "https://firm.com"})
            _, result = strategy.execute()
            assert len(result["companies"]) == 0

    def test_social_links_filtered(self):
        links = [
            {"text": "Follow Us", "href": "https://twitter.com/firm", "context_name": ""},
        ]
        with patch("src.data_strategies.portfolio_discovery_strategy.scrape_url", return_value=_mock_scrape(links)):
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
        with patch("src.data_strategies.portfolio_discovery_strategy.scrape_url", return_value=_mock_scrape(links)):
            strategy = PortfolioDiscoveryStrategy({"url": "https://firm.com"})
            _, result = strategy.execute()
            assert len(result["companies"]) == 3
            names = {c["name"] for c in result["companies"]}
            assert names == {"Acme Corp", "Beta Inc", "Gamma"}

    def test_empty_link_text_with_context(self):
        links = [
            {"text": "", "href": "https://acme.com", "context_name": "Acme Corp"},
        ]
        with patch("src.data_strategies.portfolio_discovery_strategy.scrape_url", return_value=_mock_scrape(links)):
            strategy = PortfolioDiscoveryStrategy({"url": "https://firm.com"})
            _, result = strategy.execute()
            assert len(result["companies"]) == 1

    def test_no_url_returns_empty(self):
        strategy = PortfolioDiscoveryStrategy({"url": ""})
        _, result = strategy.execute()
        assert result["companies"] == []

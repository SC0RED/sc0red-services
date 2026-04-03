"""Tests for URLResolutionStrategy."""

from unittest.mock import MagicMock

import pytest
from signalfield_core.models.enums import Precision, ReasoningEffort, Verbosity

from src.data_strategies.url_resolution_strategy import _SYSTEM_PROMPT, URLResolutionStrategy


class TestURLResolutionStrategy:
    def _make_mock_factory(self, response_data):
        """Create a mock AIClientFactory that returns structured response data."""
        mock_factory = MagicMock()
        mock_client = MagicMock()
        mock_factory.get_client.return_value = mock_client
        mock_response = MagicMock()
        mock_response.content = response_data
        mock_client.query_structured.return_value = mock_response
        return mock_factory

    def test_execute_no_url_raises(self):
        strategy = URLResolutionStrategy(config={})
        with pytest.raises(ValueError, match="URL is required"):
            strategy.execute()

    def test_execute_no_factory_raises(self):
        strategy = URLResolutionStrategy(config={"url": "https://example.com"})
        with pytest.raises(RuntimeError, match="AI client factory not configured"):
            strategy.execute()

    def test_execute_resolved_to_different_url(self):
        mock_factory = self._make_mock_factory({"actual_url": "https://actual-company.com"})

        strategy = URLResolutionStrategy(
            config={
                "url": "https://portfolio.com/company",
                "scraped_text": "Some text about the company",
                "scraped_title": "Portfolio Company",
                "scraped_links": [{"text": "Visit", "href": "https://actual-company.com"}],
                "ai_client_factory": mock_factory,
            }
        )
        url, meta = strategy.execute()
        assert url == "https://actual-company.com"
        assert meta["resolved"] is True
        assert meta["original_url"] == "https://portfolio.com/company"
        mock_factory.get_client.assert_called_once_with(
            verbosity=Verbosity.LOW,
            reasoning_effort=ReasoningEffort.LOW,
            precision=Precision.STANDARD,
            instructions=_SYSTEM_PROMPT,
        )

    def test_execute_same_url(self):
        mock_factory = self._make_mock_factory({"actual_url": "https://example.com"})

        strategy = URLResolutionStrategy(
            config={
                "url": "https://example.com",
                "scraped_text": "Text",
                "ai_client_factory": mock_factory,
            }
        )
        url, meta = strategy.execute()
        assert url == "https://example.com"
        assert meta["resolved"] is False

    def test_execute_non_http_url_fallback(self):
        mock_factory = self._make_mock_factory({"actual_url": "not-a-url"})

        strategy = URLResolutionStrategy(
            config={
                "url": "https://example.com",
                "scraped_text": "Text",
                "ai_client_factory": mock_factory,
            }
        )
        url, meta = strategy.execute()
        assert url == "https://example.com"
        assert meta["resolved"] is False

    def test_execute_api_error_fallback(self):
        mock_factory = MagicMock()
        mock_client = MagicMock()
        mock_factory.get_client.return_value = mock_client
        mock_client.query_structured.side_effect = RuntimeError("API error")

        strategy = URLResolutionStrategy(
            config={
                "url": "https://example.com",
                "scraped_text": "Text",
                "ai_client_factory": mock_factory,
            }
        )
        url, meta = strategy.execute()
        assert url == "https://example.com"
        assert meta["resolved"] is False

    def test_dependencies(self):
        strategy = URLResolutionStrategy()
        assert "web_scrape" in strategy._dependencies

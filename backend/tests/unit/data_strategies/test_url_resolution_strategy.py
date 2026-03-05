"""Tests for URLResolutionStrategy."""

import json
from unittest.mock import MagicMock, patch

from src.data_strategies.url_resolution_strategy import URLResolutionStrategy


class TestURLResolutionStrategy:
    def _make_mock_response(self, data):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps(data)
        return mock_response

    def test_execute_no_url(self):
        strategy = URLResolutionStrategy(config={})
        url, meta = strategy.execute()
        assert url == ""
        assert meta["resolved"] is False

    @patch("src.data_strategies.url_resolution_strategy.openai.OpenAI")
    def test_execute_resolved_to_different_url(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = self._make_mock_response(
            {"actual_url": "https://actual-company.com"}
        )

        strategy = URLResolutionStrategy(config={
            "url": "https://portfolio.com/company",
            "scraped_text": "Some text about the company",
            "scraped_title": "Portfolio Company",
            "scraped_links": [{"text": "Visit", "href": "https://actual-company.com"}],
            "openai_api_key": "test-key",
        })
        url, meta = strategy.execute()
        assert url == "https://actual-company.com"
        assert meta["resolved"] is True
        assert meta["original_url"] == "https://portfolio.com/company"

    @patch("src.data_strategies.url_resolution_strategy.openai.OpenAI")
    def test_execute_same_url(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = self._make_mock_response(
            {"actual_url": "https://example.com"}
        )

        strategy = URLResolutionStrategy(config={
            "url": "https://example.com",
            "scraped_text": "Text",
            "openai_api_key": "test-key",
        })
        url, meta = strategy.execute()
        assert url == "https://example.com"
        assert meta["resolved"] is False

    @patch("src.data_strategies.url_resolution_strategy.openai.OpenAI")
    def test_execute_non_http_url_fallback(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = self._make_mock_response(
            {"actual_url": "not-a-url"}
        )

        strategy = URLResolutionStrategy(config={
            "url": "https://example.com",
            "scraped_text": "Text",
            "openai_api_key": "test-key",
        })
        url, meta = strategy.execute()
        assert url == "https://example.com"
        assert meta["resolved"] is False

    @patch("src.data_strategies.url_resolution_strategy.openai.OpenAI")
    def test_execute_api_error_fallback(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.side_effect = RuntimeError("API error")

        strategy = URLResolutionStrategy(config={
            "url": "https://example.com",
            "scraped_text": "Text",
            "openai_api_key": "test-key",
        })
        url, meta = strategy.execute()
        assert url == "https://example.com"
        assert meta["resolved"] is False

    def test_dependencies(self):
        strategy = URLResolutionStrategy()
        assert "web_scrape" in strategy._dependencies

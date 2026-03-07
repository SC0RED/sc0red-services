"""Tests for ScrapeAndResolveURL pipeline step."""

from unittest.mock import MagicMock, patch

import pytest

from src.facades.company_accessor import CompanyAccessor
from src.models.model_company import Company
from src.pipeline.pipeline_steps.scrape_and_resolve import ScrapeAndResolveURL


class TestScrapeAndResolveURL:
    @patch("src.pipeline.pipeline_steps.scrape_and_resolve.URLResolutionStrategy")
    @patch("src.pipeline.pipeline_steps.scrape_and_resolve.WebScraperStrategy")
    def test_execute_no_resolution(self, mock_scraper_cls, mock_resolver_cls):
        mock_scraper = MagicMock()
        mock_scraper.execute.return_value = (
            "Sufficient content about the company for analysis purposes here",
            {"title": "Test", "links": [{"text": "L", "href": "https://l.com"}]},
        )
        mock_scraper_cls.return_value = mock_scraper

        mock_resolver = MagicMock()
        mock_resolver.execute.return_value = (
            "https://example.com",
            {"resolved": False},
        )
        mock_resolver_cls.return_value = mock_resolver

        company = Company(url="https://example.com")
        accessor = CompanyAccessor(company)

        step = ScrapeAndResolveURL(ai_client_factory=MagicMock())
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        step.execute()

        expected = "Sufficient content about the company for analysis purposes here"
        assert accessor.company.scraped_text == expected
        assert accessor.company.actual_url == "https://example.com"
        step._request_executor.mark_question_complete.assert_called_with("scrape_and_resolve")

    @patch("src.pipeline.pipeline_steps.scrape_and_resolve.scrape_url")
    @patch("src.pipeline.pipeline_steps.scrape_and_resolve.URLResolutionStrategy")
    @patch("src.pipeline.pipeline_steps.scrape_and_resolve.WebScraperStrategy")
    def test_execute_with_resolution(self, mock_scraper_cls, mock_resolver_cls, mock_scrape_url):
        mock_scraper = MagicMock()
        mock_scraper.execute.return_value = (
            "Content from portfolio page that is long enough for processing",
            {"title": "Portfolio", "links": []},
        )
        mock_scraper_cls.return_value = mock_scraper

        mock_resolver = MagicMock()
        mock_resolver.execute.return_value = (
            "https://actual-company.com",
            {"resolved": True},
        )
        mock_resolver_cls.return_value = mock_resolver

        mock_scrape_url.return_value = {
            "text": "Actual company content that is also long enough for processing here",
        }

        company = Company(url="https://portfolio.com/company")
        accessor = CompanyAccessor(company)

        step = ScrapeAndResolveURL(ai_client_factory=MagicMock())
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        step.execute()

        assert "portfolio" in accessor.company.scraped_text.lower()
        assert "actual company" in accessor.company.scraped_text.lower()
        assert accessor.company.actual_url == "https://actual-company.com"

    @patch("src.pipeline.pipeline_steps.scrape_and_resolve.URLResolutionStrategy")
    @patch("src.pipeline.pipeline_steps.scrape_and_resolve.WebScraperStrategy")
    def test_execute_insufficient_content(self, mock_scraper_cls, mock_resolver_cls):
        mock_scraper = MagicMock()
        mock_scraper.execute.return_value = ("short", {})
        mock_scraper_cls.return_value = mock_scraper

        company = Company(url="https://example.com")
        accessor = CompanyAccessor(company)

        step = ScrapeAndResolveURL(ai_client_factory=MagicMock())
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        with pytest.raises(ValueError, match="Insufficient content"):
            step.execute()

    @patch("src.pipeline.pipeline_steps.scrape_and_resolve.scrape_url")
    @patch("src.pipeline.pipeline_steps.scrape_and_resolve.URLResolutionStrategy")
    @patch("src.pipeline.pipeline_steps.scrape_and_resolve.WebScraperStrategy")
    def test_execute_resolution_scrape_failure_fallback(
        self,
        mock_scraper_cls,
        mock_resolver_cls,
        mock_scrape_url,
    ):
        mock_scraper = MagicMock()
        mock_scraper.execute.return_value = (
            "Original content that is long enough for the validation check here",
            {"title": "Test", "links": []},
        )
        mock_scraper_cls.return_value = mock_scraper

        mock_resolver = MagicMock()
        mock_resolver.execute.return_value = (
            "https://resolved.com",
            {"resolved": True},
        )
        mock_resolver_cls.return_value = mock_resolver

        mock_scrape_url.side_effect = RuntimeError("Connection error")

        company = Company(url="https://original.com")
        accessor = CompanyAccessor(company)

        step = ScrapeAndResolveURL(ai_client_factory=MagicMock())
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        step.execute()

        # Falls back to original URL on resolution scrape failure
        assert accessor.company.actual_url == "https://original.com"

    @patch("src.pipeline.pipeline_steps.scrape_and_resolve.scrape_url")
    @patch("src.pipeline.pipeline_steps.scrape_and_resolve.URLResolutionStrategy")
    @patch("src.pipeline.pipeline_steps.scrape_and_resolve.WebScraperStrategy")
    def test_execute_resolved_content_too_short(
        self,
        mock_scraper_cls,
        mock_resolver_cls,
        mock_scrape_url,
    ):
        mock_scraper = MagicMock()
        mock_scraper.execute.return_value = (
            "Original content that is long enough for the validation check here",
            {"title": "Test", "links": []},
        )
        mock_scraper_cls.return_value = mock_scraper

        mock_resolver = MagicMock()
        mock_resolver.execute.return_value = (
            "https://resolved.com",
            {"resolved": True},
        )
        mock_resolver_cls.return_value = mock_resolver

        mock_scrape_url.return_value = {"text": "short"}

        company = Company(url="https://original.com")
        accessor = CompanyAccessor(company)

        step = ScrapeAndResolveURL(ai_client_factory=MagicMock())
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        step.execute()

        # Content not combined if resolved page is too short
        assert "short" not in accessor.company.scraped_text

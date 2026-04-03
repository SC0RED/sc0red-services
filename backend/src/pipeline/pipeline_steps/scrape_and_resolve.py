"""Stage 0+1: Scrape initial URL and resolve actual company URL.

Ports analyzeCompany.ts:72-131.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, cast

import httpx
from signalfield_core.pipeline.step import RequestStep

from src.data_strategies.url_resolution_strategy import URLResolutionStrategy
from src.data_strategies.web_scraper_strategy import WebScraperStrategy, scrape_url
from src.pipeline.step_timer import StepTimer

if TYPE_CHECKING:
    from signalfield_core.services.ai_client_factory import AIClientFactory

    from src.facades.company_accessor import CompanyAccessor

logger = logging.getLogger(__name__)

_MIN_CONTENT_LENGTH = 50


class ScrapeAndResolveURL(RequestStep):
    """Scrapes the initial URL, then resolves the actual company website.

    If the URL is a PE portfolio listing, AI identifies the real company URL
    and scrapes that too. Combines both content sources.
    """

    def __init__(self, ai_client_factory: AIClientFactory | None = None) -> None:
        super().__init__()
        self._ai_client_factory = ai_client_factory

    def execute(self) -> None:
        """Scrape the initial URL and resolve the actual company website."""
        accessor = cast("CompanyAccessor", self.entity_accessor)
        url = accessor.company.url
        timer = StepTimer("ScrapeAndResolveURL")

        # Stage 0: Scrape initial URL
        with timer.measure("initial_scrape"):
            scraper = WebScraperStrategy({"url": url})
            text, metadata = scraper.execute()

        if not text or len(text.strip()) < _MIN_CONTENT_LENGTH:
            message = f"Insufficient content scraped from {url}"
            raise ValueError(message)

        accessor.set_scraped_text(text)
        accessor.set_scraped_links(metadata.get("links", []))
        accessor.set_scraped_title(metadata.get("title", ""))

        # Stage 1: Resolve actual URL
        with timer.measure("url_resolution"):
            resolver = URLResolutionStrategy(
                {
                    "url": url,
                    "scraped_text": text,
                    "scraped_title": metadata.get("title", ""),
                    "scraped_links": metadata.get("links", []),
                    "ai_client_factory": self._ai_client_factory,
                }
            )
            actual_url, resolve_meta = resolver.execute()
        accessor.set_actual_url(actual_url)

        # If resolved to a different URL, scrape it and combine content
        if resolve_meta.get("resolved"):
            with timer.measure("resolved_url_scrape"):
                try:
                    actual_result = scrape_url(actual_url)
                    actual_text = actual_result.get("text", "")
                    if actual_text and len(actual_text.strip()) >= _MIN_CONTENT_LENGTH:
                        combined = (
                            f"[Context from portfolio listing ({url}):\n{text[:2000]}]\n\n"
                            f"[Content from actual company website ({actual_url}):\n{actual_text}]"
                        )
                        accessor.set_scraped_text(combined)
                except (httpx.RequestError, httpx.HTTPStatusError):
                    logger.warning("Failed to scrape resolved URL %s, using original", actual_url)
                    accessor.set_actual_url(url)

        self.request_executor.add_details(timer.to_details())
        self.request_executor.mark_question_complete("scrape_and_resolve")

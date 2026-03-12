"""AI-powered URL resolution strategy.

Ports the URL resolution logic from pe-scan/src/lib/ai/analyzeCompany.ts:90-131.
Identifies whether a URL is a PE portfolio listing and resolves to the actual
company website.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from signalfield_core.data.strategy import DataStrategyExecutor
from signalfield_core.models.enums import Precision, ReasoningEffort, Verbosity

if TYPE_CHECKING:
    from signalfield_core.services.ai_client_factory import AIClientFactory

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a data extraction assistant. Your task is to find the actual "
    "website URL of the primary company described in the provided web page "
    "content.\n"
    "If the provided URL is already the company's actual operating website "
    "(not a private equity firm's portfolio listing), return that same URL.\n"
    "If the provided URL is a portfolio listing or directory, look at the "
    "provided text and links to find the actual external website of the "
    "company."
)

_URL_RESOLUTION_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "actual_url": {"type": "string", "description": "The actual company website URL"},
    },
    "required": ["actual_url"],
    "additionalProperties": False,
}


class URLResolutionStrategy(DataStrategyExecutor):
    """Resolves actual company URL from a potentially indirect page.

    Config keys:
        url (str): The original URL provided by the user.
        scraped_text (str): Text content from the scraped page.
        scraped_title (str): Page title.
        scraped_links (list[dict]): Links found on the page.
        ai_client_factory (AIClientFactory): Factory for creating AI clients.
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(dependencies=["web_scrape"])
        self._config = config or {}

    def execute(self) -> tuple[str, dict[str, Any]]:
        """Resolve the actual company URL from a potentially indirect page."""
        url = self._config.get("url", "")
        scraped_text = self._config.get("scraped_text", "")
        scraped_title = self._config.get("scraped_title", "")
        scraped_links = self._config.get("scraped_links", [])
        ai_client_factory: AIClientFactory | None = self._config.get("ai_client_factory")

        if not url:
            raise ValueError("URL is required for resolution")

        user_prompt = (
            f"Provided URL: {url}\n"
            f"Page Title: {scraped_title}\n\n"
            f"Text Preview:\n{scraped_text[:3000]}\n\n"
            f"Links found on page:\n{json.dumps(scraped_links[:100])}\n\n"
            "Return the actual company website URL."
        )

        if not ai_client_factory:
            raise RuntimeError("AI client factory not configured for URL resolution")

        client = ai_client_factory.get_client(
            verbosity=Verbosity.LOW,
            reasoning_effort=ReasoningEffort.LOW,
            precision=Precision.STANDARD,
        )
        prompt = f"{_SYSTEM_PROMPT}\n\n{user_prompt}"
        try:
            response = client.query_structured(
                input_text=prompt, json_schema=_URL_RESOLUTION_SCHEMA
            )
            actual_url = response.content["actual_url"]

            if actual_url and actual_url.startswith("http"):
                resolved = actual_url.rstrip("/") != url.rstrip("/")
                return actual_url, {"resolved": resolved, "original_url": url}

            logger.warning("AI returned non-HTTP URL %r for %s, using original", actual_url, url)
        except Exception:
            logger.warning("URL resolution failed for %s, using original", url, exc_info=True)

        return url, {"resolved": False, "original_url": url}

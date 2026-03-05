"""AI-powered URL resolution strategy.

Ports the URL resolution logic from pe-scan/src/lib/ai/analyzeCompany.ts:90-131.
Identifies whether a URL is a PE portfolio listing and resolves to the actual
company website.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import openai
from signalfield_core.data.strategy import DataStrategyExecutor

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a data extraction assistant. Your task is to find the actual "
    "website URL of the primary company described in the provided web page "
    "content.\n"
    "If the provided URL is already the company's actual operating website "
    "(not a private equity firm's portfolio listing), return that same URL.\n"
    "If the provided URL is a portfolio listing or directory, look at the "
    "provided text and links to find the actual external website of the "
    "company.\n"
    'Respond with ONLY a JSON object containing "actual_url" (string).'
)


class URLResolutionStrategy(DataStrategyExecutor):
    """Resolves actual company URL from a potentially indirect page.

    Config keys:
        url (str): The original URL provided by the user.
        scraped_text (str): Text content from the scraped page.
        scraped_title (str): Page title.
        scraped_links (list[dict]): Links found on the page.
        openai_api_key (str): OpenAI API key.
        model (str): Model to use (default: gpt-4o).
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
        api_key = self._config.get("openai_api_key", "")
        model = self._config.get("model", "gpt-4o")

        if not url:
            return url, {"resolved": False, "reason": "No URL provided"}

        user_prompt = (
            f"Provided URL: {url}\n"
            f"Page Title: {scraped_title}\n\n"
            f"Text Preview:\n{scraped_text[:3000]}\n\n"
            f"Links found on page:\n{json.dumps(scraped_links[:100])}\n\n"
            'Return JSON with "actual_url".'
        )

        try:
            client = openai.OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model=model,
                temperature=0.3,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
            )
            content = response.choices[0].message.content or ""
            parsed = json.loads(content)
            actual_url = parsed.get("actual_url", url)

            if actual_url and actual_url.startswith("http"):
                resolved = actual_url.rstrip("/") != url.rstrip("/")
                return actual_url, {"resolved": resolved, "original_url": url}

        except Exception:  # noqa: BLE001
            logger.warning("URL resolution failed for %s, using original", url, exc_info=True)

        return url, {"resolved": False, "original_url": url}

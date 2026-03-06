"""Web scraper data strategy — ports scrapeUrl() from pe-scan/src/lib/scraper/index.ts.

Uses httpx + BeautifulSoup4 instead of Cheerio.
"""

from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from signalfield_core.data.strategy import DataStrategyExecutor

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
_HEADERS = {
    "User-Agent": _USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
_TIMEOUT = 15.0
_MAX_TEXT_LENGTH = 20_000


def normalize_url(url: str) -> str:
    """Normalize a URL to origin + pathname."""
    if not url.startswith("http"):
        url = f"https://{url}"
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"


def scrape_url(url: str) -> dict[str, Any]:
    """Scrape a URL and return structured data.

    Returns:
        Dict with keys: title, description, text, links, meta_keywords
    """
    normalized = normalize_url(url)

    with httpx.Client(follow_redirects=True, timeout=_TIMEOUT) as client:
        response = client.get(normalized, headers=_HEADERS)
        response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # Remove script, style, nav clutter (matches Cheerio removals)
    for tag in soup.find_all(["script", "style", "noscript", "nav", "footer", "header", "aside"]):
        tag.decompose()

    # Remove elements by class name patterns
    for cls in ["nav", "footer", "header", "sidebar", "cookie", "popup"]:
        for el in soup.find_all(class_=re.compile(cls, re.IGNORECASE)):
            el.decompose()

    # Extract title
    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    if not title:
        h1 = soup.find("h1")
        if h1:
            title = h1.get_text(strip=True)

    # Extract meta description
    description = ""
    meta_desc = soup.find("meta", attrs={"name": "description"})
    if meta_desc:
        description = meta_desc.get("content", "")
    if not description:
        og_desc = soup.find("meta", attrs={"property": "og:description"})
        if og_desc:
            description = og_desc.get("content", "")

    # Extract meta keywords
    meta_kw = soup.find("meta", attrs={"name": "keywords"})
    meta_keywords = meta_kw.get("content", "") if meta_kw else ""

    # Extract body text
    body = soup.find("body")
    text = ""
    if body:
        text = re.sub(r"\s+", " ", body.get_text(separator=" ")).strip()[:_MAX_TEXT_LENGTH]

    # Extract links
    links: list[dict[str, str]] = []
    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        link_text = a.get_text(strip=True)

        # Fallback for image-based links
        if not link_text:
            link_text = a.get("aria-label", "")
            if not link_text:
                img = a.find("img")
                if img:
                    link_text = img.get("alt", "")
                link_text = link_text.strip() if link_text else ""

        if link_text and href and not href.startswith("#") and not href.startswith("mailto:"):
            links.append({"text": link_text, "href": href})

    return {
        "title": title,
        "description": description,
        "text": text,
        "links": links,
        "meta_keywords": meta_keywords,
    }


class WebScraperStrategy(DataStrategyExecutor):
    """DataStrategyExecutor that scrapes a URL using httpx + BeautifulSoup.

    Config keys:
        url (str): The URL to scrape.
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__()
        self._config = config or {}

    def execute(self) -> tuple[str, dict[str, Any]]:
        """Scrape the configured URL and return structured text and metadata."""
        url = self._config.get("url", "")
        if not url:
            return "", {"error": "No URL provided"}

        try:
            result = scrape_url(url)
            return result["text"], {
                "title": result["title"],
                "description": result["description"],
                "links": result["links"],
                "meta_keywords": result["meta_keywords"],
            }
        except httpx.HTTPStatusError as e:
            logger.warning("HTTP error scraping %s: %s", url, e)
            return "", {"error": f"HTTP {e.response.status_code}"}
        except httpx.RequestError as e:
            logger.warning("Request error scraping %s: %s", url, e)
            return "", {"error": str(e)}

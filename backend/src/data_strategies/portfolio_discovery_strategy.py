"""Portfolio company discovery strategy.

Ports discoverPortfolioCompanies() from pe-scan/src/lib/scraper/index.ts:80-196.
Crawls common portfolio page paths, filters links, and returns discovered companies.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from signalfield_core.data.strategy import DataStrategyExecutor

from src.data_strategies.web_scraper_strategy import (
    SCRAPER_HEADERS,
    SCRAPER_TIMEOUT,
    scrape_url,
)

logger = logging.getLogger(__name__)

_SOCIAL_DOMAINS = {
    "linkedin.com",
    "twitter.com",
    "facebook.com",
    "instagram.com",
    "youtube.com",
    "google.com",
    "apple.com",
    "vimeo.com",
}

_GENERIC_CTA_PATTERNS = [
    "learn more",
    "click here",
    "read more",
    "view all",
    "watch video",
    "see all",
]

_STARTS_WITH_SKIP = re.compile(
    r"^(the|our|a|an|login|sign|contact|about|terms|privacy)", re.IGNORECASE
)

_MAX_COMPANIES = 30
_HTTP_OK = 200
_MIN_COMPANY_NAME_LENGTH = 2
_MAX_COMPANY_NAME_LENGTH = 60

_PORTFOLIO_PATHS = [
    "",  # root URL
    "/portfolio",
    "/companies",
    "/investments",
    "/portfolio-companies",
    "/our-companies",
]


class PortfolioDiscoveryStrategy(DataStrategyExecutor):
    """Discovers portfolio companies from a PE firm's website.

    Config keys:
        url (str): The PE firm's website URL.
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__()
        self._config = config or {}

    def execute(self) -> tuple[str, dict[str, Any]]:
        """Crawl portfolio pages and return discovered companies."""
        firm_url = self._config.get("url", "")
        if not firm_url:
            return "", {"companies": [], "error": "No URL provided"}

        if not firm_url.startswith("http"):
            firm_url = f"https://{firm_url}"

        parsed_base = urlparse(firm_url)
        base_origin = f"{parsed_base.scheme}://{parsed_base.netloc}"
        firm_domain = parsed_base.hostname or ""

        # Collect links from all portfolio-like pages
        all_links: list[dict[str, Any]] = []
        for path in _PORTFOLIO_PATHS:
            page_url = firm_url if not path else f"{base_origin}{path}"
            try:
                result = scrape_url(page_url)
                all_links.extend({**link, "source": page_url} for link in result["links"])
            except Exception:  # scrape_url raises httpx + parsing errors
                logger.info("Failed to scrape %s", page_url, exc_info=True)
                continue

        logger.info(
            "Scraped %d links from %d paths for %s", len(all_links), len(_PORTFOLIO_PATHS), firm_url
        )

        # Filter for portfolio company links
        companies: list[dict[str, str]] = []
        seen_urls: set[str] = set()

        for link in all_links:
            try:
                href = link["href"]
                if href.startswith("http"):
                    link_url = urlparse(href)
                else:
                    suffix = href if href.startswith("/") else f"/{href}"
                    link_url = urlparse(f"{base_origin}{suffix}")

                domain = link_url.hostname or ""
                path_lower = link_url.path.lower()

                # Check if it's an internal portfolio link
                is_internal_portfolio = domain == firm_domain and any(
                    seg in path_lower for seg in ["/portfolio/", "/companies/", "/investments/"]
                )

                # Skip same-domain (unless internal portfolio), seen URLs, social links
                if not is_internal_portfolio and domain == firm_domain:
                    continue

                full_url = f"{link_url.scheme}://{link_url.netloc}{link_url.path}"
                if full_url in seen_urls:
                    continue

                is_social = any(
                    domain == social or domain.endswith(f".{social}") for social in _SOCIAL_DOMAINS
                )
                if is_social:
                    continue

                # Determine company name: prefer link text, fall back to context
                text = link["text"].strip()
                context_name = link.get("context_name", "").strip()
                company_name = text

                text_lower = text.lower()
                is_generic_cta = any(cta in text_lower for cta in _GENERIC_CTA_PATTERNS)

                if is_generic_cta or not text:
                    # CTA link — try context name from parent heading/card
                    if context_name:
                        company_name = context_name
                        logger.info(
                            "Using context name '%s' for CTA link → %s", context_name, full_url
                        )
                    else:
                        logger.info(
                            "Dropping CTA link (no context name): '%s' → %s", text, full_url
                        )
                        continue

                if (
                    len(company_name) <= _MIN_COMPANY_NAME_LENGTH
                    or len(company_name) >= _MAX_COMPANY_NAME_LENGTH
                ):
                    continue

                if _STARTS_WITH_SKIP.match(company_name):
                    continue

                seen_urls.add(full_url)
                companies.append({"name": company_name, "url": full_url, "description": ""})

            except Exception:  # urlparse and link access raise various errors
                logger.debug("Skipping malformed link", exc_info=True)
                continue

            if len(companies) >= _MAX_COMPANIES:
                break

        # Fallback: data attributes (data-company-name, data-company-link)
        if not companies:
            companies = self._fallback_data_attributes(base_origin, firm_domain)

        return json.dumps(companies), {"companies": companies, "count": len(companies)}

    def _fallback_data_attributes(self, base_origin: str, firm_domain: str) -> list[dict[str, str]]:
        """Check for data-company-name/data-company-link attributes."""
        companies: list[dict[str, str]] = []
        seen: set[str] = set()

        for path in _PORTFOLIO_PATHS:
            page_url = f"{base_origin}{path}" if path else base_origin
            try:
                with httpx.Client(follow_redirects=True, timeout=SCRAPER_TIMEOUT) as client:
                    response = client.get(
                        page_url,
                        headers=SCRAPER_HEADERS,
                    )
                    if response.status_code != _HTTP_OK:
                        continue

                soup = BeautifulSoup(response.text, "html.parser")
                attrs = {"data-company-name": True, "data-company-link": True}
                for el in soup.find_all(attrs=attrs):
                    name = (el.get("data-company-name") or "").strip()
                    url = (el.get("data-company-link") or "").strip()
                    if (
                        name
                        and url
                        and len(name) < _MAX_COMPANY_NAME_LENGTH
                        and url.startswith("http")
                        and url not in seen
                    ):
                        seen.add(url)
                        companies.append({"name": name, "url": url, "description": ""})

                if len(companies) >= _MAX_COMPANIES:
                    break
            except Exception:  # httpx + BeautifulSoup can raise various errors
                logger.debug("Skipping fallback path %s", page_url, exc_info=True)
                continue

        return companies

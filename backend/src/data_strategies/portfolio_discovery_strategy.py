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

from bs4 import BeautifulSoup
from curl_cffi.requests.exceptions import ImpersonateError, RequestException
from signalfield_core.data.strategy import DataStrategyExecutor

from src.data_strategies.web_scraper_strategy import (
    MAX_NAME_LENGTH,
    MIN_NAME_LENGTH,
    extract_name_from_url,
    fetch_page_html,
    scrape_url,
    title_case_tokens,
)


def _name_from_detail_slug(url: str) -> str:
    """Derive a company name from an internal detail-page URL's last path segment.

    Anchor-link portfolios (e.g. Francisco Partners' ``/investments/{slug}``) put
    the company name in the slug while the link text is a description. The slug is
    title-cased (``aeries-software`` -> ``Aeries Software``); returns "" if the
    result is out of the shared name-length bounds.
    """
    slug = urlparse(url).path.rstrip("/").rsplit("/", 1)[-1]
    name = title_case_tokens(slug)
    # Strict upper bound to match the downstream length filter (drops >= MAX).
    if MIN_NAME_LENGTH < len(name) < MAX_NAME_LENGTH:
        return name
    return ""


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
    r"^(the|our|a|an|login|sign|contact|about|terms|privacy)\b", re.IGNORECASE
)

# Name-length bounds live in ``web_scraper_strategy`` as the single source of
# truth — both discovery and extraction apply the same thresholds.
_MIN_COMPANY_NAME_LENGTH = MIN_NAME_LENGTH
_MAX_COMPANY_NAME_LENGTH = MAX_NAME_LENGTH

PORTFOLIO_PATHS = [
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

        # Collect links and text from all portfolio-like pages
        all_links: list[dict[str, Any]] = []
        page_texts: list[str] = []
        script_texts: list[str] = []
        # Structured {name, slug} records parsed deterministically from hydration
        # JSON, keyed by slug → a detail-page candidate. Only listing paths (not
        # the root) yield a detail-page parent, so root-page records are ignored
        # for URL construction; the same companies are recovered from /portfolio.
        structured_by_slug: dict[str, dict[str, str]] = {}
        # Names from logo-image alt grids (e.g. Vista) — no on-site URL, so these
        # seed the web-search fallback rather than becoming candidates directly.
        logo_names: dict[str, str] = {}  # lower-key -> display name (deduped)
        firm_stem = firm_domain[4:] if firm_domain.startswith("www.") else firm_domain
        firm_stem = firm_stem.split(".", 1)[0].lower()
        for path in PORTFOLIO_PATHS:
            page_url = firm_url if not path else f"{base_origin}{path}"
            try:
                result = scrape_url(page_url)
                all_links.extend({**link, "source": page_url} for link in result["links"])
                page_texts.append(result["text"])
                # Data-bearing inline script JSON (where SSR sites hide the
                # portfolio list) — fed to the AI extraction path downstream.
                if result.get("script_text"):
                    script_texts.append(result["script_text"])
                for name in result.get("logo_company_names", []):
                    key = name.lower()
                    # Exact match excludes the firm's own name without dropping
                    # companies that merely contain the stem (e.g. "Avista").
                    if key not in logo_names and key != firm_stem:
                        logo_names[key] = name
                if path:
                    for record in result.get("embedded_companies", []):
                        slug = record["slug"]
                        if slug not in structured_by_slug:
                            structured_by_slug[slug] = {
                                "name": record["name"],
                                "url": f"{page_url.rstrip('/')}/{slug}",
                                "description": "",
                            }
            except ImpersonateError:
                raise  # misconfigured _IMPERSONATE_TARGET — a bug, not a per-page failure
            except RequestException:  # transport/HTTP error — skip this page, fail-soft
                logger.info("Failed to scrape %s", page_url, exc_info=True)
                continue

        logger.info(
            "Scraped %d links from %d paths for %s", len(all_links), len(PORTFOLIO_PATHS), firm_url
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
                    # CTA link — prefer a context name from the surrounding
                    # card (heading / img alt / img filename). As a last
                    # resort, derive from the target URL's hostname so we
                    # keep the candidate rather than dropping it entirely.
                    if context_name:
                        company_name = context_name
                        logger.info(
                            "Using context name '%s' for CTA link → %s", context_name, full_url
                        )
                    else:
                        url_name = extract_name_from_url(full_url)
                        if url_name:
                            company_name = url_name
                            logger.info(
                                "Using URL-derived name '%s' for CTA link → %s",
                                url_name,
                                full_url,
                            )
                        else:
                            logger.info(
                                "Dropping CTA link (no derivable name): '%s' → %s",
                                text,
                                full_url,
                            )
                            continue

                # Internal detail links (/section/{slug}) carry the name in the
                # slug while the anchor text is often a description. When the
                # text-derived name is unusable (out of bounds), prefer the slug.
                if is_internal_portfolio and not (
                    _MIN_COMPANY_NAME_LENGTH < len(company_name) < _MAX_COMPANY_NAME_LENGTH
                ):
                    slug_name = _name_from_detail_slug(full_url)
                    if slug_name:
                        company_name = slug_name

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

        # Merge deterministic structured-JSON candidates (detail-page URLs),
        # deduped by URL against the link-derived ones. These are the reliable
        # path for SSR/headless-CMS sites whose company list lives in embedded
        # JSON rather than anchors.
        for candidate in structured_by_slug.values():
            if candidate["url"] in seen_urls:
                continue
            seen_urls.add(candidate["url"])
            companies.append(candidate)

        # Fallback: data attributes (data-company-name, data-company-link)
        if not companies:
            companies = self._fallback_data_attributes(base_origin, firm_domain)

        return json.dumps(companies), {
            "companies": companies,
            "count": len(companies),
            "page_text": "\n\n".join(page_texts),
            "script_text": "\n\n".join(script_texts),
            "all_links": all_links,
            "logo_company_names": list(logo_names.values()),
        }

    def _fallback_data_attributes(self, base_origin: str, firm_domain: str) -> list[dict[str, str]]:
        """Check for data-company-name/data-company-link attributes."""
        companies: list[dict[str, str]] = []
        seen: set[str] = set()

        for path in PORTFOLIO_PATHS:
            page_url = f"{base_origin}{path}" if path else base_origin
            try:
                html = fetch_page_html(page_url)
                soup = BeautifulSoup(html, "html.parser")
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
            except ImpersonateError:
                raise  # misconfigured _IMPERSONATE_TARGET — a bug, not a per-path failure
            except RequestException:  # transport/HTTP error — skip this path, fail-soft
                logger.debug("Skipping fallback path %s", page_url, exc_info=True)
                continue

        return companies

"""Web scraper data strategy — ports scrapeUrl() from pe-scan/src/lib/scraper/index.ts.

Uses curl_cffi (browser-impersonating TLS transport) + BeautifulSoup4 instead of
Cheerio. Impersonation lets the scraper past TLS-fingerprint bot protection.
"""

from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from curl_cffi.requests.exceptions import HTTPError, ImpersonateError, RequestException
from signalfield_core.data.strategy import DataStrategyExecutor

from src.data_strategies.logo_grid_extractor import extract_logo_companies

# Name-derivation helpers live in scraper_names (split out for file size); the
# embedded-record parser below uses the shared length bounds, and the context
# extractor uses the alt-label + img-filename helpers.
from src.data_strategies.scraper_names import (
    MAX_NAME_LENGTH,
    MIN_NAME_LENGTH,
    extract_name_from_img_src,
    titlecase_words,
)

# Re-exported: the browser-impersonating transport (with retry) lives in
# scraper_transport; callers/tests still reference it via this module.
from src.data_strategies.scraper_transport import fetch_page_html

logger = logging.getLogger(__name__)

_MAX_TEXT_LENGTH = 20_000
# Budget for data-bearing inline <script> JSON. Modern SSR sites (Next.js etc.)
# embed page data — including portfolio company lists — as JSON inside <script>
# tags rather than the visible DOM, so we capture it before stripping scripts.
# Large because a single hydration island can be 250KB+ (a 300-company portfolio),
# and the companies are spread throughout it — head-truncating too tightly drops
# most of the list. Scripts are ranked by JSON key:value density so the data
# island wins over code bundles / analytics.
_MAX_SCRIPT_TEXT_LENGTH = 200_000
_MIN_SCRIPT_JSON_PAIRS = 5  # skip code/analytics scripts with little JSON structure

# Matches a structured company record embedded as JSON in a hydration script:
# an adjacent ``"name":"…","slug":"…"`` pair, in both plain JSON and the
# escaped/stringified form SSR frameworks emit (``\"name\":\"…\"``). Requiring
# ``name`` to be immediately followed by ``slug`` is the discriminator that
# separates real company records from surrounding metadata (logo assets carry
# ``filename`` not ``name``; ``searchableNormalized`` has ``name`` but no
# adjacent ``slug``).
_EMBEDDED_RECORD_RE = re.compile(
    r'\\?"name\\?"\s*:\s*\\?"([^"\\]+)\\?"\s*,\s*\\?"slug\\?"\s*:\s*\\?"([^"\\]+)\\?"'
)


def _extract_context_name(anchor: Any) -> str:
    """Extract a company name from the context around a link.

    Looks for headings, img alt text, or title attributes in parent elements.
    Useful when the link text is a generic CTA like "LEARN MORE".
    """
    # Check link attributes first
    for attr in ("title", "aria-label"):
        value = anchor.get(attr, "").strip()
        if value and len(value) > 2 and "learn" not in value.lower():  # noqa: PLR2004
            return value

    # Walk up the DOM looking for a name in the same card/article
    for parent in anchor.parents:
        if parent.name in ("article", "div", "li", "section"):
            # Try headings first
            heading = parent.find(["h1", "h2", "h3", "h4", "h5", "h6"])
            if heading:
                name = heading.get_text(strip=True)
                if name and len(name) > 2:  # noqa: PLR2004
                    return name

            # Try img alt text (common in portfolio cards); fall back to the
            # img src filename when alt is empty/missing (common on WordPress
            # sites where logo uploads have no alt text).
            img = parent.find("img")
            if img:
                alt = (img.get("alt") or "").strip()
                if alt and len(alt) > 2:  # noqa: PLR2004
                    return titlecase_words(alt)
                src_name = extract_name_from_img_src(img.get("src") or "")
                if src_name:
                    return src_name

            # Stop at the first meaningful container
            if parent.name in ("article", "section", "li"):
                break
    return ""


def normalize_url(url: str) -> str:
    """Normalize a URL to origin + pathname."""
    if not url.startswith("http"):
        url = f"https://{url}"
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"


def _extract_data_scripts(soup: BeautifulSoup) -> str:
    """Concatenate inline ``<script>`` text that looks data-bearing (JSON islands).

    Server-rendered SPA sites embed page data — including portfolio company lists
    — as JSON inside ``<script>`` tags, leaving the visible ``<body>`` an empty
    skeleton. We rank inline scripts by JSON key:value-string density (the densest
    data island first), truncated to a budget; code bundles / analytics scripts
    with little JSON structure are skipped. Density (not a specific key like
    ``name``) is the signal because sites use different schemas. Captured BEFORE
    the scripts are decomposed so the visible-``text`` extraction is unchanged for
    other callers.
    """
    candidates: list[tuple[int, str]] = []
    for script in soup.find_all("script"):
        if script.get("src"):
            continue  # external script reference — no inline data
        content = script.string or script.get_text() or ""
        # Count JSON `"key":"value"` pairs, including escaped (`\"key\":\"value\"`)
        # blobs that SSR frameworks stringify into a JS string.
        json_pairs = content.count('":"') + content.count('\\":\\"')
        if json_pairs >= _MIN_SCRIPT_JSON_PAIRS:
            candidates.append((json_pairs, content))

    candidates.sort(key=lambda item: item[0], reverse=True)
    collected: list[str] = []
    total = 0
    for _, content in candidates:
        if total >= _MAX_SCRIPT_TEXT_LENGTH:
            break
        chunk = content[: _MAX_SCRIPT_TEXT_LENGTH - total]
        collected.append(chunk)
        total += len(chunk)
    return "\n".join(collected)


def _extract_embedded_companies(soup: BeautifulSoup) -> list[dict[str, str]]:
    """Parse structured ``{name, slug}`` company records from hydration scripts.

    SSR / headless-CMS portfolio sites embed the company list as JSON in a
    ``<script>`` island (e.g. ``{"name":"Calabrio","slug":"calabrio", …}``).
    AI extraction over that raw, deeply-nested escaped JSON is unreliable, so we
    parse the records deterministically here — over the FULL script content (not
    the truncated :func:`_extract_data_scripts` copy), so the complete list is
    recovered. Returns ``[{"name", "slug"}]`` deduplicated by slug; empty when no
    records are present (discovery then proceeds via the link / AI paths).
    """
    companies: list[dict[str, str]] = []
    seen_slugs: set[str] = set()
    for script in soup.find_all("script"):
        if script.get("src"):
            continue  # external script reference — no inline data
        content = script.string or script.get_text() or ""
        for raw_name, raw_slug in _EMBEDDED_RECORD_RE.findall(content):
            name = raw_name.strip()
            slug = raw_slug.strip()
            # Skip empty/dup slugs and slugs with "/" (would make a bad detail URL).
            if not slug or "/" in slug or slug in seen_slugs:
                continue
            if not (MIN_NAME_LENGTH < len(name) <= MAX_NAME_LENGTH):
                continue
            seen_slugs.add(slug)
            companies.append({"name": name, "slug": slug})
    return companies


def scrape_url(url: str) -> dict[str, Any]:
    """Scrape a URL and return structured data.

    Returns:
        Dict with keys: title, description, text, links, meta_keywords,
        script_text, embedded_companies, logo_company_names
    """
    normalized = normalize_url(url)
    html = fetch_page_html(normalized)
    soup = BeautifulSoup(html, "html.parser")

    # Capture data-bearing inline script JSON BEFORE stripping scripts below —
    # this is where SSR sites hide the portfolio company list. ``script_text`` is
    # the (truncated) blob fed to AI extraction; ``embedded_companies`` is the
    # deterministic parse of structured {name, slug} records over the full script.
    script_text = _extract_data_scripts(soup)
    embedded_companies = _extract_embedded_companies(soup)
    # Names from logo-image alt text (logo-grid sites with no links/JSON).
    logo_company_names = extract_logo_companies(soup)

    # Remove script, style, nav clutter (matches Cheerio removals)
    for tag in soup.find_all(["script", "style", "noscript", "nav", "footer", "header", "aside"]):
        tag.decompose()

    # Remove elements whose CSS class tokens exactly match clutter patterns.
    # Uses token-level matching (not substring regex) to avoid false positives
    # like "no-sidebar" matching "sidebar" and stripping the entire <body>.
    clutter_classes = {"nav", "footer", "header", "sidebar", "cookie", "popup"}
    for el in soup.find_all(class_=True):
        if el.name in ("html", "body"):
            continue
        # Guard: decompose() on earlier elements can corrupt the tree,
        # leaving some elements with attrs=None. Skip those.
        try:
            class_tokens = {c.lower() for c in el.get("class", [])}
        except AttributeError:
            continue
        if class_tokens & clutter_classes:
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

    # Extract links with contextual company name
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

        # Extract contextual name from surrounding elements
        # (useful when link text is generic CTA like "LEARN MORE")
        context_name = _extract_context_name(a)

        if (
            (link_text or context_name)
            and href
            and not href.startswith("#")
            and not href.startswith("mailto:")
        ):
            links.append({"text": link_text, "href": href, "context_name": context_name})

    return {
        "title": title,
        "description": description,
        "text": text,
        "links": links,
        "meta_keywords": meta_keywords,
        "script_text": script_text,
        "embedded_companies": embedded_companies,
        "logo_company_names": logo_company_names,
    }


class WebScraperStrategy(DataStrategyExecutor):
    """DataStrategyExecutor that scrapes a URL using curl_cffi + BeautifulSoup.

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
            # script_text/embedded_companies omitted — discovery-only, unused here.
            return result["text"], {
                "title": result["title"],
                "description": result["description"],
                "links": result["links"],
                "meta_keywords": result["meta_keywords"],
            }
        except ImpersonateError:
            raise  # misconfigured _IMPERSONATE_TARGET — a bug, surface it loudly
        except HTTPError as e:
            logger.warning("HTTP error scraping %s: %s", url, e)
            # curl_cffi's HTTPError.response is optional; read the status code
            # defensively so a missing response degrades to the error string
            # rather than crashing inside the handler.
            status_code = getattr(e.response, "status_code", None)
            detail = f"HTTP {status_code}" if status_code is not None else str(e)
            return "", {"error": detail}
        except RequestException as e:
            logger.warning("Request error scraping %s: %s", url, e)
            return "", {"error": str(e)}

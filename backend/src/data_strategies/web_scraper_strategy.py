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
from curl_cffi import requests as curl_requests
from curl_cffi.requests.exceptions import HTTPError, ImpersonateError, RequestException
from signalfield_core.data.strategy import DataStrategyExecutor

logger = logging.getLogger(__name__)

# Browser fingerprint to impersonate. curl_cffi (libcurl + BoringSSL) presents a
# real-browser TLS/HTTP-2 handshake so fingerprint-based bot protection
# (Cloudflare JA3 bot management) serves full content instead of a 403.
# MAINTENANCE NOTE: this target ages — stale fingerprints (e.g. chrome120/124)
# get blocked just like a plain HTTP client. Keep curl_cffi reasonably fresh and
# bump this to a current target if blocks reappear. curl_cffi also emits a
# browser-consistent header set when impersonating, so we deliberately do NOT
# layer custom headers on top (that would break fingerprint coherence).
_IMPERSONATE_TARGET = "chrome136"
_SCRAPER_TIMEOUT = 15.0
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

_LOGO_SUFFIX_RE = re.compile(r"[-_ ]?logo$", re.IGNORECASE)
_FILENAME_TOKEN_SPLIT_RE = re.compile(r"(?<=[a-z])(?=[A-Z])|[-_.\s]+")
# Public — imported by :mod:`portfolio_discovery_strategy` so both the
# discovery heuristic and the AI-derived name fallbacks apply identical bounds.
MIN_NAME_LENGTH = 2
MAX_NAME_LENGTH = 60


def _title_case_tokens(raw: str) -> str:
    """Split a slug-like string on separators / camelCase and title-case."""
    tokens = [t for t in _FILENAME_TOKEN_SPLIT_RE.split(raw) if t]
    if not tokens:
        return ""
    return " ".join(t.capitalize() for t in tokens)


def _extract_name_from_img_src(src: str) -> str:
    """Derive a company name from an image URL's filename.

    Best-effort: works well for kebab-case / snake_case / camelCase filenames
    (``access-healthcare.png`` → ``Access Healthcare``). Single-token
    lowercase filenames cannot be split and are returned title-cased as-is
    (``accesshealthcare.png`` → ``Accesshealthcare``) — imperfect, but the
    AI validation step and the user confirmation screen recover from this.
    """
    if not src:
        return ""
    # Strip query string / fragment and path, take basename
    path = src.split("?", 1)[0].split("#", 1)[0]
    basename = path.rsplit("/", 1)[-1]
    # Drop extension
    stem = basename.rsplit(".", 1)[0] if "." in basename else basename
    # Strip trailing '-logo' / '_logo' / 'logo'
    stem = _LOGO_SUFFIX_RE.sub("", stem)
    name = _title_case_tokens(stem)
    if not (MIN_NAME_LENGTH < len(name) <= MAX_NAME_LENGTH):
        return ""
    return name


def extract_name_from_url(url: str) -> str:
    """Derive a company name from the target URL's hostname as a last resort.

    Used by :mod:`portfolio_discovery_strategy` as the final fallback when
    HTML offers no name signal at all.

    ``https://www.endurancelift.com/`` → ``Endurancelift``.
    Same single-token limitation as :func:`_extract_name_from_img_src`.
    """
    if not url:
        return ""
    parsed = urlparse(url if url.startswith("http") else f"https://{url}")
    try:
        host = (parsed.hostname or "").lower()
    except ValueError:
        # Malformed IPv6 literal (e.g., "https://[::1]:99999") — `.hostname`
        # can raise on such inputs even though ``urlparse`` itself does not.
        return ""
    if not host:
        return ""
    if host.startswith("www."):
        host = host[4:]
    # Drop TLD (last dotted segment)
    parts = host.rsplit(".", 1)
    stem = parts[0] if len(parts) > 1 else host
    name = _title_case_tokens(stem)
    if not (MIN_NAME_LENGTH < len(name) <= MAX_NAME_LENGTH):
        return ""
    return name


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
                    return alt.title()
                src_name = _extract_name_from_img_src(img.get("src") or "")
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


def fetch_page_html(url: str) -> str:
    """GET a URL via the browser-impersonating transport and return its HTML.

    Sole scraping transport: ``curl_cffi`` with browser impersonation so that
    TLS-fingerprint bot protection serves full content. Raises ``curl_cffi``
    ``RequestException`` subclasses on failure (``HTTPError`` on a bad status,
    ``ConnectionError``/``Timeout`` on transport errors); callers translate
    those into their existing error contracts.
    """
    response = curl_requests.get(
        url,
        impersonate=_IMPERSONATE_TARGET,
        timeout=_SCRAPER_TIMEOUT,
        allow_redirects=True,
    )
    response.raise_for_status()
    return response.text


def scrape_url(url: str) -> dict[str, Any]:
    """Scrape a URL and return structured data.

    Returns:
        Dict with keys: title, description, text, links, meta_keywords, script_text
    """
    normalized = normalize_url(url)
    html = fetch_page_html(normalized)
    soup = BeautifulSoup(html, "html.parser")

    # Capture data-bearing inline script JSON BEFORE stripping scripts below —
    # this is where SSR sites hide the portfolio company list.
    script_text = _extract_data_scripts(soup)

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

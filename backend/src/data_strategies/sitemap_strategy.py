"""Sitemap-based portfolio discovery — a deterministic Tier-1 rung.

When a firm enumerates one detail page per portfolio company, ``sitemap.xml``
lists them all — a reliable, browser-free source even when the listing page is a
client-side-rendered shell. This rung fetches the sitemap (following a sitemap
index one level), filters ``<loc>`` URLs whose path looks like
``/<section>/<company-slug>``, and derives names from the slug.

Validated against the adaptive-portfolio-discovery spike: rescued Riverside
(``/investment-portfolio/<slug>``, HubSpot CMS) and Audax (``/portfolio/<slug>``,
Rails) — both of which the plain scrape saw as near-empty shells.

Fail-soft and additive: returns ``[]`` (never raises, except a misconfigured
impersonation target) when there is no sitemap or no company detail pages.
"""

from __future__ import annotations

import logging
import re

from curl_cffi.requests.exceptions import HTTPError, ImpersonateError, RequestException

from src.data_strategies.scraper_names import name_from_url_slug
from src.data_strategies.scraper_transport import fetch_page_html
from src.data_strategies.url_safety import UnsafeUrlError

logger = logging.getLogger(__name__)

# Common sitemap entry points to try in order.
_SITEMAP_PATHS = ("/sitemap.xml", "/sitemap_index.xml", "/sitemap-index.xml")

# A portfolio detail URL: path ending in /<section>/<slug>. Mirrors the sections
# the link-scrape recognizes, plus the hyphenated variants seen in the spike
# (Riverside ``/investment-portfolio/<slug>``).
_PORTFOLIO_PATH_RE = re.compile(
    r"/(portfolio|companies|investments?|investment-portfolio|"
    r"our-companies|portfolio-companies|holdings)/([^/]+)/?$",
    re.IGNORECASE,
)

_LOC_RE = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>", re.IGNORECASE)

_MAX_CHILD_SITEMAPS = 10  # cap child-sitemap fetches from an index
_MAX_COMPANIES = 2000  # safety cap, far beyond any real portfolio


def _fetch_locs(url: str) -> list[str]:
    """Return the ``<loc>`` values in a sitemap, or ``[]`` on any failure."""
    try:
        body = fetch_page_html(url)
    except ImpersonateError:
        raise
    except (HTTPError, RequestException, UnsafeUrlError):
        logger.info("sitemap fetch failed for %s", url, exc_info=True)
        return []
    return _LOC_RE.findall(body)


def _is_child_sitemap(loc: str) -> bool:  # noqa: NAMING001  is_-prefixed predicate (checker counts the leading _)
    """A ``<loc>`` pointing at another XML sitemap (index entry)."""
    path = loc.split("?", 1)[0].lower()
    return path.endswith(".xml")  # .xml.gz is skipped — we can't gunzip the body


def _company_from_loc(loc: str, seen: set[str]) -> dict[str, str] | None:
    """Map a portfolio-detail ``<loc>`` to a company record, or ``None``."""
    if not _PORTFOLIO_PATH_RE.search(loc):
        return None
    url = loc.split("?", 1)[0].split("#", 1)[0]
    if url in seen:
        return None
    name = name_from_url_slug(url)
    if not name:
        return None
    seen.add(url)
    # ``source="site"`` — sitemap entries are the firm's own pages, so they anchor
    # the discovery verdict's reliable-source URL like the scraped listing.
    return {"name": name, "url": url, "description": "", "source": "site"}


def discover_via_sitemap(base_origin: str) -> list[dict[str, str]]:
    """Discover portfolio companies by enumerating the firm's sitemap.

    ``base_origin`` is scheme+host (e.g. ``https://www.audaxprivateequity.com``).
    Returns ``{name, url, description, source}`` records, or ``[]`` when no sitemap
    or company detail pages are found. Never raises (fail-soft additive rung).
    """
    locs: list[str] = []
    for path in _SITEMAP_PATHS:
        locs = _fetch_locs(f"{base_origin}{path}")
        if locs:
            break
    if not locs:
        return []

    # A sitemap index lists child sitemaps; follow them one level (capped,
    # prioritising children whose URL hints at a portfolio/company section).
    child_sitemaps = [loc for loc in locs if _is_child_sitemap(loc)]
    if child_sitemaps:
        child_sitemaps.sort(
            key=lambda loc: (
                0
                if _PORTFOLIO_PATH_RE.search(loc)
                or any(hint in loc.lower() for hint in ("portfolio", "compan", "investment"))
                else 1
            )
        )
        page_locs: list[str] = [loc for loc in locs if not _is_child_sitemap(loc)]
        for child in child_sitemaps[:_MAX_CHILD_SITEMAPS]:
            page_locs.extend(_fetch_locs(child))
    else:
        page_locs = locs

    seen: set[str] = set()
    companies: list[dict[str, str]] = []
    for loc in page_locs:
        record = _company_from_loc(loc, seen)
        if record:
            companies.append(record)
            if len(companies) >= _MAX_COMPANIES:
                # Safety cap — no real portfolio is this large; surface it so a
                # runaway sitemap isn't silently truncated into a "complete" list.
                logger.warning(
                    "sitemap hit the %d-company cap for %s — list truncated",
                    _MAX_COMPANIES,
                    base_origin,
                )
                break
    logger.info("sitemap discovered %d companies for %s", len(companies), base_origin)
    return companies

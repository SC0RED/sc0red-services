"""Per-domain portfolio-discovery cache (Task 8 of adaptive-portfolio-discovery).

Records which deterministic structured rung (WordPress ``wp-json`` CPT or
``sitemap`` enumeration) reliably served a firm's portfolio, so a re-scan of the
same domain runs that proven rung FIRST and skips the costly AI extraction +
web-search fallback. Self-healing: a stale entry (the firm changed CMS, or the
endpoint moved) simply yields nothing on the fast path and discovery falls
through to the full ladder — the cache only ever saves work, never produces
wrong data.

Single-table item on the shared table::

    pk = DISCOVERY_CACHE#{domain}   sk = PROVEN_PATH   {source, count, mechanism, ttl}

Rows expire via the table's ``ttl`` attribute after ``CACHE_TTL_DAYS``.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

if TYPE_CHECKING:
    from src.repositories.dynamodb.client import DynamoDBTable

# Structured rungs worth fast-pathing. "static" anchors are already cheap on the
# normal scrape and "web_search"/"none" are non-deterministic, so neither has a
# reusable fast path — they are never cached.
PROVEN_SOURCES = frozenset({"wp_json", "sitemap"})

# A re-scan's fast-path rung must yield MORE than this to be trusted; at or below
# it the cache is treated as stale and discovery falls through to the full ladder.
# Matches the discovery low-water mark so a thin proven-rung result never
# short-circuits a firm that actually has a fuller list.
FAST_PATH_MIN_COUNT = 5

CACHE_TTL_DAYS = 30
_SK = "PROVEN_PATH"
_SECONDS_PER_DAY = 86400


def domain_of(url: str) -> str:  # noqa: NAMING001  (transform util, not a verb)
    """Lowercased host key for the cache (no ``www.``, no scheme, no path).

    Returns ``""`` for a URL with no host, so callers can treat that as "no cache".
    """
    parsed = urlparse(url if url.lower().startswith("http") else f"https://{url}")
    host = (parsed.netloc or "").lower()
    return host[4:] if host.startswith("www.") else host


class DiscoveryCacheRepository:
    """Reads/writes the per-domain proven-discovery-path cache."""

    def __init__(self, table: DynamoDBTable) -> None:
        self._table = table

    def get_proven_path(self, url: str) -> dict[str, Any] | None:
        """Return the cached proven path for the URL's domain, or ``None``.

        ``None`` for an unknown/expired domain or a URL with no host. The stored
        keys are written together by :meth:`put_proven_path`, so they are read
        directly — a missing key is corruption, not a default-to-empty case.
        """
        domain = domain_of(url)
        if not domain:
            return None
        item = self._table.get_item(pk=f"DISCOVERY_CACHE#{domain}", sk=_SK)
        if not item:
            return None
        return {
            "source": item["source"],
            "count": item["count"],
            "mechanism": item["mechanism"],
        }

    def put_proven_path(self, url: str, *, source: str, count: int, mechanism: str) -> None:
        """Record (TTL'd) the structured rung that served this domain.

        No-op for a non-fast-pathable ``source`` or a URL with no host, so callers
        can hand it any discovery outcome without pre-filtering.
        """
        domain = domain_of(url)
        if not domain or source not in PROVEN_SOURCES:
            return
        self._table.put_item(
            {
                "pk": f"DISCOVERY_CACHE#{domain}",
                "sk": _SK,
                "source": source,
                "count": count,
                "mechanism": mechanism,
                "ttl": int(time.time()) + CACHE_TTL_DAYS * _SECONDS_PER_DAY,
            }
        )

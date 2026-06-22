"""Shared portfolio-discovery merge + verdict helpers.

Pure functions used by both the initial discovery step (``DiscoverPortfolio``)
and the customer-triggered deepen step (``DeepenPortfolio``): URL-keyed dedup,
fallback merging, and the structured discovery verdict. Kept here so the two
steps share one definition rather than duplicating it.
"""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# The escalation rungs offered when a result looks incomplete. Mirrors the
# frontend `DiscoveryAction` union.
ESCALATION_ACTIONS = ["search_deeper", "render_site", "upload_list"]


def normalize_url_key(url: str) -> str:
    """Normalize a URL to a dedup key of ``host + path``.

    Strips ``www.`` and trailing slash, lowercases the host, ignores query and
    fragment. Path-aware on purpose: a firm's per-company detail pages
    (``firm.com/portfolio/a``, ``firm.com/portfolio/b``) share a domain but are
    distinct companies, so keying on the domain alone would collapse a whole
    portfolio into one. ``www``/trailing-slash variants of the *same* URL still
    map to the same key, and root-path company sites key to just the host — so
    external-company matching (heuristic ∩ AI auto-include) is unchanged.
    """
    parsed = urlparse(url if url.lower().startswith("http") else f"https://{url}")
    host = (parsed.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]
    # Lowercase the path too: detail-page slugs are case-insensitive in
    # practice, so two sources emitting different casing dedup to one key.
    path = parsed.path.lower().rstrip("/")
    return f"{host}{path}"


def merge_results(
    heuristic: list[dict[str, str]],
    ai_extracted: list[dict[str, str]],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Merge heuristic and AI results by normalized URL key (host + path).

    Returns ``(auto_included, needs_validation)``:
    - ``auto_included``: companies found by BOTH paths (high confidence, skip AI validation)
    - ``needs_validation``: companies found by only one path (require AI validation)

    Deduplicates by normalized URL key (host + path), so distinct same-domain
    detail pages are kept as distinct companies.
    """
    heuristic_by_key = {normalize_url_key(c["url"]): c for c in heuristic}
    ai_by_key = {normalize_url_key(c["url"]): c for c in ai_extracted}

    intersection = set(heuristic_by_key) & set(ai_by_key)
    remainder_keys = (set(heuristic_by_key) | set(ai_by_key)) - intersection

    auto_included = [heuristic_by_key[k] for k in intersection]
    needs_validation = [
        (heuristic_by_key if k in heuristic_by_key else ai_by_key)[k] for k in remainder_keys
    ]

    logger.info(
        "Merge: heuristic=%d, ai=%d, intersection=%d, remainder=%d, total=%d",
        len(heuristic),
        len(ai_extracted),
        len(intersection),
        len(needs_validation),
        len(auto_included) + len(needs_validation),
    )
    return auto_included, needs_validation


def merge_fallback(
    auto_included: list[dict[str, str]],
    needs_validation: list[dict[str, str]],
    fallback: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Union web-search fallback candidates into ``needs_validation`` only.

    Model-sourced candidates always require validation (never ``auto_included``).
    Deduplicated by normalized URL key against the existing site-derived results,
    so the fallback only ADDS companies the site did not surface.
    """
    seen = {normalize_url_key(c["url"]) for c in (*auto_included, *needs_validation)}
    merged = list(needs_validation)
    for company in fallback:
        # ``name``/``url`` are schema-required on the web-search response, so
        # access them directly — a missing key is a schema violation, not a
        # default-to-empty case.
        key = normalize_url_key(company["url"])
        if not key or key in seen:
            continue
        seen.add(key)
        merged.append({"name": company["name"], "url": company["url"], "description": ""})
    return merged


def build_verdict(
    *, site_total: int, total: int, site_fetch_failed: bool, fallback_ran: bool
) -> dict[str, Any]:
    """Summarise how discovery went, for a customer-facing message + next actions.

    ``completeness`` is the single signal the UI maps to a message:
    - ``full_site_list`` — the firm's own site gave us its list (site_total > 0)
    - ``site_blocked`` — the site couldn't be reached (fetch failed after retries)
    - ``web_search_subset`` — the site exposed no readable list; web search found some
    - ``genuinely_empty`` — nothing found anywhere
    A full site list pushes no escalation (only the always-available upload); an
    incomplete result offers the escalation rungs.
    """
    if site_total > 0:
        completeness, method = "full_site_list", "site"
    elif site_fetch_failed and fallback_ran:
        completeness, method = "site_blocked", "web_search"
    elif fallback_ran and total > 0:
        completeness, method = "web_search_subset", "web_search"
    else:
        completeness, method = "genuinely_empty", ("web_search" if fallback_ran else "none")
    actions = ["upload_list"] if completeness == "full_site_list" else list(ESCALATION_ACTIONS)
    return {
        "method": method,
        "count": total,
        "completeness": completeness,
        "available_actions": actions,
    }

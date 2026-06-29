"""WordPress ``wp-json`` portfolio discovery — a deterministic Tier-2 rung.

Many PE/VC firms run WordPress and expose their portfolio as a custom post type
(CPT) via the REST API. This rung probes ``/wp-json/wp/v2/types`` for a
portfolio-like CPT and fetches it (paginated), returning ``{name, url}`` records.
It is a clean, deterministic source that rescues client-side-rendered shells
*without a browser* — validated against the adaptive-portfolio-discovery spike
(Vista ``company``, Insight ``sfcompany``, General Atlantic ``investment``, Alpine
``our-companies``, Silver Lake ``portfolio``, Kohlberg/Vista ``company``, Gryphon
``companies``, Sun Capital ``post_portfolio``).

Fail-soft and additive: every entry point returns ``[]`` (never raises, except a
misconfigured impersonation target which is a bug) when the site is not WordPress,
exposes no portfolio CPT, or the REST API is unavailable.
"""

from __future__ import annotations

import html
import json
import logging
import re
from typing import Any

from curl_cffi.requests.exceptions import HTTPError, ImpersonateError, RequestException

from src.data_strategies.scraper_transport import fetch_page_html
from src.data_strategies.url_safety import UnsafeUrlError
from src.data_strategies.web_scraper_strategy import MAX_NAME_LENGTH, MIN_NAME_LENGTH

logger = logging.getLogger(__name__)

# Built-in WordPress types that are never the portfolio — excluded before
# matching, so a stray "post" label can't masquerade as a company list.
_WP_BUILTIN_TYPES = frozenset(
    {
        "post",
        "page",
        "attachment",
        "nav_menu_item",
        "wp_block",
        "wp_template",
        "wp_template_part",
        "wp_global_styles",
        "wp_navigation",
        "wp_font_family",
        "wp_font_face",
        "visibility_preset",
        "pattern",
        "view",
        "view-template",
    }
)

# Substrings (in the type key or its label) that mark a CPT as a portfolio list.
# Covers every CPT name seen across the spike corpus.
_PORTFOLIO_CPT_HINTS = ("portfolio", "compan", "investment", "holding", "our-")

_PER_PAGE = 100  # WordPress REST hard cap
_MAX_PAGES = 20  # safety cap → ≤2000 companies, far beyond any real portfolio

# Status detection: many firms model current-vs-realized as a WordPress taxonomy
# (e.g. Kohlberg's ``status-company`` → terms "Current"/"Realized"). We detect such
# a taxonomy and tag each company so the UI can default-deselect exited holdings.
# Heterogeneous across firms and absent on many (e.g. General Atlantic exposes no
# status), so this is best-effort and fail-open: no taxonomy ⇒ every company is
# tagged "" (treated as current/selectable, unchanged behaviour).
# Whole-WORD matched (not substring) so "performer" can't match "former",
# "inactive" can't match "active", "priority" can't match "prior".
_STATUS_REALIZED_WORDS = frozenset(
    {"realized", "realised", "exited", "exit", "divested", "former", "prior", "past", "sold"}
)
_STATUS_CURRENT_WORDS = frozenset({"current", "active"})
_STATUS_TAXONOMY_NAME_HINTS = ("status", "stage", "state")
_MAX_TAXONOMY_PROBES = 5  # cap taxonomy-term fetches when locating the status one
_WORD_RE = re.compile(r"[a-z]+")


def _classify_status_term(name: str) -> str:
    """Map a taxonomy term name to ``"realized"``/``"current"``/``""`` (whole-word)."""
    words = set(_WORD_RE.findall(name.lower()))
    if words & _STATUS_REALIZED_WORDS:
        return "realized"
    if words & _STATUS_CURRENT_WORDS:
        return "current"
    return ""


def _candidate_taxonomies(item: dict[str, Any]) -> list[str]:
    """Taxonomy REST bases on an item (top-level keys holding term-id lists).

    Status-named taxonomies are probed first so the common case costs one fetch.
    """
    keys = [
        key
        for key, value in item.items()
        if isinstance(value, list) and value and all(isinstance(term_id, int) for term_id in value)
    ]
    keys.sort(key=lambda k: 0 if any(h in k.lower() for h in _STATUS_TAXONOMY_NAME_HINTS) else 1)
    return keys[:_MAX_TAXONOMY_PROBES]


def _build_status_map(base_origin: str, sample_item: dict[str, Any]) -> tuple[str, dict[int, str]]:
    """Locate the firm's current/realized taxonomy and map its term ids → status.

    Returns ``(taxonomy_rest_base, {term_id: status})``, or ``("", {})`` when the
    firm exposes no status taxonomy (fail-open). A taxonomy qualifies only if its
    terms include BOTH a "realized"-like AND a "current"-like name — a true
    current/realized taxonomy distinguishes the two, whereas a sector/year
    taxonomy that happens to contain one stray word (e.g. a "Former Industries"
    sector) won't have both, so it's correctly rejected.
    """
    for taxonomy in _candidate_taxonomies(sample_item):
        try:
            terms = json.loads(
                fetch_page_html(f"{base_origin}/wp-json/wp/v2/{taxonomy}?per_page=100")
            )
        except ImpersonateError:
            raise
        except (HTTPError, RequestException, UnsafeUrlError, ValueError):
            continue
        if not isinstance(terms, list):
            continue
        status_map = {
            term["id"]: _classify_status_term(str(term.get("name", "")))
            for term in terms
            if isinstance(term, dict) and isinstance(term.get("id"), int)
        }
        status_map = {term_id: status for term_id, status in status_map.items() if status}
        statuses = set(status_map.values())
        if "realized" in statuses and "current" in statuses:
            return taxonomy, status_map
    return "", {}


def _status_for(item: dict[str, Any], taxonomy: str, status_map: dict[int, str]) -> str:
    """Status of one item from its term ids in the detected status taxonomy."""
    if not taxonomy:
        return ""
    statuses = {
        status_map.get(tid, "") for tid in (item.get(taxonomy) or []) if isinstance(tid, int)
    }
    if "realized" in statuses:
        return "realized"
    if "current" in statuses:
        return "current"
    return ""


def _portfolio_rest_bases(types: dict[str, Any]) -> list[str]:
    """Return the REST bases of portfolio-like custom post types.

    Uses each type's ``rest_base`` (the actual endpoint segment, which can differ
    from the type key) and falls back to the key when absent.
    """
    bases: list[str] = []
    for key, meta in types.items():
        if key in _WP_BUILTIN_TYPES:
            continue
        label = str(meta.get("name", "")).lower() if isinstance(meta, dict) else ""
        if any(hint in key.lower() or hint in label for hint in _PORTFOLIO_CPT_HINTS):
            rest_base = (meta.get("rest_base") if isinstance(meta, dict) else None) or key
            if rest_base not in bases:
                bases.append(rest_base)
    return bases


def _to_company(item: Any, taxonomy: str, status_map: dict[int, str]) -> dict[str, str] | None:
    """Map a WP REST item to a company record, or ``None`` if unusable."""
    if not isinstance(item, dict):
        return None
    title = item.get("title")
    name = html.unescape(title.get("rendered", "").strip()) if isinstance(title, dict) else ""
    url = (item.get("link") or "").strip()
    if not name or not url.startswith("http"):
        return None
    if not (MIN_NAME_LENGTH < len(name) < MAX_NAME_LENGTH):
        return None
    # ``source="site"`` — this is the firm's own structured data, so it anchors the
    # discovery verdict's reliable-source URL exactly like the scraped listing.
    # ``status`` is "current"/"realized"/"" (best-effort; see _build_status_map) so
    # the UI can default-deselect exited holdings.
    return {
        "name": name,
        "url": url,
        "description": "",
        "source": "site",
        "status": _status_for(item, taxonomy, status_map),
    }


def _fetch_cpt(base_origin: str, rest_base: str, seen: set[str]) -> list[dict[str, str]]:
    """Fetch one CPT, paginating until a short/empty page or a transport stop."""
    companies: list[dict[str, str]] = []
    # Detected once from the first item, reused for the whole CPT. ``probed`` (not
    # a falsy ``taxonomy``) gates the one-time probe — otherwise a firm with NO
    # status taxonomy (taxonomy stays "") would re-probe on every page.
    taxonomy: str = ""
    status_map: dict[int, str] = {}
    probed = False
    for page in range(1, _MAX_PAGES + 1):
        cpt_url = f"{base_origin}/wp-json/wp/v2/{rest_base}?per_page={_PER_PAGE}&page={page}"
        try:
            items = json.loads(fetch_page_html(cpt_url))
        except ImpersonateError:
            raise  # misconfigured impersonation target — a bug, not a per-page miss
        except (HTTPError, RequestException, UnsafeUrlError, ValueError):
            # Past-the-end pages return HTTP 400; transport/parse errors end the
            # walk too. Either way we stop paginating this CPT (fail-soft).
            break
        if not isinstance(items, list) or not items:
            break
        if not probed and isinstance(items[0], dict):
            taxonomy, status_map = _build_status_map(base_origin, items[0])
            probed = True
        for item in items:
            record = _to_company(item, taxonomy, status_map)
            if record and record["url"] not in seen:
                seen.add(record["url"])
                companies.append(record)
        if len(items) < _PER_PAGE:
            break  # last page
    else:
        # Loop ran all _MAX_PAGES without a short/empty/error page → we hit the
        # safety cap. No real portfolio is this large; surface it so a runaway
        # endpoint isn't silently truncated to look like a complete list.
        logger.warning(
            "wp-json hit the %d-page cap for %s (%s) — list may be truncated",
            _MAX_PAGES,
            base_origin,
            rest_base,
        )
    return companies


def discover_via_wp_json(base_origin: str) -> list[dict[str, str]]:
    """Discover portfolio companies via a WordPress ``wp-json`` portfolio CPT.

    ``base_origin`` is the scheme+host (e.g. ``https://www.kohlberg.com``). Returns
    company records ``{name, url, description, source, status}`` (``status`` is
    "current"/"realized"/"") or ``[]`` when the site is not a WordPress portfolio.
    Never raises (fail-soft additive rung).
    """
    types_url = f"{base_origin}/wp-json/wp/v2/types"
    try:
        types = json.loads(fetch_page_html(types_url))
    except ImpersonateError:
        raise
    except (HTTPError, RequestException, UnsafeUrlError, ValueError):
        logger.info("wp-json types unavailable for %s", base_origin, exc_info=True)
        return []
    if not isinstance(types, dict):
        return []
    rest_bases = _portfolio_rest_bases(types)
    if not rest_bases:
        return []
    seen: set[str] = set()
    companies: list[dict[str, str]] = []
    for rest_base in rest_bases:
        companies.extend(_fetch_cpt(base_origin, rest_base, seen))
    logger.info(
        "wp-json discovered %d companies for %s (CPTs: %s)",
        len(companies),
        base_origin,
        rest_bases,
    )
    return companies

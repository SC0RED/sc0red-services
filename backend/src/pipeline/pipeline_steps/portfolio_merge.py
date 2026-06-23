"""Shared portfolio-discovery merge + verdict helpers.

Pure functions used by both the initial discovery step (``DiscoverPortfolio``)
and the customer-triggered deepen step (``DeepenPortfolio``): URL- and
name-keyed dedup, confidence-aware fallback merging (trusted source wins), and
the structured discovery verdict. Kept here so the two steps share one
definition rather than duplicating it.
"""

from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# The escalation rungs offered when a result looks incomplete. Mirrors the
# frontend `DiscoveryAction` union.
ESCALATION_ACTIONS = ["search_deeper", "render_site", "upload_list"]

# Trailing legal/common suffix tokens stripped when normalizing a company name
# for dedup. Conservative — only trailing tokens are removed, so distinct firms
# aren't accidentally merged.
_NAME_SUFFIXES = frozenset(
    {
        "inc",
        "llc",
        "ltd",
        "limited",
        "corp",
        "corporation",
        "co",
        "company",
        "gmbh",
        "sa",
        "ag",
        "plc",
        "lp",
        "llp",
        "group",
        "holdings",
        "holding",
    }
)


def normalize_company_name(name: str) -> str:
    """Normalize a company name to a dedup key.

    Lowercases, replaces punctuation with spaces, and strips trailing legal/
    common suffixes (``Acme, Inc.`` / ``Acme LLC`` / ``Acme Corp`` → ``acme``).
    Used to suppress web-search duplicates of a company already found reliably
    (e.g. the same firm under ``acme.com`` and ``acme.in``). Conservative: if
    stripping suffixes would empty the name, the un-stripped tokens are kept.
    """
    cleaned = re.sub(r"[^\w\s]", " ", name.lower())
    tokens = cleaned.split()
    stripped = list(tokens)
    while stripped and stripped[-1] in _NAME_SUFFIXES:
        stripped.pop()
    return " ".join(stripped or tokens)


# Generic card CTA / link labels that extraction sometimes captures instead of
# the company name → re-derive the name from the URL.
_GENERIC_NAME_LABELS = frozenset(
    {
        "view site",
        "view",
        "view company",
        "view profile",
        "view details",
        "details",
        "learn more",
        "read more",
        "visit site",
        "visit website",
        "visit",
        "website",
        "our website",
        "see more",
        "case study",
        "read the case study",
    }
)
# Login/account links that are not portfolio companies → drop the row.
_DROP_NAMES = frozenset(
    {
        "investor login",
        "client login",
        "member login",
        "portal login",
        "log in",
        "login",
        "sign in",
        "client portal",
    }
)
# A leading 24-char hex token is a CMS object id (Webflow/Contentful) that leaked
# into the name → re-derive from the URL.
_CMS_ID_PREFIX_RE = re.compile(r"^[0-9a-f]{24}\b")
# Firm-level nav path segments — not company names, so a URL ending in one falls
# back to the host root when deriving a name.
_NAV_SEGMENTS = frozenset(
    {"portfolio", "companies", "investments", "our-companies", "our-portfolio", "our-investments"}
)
# Shortest acceptable cleaned name; below this we fall back to the URL. Mirrors
# MIN_NAME_LENGTH in web_scraper_strategy (kept local to avoid a circular import).
_MIN_NAME_LENGTH = 2
# Logo-grid pages name companies via image alt text / filenames
# ("Gatik-Logo", "Renaissant Logo Green Orange"), which AI extraction carries
# through verbatim. A standalone "logo" token marks the name as logo-derived;
# once flagged, the trailing colour/style descriptors (also from the filename)
# are stripped. Only stripped alongside "logo", so a real "Orange"/"Black" stays.
_LOGO_TOKEN_RE = re.compile(r"\blogo\b", re.IGNORECASE)
_LOGO_DESCRIPTORS = frozenset(
    {
        "green",
        "orange",
        "black",
        "white",
        "red",
        "blue",
        "yellow",
        "purple",
        "pink",
        "grey",
        "gray",
        "gold",
        "silver",
        "dark",
        "light",
        "color",
        "colour",
        "colored",
        "transparent",
        "full",
        "horizontal",
        "vertical",
        "stacked",
        "square",
        "round",
        "icon",
        "mark",
        "wordmark",
        "primary",
        "secondary",
        "alt",
        "rgb",
        "cmyk",
        "png",
        "svg",
        "jpg",
        "jpeg",
        "web",
        "small",
        "large",
        "final",
        "copy",
    }
)


def _strip_logo_cruft(name: str) -> str:
    """Strip a 'logo' token + trailing presentation descriptors from a name.

    Returns the cleaned name, or "" if nothing usable remains. A name without a
    standalone 'logo' token is returned unchanged — so "Wireless Logic" (no
    word-bounded 'logo') and a company literally called "Orange" are untouched.
    """
    normalized = name.replace("-", " ").replace("_", " ")
    if not _LOGO_TOKEN_RE.search(normalized):
        return name
    tokens = [token for token in normalized.split() if token.lower() != "logo"]
    while tokens and tokens[-1].lower() in _LOGO_DESCRIPTORS:
        tokens.pop()
    return " ".join(tokens)


def sanitize_company_name(name: str, url: str) -> str:
    """Return a clean display name, or "" if the row should be dropped.

    Extraction sometimes captures a card's CTA text ("View Site"), a CMS object
    id, or a login link instead of the company name:
    - login/account labels → "" (not a portfolio company; caller drops the row)
    - generic CTA labels / CMS-id-prefixed / empty → derive a name from the URL
      (detail-page slug, else host root)
    - otherwise the name is kept as-is
    """
    cleaned = name.strip()
    low = cleaned.lower()
    if low in _DROP_NAMES:
        return ""
    if not cleaned or low in _GENERIC_NAME_LABELS or _CMS_ID_PREFIX_RE.match(low):
        return build_name_from_url(url)
    # Logo-grid cruft ("Gatik-Logo", "Renaissant Logo Green Orange") → strip it;
    # if nothing meaningful survives, derive the name from the URL instead.
    de_logoed = _strip_logo_cruft(cleaned)
    if len(de_logoed) < _MIN_NAME_LENGTH:
        return build_name_from_url(url)
    return de_logoed


def build_name_from_url(url: str) -> str:
    """Best-effort company name from a URL: the detail-page slug, else host root.

    A firm-level nav segment (``/portfolio``, ``/companies``…) is not a company
    name, so it's skipped in favour of the host root.
    """
    trimmed = url.strip()
    parsed = urlparse(trimmed if trimmed.lower().startswith("http") else f"https://{trimmed}")
    segments = [segment for segment in parsed.path.split("/") if segment]
    if segments and segments[-1].lower() not in _NAV_SEGMENTS:
        words = [word for word in re.split(r"[-_]", segments[-1]) if word]
        if words:
            return " ".join(word.capitalize() for word in words)
    host = (parsed.netloc or "").lower().removeprefix("www.")
    root = host.split(".")[0] if host else ""
    return root.capitalize()


def sanitize_candidates(companies: list[dict[str, str]]) -> list[dict[str, str]]:
    """Clean names + strip URLs on discovered candidates; drop non-company rows.

    Preserves all other fields (``source``, ``description``). Drops rows whose
    name resolves to "" (login/account links that aren't portfolio companies).

    This is a defensive cleanup layer over imperfect extraction output, so it
    reads ``name``/``url`` with ``.get`` *by design* — a missing/empty name is
    exactly what it's here to fix (re-derive from the URL), not a fail-fast case.
    """
    cleaned: list[dict[str, str]] = []
    for company in companies:
        raw_url = company.get("url")
        raw_name = company.get("name")
        url = raw_url.strip() if isinstance(raw_url, str) else ""
        name = sanitize_company_name(raw_name if isinstance(raw_name, str) else "", url)
        if not name:
            continue
        cleaned.append({**company, "name": name, "url": url})
    return cleaned


def normalize_url_key(url: str) -> str:
    """Normalize a URL to a dedup key of ``host + path``.

    Strips ``www.`` and trailing slash, lowercases the host, ignores query and
    fragment. Path-aware on purpose: a firm's per-company detail pages
    (``firm.com/portfolio/a``, ``firm.com/portfolio/b``) share a domain but are
    distinct companies, so keying on the domain alone would collapse a whole
    portfolio into one. ``www``/trailing-slash variants of the *same* URL still
    map to the same key, and root-path company sites key to just the host — so
    external-company matching (heuristic ∩ AI auto-include) is unchanged.

    Surrounding whitespace is stripped first: extraction sometimes yields a URL
    with a trailing space (``"https://acme.com/ "``), which would otherwise key
    differently from the clean variant and survive dedup as a duplicate row.
    """
    url = url.strip()
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

    auto_included = [{**heuristic_by_key[k], "source": "site"} for k in intersection]
    needs_validation = [
        {**(heuristic_by_key if k in heuristic_by_key else ai_by_key)[k], "source": "site"}
        for k in remainder_keys
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
    Confidence-aware dedup (see :func:`find_new_candidates`): the trusted
    (site-derived) set wins, so a company already found reliably on the firm's
    site never reappears as a web-search row and TLD duplicates collapse.
    """
    trusted = [*auto_included, *needs_validation]
    return [*needs_validation, *find_new_candidates(fallback, trusted)]


def find_new_candidates(
    candidates: list[dict[str, str]],
    trusted: list[dict[str, str]],
    *,
    source: str = "web_search",
) -> list[dict[str, str]]:
    """Return the ``candidates`` not already present in ``trusted``.

    Confidence-aware dedup shared by the initial web-search fallback and the
    customer-triggered deepen: a candidate is dropped if its normalized URL key
    OR its normalized name already appears in ``trusted`` (or earlier in
    ``candidates``), so the trusted source wins and ``acme.com`` / ``acme.in``
    twins collapse. A trusted entry is never dropped — only lower-confidence
    candidates are filtered. Each kept entry is emitted as
    ``{name, url, description, source}``.

    The trusted index uses ``.get`` (a malformed trusted entry just doesn't
    contribute to dedup — graceful, never crashes the merge), while candidates
    use direct access since ``name``/``url`` are schema-required on them.

    NOTE: name dedup strips legal suffixes, so two genuinely-distinct firms with
    the same single-word stem (e.g. "Data Corp" vs "Data Inc") would collapse.
    Rare in one portfolio, and upload remains the exact-list correction.
    """
    # Build the trusted index defensively: `trusted` may include a seed loaded
    # from DynamoDB, so a non-string url/name shouldn't crash the merge — it just
    # doesn't contribute to dedup (graceful, per this function's contract).
    seen_urls: set[str] = set()
    seen_names: set[str] = set()
    for entry in trusted:
        trusted_url = entry.get("url")
        if isinstance(trusted_url, str):
            seen_urls.add(normalize_url_key(trusted_url))
        trusted_name = entry.get("name")
        if isinstance(trusted_name, str) and trusted_name:
            seen_names.add(normalize_company_name(trusted_name))
    fresh: list[dict[str, str]] = []
    for company in candidates:
        key = normalize_url_key(company["url"])
        name_key = normalize_company_name(company["name"])
        if not key or key in seen_urls or (name_key and name_key in seen_names):
            continue
        seen_urls.add(key)
        if name_key:
            seen_names.add(name_key)
        fresh.append(
            {"name": company["name"], "url": company["url"], "description": "", "source": source}
        )
    return fresh


def build_verdict(
    *,
    site_total: int,
    total: int,
    site_fetch_failed: bool,
    fallback_ran: bool,
    deepen_added: int | None = None,
    site_source_url: str = "",
) -> dict[str, Any]:
    """Summarise how discovery went, for a customer-facing message + next actions.

    ``completeness`` is the single signal the UI maps to a message:
    - ``partial_site_list`` — the site gave us a non-zero list, but we can't verify
      it's complete (CSR shells, paginated JSON, and logo grids commonly surface
      only a subset), so we never claim it's the full list
    - ``site_blocked`` — the site couldn't be reached (fetch failed after retries)
    - ``web_search_subset`` — web search contributed companies (site empty/thin)
    - ``web_search_exhausted`` — a deepen round added nothing new; web search is
      tapped out, so point the customer at upload for completeness
    - ``genuinely_empty`` — nothing found anywhere
    - ``full_site_list`` — reserved for results we have positive reason to believe
      are complete; not emitted by the current signals (kept for legacy verdicts)

    A non-zero site scrape is NOT inferred to be complete — escalation
    (search_deeper + upload_list) stays available for every completeness except a
    believed-complete ``full_site_list`` and an exhausted search (upload only).

    ``deepen_added`` is the count of NEW companies a deepen round added (``None``
    for the initial discovery pass); ``0`` means web search is exhausted.
    """
    exhausted = deepen_added == 0
    if site_fetch_failed and fallback_ran:
        completeness, method = "site_blocked", "web_search"
    elif exhausted and total > 0:
        completeness, method = "web_search_exhausted", "web_search"
    elif fallback_ran and total > 0:
        completeness, method = "web_search_subset", "web_search"
    elif site_total > 0:
        completeness, method = "partial_site_list", "site"
    else:
        completeness, method = "genuinely_empty", ("web_search" if fallback_ran else "none")

    # Escalation is hidden only when we believe we're done: a confirmed full list,
    # or an exhausted web search (where digging more is unproductive → upload).
    if completeness in ("full_site_list", "web_search_exhausted"):
        actions = ["upload_list"]
    else:
        actions = list(ESCALATION_ACTIONS)
    return {
        "method": method,
        "count": total,
        "completeness": completeness,
        "available_actions": actions,
        # The firm page we read site-derived companies from — the group-level
        # trust anchor the UI shows ("read from <site_source_url>").
        "site_source_url": site_source_url,
    }

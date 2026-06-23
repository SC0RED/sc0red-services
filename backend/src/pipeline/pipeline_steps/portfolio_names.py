"""Company-name sanitisation for discovered portfolio candidates.

Cleans the raw ``name``/``url`` that extraction emits: drops login/account rows,
re-derives a name from the URL when extraction captured a CTA label or CMS id,
and strips logo-image cruft. Split from ``portfolio_merge`` (which owns dedup +
the verdict) so each module stays focused and under the file-size limit.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

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
# 2-char minimum: a single letter surviving logo stripping is not a usable name,
# so we fall back to the URL-derived name instead.
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

    Only TRAILING descriptors are stripped, never leading/embedded ones: a real
    firm name can start with a colour word ("Silver Lake", "Orange Theory"), so
    "Silver Lake Logo" → "Silver Lake", not "Lake". The trade-off is that the
    rare "<colour> Logo <Name>" alt-text form keeps its leading descriptor — an
    acceptable miss versus mangling a legitimate name.
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

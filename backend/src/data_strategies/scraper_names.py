"""Company-name derivation helpers — split out of ``web_scraper_strategy``.

Pure string→name utilities shared across the discovery strategies (web scrape,
wp-json, sitemap): title-casing, slug/URL/filename → name, and the shared
name-length bounds. Kept dependency-free (no scraper/DOM imports) so every
discovery path applies identical name normalisation and length filtering.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

_LOGO_SUFFIX_RE = re.compile(r"[-_ ]?logo$", re.IGNORECASE)
_FILENAME_TOKEN_SPLIT_RE = re.compile(r"(?<=[a-z])(?=[A-Z])|[-_.\s]+")
# A lowercase letter at the start of the string or right after whitespace — the
# only positions an apostrophe-safe title-case capitalises (so "harry's" stays
# "Harry's", not "Harry'S" the way ``str.title()`` would render it).
_WORD_INITIAL_RE = re.compile(r"(?:^|\s)[a-z]")

# Public — imported across the discovery strategies so the heuristic, wp-json,
# sitemap, and AI-derived name fallbacks all apply identical bounds.
MIN_NAME_LENGTH = 2
MAX_NAME_LENGTH = 60


def title_case_tokens(raw: str) -> str:  # noqa: NAMING001  (transform util, not a verb)
    """Split a slug-like string on separators / camelCase and title-case."""
    tokens = [t for t in _FILENAME_TOKEN_SPLIT_RE.split(raw) if t]
    if not tokens:
        return ""
    return " ".join(t.capitalize() for t in tokens)


def titlecase_words(raw: str) -> str:  # noqa: NAMING001  (transform util, not a verb)
    """Normalise an img-``alt`` label's casing for use as a company name.

    Already-mixed-case alt is human-cased — trust it as-is (``"Harry's Fresh
    Foods"``, ``"iRobot"``). Only ALL-CAPS / all-lowercase labels are re-cased,
    and that re-casing is apostrophe-safe: it upper-cases a letter only at the
    start or after whitespace, so ``"HARRY'S FRESH FOODS"`` → ``"Harry's Fresh
    Foods"`` (not ``"Harry'S …"`` the way ``str.title()`` would render it). An
    all-caps acronym is the one casualty (``"AT&T"`` → ``"At&t"``) — rare for an
    alt label, and the AI-validation / confirm steps recover it.
    """
    if raw != raw.upper() and raw != raw.lower():
        return raw
    return _WORD_INITIAL_RE.sub(lambda match: match.group().upper(), raw.lower())


def extract_name_from_img_src(src: str) -> str:  # noqa: NAMING001  (transform util, not a verb)
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
    name = title_case_tokens(stem)
    if not (MIN_NAME_LENGTH < len(name) <= MAX_NAME_LENGTH):
        return ""
    return name


def extract_name_from_url(url: str) -> str:
    """Derive a company name from the target URL's hostname as a last resort.

    Used by :mod:`portfolio_discovery_strategy` as the final fallback when
    HTML offers no name signal at all.

    ``https://www.endurancelift.com/`` → ``Endurancelift``.
    Same single-token limitation as :func:`extract_name_from_img_src`.
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
    name = title_case_tokens(stem)
    if not (MIN_NAME_LENGTH < len(name) <= MAX_NAME_LENGTH):
        return ""
    return name


def name_from_url_slug(url: str) -> str:  # noqa: NAMING001  (transform util, not a verb)
    """Derive a company name from a detail-page URL's last path segment.

    Anchor-link and sitemap-enumerated portfolios (e.g. Francisco Partners'
    ``/investments/{slug}``, Audax's ``/portfolio/{slug}``) carry the company
    name in the slug. ``/investments/aeries-software`` -> ``Aeries Software``;
    returns "" when the title-cased slug is out of the shared name-length bounds.
    """
    slug = urlparse(url).path.rstrip("/").rsplit("/", 1)[-1]
    name = title_case_tokens(slug)
    # Strict upper bound (drops names >= MAX) to match the discovery length
    # filter; the wp-json/sitemap rungs share this convention via this helper.
    if MIN_NAME_LENGTH < len(name) < MAX_NAME_LENGTH:
        return name
    return ""

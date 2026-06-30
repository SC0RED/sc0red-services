"""Extract portfolio company names from logo-image ``alt`` text.

Some PE firms render their portfolio as a grid of company logo images with the
company name only in the ``<img alt>`` attribute (e.g. Vista Equity Partners:
``alt="Logo of software company Jamf"``), with no links and no per-company
detail pages. The visible body text and ``<a>`` links carry nothing, so the
normal scrape yields zero. This reads the names out of the logo ``alt`` text.

Names only — these sites expose no company URL, so the names are used to SEED
the grounded web-search fallback (which resolves each official URL).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from src.data_strategies.scraper_names import MAX_NAME_LENGTH, MIN_NAME_LENGTH

if TYPE_CHECKING:
    from bs4 import BeautifulSoup

# Shared name-length bounds — single-sourced in scraper_names (a leaf module, so
# no circular import). The same thresholds every discovery path applies.
_MIN_LOGO_NAME = MIN_NAME_LENGTH
_MAX_LOGO_NAME = MAX_NAME_LENGTH

# "Logo of [the] [<descriptor words>] company {Name}" — the precise, high-signal
# form. Allows multi-word descriptors ("cloud software company …"). Requiring the
# "company" keyword naturally excludes the firm's own header logo (e.g. "Vista
# logo"), partner badges, and press logos.
_LOGO_OF_COMPANY_RE = re.compile(r"(?i)^logo of (?:the )?(?:[\w-]+ )*company\s+(.+)$")


def extract_logo_companies(soup: BeautifulSoup) -> list[str]:
    """Return company names parsed from logo ``<img alt>`` text, deduped."""
    names: list[str] = []
    seen: set[str] = set()
    for img in soup.find_all("img"):
        alt = (img.get("alt") or "").strip()
        if not alt:
            continue
        match = _LOGO_OF_COMPANY_RE.match(alt)
        if not match:
            continue
        name = match.group(1).strip(" .,-'\"")
        key = name.lower()
        if not (_MIN_LOGO_NAME < len(name) <= _MAX_LOGO_NAME) or key in seen:
            continue
        seen.add(key)
        names.append(name)
    return names

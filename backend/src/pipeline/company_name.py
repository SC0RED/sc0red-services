"""Resolve a clean, never-blank display name for a company.

Profile extraction occasionally returns ``"unknown"``/blank for the company
name when the scraped page carries no explicit name (the title/logo lives in
markup the scraper strips). This resolver guarantees a usable name so the
literal never reaches a downstream AI prompt or the stored record. It is used
at two points:

* ``parallel_profile_risk`` — normalises the parsed profile up front, so the
  mid-pipeline AI steps (financial research, EBITDA tree, value chain, strategy
  map) all see the clean name.
* ``persist_results`` — a last-mile safety net before the record is written.
"""

from __future__ import annotations

from src.data_strategies.web_scraper_strategy import extract_name_from_url

# Names that must never reach a downstream AI prompt or the stored record.
_PLACEHOLDER_NAMES = frozenset({"unknown", "n/a", "none", "null", "untitled"})


def resolve_company_name(extracted_name: str, seed_name: str, url: str) -> str:
    """Return a clean company name, never blank or a placeholder.

    Prefers the AI-extracted ``extracted_name``, then the discovered
    ``seed_name`` (portfolio candidate name), then a name derived from the
    domain, then the bare URL.
    """
    for candidate in (extracted_name, seed_name, extract_name_from_url(url)):
        cleaned = (candidate or "").strip()
        if cleaned and cleaned.lower() not in _PLACEHOLDER_NAMES:
            return cleaned
    # Last resort: the bare URL still beats showing "unknown".
    return (url or "").strip() or "Unnamed company"

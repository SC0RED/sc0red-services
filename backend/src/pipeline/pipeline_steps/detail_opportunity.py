"""Opportunity detail enrichment constants — schema and prompt builder.

Each selected opportunity from the ideation phase gets a focused detail call
that adds implementation steps, timeline, investment range, and ROI estimate.
"""

from __future__ import annotations

from typing import Any

from src.pipeline.prompts.loader import load_schema, load_system_prompt, load_template

DETAIL_SYSTEM_PROMPT = load_system_prompt("opportunity_detail")

DETAIL_SCHEMA: dict[str, Any] = load_schema("detail")

_DETAIL_TEMPLATE = load_template("detail")

# The detail schema's ``implementation_steps`` is an unbounded string array, and
# the model occasionally malforms its output by appending the OTHER detail
# fields' names and values as extra "steps" (a structured-output glitch — it
# passes schema validation because they are all strings). Those leaked items
# duplicate the sibling fields, which is how we identify and strip them.
_DETAIL_FIELD_NAMES = frozenset(
    {
        "implementation_steps",
        "timeline",
        "investment_range",
        "roi_estimate",
        "investment_value_usd",
        "roi_estimate_pct",
    }
)
_MIN_STEP_LENGTH = 3  # drops punctuation/empty leaks like ","
_MAX_STEPS = 5  # the prompt asks for 3; a small cap backstops any residual leak


def sanitize_implementation_steps(detail_data: dict[str, Any]) -> list[str]:
    """Strip leaked field-name/value tokens from ``implementation_steps``.

    Drops array items that (a) match a detail field name, (b) duplicate a sibling
    field's value in the same response (e.g. the leaked ``roi_estimate`` prose or
    ``timeline`` string), or (c) are empty/punctuation-only — then caps to
    ``_MAX_STEPS``. Real steps lead the array, so the cap preserves them.
    """
    raw = detail_data.get("implementation_steps", [])
    if not isinstance(raw, list):
        return []

    # Only the STRING sibling fields can be echoed verbatim into the steps array;
    # the numeric fields' NAMES are already covered by ``_DETAIL_FIELD_NAMES``, and
    # stringifying their values (incl. ``None`` → "None") would add noise.
    leaked_values = {
        str(detail_data.get(field, "")).strip()
        for field in ("timeline", "investment_range", "roi_estimate")
    }
    leaked_values.discard("")

    cleaned: list[str] = []
    for item in raw:
        if not isinstance(item, str):
            continue
        text = item.strip()
        if len(text) < _MIN_STEP_LENGTH:
            continue
        if text in _DETAIL_FIELD_NAMES or text in leaked_values:
            continue
        cleaned.append(text)
    return cleaned[:_MAX_STEPS]


def _build_company_context(profile_dict: dict[str, Any]) -> str:
    """Build a focused company context string from profile fields."""
    lines = [f"Company: {profile_dict.get('company_name', 'Unknown')}"]

    if profile_dict.get("industry"):
        lines.append(f"Industry: {profile_dict['industry']}")
    if profile_dict.get("business_model"):
        lines.append(f"Business Model: {profile_dict['business_model']}")
    if profile_dict.get("company_size"):
        lines.append(f"Company Size: {profile_dict['company_size']}")

    products = profile_dict.get("products_services", [])
    if products:
        lines.append(f"Products/Services: {', '.join(products)}")

    tech = profile_dict.get("tech_signals", [])
    if tech:
        lines.append(f"Tech Stack: {', '.join(tech)}")

    return "\n".join(lines)


def build_detail_prompt(
    profile_dict: dict[str, Any],
    opportunity_title: str,
    opportunity_description: str,
) -> str:
    """Build prompt to detail a single opportunity with implementation specifics."""
    company_context = _build_company_context(profile_dict)

    return _DETAIL_TEMPLATE.format(
        company_context=company_context,
        opportunity_title=opportunity_title,
        opportunity_description=opportunity_description,
    )

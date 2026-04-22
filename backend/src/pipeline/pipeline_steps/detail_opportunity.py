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

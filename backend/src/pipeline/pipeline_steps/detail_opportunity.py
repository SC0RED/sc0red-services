"""Opportunity detail enrichment constants — schema and prompt builder.

Each selected opportunity from the ideation phase gets a focused detail call
that adds implementation steps, timeline, investment, ROI, and services.
"""

from __future__ import annotations

from typing import Any

DETAIL_SYSTEM_PROMPT = (
    "You are an AI transformation advisor for private equity portfolio companies. "
    "Provide specific, actionable implementation plans with realistic timelines, "
    "investment ranges, and vendor recommendations."
)

DETAIL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "implementation_steps": {
            "type": "array",
            "items": {"type": "string"},
            "description": "3 specific implementation steps",
        },
        "timeline": {
            "type": "string",
            "description": (
                "Quick Win (1-3 months)|Medium-term (3-9 months)|Long-term (9-18 months)"
            ),
        },
        "investment_range": {
            "type": "string",
            "description": "$50K-$100K|$100K-$500K|$500K-$1M|$1M+",
        },
        "roi_estimate": {
            "type": "string",
            "description": "Specific ROI description tied to this company",
        },
        "related_services": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 3,
            "description": (
                "Up to 3 relevant vendor or service names (e.g. 'Datadog - Observability')"
            ),
        },
    },
    "required": [
        "implementation_steps",
        "timeline",
        "investment_range",
        "roi_estimate",
        "related_services",
    ],
    "additionalProperties": False,
}


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

    return f"""Detail this AI opportunity for a PE portfolio company.

{company_context}

Opportunity: {opportunity_title}
{opportunity_description}

Provide 3 implementation steps, timeline, investment range, ROI estimate, \
and up to 3 vendor recommendations."""

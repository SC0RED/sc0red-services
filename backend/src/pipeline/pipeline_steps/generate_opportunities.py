"""Opportunity generation constants — schemas, prompt builders, and helpers.

Used by ParallelOpportunitiesAndEbitda to build the opportunity AI calls.
"""

from __future__ import annotations

import json
from typing import Any

from src.models.model_company import Opportunity

OPPS_SYSTEM_PROMPT = (
    "You are a senior management consultant and AI transformation advisor who specializes "
    "in helping private equity portfolio companies capture AI opportunities and defend "
    "against disruption. You combine strategic thinking with practical implementation expertise.\n\n"
    "Your recommendations are:\n"
    "- Specific and actionable: Real implementation steps, not vague suggestions\n"
    "- Industry-appropriate: Tailored to what's actually feasible in this sector\n"
    "- Commercial: Focused on ROI, competitive advantage, and revenue impact\n"
    "- Resourced: Include realistic investment ranges and timeline estimates\n\n"
    "For vendor recommendations, suggest real companies that specialize in each service area."
)

STRATEGIC_CATEGORIES_INSTRUCTIONS = """Strategic categories to use:
- "Competitive Moat" - Strengthen defensibility (data flywheels, switching costs, network effects)
- "Revenue Capture" - New AI-powered products/services to sell
- "Market Expansion" - Enter adjacent markets enabled by AI
- "Operational Efficiency" - Internal AI to cut costs and improve margins
- "Talent Strategy" - Workforce transformation, AI hiring, upskilling"""

OPPORTUNITY_ITEM_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "Specific, action-oriented title"},
        "impact_rating": {"type": "string", "enum": ["High", "Medium", "Low"]},
        "strategic_category": {
            "type": "string",
            "description": "One of: Competitive Moat, Revenue Capture, Market Expansion, Operational Efficiency, Talent Strategy",
        },
        "description": {
            "type": "string",
            "description": "2-3 sentence description",
        },
        "implementation_steps": {
            "type": "array",
            "items": {"type": "string"},
            "description": "3-5 specific implementation steps",
        },
        "timeline": {
            "type": "string",
            "description": "Quick Win (1-3 months)|Medium-term (3-9 months)|Long-term (9-18 months)",
        },
        "investment_range": {
            "type": "string",
            "description": "$50K-$100K|$100K-$500K|$500K-$1M|$1M+",
        },
        "roi_estimate": {"type": "string", "description": "Specific ROI description"},
        "related_services": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 3,
            "description": "Up to 3 relevant vendor or service names (e.g. 'Datadog - Observability')",
        },
        "value_lever": {
            "type": "string",
            "enum": ["Revenue Side", "Cost Side", "Both"],
            "description": "Whether this opportunity primarily drives revenue growth, reduces costs, or both",
        },
    },
    "required": [
        "title",
        "impact_rating",
        "strategic_category",
        "description",
        "implementation_steps",
        "timeline",
        "investment_range",
        "roi_estimate",
        "related_services",
        "value_lever",
    ],
    "additionalProperties": False,
}

HIGH_PRIORITY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "opportunities": {"type": "array", "items": OPPORTUNITY_ITEM_SCHEMA},
        "top_three_immediate_actions": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Top 3 immediate actions doable in 30 days",
        },
    },
    "required": ["opportunities", "top_three_immediate_actions"],
    "additionalProperties": False,
}

STRATEGIC_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "opportunities": {"type": "array", "items": OPPORTUNITY_ITEM_SCHEMA},
    },
    "required": ["opportunities"],
    "additionalProperties": False,
}


def build_opportunity(data: dict[str, Any]) -> Opportunity:
    """Build an Opportunity model from AI response data."""
    return Opportunity(**data)


def build_context_block(profile_dict: dict[str, Any], assessment_dict: dict[str, Any]) -> str:
    """Build the shared company/risk context included in both prompts."""
    risk_scores_json = json.dumps(assessment_dict["risk_scores"])
    top_risks = ", ".join(assessment_dict["top_risks"])

    return f"""COMPANY PROFILE:
{json.dumps(profile_dict)}

RISK ASSESSMENT:
Overall Score: {assessment_dict["overall_score"]}/10 ({assessment_dict["tier"]} risk)
Top Risks: {top_risks}
Risk Summary: {assessment_dict["analysis_summary"]}

DETAILED RISK SCORES:
{risk_scores_json}"""


def build_high_priority_prompt(
    profile_dict: dict[str, Any],
    assessment_dict: dict[str, Any],
    focus_categories: list[str],
) -> str:
    """Build prompt for high-priority opportunity generation."""
    context = build_context_block(profile_dict, assessment_dict)
    categories_list = ", ".join(focus_categories)

    return f"""Generate specific, tactical AI opportunity recommendations for this company, focusing on the highest-priority risks.

{context}

TARGET RISK CATEGORIES (highest priority): {categories_list}

Generate 2-3 high-priority opportunities targeting the risk categories listed above. For each opportunity:
- Make implementation steps specific to THIS company (3-5 steps)
- Keep descriptions concise (2-3 sentences)
- ROI estimates should be realistic for company size and industry
- For related_services, list up to 3 relevant vendors as simple strings (e.g. "Datadog - Observability")
- Classify each opportunity's value_lever: "Revenue Side" (drives top-line growth, new revenue streams, pricing optimization, market expansion), "Cost Side" (reduces operating expenses, automation, efficiency gains), or "Both" (impacts revenue and cost simultaneously)

{STRATEGIC_CATEGORIES_INSTRUCTIONS}

Also provide top_three_immediate_actions: the 3 most impactful actions this company can start within 30 days."""


def build_strategic_prompt(
    profile_dict: dict[str, Any],
    assessment_dict: dict[str, Any],
    focus_categories: list[str],
) -> str:
    """Build prompt for strategic opportunity generation."""
    context = build_context_block(profile_dict, assessment_dict)
    categories_list = ", ".join(focus_categories)

    return f"""Generate specific, tactical AI opportunity recommendations for this company, focusing on strategic risk categories.

{context}

TARGET RISK CATEGORIES (strategic): {categories_list}

Generate 1-2 strategic opportunities targeting the risk categories listed above. For each opportunity:
- Make implementation steps specific to THIS company (3-5 steps)
- Keep descriptions concise (2-3 sentences)
- ROI estimates should be realistic for company size and industry
- For related_services, list up to 3 relevant vendors as simple strings (e.g. "Datadog - Observability")
- Classify each opportunity's value_lever: "Revenue Side" (drives top-line growth, new revenue streams, pricing optimization, market expansion), "Cost Side" (reduces operating expenses, automation, efficiency gains), or "Both" (impacts revenue and cost simultaneously)

{STRATEGIC_CATEGORIES_INSTRUCTIONS}

Generate the opportunities. Do NOT include top_three_immediate_actions."""

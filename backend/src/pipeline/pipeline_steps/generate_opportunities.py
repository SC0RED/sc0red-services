"""Opportunity generation shared constants — system prompt, categories, and helpers.

Shared by ideate_opportunities.py and detail_opportunity.py. The old schemas
(OPPORTUNITY_ITEM_SCHEMA, HIGH_PRIORITY_SCHEMA, STRATEGIC_SCHEMA) and prompt
builders (build_context_block, build_high_priority_prompt, build_strategic_prompt)
have been replaced by the ideation + detail decomposition.
"""

from __future__ import annotations

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


def build_opportunity(data: dict[str, Any]) -> Opportunity:
    """Build an Opportunity model from AI response data."""
    return Opportunity(**data)

"""Opportunity generation shared constants and helpers.

Shared by ideate_opportunities.py and detail_opportunities.py.
"""

from __future__ import annotations

from typing import Any

from src.models.model_company import Opportunity

STRATEGIC_CATEGORIES_INSTRUCTIONS = """Strategic categories to use:
- "Competitive Moat" - Strengthen defensibility (data flywheels, switching costs, network effects)
- "Revenue Capture" - New AI-powered products/services to sell
- "Market Expansion" - Enter adjacent markets enabled by AI
- "Operational Efficiency" - Internal AI to cut costs and improve margins
- "Talent Strategy" - Workforce transformation, AI hiring, upskilling"""


def build_opportunity(data: dict[str, Any]) -> Opportunity:
    """Build an Opportunity model from AI response data."""
    return Opportunity(**data)

"""Opportunity ideation constants — schema and prompt builder for tiny parallel calls.

Each of the 8 risk categories gets one ideation call that runs at Level 1
(in parallel with profile extraction and risk assessment). The ideation call
uses raw scraped content (not structured profile) so it can start immediately.
"""

from __future__ import annotations

from typing import Any

from src.documents.extract_text import MAX_CHARS_COMBINED
from src.models.model_literals import RISK_SCOPE_DISPLAY
from src.pipeline.pipeline_steps.generate_opportunities import STRATEGIC_CATEGORIES_INSTRUCTIONS

IDEATION_SYSTEM_PROMPT = (
    "You are a senior management consultant specialising in AI transformation for "
    "private equity portfolio companies. Given a company's website and a specific risk "
    "category, propose ONE concrete AI opportunity that directly addresses that risk.\n\n"
    "Your recommendation must be:\n"
    "- Specific and actionable, not a vague suggestion\n"
    "- Directly tied to the risk category provided\n"
    "- Commercially focused on ROI and competitive advantage"
)

IDEATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "Specific, action-oriented title"},
        "description": {
            "type": "string",
            "description": "2-3 sentence description of the opportunity",
        },
        "value_lever": {
            "type": "string",
            "enum": ["Revenue Side", "Cost Side", "Both"],
            "description": "Whether this drives revenue growth, reduces costs, or both",
        },
        "strategic_category": {
            "type": "string",
            "description": (
                "One of: Competitive Moat, Revenue Capture,"
                " Market Expansion, Operational Efficiency, Talent Strategy"
            ),
        },
        "impact_rating": {
            "type": "string",
            "enum": ["High", "Medium", "Low"],
        },
    },
    "required": ["title", "description", "value_lever", "strategic_category", "impact_rating"],
    "additionalProperties": False,
}


def build_ideation_prompt(
    scraped_text: str,
    url: str,
    category_id: str,
    category_name: str,
    category_description: str,
    document_text: str | None = None,
) -> str:
    """Build prompt for a single-category ideation call."""
    document_section = ""
    if document_text:
        document_section = f"\n\nSUPPLEMENTARY DOCUMENTS:\n{document_text[:MAX_CHARS_COMBINED]}"

    return f"""Analyse this company and propose ONE specific AI opportunity \
that addresses the risk category below.

COMPANY URL: {url}

WEBSITE CONTENT:
{scraped_text[:12000]}{document_section}

RISK CATEGORY: {category_id} — {category_name}
{category_description}

{STRATEGIC_CATEGORIES_INSTRUCTIONS}

Propose exactly one opportunity. Make the title specific and action-oriented. \
Classify the value_lever as "Revenue Side", "Cost Side", or "Both"."""


def get_all_ideation_categories() -> list[dict[str, str]]:
    """Return all 8 risk categories with id, name, and description for ideation calls."""
    return [
        {
            "id": category_id,
            "name": display["name"],
            "description": display["description"],
        }
        for category_id, display in RISK_SCOPE_DISPLAY.items()
    ]

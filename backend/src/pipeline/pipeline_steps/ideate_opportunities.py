"""Opportunity ideation constants — schema and prompt builder for tiny parallel calls.

Each of the 8 risk categories gets one ideation call that runs at Level 1
(in parallel with profile extraction and risk assessment). The ideation call
uses raw scraped content (not structured profile) so it can start immediately.
"""

from __future__ import annotations

from typing import Any

from src.documents.extract_text import MAX_CHARS_COMBINED, MAX_SCRAPED_TEXT_CHARS
from src.models.model_literals import RISK_SCOPE_DISPLAY
from src.pipeline.pipeline_steps.generate_opportunities import STRATEGIC_CATEGORIES_INSTRUCTIONS
from src.pipeline.prompts.loader import load_schema, load_system_prompt, load_template

IDEATION_SYSTEM_PROMPT = load_system_prompt("opportunity_ideation")

IDEATION_SCHEMA: dict[str, Any] = load_schema("ideation")

_IDEATION_TEMPLATE = load_template("ideation")


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

    return _IDEATION_TEMPLATE.format(
        url=url,
        scraped_text=scraped_text[:MAX_SCRAPED_TEXT_CHARS],
        document_section=document_section,
        category_id=category_id,
        category_name=category_name,
        category_description=category_description,
        strategic_categories=STRATEGIC_CATEGORIES_INSTRUCTIONS,
    )


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

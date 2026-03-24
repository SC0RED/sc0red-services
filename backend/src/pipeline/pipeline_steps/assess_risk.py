"""Risk assessment constants — system prompt, schema, and shared prompt components.

Used by ParallelProfileRiskAndIdeation to build the risk assessment AI calls.
The risk assessment is split into two parallel batches of 4 categories each,
grouped by thematic relevance (external market threats vs internal/operational risks).
"""

from __future__ import annotations

from typing import Any

from src.models.model_literals import RISK_SCOPE_DISPLAY
from src.pipeline.prompts.loader import load_schema, load_system_prompt

RISK_SYSTEM_PROMPT = load_system_prompt("risk_assessment")

# Batch schema -- used for the 2x4 parallel risk split.
# Returns only risk_scores (no aggregates — those are computed programmatically).
RISK_BATCH_SCHEMA: dict[str, Any] = load_schema("risk_batch")

# Category batches grouped by thematic relevance for cross-category reasoning.
# Batch A: external market threats — these naturally cross-reference each other.
# Batch B: internal/operational risks — these naturally cross-reference each other.
RISK_BATCH_A_CATEGORIES: list[str] = [
    "competitive_displacement",
    "technology_obsolescence",
    "customer_behavior",
    "margin_compression",
]

RISK_BATCH_B_CATEGORIES: list[str] = [
    "talent_workforce",
    "regulatory_compliance",
    "supply_chain",
    "data_ip",
]

# Shared prompt components used by ParallelProfileRiskAndIdeation

RISK_INDUSTRY_WEIGHTING = """\
- If Financial Services: Weight regulatory_compliance and competitive_displacement higher
- If Healthcare: Weight regulatory_compliance and data_ip higher
- If Manufacturing: Weight supply_chain and talent_workforce higher
- If Technology/SaaS: Weight technology_obsolescence and competitive_displacement higher
- If Professional Services: Weight talent_workforce and technology_obsolescence higher
- If Retail/Consumer: Weight customer_behavior and margin_compression higher"""

RISK_ASSESSMENT_QUESTIONS = """\
For each risk category, consider:
1. What specific AI technologies are threatening this company's position?
2. Who are the AI-native competitors entering this space?
3. What is the timeline of disruption risk?
4. Are there any moats protecting against this risk?

Assess all risk categories and provide the overall analysis."""


def build_risk_batch_categories_block(categories: list[str]) -> str:
    """Build a categories block for a subset of risk categories."""
    return "\n".join(
        f"- {scope_id}: {RISK_SCOPE_DISPLAY[scope_id]['name']} — "
        f"{RISK_SCOPE_DISPLAY[scope_id]['description']}"
        for scope_id in categories
    )

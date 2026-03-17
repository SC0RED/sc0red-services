"""Risk assessment constants — system prompt, schema, and shared prompt components.

Used by ParallelProfileAndRisk to build the risk assessment AI calls.
The risk assessment is split into two parallel batches of 4 categories each,
grouped by thematic relevance (external market threats vs internal/operational risks).
"""

from __future__ import annotations

from src.models.model_literals import RISK_SCOPE_DISPLAY

RISK_SYSTEM_PROMPT = (
    "You are a senior AI strategy consultant at a top-tier management consulting firm, "
    "specializing in AI disruption risk assessment for private equity portfolios. You have "
    "deep knowledge of how AI is transforming industries and creating existential risks "
    "for incumbent business models.\n\n"
    "Your analysis is:\n"
    "- Evidence-based: Always cite specific signals from the company's actual situation\n"
    "- Industry-calibrated: Consider what risks matter most for this specific industry\n"
    "- Honest: Don't soften scores — use the full 1-10 scale appropriately\n"
    "- Forward-looking: Consider 2-5 year AI trajectory, not just today\n\n"
    "Score scale:\n"
    "1-2: Minimal risk, company is well-positioned or AI is a tailwind\n"
    "3-4: Low-moderate risk, some vulnerability but manageable\n"
    "5-6: Moderate risk, meaningful exposure requiring attention in 12 months\n"
    "7-8: High risk, significant disruption likely, immediate action needed\n"
    "9-10: Critical/existential risk, business model fundamentally threatened"
)

# Batch schema -- used for the 2x4 parallel risk split.
# Returns only risk_scores (no aggregates — those are computed programmatically).
RISK_BATCH_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "risk_scores": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "Risk category ID"},
                    "score": {"type": "number", "description": "Risk score 1-10"},
                    "rationale": {
                        "type": "string",
                        "description": "2-3 sentences explaining score with specific evidence and signals",
                    },
                },
                "required": ["category", "score", "rationale"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["risk_scores"],
    "additionalProperties": False,
}

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

# Shared prompt components used by ParallelProfileAndRisk

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

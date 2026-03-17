"""Risk assessment constants — system prompt, schema, and shared prompt components.

Used by ParallelProfileAndRisk to build the risk assessment AI call.
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

RISK_SCHEMA: dict[str, object] = {
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
        "overall_score": {"type": "number", "description": "Overall risk score 1-10"},
        "tier": {
            "type": "string",
            "enum": ["low", "moderate", "high", "critical"],
            "description": "Risk tier",
        },
        "top_risks": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Top 3 most critical risk category IDs",
        },
        "analysis_summary": {"type": "string", "description": "3-4 sentence executive summary"},
    },
    "required": ["risk_scores", "overall_score", "tier", "top_risks", "analysis_summary"],
    "additionalProperties": False,
}

# Shared prompt components used by ParallelProfileAndRisk

RISK_CATEGORIES_BLOCK = "\n".join(
    f"- {scope_id}: {info['name']} — {info['description']}"
    for scope_id, info in RISK_SCOPE_DISPLAY.items()
)

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

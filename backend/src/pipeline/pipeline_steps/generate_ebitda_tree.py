"""EBITDA tree constants — system prompt, schema, prompt builder, and node builder.

Used by ParallelOpportunitiesAndEbitda to build the EBITDA decomposition AI call.
"""

from __future__ import annotations

import json
from typing import Any

from src.models.model_company import EbitdaNode

EBITDA_SYSTEM_PROMPT = (
    "You are a senior financial analyst and business model strategist who specialises "
    "in decomposing company economics into P&L trees for private equity portfolio companies. "
    "You understand how AI opportunities map to specific revenue and cost line items.\n\n"
    "Your analysis is:\n"
    "- Structured: Build a clear top-down tree from Revenue → Gross Profit → EBITDA\n"
    "- Specific: Use industry-typical line items relevant to this company's business model\n"
    "- Actionable: Link AI opportunities to specific P&L nodes where they'd have impact\n"
    "- Realistic: Provide reasonable estimates based on company size and industry benchmarks"
)

EBITDA_NODE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "label": {"type": "string"},
        "type": {"type": "string", "enum": ["revenue", "cost", "margin", "subtotal"]},
        "value_range": {
            "type": "string",
            "description": "Estimated value range (e.g. '$10M-$50M')",
        },
        "percentage_of_parent": {
            "type": ["number", "null"],
            "description": "Percentage of parent node value",
        },
        "description": {"type": "string"},
        "children": {"type": "array", "items": {"$ref": "#/$defs/node"}},
    },
    "required": [
        "id",
        "label",
        "type",
        "value_range",
        "percentage_of_parent",
        "description",
        "children",
    ],
    "additionalProperties": False,
}

EBITDA_TREE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "$defs": {"node": EBITDA_NODE_SCHEMA},
    "properties": {
        "summary": {
            "type": "string",
            "description": (
                "2-3 sentence overview of business model economics "
                "and where AI has the most P&L impact"
            ),
        },
        "revenue_estimate": {
            "type": "string",
            "description": "Estimated annual revenue range (e.g. '$10M-$50M')",
        },
        "ebitda_estimate": {
            "type": "string",
            "description": "Estimated EBITDA range or margin (e.g. '$2M-$8M' or '15-25% margin')",
        },
        "nodes": {
            "type": "array",
            "items": {"$ref": "#/$defs/node"},
            "description": "Top-level tree nodes (typically starts with Revenue)",
        },
    },
    "required": ["summary", "revenue_estimate", "ebitda_estimate", "nodes"],
    "additionalProperties": False,
}


def build_ebitda_node(data: dict[str, Any]) -> EbitdaNode:
    """Recursively build an EbitdaNode from a dict (AI response or test fixture)."""
    children = [build_ebitda_node(child) for child in data["children"]]
    return EbitdaNode(
        id=data["id"],
        label=data["label"],
        type=data["type"],
        value_range=data["value_range"],
        percentage_of_parent=data["percentage_of_parent"],
        description=data["description"],
        linked_opportunity_indices=data.get("linked_opportunity_indices", []),
        children=children,
    )


def build_ebitda_prompt(
    profile_dict: dict[str, Any],
    assessment_dict: dict[str, Any],
) -> str:
    """Build EBITDA tree prompt from profile and risk assessment (no opportunities needed)."""
    return f"""Build an EBITDA decomposition tree for this company \
showing how AI could impact the P&L.

COMPANY PROFILE:
{json.dumps(profile_dict)}

RISK ASSESSMENT:
Overall Score: {assessment_dict["overall_score"]}/10 \
({assessment_dict["tier"]} risk)
Summary: {assessment_dict["analysis_summary"]}

Build a tree from Revenue down to EBITDA. The tree should \
reflect this company's actual business model and industry.

Tree structure guidelines:
- Start with total Revenue at the top
- Break revenue into 2-4 revenue streams specific to this company
- Show COGS / Cost of Revenue
- Show Gross Profit (subtotal)
- Show 3-5 key operating expense categories relevant to this business
- Show EBITDA (subtotal)

Generate the EBITDA decomposition tree."""

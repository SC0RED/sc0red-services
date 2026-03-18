"""EBITDA tree constants — system prompt, schema, prompt builder, and node builder.

Used by ParallelOpportunityDetailsAndEbitda to build the EBITDA decomposition AI call.

The schema uses a flat list of nodes with parent_id references instead of recursive
$ref nesting. This eliminates the complex constrained decoding state machine and
reduces output tokens by ~3x, cutting generation time from ~70s to ~25-35s.
The flat list is reconstructed into a nested tree programmatically before being
sent to the frontend.
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

# Flat node schema — no recursive $ref. Each node references its parent via parent_id.
# Top-level section headers (Revenue, COGS, Gross Profit, Operating Expenses, EBITDA)
# use parent_id: null.
EBITDA_FLAT_NODE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "id": {
            "type": "string",
            "description": "Unique node identifier (e.g. 'revenue', 'cogs', 'subs')",
        },
        "parent_id": {
            "type": ["string", "null"],
            "description": "ID of parent node, or null for top-level nodes",
        },
        "label": {"type": "string", "description": "Display label (e.g. 'Total Revenue')"},
        "type": {"type": "string", "enum": ["revenue", "cost", "margin", "subtotal"]},
        "value_range": {
            "type": "string",
            "description": "Estimated value range (e.g. '$10M-$50M')",
        },
        "percentage_of_parent": {
            "type": ["number", "null"],
            "description": "Percentage of parent node value, or null for top-level nodes",
        },
        "description": {"type": "string"},
    },
    "required": [
        "id",
        "parent_id",
        "label",
        "type",
        "value_range",
        "percentage_of_parent",
        "description",
    ],
    "additionalProperties": False,
}

EBITDA_TREE_SCHEMA: dict[str, Any] = {
    "type": "object",
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
            "items": EBITDA_FLAT_NODE_SCHEMA,
            "description": "Flat list of all P&L nodes with parent_id references",
        },
    },
    "required": ["summary", "revenue_estimate", "ebitda_estimate", "nodes"],
    "additionalProperties": False,
}


def build_ebitda_tree_from_flat_nodes(flat_nodes: list[dict[str, Any]]) -> list[EbitdaNode]:
    """Reconstruct a nested EbitdaNode tree from a flat list with parent_id references.

    Groups nodes by parent_id, attaches children to parents, and returns the root nodes
    (those with parent_id=None). The frontend receives the same nested structure — no
    frontend changes needed.
    """
    # Build all nodes without children first
    nodes_by_id: dict[str, EbitdaNode] = {}
    for item in flat_nodes:
        nodes_by_id[item["id"]] = EbitdaNode(
            id=item["id"],
            label=item["label"],
            type=item["type"],
            value_range=item["value_range"],
            percentage_of_parent=item["percentage_of_parent"],
            description=item["description"],
        )

    # Attach children to parents
    roots: list[EbitdaNode] = []
    for item in flat_nodes:
        node = nodes_by_id[item["id"]]
        parent_id = item["parent_id"]
        if parent_id is None:
            roots.append(node)
        else:
            parent = nodes_by_id[parent_id]
            parent.children.append(node)

    return roots


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

OUTPUT FORMAT: Return nodes as a flat JSON array (no nested children objects). \
Use the parent_id field to express hierarchy — set it to the id of the parent \
node, or null for the 5 P&L section headers only (Revenue, COGS, Gross Profit, \
Operating Expenses, EBITDA).

IMPORTANT: Revenue sub-streams MUST have parent_id referencing the Revenue node. \
Individual cost items (e.g. cloud hosting, customer support) MUST have parent_id \
referencing COGS. Individual operating expense items (e.g. R&D, Sales & Marketing, \
G&A) MUST have parent_id referencing an Operating Expenses node. Only the 5 \
section headers should have parent_id: null.

Generate the EBITDA decomposition tree."""

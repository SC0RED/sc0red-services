"""Stage 5: AI EBITDA decomposition tree generation.

Generates a hierarchical P&L tree (Revenue → Costs → Gross Profit → OpEx → EBITDA)
with links back to opportunity indices showing where AI can impact the P&L.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, cast

from signalfield_core.models.enums import Precision, ReasoningEffort, Verbosity
from signalfield_core.pipeline.step import RequestStep

from src.models.model_company import EbitdaNode, EbitdaTreeResult
from src.pipeline.step_timer import StepTimer

if TYPE_CHECKING:
    from signalfield_core.services.ai_client_factory import AIClientFactory

    from src.facades.company_accessor import CompanyAccessor

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a senior financial analyst and business model strategist who specialises "
    "in decomposing company economics into P&L trees for private equity portfolio companies. "
    "You understand how AI opportunities map to specific revenue and cost line items.\n\n"
    "Your analysis is:\n"
    "- Structured: Build a clear top-down tree from Revenue → Gross Profit → EBITDA\n"
    "- Specific: Use industry-typical line items relevant to this company's business model\n"
    "- Actionable: Link AI opportunities to specific P&L nodes where they'd have impact\n"
    "- Realistic: Provide reasonable estimates based on company size and industry benchmarks\n\n"
    "Always respond with valid JSON only. No markdown, no explanation text outside the JSON."
)

_EBITDA_NODE_SCHEMA: dict = {
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
        "parent_id": {"type": ["string", "null"]},
        "description": {"type": "string"},
        "linked_opportunity_indices": {
            "type": "array",
            "items": {"type": "integer"},
            "description": "Indices of AI opportunities that impact this line item",
        },
        "children": {"type": "array", "items": {"$ref": "#/$defs/node"}},
    },
    "required": [
        "id",
        "label",
        "type",
        "value_range",
        "percentage_of_parent",
        "parent_id",
        "description",
        "linked_opportunity_indices",
        "children",
    ],
    "additionalProperties": False,
}

_EBITDA_TREE_SCHEMA: dict = {
    "type": "object",
    "$defs": {"node": _EBITDA_NODE_SCHEMA},
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


def _build_ebitda_node(data: dict) -> EbitdaNode:
    children = [_build_ebitda_node(child) for child in data["children"]]
    return EbitdaNode(
        id=data["id"],
        label=data["label"],
        type=data["type"],
        value_range=data.get("value_range"),
        percentage_of_parent=data.get("percentage_of_parent"),
        parent_id=data.get("parent_id"),
        description=data["description"],
        linked_opportunity_indices=data["linked_opportunity_indices"],
        children=children,
    )


def _build_ebitda_prompt(
    profile_dict: dict,
    assessment_dict: dict,
    opportunities_list: list[dict],
) -> str:
    opportunity_lines = "\n".join(
        f"[{i}] {opp.get('title', '')} ({opp.get('value_lever', 'N/A')})"
        f" - {opp.get('strategic_category', '')}"
        for i, opp in enumerate(opportunities_list)
    )

    return f"""Build an EBITDA decomposition tree for this company \
showing where AI opportunities would impact the P&L.

COMPANY PROFILE:
{json.dumps(profile_dict, indent=2)}

RISK ASSESSMENT:
Overall Score: {assessment_dict["overall_score"]}/10 \
({assessment_dict["tier"]} risk)
Summary: {assessment_dict["analysis_summary"]}

AI OPPORTUNITIES (indexed 0-{len(opportunities_list) - 1}):
{opportunity_lines}

Build a tree from Revenue down to EBITDA. The tree should \
reflect this company's actual business model and industry.

Tree structure guidelines:
- Start with total Revenue at the top
- Break revenue into 2-4 revenue streams specific to this company
- Show COGS / Cost of Revenue
- Show Gross Profit (subtotal)
- Show 3-5 key operating expense categories relevant to this business
- Show EBITDA (subtotal)
- For each node, indicate which AI opportunities (by index) could impact that line item

Generate the EBITDA decomposition tree."""


class GenerateEbitdaTree(RequestStep):
    """Generates an EBITDA decomposition tree linking AI opportunities to P&L line items."""

    def __init__(self, ai_client_factory: AIClientFactory | None = None) -> None:
        super().__init__()
        self._ai_client_factory = ai_client_factory

    def execute(self) -> None:
        """Generate EBITDA tree from company profile, risk assessment, and opportunities."""
        accessor = cast("CompanyAccessor", self.entity_accessor)
        company = accessor.company
        profile = company.profile
        risk_assessment = company.risk_assessment
        opportunity_result = company.opportunity_result

        if not profile or not risk_assessment or not opportunity_result:
            message = (
                "Cannot generate EBITDA tree: profile, risk assessment, or opportunities missing"
            )
            raise ValueError(message)

        opportunities_list = [opp.model_dump() for opp in opportunity_result.opportunities]
        user_prompt = _build_ebitda_prompt(
            profile.model_dump(),
            risk_assessment.model_dump(),
            opportunities_list,
        )

        if not self._ai_client_factory:
            message = "AI client factory not configured"
            raise RuntimeError(message)

        timer = StepTimer("GenerateEbitdaTree")

        client = self._ai_client_factory.get_client(
            verbosity=Verbosity.MEDIUM,
            reasoning_effort=ReasoningEffort.LOW,
            precision=Precision.STANDARD,
        )
        prompt = f"{_SYSTEM_PROMPT}\n\n{user_prompt}"
        logger.info(
            "[GenerateEbitdaTree] sending AI request: prompt_len=%d, model=%s",
            len(prompt),
            getattr(client, "model", "unknown"),
        )
        with timer.measure("ai_call"):
            try:
                response = client.query_structured(
                    input_text=prompt, json_schema=_EBITDA_TREE_SCHEMA
                )
            except Exception:
                logger.exception("[GenerateEbitdaTree] AI request failed")
                raise
        logger.info(
            "[GenerateEbitdaTree] AI response received: metadata=%s",
            response.metadata,
        )
        data = response.content

        nodes = [_build_ebitda_node(node) for node in data["nodes"]]
        result = EbitdaTreeResult(
            summary=data["summary"],
            revenue_estimate=data["revenue_estimate"],
            ebitda_estimate=data["ebitda_estimate"],
            nodes=nodes,
        )

        accessor.set_ebitda_tree(result)
        self.request_executor.add_details(timer.to_details())
        self.request_executor.mark_question_complete("generate_ebitda_tree")

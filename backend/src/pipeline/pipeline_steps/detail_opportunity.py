"""Opportunity detail enrichment constants — schema and prompt builder.

Each selected opportunity from the ideation phase gets a focused detail call
that adds implementation steps, timeline, investment, ROI, and services.
Runs at Level 3, after profile and risk assessment are available.
"""

from __future__ import annotations

import json
from typing import Any

from src.pipeline.pipeline_steps.generate_opportunities import OPPS_SYSTEM_PROMPT

DETAIL_SYSTEM_PROMPT = OPPS_SYSTEM_PROMPT

DETAIL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "implementation_steps": {
            "type": "array",
            "items": {"type": "string"},
            "description": "3-5 specific implementation steps",
        },
        "timeline": {
            "type": "string",
            "description": (
                "Quick Win (1-3 months)|Medium-term (3-9 months)|Long-term (9-18 months)"
            ),
        },
        "investment_range": {
            "type": "string",
            "description": "$50K-$100K|$100K-$500K|$500K-$1M|$1M+",
        },
        "roi_estimate": {
            "type": "string",
            "description": "Specific ROI description tied to this company",
        },
        "related_services": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 3,
            "description": (
                "Up to 3 relevant vendor or service names (e.g. 'Datadog - Observability')"
            ),
        },
    },
    "required": [
        "implementation_steps",
        "timeline",
        "investment_range",
        "roi_estimate",
        "related_services",
    ],
    "additionalProperties": False,
}


def build_detail_prompt(
    profile_dict: dict[str, Any],
    assessment_dict: dict[str, Any],
    opportunity_title: str,
    opportunity_description: str,
) -> str:
    """Build prompt to detail a single opportunity with implementation specifics."""
    risk_scores_json = json.dumps(assessment_dict["risk_scores"])
    top_risks = ", ".join(assessment_dict["top_risks"])

    return f"""Provide detailed implementation specifics for the following AI opportunity.

COMPANY PROFILE:
{json.dumps(profile_dict)}

RISK ASSESSMENT:
Overall Score: {assessment_dict["overall_score"]}/10 ({assessment_dict["tier"]} risk)
Top Risks: {top_risks}
Risk Summary: {assessment_dict["analysis_summary"]}

DETAILED RISK SCORES:
{risk_scores_json}

OPPORTUNITY TO DETAIL:
Title: {opportunity_title}
Description: {opportunity_description}

Provide:
- 3-5 implementation steps specific to THIS company
- Realistic timeline (Quick Win 1-3 months, Medium-term 3-9 months, or Long-term 9-18 months)
- Investment range appropriate for this company size
- Specific ROI estimate grounded in the company's industry and scale
- Up to 3 relevant vendor or service recommendations \
as simple strings (e.g. "Datadog - Observability")"""

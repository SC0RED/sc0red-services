"""Stage 2: 8-category AI risk scoring.

Ports buildRiskPrompt from pe-scan/src/lib/ai/prompts.ts:68-108.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, cast

from signalfield_core.models.enums import Precision, ReasoningEffort, Verbosity
from signalfield_core.pipeline.step import RequestStep

from src.models.model_company import RiskAssessment, RiskScore

if TYPE_CHECKING:
    from signalfield_core.services.ai_client_factory import AIClientFactory

    from src.facades.company_accessor import CompanyAccessor
from src.models.model_literals import RISK_SCOPE_DISPLAY

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
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
    "9-10: Critical/existential risk, business model fundamentally threatened\n\n"
    "Always respond with valid JSON only. No markdown, no explanation text outside the JSON."
)

_RISK_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "risk_scores": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "Risk category ID"},
                    "score": {"type": "number", "description": "Risk score 1-10"},
                    "explanation": {
                        "type": "string",
                        "description": "2-3 sentences explaining this specific score",
                    },
                    "evidence": {
                        "type": "string",
                        "description": "Specific signals supporting this assessment",
                    },
                },
                "required": ["category", "score", "explanation", "evidence"],
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


def _build_risk_prompt(profile_dict: dict) -> str:
    categories = "\n".join(
        f"- {scope_id}: {info['name']} — {info['description']}"
        for scope_id, info in RISK_SCOPE_DISPLAY.items()
    )

    industry_sector = profile_dict.get("industry_sector", "")

    return f"""Perform a comprehensive AI disruption risk assessment for this company.

COMPANY PROFILE:
{json.dumps(profile_dict, indent=2)}

RISK CATEGORIES TO ASSESS:
{categories}

INDUSTRY CONTEXT: The company operates in "{industry_sector}". Apply industry-specific weighting:
- If Financial Services: Weight regulatory_compliance and competitive_displacement higher
- If Healthcare: Weight regulatory_compliance and data_ip higher
- If Manufacturing: Weight supply_chain and talent_workforce higher
- If Technology/SaaS: Weight technology_obsolescence and competitive_displacement higher
- If Professional Services: Weight talent_workforce and technology_obsolescence higher
- If Retail/Consumer: Weight customer_behavior and margin_compression higher

For each risk category, consider:
1. What specific AI technologies are threatening this company's position?
2. Who are the AI-native competitors entering this space?
3. What is the timeline of disruption risk?
4. Are there any moats protecting against this risk?

Assess all risk categories and provide the overall analysis."""


class AssessRisk(RequestStep):
    """Runs 8-category AI risk assessment on the company profile."""

    def __init__(self, ai_client_factory: AIClientFactory | None = None) -> None:
        super().__init__()
        self._ai_client_factory = ai_client_factory

    def execute(self) -> None:
        """Run the 8-category AI risk assessment and store results on the accessor."""
        accessor = cast("CompanyAccessor", self.entity_accessor)
        profile = accessor.company.profile
        if not profile:
            message = "Cannot assess risk: no company profile available"
            raise ValueError(message)

        user_prompt = _build_risk_prompt(profile.model_dump())

        if not self._ai_client_factory:
            message = "AI client factory not configured"
            raise RuntimeError(message)

        client = self._ai_client_factory.get_client(
            verbosity=Verbosity.MEDIUM,
            reasoning_effort=ReasoningEffort.MEDIUM,
            precision=Precision.STANDARD,
        )
        prompt = f"{_SYSTEM_PROMPT}\n\n{user_prompt}"
        logger.info(
            "[AssessRisk] sending AI request: prompt_len=%d, model=%s",
            len(prompt),
            getattr(client, "model", "unknown"),
        )
        try:
            response = client.query_structured(input_text=prompt, json_schema=_RISK_SCHEMA)
        except Exception:
            logger.exception("[AssessRisk] AI request failed")
            raise
        logger.info(
            "[AssessRisk] AI response: input_tokens=%d, output_tokens=%d",
            response.input_tokens,
            response.output_tokens,
        )
        data = response.content

        risk_scores = [RiskScore(**rs) for rs in data.get("risk_scores", [])]
        if not risk_scores:
            message = "Risk assessment returned no risk scores"
            raise ValueError(message)

        assessment = RiskAssessment(
            risk_scores=risk_scores,
            overall_score=data["overall_score"],
            tier=data["tier"],
            top_risks=data["top_risks"],
            analysis_summary=data["analysis_summary"],
        )

        accessor.set_risk_assessment(assessment)
        self.request_executor.mark_question_complete("assess_risk")

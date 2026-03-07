"""Stage 3: AI opportunity generation.

Ports buildOpportunityPrompt from pe-scan/src/lib/ai/prompts.ts:110-176.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, cast

from signalfield_core.models.enums import Precision, ReasoningEffort, Verbosity
from signalfield_core.pipeline.step import RequestStep

from src.models.model_company import Opportunity, OpportunityResult, RelatedService, Vendor

if TYPE_CHECKING:
    from signalfield_core.services.ai_client_factory import AIClientFactory

    from src.facades.company_accessor import CompanyAccessor

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a senior management consultant and AI transformation advisor who specializes "
    "in helping private equity portfolio companies capture AI opportunities and defend "
    "against disruption. You combine strategic thinking with practical implementation expertise.\n\n"
    "Your recommendations are:\n"
    "- Specific and actionable: Real implementation steps, not vague suggestions\n"
    "- Industry-appropriate: Tailored to what's actually feasible in this sector\n"
    "- Commercial: Focused on ROI, competitive advantage, and revenue impact\n"
    "- Resourced: Include realistic investment ranges and timeline estimates\n\n"
    "For vendor recommendations, suggest real companies that specialize in each service area.\n\n"
    "Always respond with valid JSON only. No markdown, no explanation text outside the JSON."
)

_OPPORTUNITY_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "opportunities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Specific, action-oriented title"},
                    "risk_mitigated": {
                        "type": "string",
                        "description": "Category ID this primarily addresses",
                    },
                    "impact_rating": {"type": "string", "enum": ["High", "Medium", "Low"]},
                    "strategic_category": {
                        "type": "string",
                        "description": "One of: Competitive Moat, Revenue Capture, Market Expansion, Operational Efficiency, Talent Strategy",
                    },
                    "description": {
                        "type": "string",
                        "description": "2-3 paragraph detailed description",
                    },
                    "implementation_steps": {"type": "array", "items": {"type": "string"}},
                    "timeline": {
                        "type": "string",
                        "description": "Quick Win (1-3 months)|Medium-term (3-9 months)|Long-term (9-18 months)",
                    },
                    "investment_range": {
                        "type": "string",
                        "description": "$50K-$100K|$100K-$500K|$500K-$1M|$1M+",
                    },
                    "roi_estimate": {"type": "string", "description": "Specific ROI description"},
                    "related_services": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "service_type": {"type": "string"},
                                "vendors": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "name": {"type": "string"},
                                            "url": {"type": "string"},
                                            "specialty": {"type": "string"},
                                        },
                                        "required": ["name", "url", "specialty"],
                                    },
                                },
                            },
                            "required": ["service_type", "vendors"],
                        },
                    },
                },
                "required": [
                    "title",
                    "risk_mitigated",
                    "impact_rating",
                    "strategic_category",
                    "description",
                    "implementation_steps",
                    "timeline",
                    "investment_range",
                    "roi_estimate",
                    "related_services",
                ],
            },
        },
        "top_three_immediate_actions": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Top 3 immediate actions doable in 30 days",
        },
    },
    "required": ["opportunities", "top_three_immediate_actions"],
}


def _build_opportunity_prompt(profile_dict: dict, assessment_dict: dict) -> str:
    risk_scores_json = json.dumps(assessment_dict.get("risk_scores", []), indent=2)
    top_risks = ", ".join(assessment_dict.get("top_risks", []))

    return f"""Generate specific, tactical AI opportunity recommendations for this company based on their risk profile.

COMPANY PROFILE:
{json.dumps(profile_dict, indent=2)}

RISK ASSESSMENT:
Overall Score: {assessment_dict.get("overall_score", 0)}/10 ({assessment_dict.get("tier", "low")} risk)
Top Risks: {top_risks}
Risk Summary: {assessment_dict.get("analysis_summary", "")}

DETAILED RISK SCORES:
{risk_scores_json}

Generate 4-6 high-priority opportunities. For each opportunity:
- Focus on the highest-scoring risks first
- Make implementation steps genuinely specific to THIS company
- Use real vendor/partner names (not generic descriptions)
- ROI estimates should be realistic for company size and industry
- Timeline should account for typical implementation complexity

Strategic categories to use:
- "Competitive Moat" - Strengthen defensibility (data flywheels, switching costs, network effects)
- "Revenue Capture" - New AI-powered products/services to sell
- "Market Expansion" - Enter adjacent markets enabled by AI
- "Operational Efficiency" - Internal AI to cut costs and improve margins
- "Talent Strategy" - Workforce transformation, AI hiring, upskilling

Generate the opportunities and top three immediate actions."""


class GenerateOpportunities(RequestStep):
    """Generates AI opportunity recommendations based on risk profile."""

    def __init__(self, ai_client_factory: AIClientFactory | None = None) -> None:
        super().__init__()
        self._ai_client_factory = ai_client_factory

    def execute(self) -> None:
        """Generate AI opportunity recommendations from the company risk profile."""
        accessor = cast("CompanyAccessor", self.entity_accessor)
        profile = accessor.company.profile
        risk_assessment = accessor.company.risk_assessment

        if not profile or not risk_assessment:
            message = "Cannot generate opportunities: profile or risk assessment missing"
            raise ValueError(message)

        user_prompt = _build_opportunity_prompt(profile.model_dump(), risk_assessment.model_dump())

        if not self._ai_client_factory:
            message = "AI client factory not configured"
            raise RuntimeError(message)

        client = self._ai_client_factory.get_client(
            verbosity=Verbosity.HIGH,
            reasoning_effort=ReasoningEffort.MEDIUM,
            precision=Precision.STANDARD,
        )
        prompt = f"{_SYSTEM_PROMPT}\n\n{user_prompt}"
        response = client.query_structured(input_text=prompt, json_schema=_OPPORTUNITY_SCHEMA)
        data = response.content

        opportunities = []
        for opp_data in data.get("opportunities", []):
            related_services = []
            for svc in opp_data.get("related_services", []):
                vendors = [Vendor(**v) for v in svc.get("vendors", [])]
                related_services.append(
                    RelatedService(service_type=svc.get("service_type", ""), vendors=vendors)
                )
            opp_data["related_services"] = related_services
            opportunities.append(Opportunity(**opp_data))

        result = OpportunityResult(
            opportunities=opportunities,
            top_three_immediate_actions=data.get("top_three_immediate_actions", []),
        )

        accessor.set_opportunities(result)
        self.request_executor.mark_question_complete("generate_opportunities")

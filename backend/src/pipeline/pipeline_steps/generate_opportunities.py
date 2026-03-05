"""Stage 3: AI opportunity generation.

Ports buildOpportunityPrompt from pe-scan/src/lib/ai/prompts.ts:110-176.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, cast

import openai
from signalfield_core.pipeline.step import RequestStep

from src.models.model_company import Opportunity, OpportunityResult, RelatedService, Vendor

if TYPE_CHECKING:
    from src.facades.company_accessor import CompanyAccessor
from src.utilities.json_utils import parse_json_response

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

Respond with this exact JSON:
{{
  "opportunities": [
    {{
      "title": "Specific, action-oriented title (e.g. 'Deploy AI-Powered Customer Churn Prediction')",
      "risk_mitigated": "category_id this primarily addresses",
      "impact_rating": "High|Medium|Low",
      "strategic_category": "one of the 5 categories above",
      "description": "2-3 paragraph detailed description",
      "implementation_steps": [
        "Step 1: Specific action with concrete details",
        "Step 2: ...",
        "Step 3: ...",
        "Step 4: ...",
        "Step 5: ..."
      ],
      "timeline": "Quick Win (1-3 months)|Medium-term (3-9 months)|Long-term (9-18 months)",
      "investment_range": "$50K-$100K|$100K-$500K|$500K-$1M|$1M+",
      "roi_estimate": "Specific ROI description",
      "related_services": [
        {{
          "service_type": "e.g. AI Strategy Consulting",
          "vendors": [
            {{
              "name": "Company name",
              "url": "https://...",
              "specialty": "What specifically they do"
            }}
          ]
        }}
      ]
    }}
  ],
  "top_three_immediate_actions": [
    "Action 1 - very specific, doable in 30 days",
    "Action 2",
    "Action 3"
  ]
}}"""


class GenerateOpportunities(RequestStep):
    """Generates AI opportunity recommendations based on risk profile."""

    def __init__(self, openai_api_key: str = "", model: str = "gpt-4o") -> None:
        super().__init__()
        self._openai_api_key = openai_api_key
        self._model = model

    def execute(self) -> None:
        """Generate AI opportunity recommendations from the company risk profile."""
        accessor = cast("CompanyAccessor", self.entity_accessor)
        profile = accessor.company.profile
        risk_assessment = accessor.company.risk_assessment

        if not profile or not risk_assessment:
            message = "Cannot generate opportunities: profile or risk assessment missing"
            raise ValueError(message)

        user_prompt = _build_opportunity_prompt(profile.model_dump(), risk_assessment.model_dump())

        client = openai.OpenAI(api_key=self._openai_api_key)
        response = client.chat.completions.create(
            model=self._model,
            temperature=0.3,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )

        content = response.choices[0].message.content or ""
        data = parse_json_response(content)

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

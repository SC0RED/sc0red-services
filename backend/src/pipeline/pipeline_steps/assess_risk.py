"""Stage 2: 8-category AI risk scoring.

Ports buildRiskPrompt from pe-scan/src/lib/ai/prompts.ts:68-108.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

import openai
from signalfield_core.pipeline.step import RequestStep

from src.models.model_company import RiskAssessment, RiskScore

if TYPE_CHECKING:
    from src.facades.company_accessor import CompanyAccessor
from src.models.model_literals import RISK_SCOPE_DISPLAY
from src.utilities.json_utils import parse_json_response

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

Respond with this exact JSON:
{{
  "risk_scores": [
    {{
      "category": "category_id_from_list",
      "score": 1-10,
      "explanation": "2-3 sentences explaining this specific score for this specific company",
      "evidence": "Specific signals, competitor names, or industry trends supporting this assessment"
    }}
  ],
  "overall_score": number,
  "tier": "low|moderate|high|critical",
  "top_risks": ["top 3 most critical risk category IDs"],
  "analysis_summary": "3-4 sentence executive summary of the overall AI risk picture for this company"
}}"""


class AssessRisk(RequestStep):
    """Runs 8-category AI risk assessment on the company profile."""

    def __init__(self, openai_api_key: str = "", model: str = "gpt-4o") -> None:
        super().__init__()
        self._openai_api_key = openai_api_key
        self._model = model

    def execute(self) -> None:
        """Run the 8-category AI risk assessment and store results on the accessor."""
        accessor: CompanyAccessor = self.entity_accessor  # type: ignore[assignment]
        profile = accessor.company.profile
        if not profile:
            msg = "Cannot assess risk: no company profile available"
            raise ValueError(msg)

        user_prompt = _build_risk_prompt(profile.model_dump())

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

        risk_scores = [RiskScore(**rs) for rs in data.get("risk_scores", [])]
        if not risk_scores:
            msg = "Risk assessment returned no risk scores"
            raise ValueError(msg)

        assessment = RiskAssessment(
            risk_scores=risk_scores,
            overall_score=data.get("overall_score", 0),
            tier=data.get("tier", "low"),
            top_risks=data.get("top_risks", []),
            analysis_summary=data.get("analysis_summary", ""),
        )

        accessor.set_risk_assessment(assessment)
        self.request_executor.mark_question_complete("assess_risk")

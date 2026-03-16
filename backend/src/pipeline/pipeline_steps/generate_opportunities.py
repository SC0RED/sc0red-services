"""Stage 3: AI opportunity generation.

Ports buildOpportunityPrompt from pe-scan/src/lib/ai/prompts.ts:110-176.
Runs two parallel AI calls — one for high-priority risks, one for strategic risks —
then merges the results.
"""

from __future__ import annotations

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING, Any, cast

from signalfield_core.models.enums import Precision, ReasoningEffort, Verbosity
from signalfield_core.pipeline.step import RequestStep

from src.models.model_company import Opportunity, OpportunityResult
from src.models.model_literals import RISK_SCOPE_NAMES
from src.pipeline.step_timer import StepTimer

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
    "For vendor recommendations, suggest real companies that specialize in each service area."
)

_STRATEGIC_CATEGORIES_INSTRUCTIONS = """Strategic categories to use:
- "Competitive Moat" - Strengthen defensibility (data flywheels, switching costs, network effects)
- "Revenue Capture" - New AI-powered products/services to sell
- "Market Expansion" - Enter adjacent markets enabled by AI
- "Operational Efficiency" - Internal AI to cut costs and improve margins
- "Talent Strategy" - Workforce transformation, AI hiring, upskilling"""

_OPPORTUNITY_ITEM_SCHEMA: dict[str, Any] = {
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
            "description": "2-3 sentence description",
        },
        "implementation_steps": {
            "type": "array",
            "items": {"type": "string"},
            "description": "3-5 specific implementation steps",
        },
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
            "items": {"type": "string"},
            "description": "Relevant vendor or service names (e.g. 'Datadog - Observability', 'Snowflake - Data Platform')",
        },
        "value_lever": {
            "type": "string",
            "enum": ["Revenue Side", "Cost Side", "Both"],
            "description": "Whether this opportunity primarily drives revenue growth, reduces costs, or both",
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
        "value_lever",
    ],
    "additionalProperties": False,
}

_HIGH_PRIORITY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "opportunities": {"type": "array", "items": _OPPORTUNITY_ITEM_SCHEMA},
        "top_three_immediate_actions": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Top 3 immediate actions doable in 30 days",
        },
    },
    "required": ["opportunities", "top_three_immediate_actions"],
    "additionalProperties": False,
}

_STRATEGIC_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "opportunities": {"type": "array", "items": _OPPORTUNITY_ITEM_SCHEMA},
    },
    "required": ["opportunities"],
    "additionalProperties": False,
}


def _build_opportunity(data: dict[str, Any]) -> Opportunity:
    return Opportunity(**data)


def _build_context_block(profile_dict: dict[str, Any], assessment_dict: dict[str, Any]) -> str:
    """Build the shared company/risk context included in both prompts."""
    risk_scores_json = json.dumps(assessment_dict["risk_scores"])
    top_risks = ", ".join(assessment_dict["top_risks"])

    return f"""COMPANY PROFILE:
{json.dumps(profile_dict)}

RISK ASSESSMENT:
Overall Score: {assessment_dict["overall_score"]}/10 ({assessment_dict["tier"]} risk)
Top Risks: {top_risks}
Risk Summary: {assessment_dict["analysis_summary"]}

DETAILED RISK SCORES:
{risk_scores_json}"""


def _build_high_priority_prompt(
    profile_dict: dict[str, Any],
    assessment_dict: dict[str, Any],
    focus_categories: list[str],
) -> str:
    context = _build_context_block(profile_dict, assessment_dict)
    categories_list = ", ".join(focus_categories)

    return f"""Generate specific, tactical AI opportunity recommendations for this company, focusing on the highest-priority risks.

{context}

TARGET RISK CATEGORIES (highest priority): {categories_list}

Generate 2-3 high-priority opportunities targeting the risk categories listed above. For each opportunity:
- Make implementation steps specific to THIS company (3-5 steps)
- Keep descriptions concise (2-3 sentences)
- ROI estimates should be realistic for company size and industry
- For related_services, list relevant vendors as simple strings (e.g. "Datadog - Observability")
- Classify each opportunity's value_lever: "Revenue Side" (drives top-line growth, new revenue streams, pricing optimization, market expansion), "Cost Side" (reduces operating expenses, automation, efficiency gains), or "Both" (impacts revenue and cost simultaneously)

{_STRATEGIC_CATEGORIES_INSTRUCTIONS}

Also provide top_three_immediate_actions: the 3 most impactful actions this company can start within 30 days."""


def _build_strategic_prompt(
    profile_dict: dict[str, Any],
    assessment_dict: dict[str, Any],
    focus_categories: list[str],
) -> str:
    context = _build_context_block(profile_dict, assessment_dict)
    categories_list = ", ".join(focus_categories)

    return f"""Generate specific, tactical AI opportunity recommendations for this company, focusing on strategic risk categories.

{context}

TARGET RISK CATEGORIES (strategic): {categories_list}

Generate 1-2 strategic opportunities targeting the risk categories listed above. For each opportunity:
- Make implementation steps specific to THIS company (3-5 steps)
- Keep descriptions concise (2-3 sentences)
- ROI estimates should be realistic for company size and industry
- For related_services, list relevant vendors as simple strings (e.g. "Datadog - Observability")
- Classify each opportunity's value_lever: "Revenue Side" (drives top-line growth, new revenue streams, pricing optimization, market expansion), "Cost Side" (reduces operating expenses, automation, efficiency gains), or "Both" (impacts revenue and cost simultaneously)

{_STRATEGIC_CATEGORIES_INSTRUCTIONS}

Generate the opportunities. Do NOT include top_three_immediate_actions."""


class GenerateOpportunities(RequestStep):
    """Generates AI opportunity recommendations based on risk profile.

    Runs two parallel AI calls — one for high-priority risk categories and one for
    remaining strategic categories — then merges results.
    """

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

        if not self._ai_client_factory:
            message = "AI client factory not configured"
            raise RuntimeError(message)

        profile_dict = profile.model_dump()
        assessment_dict = risk_assessment.model_dump()

        top_risk_categories = risk_assessment.top_risks[:3]
        other_categories = [
            category for category in RISK_SCOPE_NAMES if category not in top_risk_categories
        ]

        timer = StepTimer("GenerateOpportunities")

        high_priority_prompt = _build_high_priority_prompt(
            profile_dict, assessment_dict, top_risk_categories
        )
        strategic_prompt = _build_strategic_prompt(profile_dict, assessment_dict, other_categories)

        with ThreadPoolExecutor(max_workers=2) as pool:
            future_high = pool.submit(
                self._run_ai_call,
                high_priority_prompt,
                _HIGH_PRIORITY_SCHEMA,
                "high_priority",
            )
            future_strategic = pool.submit(
                self._run_ai_call,
                strategic_prompt,
                _STRATEGIC_SCHEMA,
                "strategic",
            )

            results: dict[str, tuple[dict[str, Any], float]] = {}
            for future in as_completed([future_high, future_strategic]):
                label, data, elapsed = future.result()
                results[label] = (data, elapsed)

        high_priority_data, high_elapsed = results["high_priority"]
        strategic_data, strategic_elapsed = results["strategic"]

        timer.record("ai_call_high_priority", high_elapsed)
        timer.record("ai_call_strategic", strategic_elapsed)

        all_opportunities = [
            _build_opportunity(opp)
            for opp in high_priority_data["opportunities"] + strategic_data["opportunities"]
        ]
        top_actions = high_priority_data["top_three_immediate_actions"]

        result = OpportunityResult(
            opportunities=all_opportunities,
            top_three_immediate_actions=top_actions,
        )

        accessor.set_opportunities(result)
        self.request_executor.add_details(timer.to_details())
        self.request_executor.mark_question_complete("generate_opportunities")

    def _run_ai_call(
        self,
        user_prompt: str,
        schema: dict[str, Any],
        label: str,
    ) -> tuple[str, dict[str, Any], float]:
        """Execute a single AI call and return (label, response_data, elapsed_seconds)."""
        # _ai_client_factory is validated non-None in execute() before threads are spawned
        client = self._ai_client_factory.get_client(
            verbosity=Verbosity.MEDIUM,
            reasoning_effort=ReasoningEffort.LOW,
            precision=Precision.STANDARD,
            instructions=_SYSTEM_PROMPT,
        )
        logger.info(
            "[GenerateOpportunities:%s] sending AI request: prompt_len=%d, model=%s",
            label,
            len(user_prompt),
            getattr(client, "model", "unknown"),
        )
        start = time.monotonic()
        try:
            response = client.query_structured(input_text=user_prompt, json_schema=schema)
        except Exception:
            logger.exception("[GenerateOpportunities:%s] AI request failed", label)
            raise
        elapsed = time.monotonic() - start
        logger.info(
            "[GenerateOpportunities:%s] AI response received in %.2fs: metadata=%s",
            label,
            elapsed,
            response.metadata,
        )
        return label, response.content, elapsed

"""Pipeline step: enrich ranked ideations with implementation details via parallel AI calls.

Takes the ranked ideations from Level 1 and runs N parallel AI calls
(one per ideation) to add implementation steps, timeline, investment
range, and ROI estimate.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, cast

from signalfield_core.pipeline.step import RequestStep
from signalfield_core.utilities.future_manager import FutureManager

from src.models.model_company import OpportunityResult
from src.pipeline.pipeline_steps.ai_call import run_structured_ai_call
from src.pipeline.pipeline_steps.detail_opportunity import (
    DETAIL_SCHEMA,
    DETAIL_SYSTEM_PROMPT,
    build_detail_prompt,
    sanitize_implementation_steps,
)
from src.pipeline.pipeline_steps.generate_opportunities import build_opportunity
from src.pipeline.step_timer import StepTimer

if TYPE_CHECKING:
    from signalfield_core.services.ai_client_factory import AIClientFactory

    from src.facades.company_accessor import CompanyAccessor
    from src.pipeline.pipeline_steps.ai_call import TokenCounts

logger = logging.getLogger(__name__)


class DetailOpportunities(RequestStep):
    """Enrich ranked ideations with implementation details via parallel AI calls.

    Takes ranked ideations from Level 1 and runs N detail calls (one per ideation)
    in parallel. Merges ideation + detail into full Opportunity objects.
    """

    def __init__(self, ai_client_factory: AIClientFactory | None = None) -> None:
        super().__init__()
        self._ai_client_factory = ai_client_factory

    def execute(self) -> None:
        """Run opportunity detail calls in parallel."""
        accessor = cast("CompanyAccessor", self.entity_accessor)
        profile = accessor.company.profile
        risk_assessment = accessor.company.risk_assessment

        if not profile or not risk_assessment:
            message = "Cannot detail opportunities: profile or risk assessment missing"
            raise ValueError(message)

        if not self._ai_client_factory:
            message = "AI client factory not configured"
            raise RuntimeError(message)

        profile_dict = profile.model_dump()

        ranked_ideations = accessor.get_ranked_ideations()
        if not ranked_ideations:
            message = "No ranked ideations available for detail phase"
            raise ValueError(message)

        top_actions = ranked_ideations[0]["top_three_immediate_actions"]

        # Build detail prompts (one per ranked ideation)
        detail_prompts: list[tuple[str, str, dict[str, Any]]] = []
        for i, ideation in enumerate(ranked_ideations):
            prompt = build_detail_prompt(
                profile_dict=profile_dict,
                opportunity_title=str(ideation["title"]),
                opportunity_description=str(ideation["description"]),
            )
            detail_prompts.append((f"detail_{i}", prompt, ideation))
            logger.info(
                "[DetailOpportunities:detail_%d] system_prompt:\n%s",
                i,
                DETAIL_SYSTEM_PROMPT,
            )

        timer = StepTimer("DetailOpportunities")

        with FutureManager(name="DetailOpportunities", max_workers=len(detail_prompts)) as manager:
            for label, prompt, _ideation in detail_prompts:
                manager.submit_task(
                    self._run_ai_call,
                    prompt,
                    DETAIL_SCHEMA,
                    DETAIL_SYSTEM_PROMPT,
                    label,
                )
            all_results = manager.wait_for_all_and_collect_results()

        # Drop the per-call ``TokenCounts`` (4th tuple element from
        # run_structured_ai_call as of 2026-05-15) — DetailOpportunities
        # doesn't surface token telemetry yet. Opt-in by calling
        # timer.record_tokens(...) here if/when that becomes desired.
        results: dict[str, tuple[dict[str, Any], float]] = {}
        for label, data, elapsed, _tokens in all_results:
            results[label] = (data, elapsed)

        all_opportunities = []
        for i, (_label, _prompt, ideation) in enumerate(detail_prompts):
            detail_data, detail_elapsed = results[f"detail_{i}"]
            # Phase-14 telemetry — dump the two numeric axes for the
            # ROI x Investment matrix so we can see how often the AI
            # emits null vs a real number. Lives behind the request-id
            # filter in CloudWatch; remove once we have enough
            # production signal to tune the prompt.
            logger.info(
                "[DetailOpportunities:detail_%d] numeric axes: "
                "investment_value_usd=%s roi_estimate_pct=%s",
                i,
                detail_data.get("investment_value_usd"),
                detail_data.get("roi_estimate_pct"),
            )
            timer.record(f"ai_call_detail_{i}", detail_elapsed)

            merged = {
                "title": ideation["title"],
                "description": ideation["description"],
                "value_lever": ideation["value_lever"],
                "strategic_category": ideation["strategic_category"],
                "impact_rating": ideation["impact_rating"],
                **detail_data,
                # Strip any leaked field-name/value tokens the model appended to
                # the steps array (override must follow ``**detail_data``).
                "implementation_steps": sanitize_implementation_steps(detail_data),
            }
            all_opportunities.append(build_opportunity(merged))

        opportunity_result = OpportunityResult(
            opportunities=all_opportunities,
            top_three_immediate_actions=top_actions,
        )
        accessor.set_opportunities(opportunity_result)

        self.request_executor.add_details(timer.to_details())
        self.request_executor.mark_question_complete("generate_opportunities")

    def _run_ai_call(
        self,
        user_prompt: str,
        schema: dict[str, Any],
        system_prompt: str,
        label: str,
    ) -> tuple[str, dict[str, Any], float, TokenCounts]:
        """Execute a single AI call via the shared run_structured_ai_call.

        Uses the default ``Precision.STANDARD`` (gpt-5.4-mini). The sc0red Services
        2026-05-15 benchmark initially flagged mini for compressing the
        ROI estimate ~4x (1167 → 278 chars), but a re-read showed mini's
        output is structurally complete (lever + financial impact +
        payback period + driving action). The verbose gpt-5.1 ROI adds
        supporting math (COGS breakdown, 3-yr cumulative, valuation at
        EBITDA multiple) that PE diligence users can re-derive themselves
        and that doesn't justify the recurring 3-minute tail-latency
        spikes gpt-5.1 hits on this call site (e.g., ``detail_3`` ran
        201s in production on 2026-05-15). If real PE users surface
        quality complaints post-deploy, re-pin to ``Precision.ADVANCED``
        — one-line revert; token telemetry monitors the impact.
        """
        return run_structured_ai_call(
            ai_client_factory=self._ai_client_factory,
            user_prompt=user_prompt,
            schema=schema,
            system_prompt=system_prompt,
            label=label,
            step_name="DetailOpportunities",
        )

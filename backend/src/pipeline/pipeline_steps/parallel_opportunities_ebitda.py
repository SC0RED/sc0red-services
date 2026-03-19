"""Composite step: runs opportunity detail enrichment and programmatic EBITDA tree.

Takes the ranked ideations from Level 1 and enriches each with implementation
details via focused AI calls. EBITDA tree is built programmatically from the
company profile using industry templates — no AI call required.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any, cast

from signalfield_core.models.enums import Precision, ReasoningEffort, Verbosity
from signalfield_core.pipeline.step import RequestStep
from signalfield_core.utilities.future_manager import FutureManager

from src.models.model_company import OpportunityResult
from src.pipeline.pipeline_steps.build_ebitda_tree import build_programmatic_ebitda_tree
from src.pipeline.pipeline_steps.detail_opportunity import (
    DETAIL_SCHEMA,
    DETAIL_SYSTEM_PROMPT,
    build_detail_prompt,
)
from src.pipeline.pipeline_steps.generate_opportunities import build_opportunity
from src.pipeline.step_timer import StepTimer

if TYPE_CHECKING:
    from signalfield_core.services.ai_client_factory import AIClientFactory

    from src.facades.company_accessor import CompanyAccessor
    from src.models.model_company import EbitdaNode, Opportunity

logger = logging.getLogger(__name__)


def link_opportunities_to_ebitda_nodes(
    opportunities: list[Opportunity],
    nodes: list[EbitdaNode],
) -> None:
    """Programmatically link opportunities to EBITDA nodes based on value_lever.

    Revenue Side opportunities → revenue nodes
    Cost Side opportunities → cost nodes
    Both → revenue and cost nodes
    """
    revenue_indices: list[int] = []
    cost_indices: list[int] = []

    for i, opportunity in enumerate(opportunities):
        if opportunity.value_lever in ("Revenue Side", "Both"):
            revenue_indices.append(i)
        if opportunity.value_lever in ("Cost Side", "Both"):
            cost_indices.append(i)

    def _link_node(node: EbitdaNode) -> None:
        if node.type == "revenue":
            node.linked_opportunity_indices = list(revenue_indices)
        elif node.type == "cost":
            node.linked_opportunity_indices = list(cost_indices)
        elif node.type in ("subtotal", "margin"):
            node.linked_opportunity_indices = sorted(set(revenue_indices + cost_indices))
        for child in node.children:
            _link_node(child)

    for node in nodes:
        _link_node(node)


class ParallelOpportunityDetailsAndEbitda(RequestStep):
    """Runs opportunity detail enrichment and builds EBITDA tree programmatically.

    Takes ranked ideations from Level 1 and runs N detail calls (one per ideation)
    in parallel. EBITDA tree is built deterministically from company profile.
    """

    def __init__(self, ai_client_factory: AIClientFactory | None = None) -> None:
        super().__init__()
        self._ai_client_factory = ai_client_factory

    def execute(self) -> None:
        """Run opportunity detail calls and build programmatic EBITDA tree."""
        accessor = cast("CompanyAccessor", self.entity_accessor)
        profile = accessor.company.profile
        risk_assessment = accessor.company.risk_assessment

        if not profile or not risk_assessment:
            message = (
                "Cannot generate opportunities and EBITDA tree: profile or risk assessment missing"
            )
            raise ValueError(message)

        if not self._ai_client_factory:
            message = "AI client factory not configured"
            raise RuntimeError(message)

        profile_dict = profile.model_dump()
        assessment_dict = risk_assessment.model_dump()

        # Get ranked ideations from Level 1
        ranked_ideations = accessor.get_ranked_ideations()
        if not ranked_ideations:
            message = "No ranked ideations available for detail phase"
            raise ValueError(message)

        # Extract top_three_immediate_actions (stored on each ideation by Level 1)
        top_actions = ranked_ideations[0]["top_three_immediate_actions"]

        # Build detail prompts (one per ranked ideation)
        detail_prompts: list[tuple[str, str, dict[str, Any]]] = []  # (label, prompt, ideation)
        for i, ideation in enumerate(ranked_ideations):
            prompt = build_detail_prompt(
                profile_dict=profile_dict,
                assessment_dict=assessment_dict,
                opportunity_title=str(ideation["title"]),
                opportunity_description=str(ideation["description"]),
            )
            detail_prompts.append((f"detail_{i}", prompt, ideation))

        timer = StepTimer("ParallelOpportunityDetailsAndEbitda")

        # Build EBITDA tree programmatically (no AI call — deterministic)
        ebitda_start = time.monotonic()
        ebitda_result = build_programmatic_ebitda_tree(profile)
        timer.record("build_ebitda_tree", time.monotonic() - ebitda_start)

        # Run detail AI calls in parallel
        with FutureManager(
            name="ParallelOpportunityDetailsAndEbitda", max_workers=len(detail_prompts)
        ) as manager:
            for label, prompt, _ideation in detail_prompts:
                manager.submit_task(
                    self._run_ai_call,
                    prompt,
                    DETAIL_SCHEMA,
                    DETAIL_SYSTEM_PROMPT,
                    label,
                )
            all_results = manager.wait_for_all_and_collect_results()

        results: dict[str, tuple[dict[str, Any], float]] = {}
        for label, data, elapsed in all_results:
            results[label] = (data, elapsed)

        # Merge ideation + detail into full Opportunity objects
        all_opportunities = []
        for i, (_label, _prompt, ideation) in enumerate(detail_prompts):
            detail_data, detail_elapsed = results[f"detail_{i}"]
            timer.record(f"ai_call_detail_{i}", detail_elapsed)

            merged = {
                "title": ideation["title"],
                "description": ideation["description"],
                "value_lever": ideation["value_lever"],
                "strategic_category": ideation["strategic_category"],
                "impact_rating": ideation["impact_rating"],
                **detail_data,
            }
            all_opportunities.append(build_opportunity(merged))

        opportunity_result = OpportunityResult(
            opportunities=all_opportunities,
            top_three_immediate_actions=top_actions,
        )
        accessor.set_opportunities(opportunity_result)

        # Link EBITDA nodes to opportunities
        link_opportunities_to_ebitda_nodes(all_opportunities, ebitda_result.nodes)
        accessor.set_ebitda_tree(ebitda_result)

        self.request_executor.add_details(timer.to_details())
        self.request_executor.mark_question_complete("generate_opportunities")
        self.request_executor.mark_question_complete("generate_ebitda_tree")

    def _run_ai_call(
        self,
        user_prompt: str,
        schema: dict[str, Any],
        system_prompt: str,
        label: str,
    ) -> tuple[str, dict[str, Any], float]:
        """Execute a single AI call and return (label, response_data, elapsed)."""
        client = self._ai_client_factory.get_client(
            verbosity=Verbosity.MEDIUM,
            reasoning_effort=ReasoningEffort.LOW,
            precision=Precision.STANDARD,
            instructions=system_prompt,
        )
        logger.info(
            "[ParallelDetailsAndEbitda:%s] sending AI request: prompt_len=%d, model=%s",
            label,
            len(user_prompt),
            getattr(client, "model", "unknown"),
        )
        start = time.monotonic()
        try:
            response = client.query_structured(input_text=user_prompt, json_schema=schema)
        except Exception:
            logger.exception("[ParallelDetailsAndEbitda:%s] AI request failed", label)
            raise
        elapsed = time.monotonic() - start
        logger.info(
            "[ParallelDetailsAndEbitda:%s] AI response in %.2fs: metadata=%s",
            label,
            elapsed,
            response.metadata,
        )
        return label, response.content, elapsed

"""Composite step: runs opportunity generation and EBITDA tree AI calls in parallel.

Instead of the sequential GenerateOpportunities → GenerateEbitdaTree flow, this step
runs all 3 AI calls concurrently (2 opportunity calls + 1 EBITDA tree call). The EBITDA
tree is built from profile + risk assessment only — opportunity-to-node linking is done
programmatically after all calls complete.

Saves ~60-90s of wall-clock time by overlapping the EBITDA tree call with opportunities.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any, cast

from signalfield_core.models.enums import Precision, ReasoningEffort, Verbosity
from signalfield_core.pipeline.step import RequestStep
from signalfield_core.utilities.future_manager import FutureManager

from src.models.model_company import EbitdaTreeResult, OpportunityResult
from src.models.model_literals import RISK_SCOPE_NAMES
from src.pipeline.pipeline_steps.generate_ebitda_tree import (
    EBITDA_SYSTEM_PROMPT,
    EBITDA_TREE_SCHEMA,
    build_ebitda_prompt,
    build_ebitda_tree_from_flat_nodes,
)
from src.pipeline.pipeline_steps.generate_opportunities import (
    HIGH_PRIORITY_SCHEMA,
    OPPS_SYSTEM_PROMPT,
    STRATEGIC_SCHEMA,
    build_high_priority_prompt,
    build_opportunity,
    build_strategic_prompt,
)
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
            # Subtotals and margins get both revenue and cost indices (deduplicated)
            node.linked_opportunity_indices = sorted(set(revenue_indices + cost_indices))
        for child in node.children:
            _link_node(child)

    for node in nodes:
        _link_node(node)


class ParallelOpportunitiesAndEbitda(RequestStep):
    """Runs opportunity generation and EBITDA tree AI calls in parallel.

    Replaces the sequential GenerateOpportunities → GenerateEbitdaTree pair.
    Runs 3 AI calls concurrently: high-priority opportunities, strategic
    opportunities, and EBITDA tree. After all complete, links EBITDA nodes
    to opportunities programmatically based on value_lever.
    """

    def __init__(self, ai_client_factory: AIClientFactory | None = None) -> None:
        super().__init__()
        self._ai_client_factory = ai_client_factory

    def execute(self) -> None:
        """Run opportunity generation and EBITDA tree in parallel."""
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

        # Build opportunity prompts
        top_risk_categories = risk_assessment.top_risks[:3]
        other_categories = [
            category for category in RISK_SCOPE_NAMES if category not in top_risk_categories
        ]
        high_priority_prompt = build_high_priority_prompt(
            profile_dict, assessment_dict, top_risk_categories
        )
        strategic_prompt = build_strategic_prompt(profile_dict, assessment_dict, other_categories)

        # Build EBITDA prompt (from profile + risk only, no opportunities)
        ebitda_prompt = build_ebitda_prompt(profile_dict, assessment_dict)

        timer = StepTimer("ParallelOpportunitiesAndEbitda")

        # Run all 3 AI calls in parallel
        with FutureManager(name="ParallelOpportunitiesAndEbitda", max_workers=3) as manager:
            manager.submit_task(
                self._run_ai_call,
                high_priority_prompt,
                HIGH_PRIORITY_SCHEMA,
                OPPS_SYSTEM_PROMPT,
                "high_priority",
            )
            manager.submit_task(
                self._run_ai_call,
                strategic_prompt,
                STRATEGIC_SCHEMA,
                OPPS_SYSTEM_PROMPT,
                "strategic",
            )
            manager.submit_task(
                self._run_ai_call,
                ebitda_prompt,
                EBITDA_TREE_SCHEMA,
                EBITDA_SYSTEM_PROMPT,
                "ebitda_tree",
            )
            all_results = manager.wait_for_all_and_collect_results()

        results: dict[str, tuple[dict[str, Any], float]] = {}
        for label, data, elapsed in all_results:
            results[label] = (data, elapsed)

        high_data, high_elapsed = results["high_priority"]
        strategic_data, strategic_elapsed = results["strategic"]
        ebitda_data, ebitda_elapsed = results["ebitda_tree"]

        timer.record("ai_call_high_priority", high_elapsed)
        timer.record("ai_call_strategic", strategic_elapsed)
        timer.record("ai_call_ebitda_tree", ebitda_elapsed)

        # Build opportunities
        all_opportunities = [
            build_opportunity(opp)
            for opp in high_data["opportunities"] + strategic_data["opportunities"]
        ]
        top_actions = high_data["top_three_immediate_actions"]

        opportunity_result = OpportunityResult(
            opportunities=all_opportunities,
            top_three_immediate_actions=top_actions,
        )
        accessor.set_opportunities(opportunity_result)

        # Reconstruct nested EBITDA tree from flat node list and link to opportunities
        ebitda_nodes = build_ebitda_tree_from_flat_nodes(ebitda_data["nodes"])
        link_opportunities_to_ebitda_nodes(all_opportunities, ebitda_nodes)

        ebitda_result = EbitdaTreeResult(
            summary=ebitda_data["summary"],
            revenue_estimate=ebitda_data["revenue_estimate"],
            ebitda_estimate=ebitda_data["ebitda_estimate"],
            nodes=ebitda_nodes,
        )
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
            "[ParallelOppsAndEbitda:%s] sending AI request: prompt_len=%d, model=%s",
            label,
            len(user_prompt),
            getattr(client, "model", "unknown"),
        )
        start = time.monotonic()
        try:
            response = client.query_structured(input_text=user_prompt, json_schema=schema)
        except Exception:
            logger.exception("[ParallelOppsAndEbitda:%s] AI request failed", label)
            raise
        elapsed = time.monotonic() - start
        logger.info(
            "[ParallelOppsAndEbitda:%s] AI response in %.2fs: metadata=%s",
            label,
            elapsed,
            response.metadata,
        )
        return label, response.content, elapsed

"""Pipeline step: build EBITDA tree programmatically from company profile.

No AI call — uses industry templates and benchmarks to produce a
deterministic P&L decomposition tree in <1ms.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, cast

from signalfield_core.pipeline.step import RequestStep

from src.pipeline.pipeline_steps.build_ebitda_tree import build_programmatic_ebitda_tree

if TYPE_CHECKING:
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


class ComputeEbitdaTree(RequestStep):
    """Build EBITDA tree programmatically and link to opportunities.

    Must run after DetailOpportunities so that opportunities are available
    for linking to EBITDA nodes.
    """

    def execute(self) -> None:
        """Build EBITDA tree from profile and link to opportunities."""
        accessor = cast("CompanyAccessor", self.entity_accessor)
        profile = accessor.company.profile

        if not profile:
            message = "Cannot build EBITDA tree: profile missing"
            raise ValueError(message)

        ebitda_result = build_programmatic_ebitda_tree(profile)

        # Link to opportunities if available
        opportunity_result = accessor.company.opportunity_result
        if opportunity_result:
            link_opportunities_to_ebitda_nodes(
                opportunity_result.opportunities, ebitda_result.nodes
            )

        accessor.set_ebitda_tree(ebitda_result)
        self.request_executor.mark_question_complete("generate_ebitda_tree")

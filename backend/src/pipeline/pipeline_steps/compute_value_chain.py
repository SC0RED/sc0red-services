"""Pipeline step: build value chain from company profile and link to risks/opportunities.

No AI call — uses business model templates and programmatic linking.
Must run after DetailOpportunities and ComputeEbitdaTree.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from signalfield_core.pipeline.step import RequestStep

from src.pipeline.pipeline_steps.build_value_chain import build_programmatic_value_chain

if TYPE_CHECKING:
    from src.facades.company_accessor import CompanyAccessor


class ComputeValueChain(RequestStep):
    """Build value chain and link to risks and opportunities."""

    def execute(self) -> None:
        """Build value chain from profile, risk assessment, and opportunities."""
        accessor = cast("CompanyAccessor", self.entity_accessor)
        profile = accessor.company.profile

        if not profile:
            message = "Cannot build value chain: profile missing"
            raise ValueError(message)

        opportunities = (
            accessor.company.opportunity_result.opportunities
            if accessor.company.opportunity_result
            else []
        )

        value_chain = build_programmatic_value_chain(
            profile=profile,
            opportunities=opportunities,
        )

        accessor.set_value_chain(value_chain)
        self.request_executor.mark_question_complete("compute_value_chain")

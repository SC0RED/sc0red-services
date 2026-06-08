"""Pipeline step: research the company's financials + operating model via AI.

Replaces the deterministic ``ComputeEbitdaTree`` + ``ComputeValueChain`` steps.
Runs the decomposed research DAG (``run_financial_research``) and assembles both
the EBITDA tree and the value chain from the researched facts, tagging every fact
with provenance + deterministic confidence + any web-search citations.

Soft-fail semantics: the EBITDA tree and value chain are FACT surfaces. If the
research fails (rate limit, schema/aggregation error, malformed output) OR the
adversarial verification judges the revenue model implausible, both surfaces fall
to the "insufficient public data" placeholder and the rest of the analysis
persists intact — never a fabricated P&L. Programming errors (AttributeError)
propagate so SQS retries and CloudWatch shows the stack trace.

Must run after ``DetailOpportunities`` so opportunities are available for linking
to EBITDA nodes.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, cast

from signalfield_core.exceptions.base import EngineError
from signalfield_core.pipeline.step import RequestStep
from signalfield_core.utilities.future_manager import FutureManagerError

from src.models.model_company import EbitdaTreeResult, ValueChainResult
from src.pipeline.pipeline_steps._financial_research import run_financial_research
from src.pipeline.pipeline_steps.build_ebitda_tree import assemble_ebitda_tree
from src.pipeline.pipeline_steps.build_value_chain import assemble_value_chain

if TYPE_CHECKING:
    from signalfield_core.services.ai_client_factory import AIClientFactory

    from src.facades.company_accessor import CompanyAccessor
    from src.models.model_company import EbitdaNode, Opportunity

logger = logging.getLogger(__name__)

STEP_NAME = "ResearchFinancials"

_EBITDA_UNCONFIRMED = (
    "Could not confirm this company's revenue model from available evidence; "
    "financials are shown only when they can be grounded."
)
_VALUE_CHAIN_UNCONFIRMED = (
    "Could not confirm how this business operates from available evidence; "
    "the operating model is shown only when it can be grounded."
)


def link_opportunities_to_ebitda_nodes(  # noqa: NAMING001  "link" is a verb; validator list is partial
    opportunities: list[Opportunity],
    nodes: list[EbitdaNode],
) -> None:
    """Link opportunities to EBITDA nodes by value_lever.

    Revenue Side → revenue nodes; Cost Side → cost nodes; Both → both.
    Subtotal/margin rollups receive the union.
    """
    revenue_indices = [
        i for i, opp in enumerate(opportunities) if opp.value_lever in ("Revenue Side", "Both")
    ]
    cost_indices = [
        i for i, opp in enumerate(opportunities) if opp.value_lever in ("Cost Side", "Both")
    ]

    def _link_node(node: EbitdaNode) -> None:
        if node.type == "revenue":
            node.linked_opportunity_indices = list(revenue_indices)
        elif node.type == "cost":
            node.linked_opportunity_indices = list(cost_indices)
        else:
            node.linked_opportunity_indices = sorted(set(revenue_indices + cost_indices))
        for child in node.children:
            _link_node(child)

    for node in nodes:
        _link_node(node)


class ResearchFinancials(RequestStep):
    """Research + assemble the EBITDA tree and value chain (replaces the templates)."""

    def __init__(self, ai_client_factory: AIClientFactory) -> None:
        super().__init__()
        self._ai_client_factory = ai_client_factory

    def execute(self) -> None:
        """Run the research DAG, assemble both surfaces, link opportunities."""
        accessor = cast("CompanyAccessor", self.entity_accessor)
        company = accessor.company
        profile = company.profile
        if not profile:
            message = "Cannot research financials: profile missing"
            raise ValueError(message)

        ebitda, value_chain = self._research_and_assemble(accessor, company, profile)

        opportunity_result = company.opportunity_result
        if opportunity_result and ebitda.grounded:
            link_opportunities_to_ebitda_nodes(opportunity_result.opportunities, ebitda.nodes)

        accessor.set_ebitda_tree(ebitda)
        accessor.set_value_chain(value_chain)
        self.request_executor.mark_question_complete("generate_ebitda_tree")
        self.request_executor.mark_question_complete("compute_value_chain")

    def _research_and_assemble(
        self,
        accessor: CompanyAccessor,
        company: object,
        profile: object,
    ) -> tuple[EbitdaTreeResult, ValueChainResult]:
        """Run research + assembly with soft-fail to the placeholder floor."""
        company_any = cast("object", company)
        try:
            facts = run_financial_research(
                self._ai_client_factory,
                company_name=getattr(company_any, "company_name", ""),
                url=getattr(company_any, "actual_url", "") or getattr(company_any, "url", ""),
                industry=getattr(profile, "industry", ""),
                scraped_text=accessor.get_scraped_text(),
                document_text=accessor.get_document_text() or "",
            )
        except (EngineError, FutureManagerError, ValueError, RuntimeError, KeyError, TypeError):
            logger.exception(
                "[%s] Financial research failed; rendering insufficient-data placeholders",
                STEP_NAME,
            )
            return (
                EbitdaTreeResult(grounded=False, insufficient_data_reason=_EBITDA_UNCONFIRMED),
                ValueChainResult(grounded=False, insufficient_data_reason=_VALUE_CHAIN_UNCONFIRMED),
            )

        if not facts.revenue_model_plausible:
            logger.info("[%s] Revenue model judged implausible — rendering placeholders", STEP_NAME)
            return (
                EbitdaTreeResult(grounded=False, insufficient_data_reason=_EBITDA_UNCONFIRMED),
                ValueChainResult(grounded=False, insufficient_data_reason=_VALUE_CHAIN_UNCONFIRMED),
            )

        company_name = getattr(company_any, "company_name", "")
        return (
            assemble_ebitda_tree(facts, company_name),
            assemble_value_chain(facts, company_name),
        )

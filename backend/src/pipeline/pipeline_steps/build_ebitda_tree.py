"""EBITDA tree assembler — builds the P&L tree from researched financial facts.

Replaces the old industry-template builder: instead of keyword-matching a company
to a hardcoded P&L, this assembles the tree from ``FinancialResearchFacts``
produced by the decomposed research DAG (``_financial_research``). Each node
carries a provenance tier, a deterministic confidence level derived from that
tier, and any web-search citations — see the ``decomposed-financial-research``,
``fact-provenance-labeling``, and ``ebitda-tree-confidence`` capabilities.

When the facts can't support a grounded tree (invalid range, or the caller's
plausibility gate failed), the report falls to the "insufficient public data"
placeholder per ``report-data-integrity``.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any, Literal

from src.models.model_company import Citation, EbitdaNode, EbitdaTreeResult
from src.pipeline.pipeline_steps._provenance import (
    confidence_from_provenance,
    reconcile_provenance,
)

if TYPE_CHECKING:
    from src.models.model_literals import ProvenanceTier
    from src.pipeline.pipeline_steps._financial_research import FinancialResearchFacts

logger = logging.getLogger(__name__)

_BILLION = 1_000_000_000
_MILLION = 1_000_000
_THOUSAND = 1000


def _format_currency(amount: int) -> str:
    """Format an integer dollar amount as a compact string (e.g. $10M, $500K)."""
    if amount >= _BILLION:
        billions = amount / _BILLION
        return f"${billions:.1f}B" if billions % 1 else f"${int(billions)}B"
    if amount >= _MILLION:
        return f"${int(amount / _MILLION)}M"
    if amount >= _THOUSAND:
        return f"${int(amount / _THOUSAND)}K"
    return f"${amount}"


def _format_range(low: int, high: int) -> str:
    """Format a (low, high) dollar range as '$XM-$YM'."""
    return f"{_format_currency(low)}-{_format_currency(high)}"


def _clamp_pct(pct: Any) -> int:
    """Coerce a model-supplied percentage to an int in [0, 100]."""
    try:
        value = int(pct)
    except (TypeError, ValueError):
        return 0
    return max(0, min(100, value))


def _slug(label: str, fallback: str) -> str:
    """Derive a stable node id from a free-text label."""
    slug = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")
    return slug or fallback


def _to_citations(web_sources: list[Any]) -> list[Citation]:
    """Map provider ``WebSearchSource`` objects to ``Citation`` models."""
    citations: list[Citation] = []
    for source in web_sources:
        url = getattr(source, "url", "")
        if url:
            citations.append(Citation(url=url, title=getattr(source, "title", None) or ""))
    return citations


def _insufficient_data_result(reason: str) -> EbitdaTreeResult:
    """Build the ungrounded placeholder result — no fabricated figures."""
    return EbitdaTreeResult(grounded=False, insufficient_data_reason=reason)


def _stream_children(
    items: list[dict[str, Any]],
    parent_low: int,
    parent_high: int,
    node_type: Literal["revenue", "cost"],
    provenance: ProvenanceTier,
    confidence: Literal["high", "medium", "low"],
    basis: str,
    parent_id: str,
) -> list[EbitdaNode]:
    """Build leaf nodes for a set of researched {label, pct} line items."""
    children: list[EbitdaNode] = []
    for index, item in enumerate(items):
        pct = _clamp_pct(item.get("pct"))
        label = str(item.get("label", "Other"))
        low = int(parent_low * pct / 100)
        high = int(parent_high * pct / 100)
        children.append(
            EbitdaNode(
                id=_slug(label, f"{parent_id}_{index}"),
                label=label,
                type=node_type,
                value_range=_format_range(low, high),
                percentage_of_parent=pct,
                description=f"{label} ({pct}% of {parent_id})",
                confidence_level=confidence,
                confidence_basis=basis,
                provenance=provenance,
            )
        )
    return children


def assemble_ebitda_tree(  # noqa: NAMING001  "assemble" is a verb; validator list is partial
    facts: FinancialResearchFacts, company_name: str
) -> EbitdaTreeResult:
    """Assemble the EBITDA tree from researched facts, tagging provenance per node.

    Returns the insufficient-data placeholder when the researched revenue range is
    missing or invalid. Confidence is deterministic from each node's provenance
    tier (downgraded if the revenue model was judged implausible).
    """
    revenue_range = facts.revenue_range
    revenue_low = int(revenue_range.get("revenue_low_usd", 0) or 0)
    revenue_high = int(revenue_range.get("revenue_high_usd", 0) or 0)
    if revenue_low <= 0 or revenue_high < revenue_low:
        return _insufficient_data_result(
            "Could not establish a reliable revenue figure from public information; "
            "financials are shown only when they can be grounded in evidence."
        )

    plausible = facts.revenue_model_plausible
    revenue_citations = _to_citations(facts.citations.get("revenue_range", []))
    revenue_prov: ProvenanceTier = reconcile_provenance(
        revenue_range.get("provenance", "derived_estimate"),
        has_citation=bool(revenue_citations),
    )
    revenue_conf = confidence_from_provenance(revenue_prov, plausible=plausible)
    revenue_basis = str(revenue_range.get("basis", ""))

    mix_prov: ProvenanceTier = facts.revenue_mix.get("provenance", "industry_typical")
    mix_conf = confidence_from_provenance(mix_prov, plausible=plausible)
    cost_prov: ProvenanceTier = facts.cost_drivers.get("provenance", "industry_typical")
    cost_conf = confidence_from_provenance(cost_prov, plausible=plausible)

    margins = facts.margins
    gross_low = _clamp_pct(margins.get("gross_margin_low"))
    gross_high = _clamp_pct(margins.get("gross_margin_high"))
    ebitda_low_pct = _clamp_pct(margins.get("ebitda_margin_low"))
    ebitda_high_pct = _clamp_pct(margins.get("ebitda_margin_high"))

    nodes = _build_nodes(
        facts=facts,
        company_name=company_name,
        revenue_low=revenue_low,
        revenue_high=revenue_high,
        margins=(gross_low, gross_high, ebitda_low_pct, ebitda_high_pct),
        revenue=(revenue_prov, revenue_conf, revenue_basis, revenue_citations),
        mix=(mix_prov, mix_conf),
        cost=(cost_prov, cost_conf),
    )

    revenue_estimate = _format_range(revenue_low, revenue_high)
    ebitda_low = int(revenue_low * ebitda_low_pct / 100)
    ebitda_high = int(revenue_high * ebitda_high_pct / 100)
    ebitda_estimate = (
        f"{_format_range(ebitda_low, ebitda_high)} ({ebitda_low_pct}-{ebitda_high_pct}% margin)"
    )
    top_stream = facts.revenue_mix.get("streams", [{}])[0]
    summary = (
        f"{company_name} is a {facts.company_type} with a "
        f"{facts.revenue_model.get('revenue_model', 'n/a')} revenue model. "
        f"Estimated annual revenue {revenue_estimate}. "
        f"Primary revenue: {top_stream.get('label', 'n/a')} "
        f"(~{_clamp_pct(top_stream.get('pct'))}%). Estimated EBITDA {ebitda_estimate}."
    )
    logger.info(
        "Assembled EBITDA tree: company_type=%s revenue=%s provenance=%s plausible=%s",
        facts.company_type,
        revenue_estimate,
        revenue_prov,
        plausible,
    )
    return EbitdaTreeResult(
        summary=summary,
        revenue_estimate=revenue_estimate,
        ebitda_estimate=ebitda_estimate,
        nodes=nodes,
        grounded=True,
    )


def _build_nodes(
    *,
    facts: FinancialResearchFacts,
    company_name: str,
    revenue_low: int,
    revenue_high: int,
    margins: tuple[int, int, int, int],
    revenue: tuple[ProvenanceTier, Literal["high", "medium", "low"], str, list[Citation]],
    mix: tuple[ProvenanceTier, Literal["high", "medium", "low"]],
    cost: tuple[ProvenanceTier, Literal["high", "medium", "low"]],
) -> list[EbitdaNode]:
    """Build the five root nodes (revenue, COGS, gross profit, OpEx, EBITDA)."""
    gross_low, gross_high, ebitda_low_pct, ebitda_high_pct = margins
    revenue_prov, revenue_conf, revenue_basis, revenue_citations = revenue
    mix_prov, mix_conf = mix
    cost_prov, cost_conf = cost
    cost_basis = str(facts.cost_drivers.get("basis", ""))

    cogs_low = int(revenue_low * (100 - gross_high) / 100)
    cogs_high = int(revenue_high * (100 - gross_low) / 100)
    opex_low = int(revenue_low * max(0, gross_low - ebitda_high_pct) / 100)
    opex_high = int(revenue_high * max(0, gross_high - ebitda_low_pct) / 100)

    revenue_node = EbitdaNode(
        id="revenue",
        label="Total Revenue",
        type="revenue",
        value_range=_format_range(revenue_low, revenue_high),
        description=f"Total annual revenue for {company_name}",
        children=_stream_children(
            facts.revenue_mix.get("streams", []),
            revenue_low,
            revenue_high,
            "revenue",
            mix_prov,
            mix_conf,
            str(facts.revenue_mix.get("basis", "")),
            "revenue",
        ),
        confidence_level=revenue_conf,
        confidence_basis=revenue_basis,
        provenance=revenue_prov,
        citations=revenue_citations,
    )
    cogs_node = EbitdaNode(
        id="cogs",
        label="Cost of Revenue",
        type="cost",
        value_range=_format_range(cogs_low, cogs_high),
        description="Direct costs of delivering the service",
        children=_stream_children(
            facts.cost_drivers.get("cogs_items", []),
            cogs_low,
            cogs_high,
            "cost",
            cost_prov,
            cost_conf,
            cost_basis,
            "cogs",
        ),
        confidence_level=cost_conf,
        confidence_basis=cost_basis,
        provenance=cost_prov,
    )
    gross_profit_node = EbitdaNode(
        id="gross_profit",
        label="Gross Profit",
        type="subtotal",
        value_range=_format_range(
            int(revenue_low * gross_low / 100), int(revenue_high * gross_high / 100)
        ),
        description=f"Revenue minus cost of revenue ({gross_low}-{gross_high}% margin)",
    )
    opex_node = EbitdaNode(
        id="opex",
        label="Operating Expenses",
        type="cost",
        value_range=_format_range(opex_low, opex_high),
        description="Operating expenses excluding COGS",
        children=_stream_children(
            facts.cost_drivers.get("opex_items", []),
            opex_low,
            opex_high,
            "cost",
            cost_prov,
            cost_conf,
            cost_basis,
            "opex",
        ),
        confidence_level=cost_conf,
        confidence_basis=cost_basis,
        provenance=cost_prov,
    )
    ebitda_node = EbitdaNode(
        id="ebitda",
        label="EBITDA",
        type="subtotal",
        value_range=_format_range(
            int(revenue_low * ebitda_low_pct / 100), int(revenue_high * ebitda_high_pct / 100)
        ),
        description=(
            f"Earnings before interest, taxes, depreciation and amortisation "
            f"({ebitda_low_pct}-{ebitda_high_pct}% margin)"
        ),
    )
    return [revenue_node, cogs_node, gross_profit_node, opex_node, ebitda_node]

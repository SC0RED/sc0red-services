"""Programmatic EBITDA tree builder — replaces the AI-generated EBITDA call.

Builds a P&L decomposition tree deterministically from the company profile,
using industry benchmarks and business-model-specific templates. This eliminates
a ~27s AI call from the pipeline's critical path.

Inputs: CompanyProfile (business_model, company_size, company_name, industry)
Output: EbitdaTreeResult (summary, revenue_estimate, ebitda_estimate, nested nodes)

The static template data and the input-matching helpers
(``_resolve_template``, ``_estimate_revenue``) live in ``_ebitda_templates.py``.
The derivation-provenance label (``_compute_confidence``) lives in
``_ebitda_confidence.py``. Both are split out to keep this file under the
400-line module-size limit; everything is private (``_``-prefixed) so the
public surface of ``pipeline_steps`` is unchanged.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Literal

from src.models.model_company import EbitdaNode, EbitdaTreeResult
from src.pipeline.pipeline_steps._ebitda_confidence import _compute_confidence
from src.pipeline.pipeline_steps._ebitda_templates import (
    _estimate_revenue,
    _resolve_template,
)

if TYPE_CHECKING:
    from src.models.model_company import CompanyProfile

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Currency formatting helpers
# ---------------------------------------------------------------------------

_BILLION = 1_000_000_000
_MILLION = 1_000_000
_THOUSAND = 1000
_MAX_PERCENTAGE = 100


def _format_currency(amount: int) -> str:
    """Format an integer dollar amount as a compact string (e.g. $10M, $500K)."""
    if amount >= _BILLION:
        billions = amount / _BILLION
        return f"${billions:.1f}B" if billions % 1 else f"${int(billions)}B"
    if amount >= _MILLION:
        millions = amount / _MILLION
        return f"${int(millions)}M"
    if amount >= _THOUSAND:
        return f"${int(amount / _THOUSAND)}K"
    return f"${amount}"


def _format_range(low: int, high: int) -> str:
    """Format a (low, high) dollar range as '$XM-$YM'."""
    return f"{_format_currency(low)}-{_format_currency(high)}"


def _apply_percentage(low: int, high: int, pct: int) -> tuple[int, int]:
    """Apply a percentage to a revenue range, returning (low, high) in dollars."""
    if not 0 <= pct <= _MAX_PERCENTAGE:
        message = f"Percentage must be 0-100, got {pct}"
        raise ValueError(message)
    return int(low * pct / 100), int(high * pct / 100)


def _build_child_nodes(
    items: list[tuple[str, str, int]],
    parent_id: str,
    node_type: Literal["revenue", "cost", "margin", "subtotal"],
    parent_low: int,
    parent_high: int,
    confidence_level: Literal["high", "medium", "low"] | None,
    confidence_basis: str | None,
) -> list[EbitdaNode]:
    """Build child EbitdaNode objects for a set of line items.

    ``confidence_level`` and ``confidence_basis`` are propagated to every leaf
    child as-is — children inherit their parent's provenance signal because the
    underlying inputs (template + size) are identical.
    """
    children: list[EbitdaNode] = []
    for item_id, label, pct in items:
        child_low, child_high = _apply_percentage(parent_low, parent_high, pct)
        children.append(
            EbitdaNode(
                id=item_id,
                label=label,
                type=node_type,
                value_range=_format_range(child_low, child_high),
                percentage_of_parent=pct,
                description=f"{label} ({pct}% of {parent_id})",
                confidence_level=confidence_level,
                confidence_basis=confidence_basis,
            )
        )
    return children


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_programmatic_ebitda_tree(profile: CompanyProfile) -> EbitdaTreeResult:
    """Build a complete EBITDA tree from the company profile using industry templates.

    Uses business_model to select a P&L template and company_size to estimate
    revenue ranges. All values are deterministic — no AI call required.
    """
    template, template_matched = _resolve_template(profile.business_model)
    revenue_low, revenue_high, size_matched = _estimate_revenue(template, profile.company_size)

    revenue_confidence_level, revenue_confidence_basis = _compute_confidence(
        template=template,
        template_matched=template_matched,
        company_size=profile.company_size,
        size_matched=size_matched,
        node_kind="revenue",
    )
    cost_confidence_level, cost_confidence_basis = _compute_confidence(
        template=template,
        template_matched=template_matched,
        company_size=profile.company_size,
        size_matched=size_matched,
        node_kind="cost",
    )

    logger.info(
        "Building programmatic EBITDA tree: business_model=%s template=%s "
        "revenue=%s confidence=%s (template_matched=%s size_matched=%s)",
        profile.business_model,
        template.label,
        _format_range(revenue_low, revenue_high),
        revenue_confidence_level,
        template_matched,
        size_matched,
    )

    # Derive COGS percentage from gross margin (inverse relationship)
    cogs_pct_low = 100 - template.gross_margin[1]  # low COGS when high margin
    cogs_pct_high = 100 - template.gross_margin[0]  # high COGS when low margin
    cogs_low = int(revenue_low * cogs_pct_low / 100)
    cogs_high = int(revenue_high * cogs_pct_high / 100)

    # Gross Profit derived directly from gross margin percentages
    gross_profit_low = int(revenue_low * template.gross_margin[0] / 100)
    gross_profit_high = int(revenue_high * template.gross_margin[1] / 100)

    # Derive OpEx percentage from the spread between gross margin and EBITDA margin
    opex_pct_low = template.gross_margin[0] - template.ebitda_margin[1]
    opex_pct_high = template.gross_margin[1] - template.ebitda_margin[0]
    opex_low = int(revenue_low * opex_pct_low / 100)
    opex_high = int(revenue_high * opex_pct_high / 100)

    # EBITDA
    ebitda_low = int(revenue_low * template.ebitda_margin[0] / 100)
    ebitda_high = int(revenue_high * template.ebitda_margin[1] / 100)

    # Build node tree. Leaf nodes (revenue streams, COGS items, OpEx items) carry
    # the per-kind confidence pair; subtotal/margin rollups (gross profit, EBITDA)
    # do NOT — they inherit visually via their children's chips, per the
    # ebitda-tree-confidence spec.
    revenue_children = _build_child_nodes(
        template.revenue_streams,
        "revenue",
        "revenue",
        revenue_low,
        revenue_high,
        revenue_confidence_level,
        revenue_confidence_basis,
    )
    revenue_node = EbitdaNode(
        id="revenue",
        label="Total Revenue",
        type="revenue",
        value_range=_format_range(revenue_low, revenue_high),
        description=f"Total annual revenue for {profile.company_name}",
        children=revenue_children,
        confidence_level=revenue_confidence_level,
        confidence_basis=revenue_confidence_basis,
    )

    cogs_children = _build_child_nodes(
        template.cogs_items,
        "cogs",
        "cost",
        cogs_low,
        cogs_high,
        cost_confidence_level,
        cost_confidence_basis,
    )
    cogs_node = EbitdaNode(
        id="cogs",
        label="Cost of Revenue",
        type="cost",
        value_range=_format_range(cogs_low, cogs_high),
        description="Direct costs of delivering products and services",
        children=cogs_children,
        confidence_level=cost_confidence_level,
        confidence_basis=cost_confidence_basis,
    )

    gross_profit_node = EbitdaNode(
        id="gross_profit",
        label="Gross Profit",
        type="subtotal",
        value_range=_format_range(gross_profit_low, gross_profit_high),
        description=(
            f"Revenue minus cost of revenue "
            f"({template.gross_margin[0]}-{template.gross_margin[1]}% margin)"
        ),
    )

    opex_children = _build_child_nodes(
        template.opex_items,
        "opex",
        "cost",
        opex_low,
        opex_high,
        cost_confidence_level,
        cost_confidence_basis,
    )
    opex_node = EbitdaNode(
        id="opex",
        label="Operating Expenses",
        type="cost",
        value_range=_format_range(opex_low, opex_high),
        description="Total operating expenses excluding COGS",
        children=opex_children,
        confidence_level=cost_confidence_level,
        confidence_basis=cost_confidence_basis,
    )

    ebitda_node = EbitdaNode(
        id="ebitda",
        label="EBITDA",
        type="subtotal",
        value_range=_format_range(ebitda_low, ebitda_high),
        description=(
            f"Earnings before interest, taxes, depreciation and amortisation "
            f"({template.ebitda_margin[0]}-{template.ebitda_margin[1]}% margin)"
        ),
    )

    revenue_estimate = _format_range(revenue_low, revenue_high)
    ebitda_estimate = (
        f"{_format_range(ebitda_low, ebitda_high)} "
        f"({template.ebitda_margin[0]}-{template.ebitda_margin[1]}% margin)"
    )

    primary_stream = template.revenue_streams[0][1]
    summary = (
        f"{profile.company_name} operates a {template.label} business model "
        f"with estimated annual revenue of {revenue_estimate}. "
        f"Primary revenue comes from {primary_stream} "
        f"(~{template.revenue_streams[0][2]}%). "
        f"At industry-typical margins, estimated EBITDA is {ebitda_estimate}."
    )

    return EbitdaTreeResult(
        summary=summary,
        revenue_estimate=revenue_estimate,
        ebitda_estimate=ebitda_estimate,
        nodes=[revenue_node, cogs_node, gross_profit_node, opex_node, ebitda_node],
    )

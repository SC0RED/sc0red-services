"""Programmatic EBITDA tree builder — replaces the AI-generated EBITDA call.

Builds a P&L decomposition tree deterministically from the company profile,
using industry benchmarks and business-model-specific templates. This eliminates
a ~27s AI call from the pipeline's critical path.

Inputs: CompanyProfile (business_model, company_size, company_name, industry)
Output: EbitdaTreeResult (summary, revenue_estimate, ebitda_estimate, nested nodes)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Literal

from src.models.model_company import EbitdaNode, EbitdaTreeResult

if TYPE_CHECKING:
    from src.models.model_company import CompanyProfile

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Company size → employee count range
# ---------------------------------------------------------------------------
_SIZE_TO_EMPLOYEES: dict[str, tuple[int, int]] = {
    "Startup <50": (10, 50),
    "Small 50-200": (50, 200),
    "Mid-market 200-1000": (200, 1000),
    "Large 1000-5000": (1000, 5000),
    "Enterprise 5000+": (5000, 10000),
}

_DEFAULT_EMPLOYEES = (100, 500)


# ---------------------------------------------------------------------------
# Business model templates
# ---------------------------------------------------------------------------
class _Template:
    """Immutable template for a business model's P&L structure."""

    __slots__ = (
        "cogs_items",
        "ebitda_margin",
        "gross_margin",
        "label",
        "opex_items",
        "revenue_per_employee",
        "revenue_streams",
    )

    def __init__(
        self,
        *,
        label: str,
        revenue_streams: list[tuple[str, str, int]],
        cogs_items: list[tuple[str, str, int]],
        opex_items: list[tuple[str, str, int]],
        gross_margin: tuple[int, int],
        ebitda_margin: tuple[int, int],
        revenue_per_employee: tuple[int, int],
    ) -> None:
        self.label = label
        self.revenue_streams = revenue_streams  # (id, label, pct_of_revenue)
        self.cogs_items = cogs_items  # (id, label, pct_of_cogs)
        self.opex_items = opex_items  # (id, label, pct_of_opex)
        self.gross_margin = gross_margin  # (low%, high%)
        self.ebitda_margin = ebitda_margin  # (low%, high%)
        self.revenue_per_employee = revenue_per_employee  # (low$K, high$K)


_TEMPLATES: dict[str, _Template] = {
    "saas": _Template(
        label="SaaS",
        revenue_streams=[
            ("subscriptions", "Subscriptions", 80),
            ("professional_services", "Professional Services", 15),
            ("other_revenue", "Other Revenue", 5),
        ],
        cogs_items=[
            ("cloud_infrastructure", "Cloud Infrastructure", 45),
            ("customer_support", "Customer Support", 35),
            ("implementation_costs", "Implementation Costs", 20),
        ],
        opex_items=[
            ("sales_marketing", "Sales & Marketing", 45),
            ("research_development", "R&D", 30),
            ("general_admin", "G&A", 25),
        ],
        gross_margin=(70, 85),
        ebitda_margin=(15, 35),
        revenue_per_employee=(150, 400),
    ),
    "services": _Template(
        label="Professional Services",
        revenue_streams=[
            ("project_revenue", "Project-Based Revenue", 50),
            ("retainer_revenue", "Retainers / Managed Services", 40),
            ("training_other", "Training & Other", 10),
        ],
        cogs_items=[
            ("delivery_labour", "Delivery Labour", 70),
            ("subcontractors", "Subcontractors", 20),
            ("delivery_tools", "Delivery Tools & Licences", 10),
        ],
        opex_items=[
            ("sales_marketing", "Sales & Marketing", 40),
            ("research_development", "R&D", 20),
            ("general_admin", "G&A", 40),
        ],
        gross_margin=(30, 50),
        ebitda_margin=(10, 25),
        revenue_per_employee=(100, 250),
    ),
    "ecommerce": _Template(
        label="E-commerce / Marketplace",
        revenue_streams=[
            ("product_sales", "Product Sales", 70),
            ("marketplace_fees", "Marketplace Fees", 20),
            ("advertising_revenue", "Advertising & Other", 10),
        ],
        cogs_items=[
            ("product_fulfilment", "Product & Fulfilment", 70),
            ("shipping_logistics", "Shipping & Logistics", 20),
            ("payment_processing", "Payment Processing", 10),
        ],
        opex_items=[
            ("sales_marketing", "Sales & Marketing", 50),
            ("technology", "Technology", 25),
            ("general_admin", "G&A", 25),
        ],
        gross_margin=(25, 45),
        ebitda_margin=(5, 15),
        revenue_per_employee=(200, 800),
    ),
    "manufacturing": _Template(
        label="Manufacturing",
        revenue_streams=[
            ("product_sales", "Product Sales", 85),
            ("aftermarket_services", "Services & Aftermarket", 15),
        ],
        cogs_items=[
            ("raw_materials", "Raw Materials", 55),
            ("direct_labour", "Direct Labour", 30),
            ("manufacturing_overhead", "Manufacturing Overhead", 15),
        ],
        opex_items=[
            ("sales_marketing", "Sales & Marketing", 35),
            ("research_development", "R&D", 25),
            ("general_admin", "G&A", 40),
        ],
        gross_margin=(25, 40),
        ebitda_margin=(8, 20),
        revenue_per_employee=(100, 300),
    ),
    "financial_services": _Template(
        label="Financial Services",
        revenue_streams=[
            ("fee_income", "Fee Income", 60),
            ("interest_income", "Interest & Spread Income", 25),
            ("advisory_revenue", "Advisory Revenue", 15),
        ],
        cogs_items=[
            ("compensation", "Compensation & Benefits", 60),
            ("technology_data", "Technology & Data", 25),
            ("regulatory_costs", "Regulatory & Compliance", 15),
        ],
        opex_items=[
            ("sales_marketing", "Sales & Marketing", 30),
            ("technology_ops", "Technology Operations", 35),
            ("general_admin", "G&A", 35),
        ],
        gross_margin=(50, 70),
        ebitda_margin=(20, 40),
        revenue_per_employee=(200, 500),
    ),
}

# Keyword → template key mapping for fuzzy matching
_MODEL_KEYWORDS: list[tuple[list[str], str]] = [
    (["saas", "software as a service", "subscription software"], "saas"),
    (["consulting", "professional service", "advisory", "agency"], "services"),
    (["e-commerce", "ecommerce", "marketplace", "retail", "dtc"], "ecommerce"),
    (["manufactur", "industrial", "hardware"], "manufacturing"),
    (["financial", "fintech", "banking", "insurance", "asset management"], "financial_services"),
]

_DEFAULT_TEMPLATE_KEY = "saas"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_template(business_model: str) -> tuple[_Template, bool]:
    """Match a free-text business_model string to the closest template.

    Returns a tuple of (template, matched) where ``matched`` is True if a keyword
    in ``_MODEL_KEYWORDS`` fired and False if we fell back to ``_DEFAULT_TEMPLATE_KEY``.
    The flag drives the confidence label per the ebitda-tree-confidence spec —
    callers MUST NOT discard it.
    """
    lower = business_model.lower()
    for keywords, key in _MODEL_KEYWORDS:
        for keyword in keywords:
            if keyword in lower:
                return _TEMPLATES[key], True
    return _TEMPLATES[_DEFAULT_TEMPLATE_KEY], False


def _estimate_revenue(
    template: _Template,
    company_size: str,
) -> tuple[int, int, bool]:
    """Estimate (low, high) annual revenue in dollars and report whether size resolved.

    Returns a tuple of (revenue_low, revenue_high, size_matched). ``size_matched``
    is True when ``company_size`` is a known key in ``_SIZE_TO_EMPLOYEES`` and
    False when ``_DEFAULT_EMPLOYEES`` was used as the fallback. The flag drives
    the confidence label.
    """
    size_matched = company_size in _SIZE_TO_EMPLOYEES
    employee_low, employee_high = _SIZE_TO_EMPLOYEES.get(company_size, _DEFAULT_EMPLOYEES)
    rev_per_emp_low, rev_per_emp_high = template.revenue_per_employee
    low = employee_low * rev_per_emp_low * 1000
    high = employee_high * rev_per_emp_high * 1000
    return low, high, size_matched


def _compute_confidence(
    *,
    template: _Template,
    template_matched: bool,
    company_size: str,
    size_matched: bool,
    node_kind: Literal["revenue", "cost"],
) -> tuple[Literal["high", "medium", "low"], str]:
    """Compute the confidence (level, basis) pair for a leaf node.

    The level reflects how cleanly the build inputs resolved against the
    deterministic logic in this module. ``template_matched`` and ``size_matched``
    each indicate whether their input resolved against a known entry; both
    booleans together pick the level:

    * both True  → "high"   — both inputs gave usable signal
    * exactly 1  → "medium" — one input defaulted
    * both False → "low"    — both inputs defaulted; figure is a generic guess

    The ``basis`` string is a 1-2 sentence human-readable explanation that names
    the resolved input(s) and the defaulted one(s); it is phrased differently
    for revenue vs cost provenance because the inputs flow through differently
    (revenue is computed directly from size times rev-per-employee; cost is
    computed by applying template margins to revenue, so cost provenance always
    references "industry-benchmark margin" in addition to the upstream revenue
    inputs).
    See the ebitda-tree-confidence spec for the canonical rules.
    """
    template_clause = (
        f"a {template.label} template (matched on business model)"
        if template_matched
        else f"a defaulted {template.label} template (no matching business model keyword)"
    )
    size_clause = (
        f"a known size bracket ({company_size!r})"
        if size_matched
        else "a defaulted mid-market size bracket (no matching company-size signal)"
    )

    if template_matched and size_matched:
        level: Literal["high", "medium", "low"] = "high"
    elif template_matched or size_matched:
        level = "medium"
    else:
        level = "low"

    if node_kind == "revenue":
        basis = f"Revenue derived from {template_clause} applied to {size_clause}."
    else:
        basis = (
            f"Cost derived from industry-benchmark margins on {template_clause}, "
            f"applied to revenue estimated from {size_clause}."
        )
    return level, basis


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

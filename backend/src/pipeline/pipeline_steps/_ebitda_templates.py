"""Industry-template data for the programmatic EBITDA tree builder.

Owns the deterministic inputs that ``build_ebitda_tree.build_programmatic_ebitda_tree``
reads at request time: the company-size → employee-count map, the per-business-model
P&L templates (``_Template``), and the keyword fuzzy match for free-text business
model strings. There is deliberately no default business-model template — an
unmatched model is reported as ungrounded by the builder (which renders the
"insufficient public data" placeholder) rather than silently fabricated as SaaS.

Lives in its own module because the data block is large (~150 lines on its own) and
splitting it out keeps the main builder file under the 400-line limit.

Module-private — exported only to ``build_ebitda_tree.py``. Underscore prefixes are
preserved so the public surface of ``pipeline_steps`` is unchanged.
"""

from __future__ import annotations

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


def _resolve_template(business_model: str) -> _Template | None:
    """Match a free-text business_model string to the closest template.

    Returns the matched ``_Template`` or ``None`` when no keyword in
    ``_MODEL_KEYWORDS`` fires. There is deliberately NO default template: a
    business model we cannot place is reported as ungrounded by the builder
    (which renders the "insufficient public data" placeholder) rather than
    silently fabricated as SaaS. See the report-data-integrity and
    ebitda-tree-confidence specs.
    """
    lower = business_model.lower()
    for keywords, key in _MODEL_KEYWORDS:
        for keyword in keywords:
            if keyword in lower:
                return _TEMPLATES[key]
    return None


def _estimate_revenue(
    template: _Template,
    company_size: str,
) -> tuple[int, int, bool]:
    """Estimate (low, high) annual revenue in dollars and report whether size resolved.

    Returns a tuple of (revenue_low, revenue_high, size_matched). ``size_matched``
    is True when ``company_size`` is a known key in ``_SIZE_TO_EMPLOYEES`` and
    False when ``_DEFAULT_EMPLOYEES`` was used as the fallback. The flag drives
    the confidence label.

    The range is driven by a single uncertainty band, not two multiplied
    together: a representative (midpoint) employee count is multiplied by the low
    and high ends of revenue-per-employee. The previous formula multiplied the
    bottom of the employee band by the bottom of the rev-per-employee band and
    the two tops together, compounding two independent uncertainties into a
    ~13x-wide range presented as fact. With the midpoint the emitted high/low
    ratio equals the rev-per-employee band's ratio and never exceeds the larger
    of the two input bands' ratios — see the ebitda-tree-confidence spec.
    """
    size_matched = company_size in _SIZE_TO_EMPLOYEES
    employee_low, employee_high = _SIZE_TO_EMPLOYEES.get(company_size, _DEFAULT_EMPLOYEES)
    employee_mid = (employee_low + employee_high) // 2
    rev_per_emp_low, rev_per_emp_high = template.revenue_per_employee
    low = employee_mid * rev_per_emp_low * 1000
    high = employee_mid * rev_per_emp_high * 1000
    return low, high, size_matched

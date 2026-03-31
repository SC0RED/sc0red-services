"""Value chain business model templates.

Defines step templates for each business model type: SaaS, Professional Services,
E-commerce, Manufacturing, Financial Services. Each step maps risk categories
and strategic opportunity categories.

Extracted from build_value_chain.py to stay under the 400-line file limit.
"""

from __future__ import annotations


class StepTemplate:
    """Immutable template for a single value chain step."""

    __slots__ = (
        "category",
        "description",
        "id",
        "label",
        "risk_categories",
        "strategic_categories",
    )

    def __init__(
        self,
        *,
        step_id: str,
        label: str,
        description: str,
        category: str,
        risk_categories: list[str],
        strategic_categories: list[str],
    ) -> None:
        self.id = step_id
        self.label = label
        self.description = description
        self.category = category
        self.risk_categories = risk_categories
        self.strategic_categories = strategic_categories


# ---------------------------------------------------------------------------
# SaaS
# ---------------------------------------------------------------------------
SAAS_TEMPLATE = [
    StepTemplate(
        step_id="lead_generation",
        label="Lead Generation & Marketing",
        description="Attract and nurture potential customers through digital channels",
        category="primary",
        risk_categories=["competitive_displacement", "customer_behavior"],
        strategic_categories=["Revenue Capture", "Market Expansion"],
    ),
    StepTemplate(
        step_id="sales",
        label="Sales & Conversion",
        description="Convert leads into paying customers through demos and trials",
        category="primary",
        risk_categories=["competitive_displacement", "margin_compression"],
        strategic_categories=["Revenue Capture", "Competitive Moat"],
    ),
    StepTemplate(
        step_id="onboarding",
        label="Onboarding & Implementation",
        description="Get new customers set up and productive on the platform",
        category="primary",
        risk_categories=["technology_obsolescence", "talent_workforce"],
        strategic_categories=["Operational Efficiency"],
    ),
    StepTemplate(
        step_id="product_delivery",
        label="Product Delivery & Platform",
        description="Core product functionality and ongoing platform operations",
        category="primary",
        risk_categories=["technology_obsolescence", "data_ip"],
        strategic_categories=["Competitive Moat", "Operational Efficiency"],
    ),
    StepTemplate(
        step_id="customer_success",
        label="Customer Success & Support",
        description="Ensure customer satisfaction and resolve issues",
        category="primary",
        risk_categories=["customer_behavior", "talent_workforce"],
        strategic_categories=["Operational Efficiency", "Revenue Capture"],
    ),
    StepTemplate(
        step_id="renewal",
        label="Renewal & Expansion",
        description="Retain customers and grow account revenue",
        category="primary",
        risk_categories=["competitive_displacement", "margin_compression", "customer_behavior"],
        strategic_categories=["Revenue Capture", "Competitive Moat"],
    ),
    StepTemplate(
        step_id="engineering",
        label="R&D / Engineering",
        description="Product development, innovation, and technical debt management",
        category="support",
        risk_categories=["technology_obsolescence", "talent_workforce"],
        strategic_categories=["Competitive Moat", "Talent Strategy"],
    ),
    StepTemplate(
        step_id="data_infrastructure",
        label="Data & Infrastructure",
        description="Cloud infrastructure, data management, and security",
        category="support",
        risk_categories=["data_ip", "supply_chain", "regulatory_compliance"],
        strategic_categories=["Operational Efficiency"],
    ),
]

# ---------------------------------------------------------------------------
# Professional Services
# ---------------------------------------------------------------------------
SERVICES_TEMPLATE = [
    StepTemplate(
        step_id="business_development",
        label="Business Development",
        description="Identify and pursue new client engagements",
        category="primary",
        risk_categories=["competitive_displacement", "customer_behavior"],
        strategic_categories=["Revenue Capture", "Market Expansion"],
    ),
    StepTemplate(
        step_id="proposal_scoping",
        label="Proposal & Scoping",
        description="Define project scope, deliverables, and pricing",
        category="primary",
        risk_categories=["competitive_displacement", "margin_compression"],
        strategic_categories=["Revenue Capture", "Competitive Moat"],
    ),
    StepTemplate(
        step_id="project_delivery",
        label="Project Delivery",
        description="Execute client engagements and deliver results",
        category="primary",
        risk_categories=["technology_obsolescence", "talent_workforce"],
        strategic_categories=["Operational Efficiency", "Competitive Moat"],
    ),
    StepTemplate(
        step_id="quality_assurance",
        label="Quality Assurance",
        description="Ensure deliverable quality and client satisfaction",
        category="primary",
        risk_categories=["technology_obsolescence", "regulatory_compliance"],
        strategic_categories=["Operational Efficiency"],
    ),
    StepTemplate(
        step_id="client_management",
        label="Client Relationship Management",
        description="Maintain and grow client relationships for repeat business",
        category="primary",
        risk_categories=["customer_behavior", "competitive_displacement"],
        strategic_categories=["Revenue Capture", "Competitive Moat"],
    ),
    StepTemplate(
        step_id="knowledge_management",
        label="Knowledge Management",
        description="Capture and share institutional knowledge across the firm",
        category="support",
        risk_categories=["data_ip", "talent_workforce"],
        strategic_categories=["Operational Efficiency", "Talent Strategy"],
    ),
    StepTemplate(
        step_id="talent_training",
        label="Talent & Training",
        description="Recruit, develop, and retain skilled professionals",
        category="support",
        risk_categories=["talent_workforce", "competitive_displacement"],
        strategic_categories=["Talent Strategy"],
    ),
]

# ---------------------------------------------------------------------------
# E-commerce
# ---------------------------------------------------------------------------
ECOMMERCE_TEMPLATE = [
    StepTemplate(
        step_id="sourcing",
        label="Product Sourcing / Curation",
        description="Source, select, and manage product catalog",
        category="primary",
        risk_categories=["supply_chain", "competitive_displacement"],
        strategic_categories=["Competitive Moat", "Revenue Capture"],
    ),
    StepTemplate(
        step_id="marketing",
        label="Marketing & Acquisition",
        description="Drive traffic and acquire customers through digital channels",
        category="primary",
        risk_categories=["competitive_displacement", "customer_behavior"],
        strategic_categories=["Revenue Capture", "Market Expansion"],
    ),
    StepTemplate(
        step_id="storefront",
        label="Storefront / UX",
        description="Online shopping experience, search, and product discovery",
        category="primary",
        risk_categories=["technology_obsolescence", "customer_behavior"],
        strategic_categories=["Competitive Moat", "Operational Efficiency"],
    ),
    StepTemplate(
        step_id="fulfillment",
        label="Order Fulfillment",
        description="Pick, pack, ship, and deliver orders to customers",
        category="primary",
        risk_categories=["supply_chain", "margin_compression"],
        strategic_categories=["Operational Efficiency"],
    ),
    StepTemplate(
        step_id="customer_service",
        label="Customer Service",
        description="Handle inquiries, complaints, and post-purchase support",
        category="primary",
        risk_categories=["customer_behavior", "talent_workforce"],
        strategic_categories=["Operational Efficiency", "Revenue Capture"],
    ),
    StepTemplate(
        step_id="returns",
        label="Returns & Logistics",
        description="Process returns, exchanges, and reverse logistics",
        category="primary",
        risk_categories=["supply_chain", "margin_compression"],
        strategic_categories=["Operational Efficiency"],
    ),
    StepTemplate(
        step_id="technology",
        label="Technology / Platform",
        description="E-commerce platform, payments, and data analytics",
        category="support",
        risk_categories=["technology_obsolescence", "data_ip"],
        strategic_categories=["Competitive Moat", "Operational Efficiency"],
    ),
]

# ---------------------------------------------------------------------------
# Manufacturing
# ---------------------------------------------------------------------------
MANUFACTURING_TEMPLATE = [
    StepTemplate(
        step_id="procurement",
        label="Raw Material Procurement",
        description="Source and purchase raw materials from suppliers",
        category="primary",
        risk_categories=["supply_chain", "margin_compression"],
        strategic_categories=["Operational Efficiency"],
    ),
    StepTemplate(
        step_id="production",
        label="Production / Assembly",
        description="Transform raw materials into finished products",
        category="primary",
        risk_categories=["technology_obsolescence", "talent_workforce"],
        strategic_categories=["Operational Efficiency", "Competitive Moat"],
    ),
    StepTemplate(
        step_id="quality_control",
        label="Quality Control",
        description="Inspect and test products to ensure quality standards",
        category="primary",
        risk_categories=["technology_obsolescence", "regulatory_compliance"],
        strategic_categories=["Operational Efficiency"],
    ),
    StepTemplate(
        step_id="distribution",
        label="Distribution & Logistics",
        description="Warehouse, ship, and deliver finished products",
        category="primary",
        risk_categories=["supply_chain", "margin_compression"],
        strategic_categories=["Operational Efficiency"],
    ),
    StepTemplate(
        step_id="sales_marketing",
        label="Sales & Marketing",
        description="Promote and sell products to customers and distributors",
        category="primary",
        risk_categories=["competitive_displacement", "customer_behavior"],
        strategic_categories=["Revenue Capture", "Market Expansion"],
    ),
    StepTemplate(
        step_id="after_sales",
        label="After-Sales Service",
        description="Warranty, maintenance, and spare parts support",
        category="primary",
        risk_categories=["customer_behavior", "talent_workforce"],
        strategic_categories=["Revenue Capture", "Competitive Moat"],
    ),
    StepTemplate(
        step_id="rnd",
        label="R&D / Product Design",
        description="Design new products and improve existing ones",
        category="support",
        risk_categories=["technology_obsolescence", "data_ip"],
        strategic_categories=["Competitive Moat", "Talent Strategy"],
    ),
]

# ---------------------------------------------------------------------------
# Financial Services
# ---------------------------------------------------------------------------
FINANCIAL_SERVICES_TEMPLATE = [
    StepTemplate(
        step_id="acquisition",
        label="Client Acquisition",
        description="Marketing, lead generation, and initial client outreach",
        category="primary",
        risk_categories=["competitive_displacement", "customer_behavior"],
        strategic_categories=["Revenue Capture", "Market Expansion"],
    ),
    StepTemplate(
        step_id="onboarding_kyc",
        label="Onboarding & KYC",
        description="Client verification, compliance checks, and account setup",
        category="primary",
        risk_categories=["regulatory_compliance", "technology_obsolescence"],
        strategic_categories=["Operational Efficiency"],
    ),
    StepTemplate(
        step_id="product_delivery",
        label="Product Delivery / Advisory",
        description="Deliver financial products, advice, and portfolio management",
        category="primary",
        risk_categories=["technology_obsolescence", "competitive_displacement"],
        strategic_categories=["Competitive Moat", "Revenue Capture"],
    ),
    StepTemplate(
        step_id="risk_management",
        label="Risk Management",
        description="Monitor and manage financial, credit, and operational risk",
        category="primary",
        risk_categories=["regulatory_compliance", "data_ip"],
        strategic_categories=["Operational Efficiency", "Competitive Moat"],
    ),
    StepTemplate(
        step_id="client_servicing",
        label="Client Servicing",
        description="Ongoing account management and client support",
        category="primary",
        risk_categories=["customer_behavior", "talent_workforce"],
        strategic_categories=["Revenue Capture", "Operational Efficiency"],
    ),
    StepTemplate(
        step_id="compliance",
        label="Reporting & Compliance",
        description="Regulatory reporting, audits, and compliance management",
        category="support",
        risk_categories=["regulatory_compliance", "technology_obsolescence"],
        strategic_categories=["Operational Efficiency"],
    ),
    StepTemplate(
        step_id="infrastructure",
        label="Technology / Infrastructure",
        description="Core systems, data platforms, and cybersecurity",
        category="support",
        risk_categories=["technology_obsolescence", "data_ip", "supply_chain"],
        strategic_categories=["Operational Efficiency", "Competitive Moat"],
    ),
]

# ---------------------------------------------------------------------------
# Template registry
# ---------------------------------------------------------------------------
TEMPLATES: dict[str, list[StepTemplate]] = {
    "saas": SAAS_TEMPLATE,
    "services": SERVICES_TEMPLATE,
    "ecommerce": ECOMMERCE_TEMPLATE,
    "manufacturing": MANUFACTURING_TEMPLATE,
    "financial_services": FINANCIAL_SERVICES_TEMPLATE,
}

MODEL_KEYWORDS: list[tuple[list[str], str]] = [
    (["saas", "software as a service", "subscription software"], "saas"),
    (["consulting", "professional service", "advisory", "agency"], "services"),
    (["e-commerce", "ecommerce", "marketplace", "retail", "dtc"], "ecommerce"),
    (["manufactur", "industrial", "hardware"], "manufacturing"),
    (["financial", "fintech", "banking", "insurance", "asset management"], "financial_services"),
]

DEFAULT_TEMPLATE_KEY = "saas"

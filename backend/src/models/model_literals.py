"""Literal types for the sc0red Services PE Risk Assessment domain."""

from typing import Literal

RiskScopeLiterals = Literal[
    "competitive_displacement",
    "technology_obsolescence",
    "talent_workforce",
    "margin_compression",
    "customer_behavior",
    "regulatory_compliance",
    "supply_chain",
    "data_ip",
]

RISK_SCOPE_NAMES: list[str] = [
    "competitive_displacement",
    "technology_obsolescence",
    "talent_workforce",
    "margin_compression",
    "customer_behavior",
    "regulatory_compliance",
    "supply_chain",
    "data_ip",
]

RISK_SCOPE_DISPLAY: dict[str, dict[str, str]] = {
    "competitive_displacement": {
        "name": "Competitive Displacement",
        "description": "Risk of AI-native competitors capturing market share",
    },
    "technology_obsolescence": {
        "name": "Technology Obsolescence",
        "description": "Risk that core products/services become obsolete due to AI",
    },
    "talent_workforce": {
        "name": "Talent & Workforce",
        "description": "Risk that AI automates key workforce functions",
    },
    "margin_compression": {
        "name": "Margin Compression",
        "description": "Risk that AI enables competitors to operate at dramatically lower costs",
    },
    "customer_behavior": {
        "name": "Customer Behavior Shift",
        "description": "Risk that customers adopt AI-powered alternatives",
    },
    "regulatory_compliance": {
        "name": "Regulatory & Compliance",
        "description": "Risk from emerging AI regulations",
    },
    "supply_chain": {
        "name": "Supply Chain & Vendor",
        "description": "Risk that key suppliers are disrupted by AI",
    },
    "data_ip": {
        "name": "Data & IP Vulnerability",
        "description": "Risk that proprietary data or IP loses value",
    },
}

AssessmentTypeLiterals = Literal[
    "company_analysis",
    "portfolio_scan",
]

DataStrategyLiterals = Literal[
    "web_scrape",
    "url_resolution",
    "portfolio_discovery",
]

StrategicCategoryLiterals = Literal[
    "Competitive Moat",
    "Revenue Capture",
    "Market Expansion",
    "Operational Efficiency",
    "Talent Strategy",
]

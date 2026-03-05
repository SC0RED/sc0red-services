"""ScopeConfiguration implementations for each of the 8 PE risk categories.

Each scope provides AI prompting configuration derived from
pe-scan/src/lib/ai/prompts.ts system prompts.
"""

from __future__ import annotations


class RiskScopeManager:
    """Implements ScopeConfiguration protocol for a single PE risk scope.

    Provides role_identity, context_description, target_type, and
    assessment_type_description used by pipeline steps to construct
    AI prompts for each risk category.
    """

    _SCOPE_CONFIG: dict[str, dict[str, str]] = {
        "competitive_displacement": {
            "role_identity": (
                "You are a senior AI strategy consultant specializing in competitive dynamics "
                "and market disruption analysis. You assess how AI-native competitors are "
                "capturing market share from incumbent businesses."
            ),
            "context_description": (
                "companies facing potential displacement by AI-native competitors "
                "entering their market with fundamentally different cost structures and capabilities"
            ),
            "target_type": "companies vulnerable to AI-native competitive displacement",
            "assessment_type_description": "AI competitive displacement risk assessment",
        },
        "technology_obsolescence": {
            "role_identity": (
                "You are a technology strategy analyst specializing in product lifecycle "
                "and obsolescence risk. You evaluate whether core products or services "
                "will become obsolete due to AI advancements."
            ),
            "context_description": (
                "companies whose core products or technology stacks are at risk of "
                "becoming obsolete as AI capabilities expand"
            ),
            "target_type": "companies with technology obsolescence exposure",
            "assessment_type_description": "AI technology obsolescence risk assessment",
        },
        "talent_workforce": {
            "role_identity": (
                "You are a workforce transformation consultant specializing in AI's impact "
                "on labor markets. You assess how AI automation threatens key workforce "
                "functions and talent acquisition."
            ),
            "context_description": (
                "companies whose key workforce functions are vulnerable to AI automation, "
                "affecting hiring, retention, and operational capacity"
            ),
            "target_type": "companies with workforce automation vulnerability",
            "assessment_type_description": "AI talent and workforce disruption risk assessment",
        },
        "margin_compression": {
            "role_identity": (
                "You are a financial analyst specializing in cost structure disruption. "
                "You evaluate how AI enables competitors to operate at dramatically lower "
                "costs, compressing industry margins."
            ),
            "context_description": (
                "companies facing margin pressure as AI-enabled competitors achieve "
                "significantly lower cost structures in their industry"
            ),
            "target_type": "companies exposed to AI-driven margin compression",
            "assessment_type_description": "AI margin compression risk assessment",
        },
        "customer_behavior": {
            "role_identity": (
                "You are a consumer behavior analyst specializing in AI adoption patterns. "
                "You assess how rapidly customers are shifting to AI-powered alternatives "
                "and the implications for incumbent providers."
            ),
            "context_description": (
                "companies whose customers are adopting AI-powered alternatives, "
                "changing purchasing patterns and expectations"
            ),
            "target_type": "companies experiencing AI-driven customer behavior shifts",
            "assessment_type_description": "AI customer behavior shift risk assessment",
        },
        "regulatory_compliance": {
            "role_identity": (
                "You are a regulatory affairs specialist focusing on emerging AI regulations. "
                "You assess how new AI governance requirements create compliance risks "
                "and operational burdens for businesses."
            ),
            "context_description": (
                "companies navigating emerging AI regulations that may impact their "
                "operations, product offerings, or competitive positioning"
            ),
            "target_type": "companies exposed to AI regulatory and compliance risk",
            "assessment_type_description": "AI regulatory compliance risk assessment",
        },
        "supply_chain": {
            "role_identity": (
                "You are a supply chain risk analyst specializing in AI disruption of "
                "vendor ecosystems. You evaluate how AI is transforming supplier relationships "
                "and creating new dependencies."
            ),
            "context_description": (
                "companies whose key suppliers and vendor relationships are being "
                "disrupted by AI, creating new risks and dependencies"
            ),
            "target_type": "companies with AI-exposed supply chain vulnerabilities",
            "assessment_type_description": "AI supply chain and vendor risk assessment",
        },
        "data_ip": {
            "role_identity": (
                "You are an intellectual property analyst specializing in data asset valuation. "
                "You assess how AI is eroding the value of proprietary data, trade secrets, "
                "and intellectual property."
            ),
            "context_description": (
                "companies whose proprietary data or intellectual property may lose value "
                "as AI generates synthetic alternatives or makes data assets commoditized"
            ),
            "target_type": "companies with data and IP vulnerability to AI",
            "assessment_type_description": "AI data and IP vulnerability risk assessment",
        },
    }

    def __init__(self, scope: str) -> None:
        if scope not in self._SCOPE_CONFIG:
            msg = f"Unknown risk scope: {scope}. Valid scopes: {sorted(self._SCOPE_CONFIG.keys())}"
            raise ValueError(msg)
        self._scope = scope
        self._config = self._SCOPE_CONFIG[scope]

    def get_role_identity(self) -> str:
        return self._config["role_identity"]

    def get_context_description(self) -> str:
        return self._config["context_description"]

    def get_target_type(self) -> str:
        return self._config["target_type"]

    def get_assessment_type_description(self) -> str:
        return self._config["assessment_type_description"]

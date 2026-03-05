"""DomainPlugin implementation for the PE Risk Assessment domain.

Wires Janus's domain-specific components (risk categories, company accessor,
data strategies) into the signalfield-core SDK framework.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.facades.company_accessor import CompanyAccessor
from src.models.model_company import Company
from src.utilities.scope_manager import RiskScopeManager

if TYPE_CHECKING:
    from signalfield_core.data.registry import DataStrategyRegistry
    from signalfield_core.domain.entity import EntityAccessor
    from signalfield_core.domain.scope import ScopeConfiguration


class PERiskAssessmentPlugin:
    """DomainPlugin for PE risk assessment.

    Satisfies the signalfield_core.domain.DomainPlugin protocol.
    """

    @property
    def domain_name(self) -> str:
        return "pe_risk_assessment"

    @property
    def event_source(self) -> str:
        return "signalfield.janus"

    def get_scope_names(self) -> list[str]:
        return sorted(RiskScopeManager._SCOPE_CONFIG.keys())

    def get_scope_configuration(self, scope: str) -> ScopeConfiguration:
        return RiskScopeManager(scope)

    def create_entity_accessor(self, **kwargs: Any) -> EntityAccessor:
        company = kwargs.get("company")
        if isinstance(company, Company):
            return CompanyAccessor(company)
        return CompanyAccessor()

    def register_data_strategies(self, registry: DataStrategyRegistry) -> None:
        from src.data_strategies.portfolio_discovery_strategy import PortfolioDiscoveryStrategy  # noqa: IMPORT (lazy to avoid circular deps)
        from src.data_strategies.url_resolution_strategy import URLResolutionStrategy  # noqa: IMPORT (lazy to avoid circular deps)
        from src.data_strategies.web_scraper_strategy import WebScraperStrategy  # noqa: IMPORT (lazy to avoid circular deps)

        registry.register(
            "web_scrape",
            lambda config: WebScraperStrategy(config),
        )
        registry.register(
            "url_resolution",
            lambda config: URLResolutionStrategy(config),
            dependencies=["web_scrape"],
        )
        registry.register(
            "portfolio_discovery",
            lambda config: PortfolioDiscoveryStrategy(config),
        )

    def get_assessment_types(self) -> list[str]:
        return ["company_analysis", "portfolio_scan"]

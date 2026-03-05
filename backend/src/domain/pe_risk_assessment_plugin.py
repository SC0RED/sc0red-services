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
        """Return the domain identifier for this plugin."""
        return "pe_risk_assessment"

    @property
    def event_source(self) -> str:
        """Return the event source identifier for this plugin."""
        return "signalfield.janus"

    def get_scope_names(self) -> list[str]:
        """Return sorted list of available risk scope names."""
        return sorted(RiskScopeManager._SCOPE_CONFIG.keys())

    def get_scope_configuration(self, scope: str) -> ScopeConfiguration:
        """Return the ScopeConfiguration instance for the given scope name."""
        return RiskScopeManager(scope)

    def create_entity_accessor(self, **kwargs: Any) -> EntityAccessor:
        """Create and return a CompanyAccessor for the given company entity."""
        company = kwargs.get("company")
        if isinstance(company, Company):
            return CompanyAccessor(company)
        return CompanyAccessor()

    def register_data_strategies(self, registry: DataStrategyRegistry) -> None:
        """Register all PE-domain data strategies with the provided registry."""
        from src.data_strategies.portfolio_discovery_strategy import (  # noqa: IMPORT001
            PortfolioDiscoveryStrategy,
        )
        from src.data_strategies.url_resolution_strategy import (  # noqa: IMPORT001
            URLResolutionStrategy,
        )
        from src.data_strategies.web_scraper_strategy import (  # noqa: IMPORT001
            WebScraperStrategy,
        )

        registry.register(
            "web_scrape",
            WebScraperStrategy,
        )
        registry.register(
            "url_resolution",
            URLResolutionStrategy,
            dependencies=["web_scrape"],
        )
        registry.register(
            "portfolio_discovery",
            PortfolioDiscoveryStrategy,
        )

    def get_assessment_types(self) -> list[str]:
        """Return the list of assessment types supported by this domain."""
        return ["company_analysis", "portfolio_scan"]

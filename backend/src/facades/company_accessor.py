"""EntityAccessor implementation for PE risk assessment companies.

Much simpler than Engine's FacilityFetcher (306 lines) since companies
have a flatter data model than facilities.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.models.model_company import Company

if TYPE_CHECKING:
    from src.models.model_company import (
        CompanyProfile,
        EbitdaTreeResult,
        OpportunityResult,
        RiskAssessment,
        ValueChainResult,
    )
    from src.models.model_strategy_map import StrategyMap


class CompanyAccessor:
    """Implements EntityAccessor protocol for Company entities.

    Provides the 7 read methods required by the SDK, plus PE-specific
    setters for pipeline steps to populate during execution.
    """

    def __init__(self, company: Company | None = None) -> None:
        self._company = company or Company()

    @property
    def company(self) -> Company:
        """Return the underlying company entity."""
        return self._company

    # ── EntityAccessor protocol (7 read methods) ─────────────────────

    def get_entity_id(self) -> str:
        """Return the entity ID."""
        return self._company.id

    def get_entity_name(self) -> str:
        """Return the entity name."""
        if self._company.profile:
            return self._company.profile.company_name
        return self._company.company_name

    def get_region(self) -> str:
        """Maps to industry_sector for the PE domain."""
        if self._company.profile:
            return self._company.profile.industry_sector
        return ""

    def get_probability(self) -> float:
        """Maps to overall_risk_score / 10 for the PE domain."""
        if self._company.risk_assessment:
            return self._company.risk_assessment.overall_score / 10.0
        return 0.0

    def get_total_score(self) -> float:
        """Returns the overall risk score (1-10 scale)."""
        if self._company.risk_assessment:
            return self._company.risk_assessment.overall_score
        return 0.0

    def get_categories(self) -> list[dict[str, Any]]:
        """Returns risk scores as category dicts."""
        if self._company.risk_assessment:
            return [rs.model_dump() for rs in self._company.risk_assessment.risk_scores]
        return []

    def has_dealbreaker_triggered(self) -> bool:
        """Returns True if risk tier is 'critical'."""
        if self._company.risk_assessment:
            return self._company.risk_assessment.tier == "critical"
        return False

    # ── PE-specific setters ──────────────────────────────────────────

    def set_profile(self, profile: CompanyProfile) -> None:
        """Set the company profile."""
        self._company.profile = profile

    def set_risk_assessment(self, assessment: RiskAssessment) -> None:
        """Set the company risk assessment."""
        self._company.risk_assessment = assessment

    def set_opportunities(self, result: OpportunityResult) -> None:
        """Set the company opportunity result."""
        self._company.opportunity_result = result

    def set_ebitda_tree(self, result: EbitdaTreeResult) -> None:
        """Set the EBITDA decomposition tree."""
        self._company.ebitda_tree = result

    def set_value_chain(self, result: ValueChainResult) -> None:
        """Set the value chain analysis."""
        self._company.value_chain = result

    def set_strategy_map(self, strategy_map: StrategyMap) -> None:
        """Set the AI-generated Balanced Scorecard strategy map."""
        self._company.strategy_map = strategy_map

    # NOTE: PDF export state intentionally has no accessor methods. The
    # state is persisted via `assessment_repository.save_pdf_export`
    # and never threaded through the pipeline — there's no current
    # pipeline step that needs to read or write it. Add accessor
    # methods here if (and only if) a step does.

    def set_url(self, url: str) -> None:
        """Set the company URL."""
        self._company.url = url

    def set_actual_url(self, actual_url: str) -> None:
        """Set the resolved actual URL."""
        self._company.actual_url = actual_url

    def set_id(self, entity_id: str) -> None:
        """Set the entity ID."""
        self._company.id = entity_id

    def set_scan_id(self, scan_id: str) -> None:
        """Set the scan ID."""
        self._company.scan_id = scan_id

    def set_org_id(self, org_id: str) -> None:
        """Set the organisation ID."""
        self._company.org_id = org_id

    def set_error(self, error: str) -> None:
        """Set the error message."""
        self._company.error = error

    def set_scraped_text(self, text: str) -> None:
        """Set the scraped page text."""
        self._company.scraped_text = text

    def get_scraped_text(self) -> str:
        """Return the scraped page text."""
        return self._company.scraped_text

    def set_scraped_links(self, links: list[dict[str, str]]) -> None:
        """Set the scraped page links."""
        self._company.scraped_links = links

    def get_scraped_links(self) -> list[dict[str, str]]:
        """Return the scraped page links."""
        return self._company.scraped_links

    def set_scraped_title(self, title: str) -> None:
        """Set the scraped page title."""
        self._company.scraped_title = title

    def get_scraped_title(self) -> str:
        """Return the scraped page title."""
        return self._company.scraped_title

    def set_document_text(self, text: str) -> None:
        """Set supplementary document text for enriched analysis."""
        self._company.document_text = text

    def get_document_text(self) -> str | None:
        """Return supplementary document text, or None if no documents uploaded."""
        return self._company.document_text

    def set_ranked_ideations(self, ideations: list[dict[str, Any]]) -> None:
        """Set the ranked opportunity ideations for the detail phase."""
        self._company.ranked_ideations = ideations

    def get_ranked_ideations(self) -> list[dict[str, Any]]:
        """Return the ranked opportunity ideations."""
        return self._company.ranked_ideations

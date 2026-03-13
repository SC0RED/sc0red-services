"""Pydantic models for the Janus PE Risk Assessment domain.

Ported from pe-scan/src/lib/ai/prompts.ts interfaces (lines 179-237).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class CompanyProfile(BaseModel):
    """Structured company profile extracted from website content."""

    company_name: str
    industry: str
    industry_sector: str = ""
    business_model: str = ""
    description: str = ""
    products_services: list[str] = Field(default_factory=list)
    target_market: str = ""
    company_size: str = ""
    revenue_model: str = ""
    tech_signals: list[str] = Field(default_factory=list)
    competitive_positioning: str = ""
    ai_maturity: str = ""
    key_risks_visible: list[str] = Field(default_factory=list)


class RiskScore(BaseModel):
    """Individual risk category assessment."""

    category: str
    score: float = Field(ge=1, le=10)
    explanation: str = ""
    evidence: str = ""


class RiskAssessment(BaseModel):
    """Overall risk analysis with per-category scores."""

    risk_scores: list[RiskScore] = Field(default_factory=list)
    overall_score: float = 0.0
    tier: str = "low"  # low | moderate | high | critical
    top_risks: list[str] = Field(default_factory=list)
    analysis_summary: str = ""


class Vendor(BaseModel):
    """Vendor recommendation within a related service."""

    name: str
    url: str = ""
    specialty: str = ""


class RelatedService(BaseModel):
    """Service type with vendor recommendations."""

    service_type: str
    vendors: list[Vendor] = Field(default_factory=list)


class Opportunity(BaseModel):
    """AI opportunity recommendation."""

    title: str
    risk_mitigated: str = ""
    impact_rating: str = ""  # High | Medium | Low
    strategic_category: str = ""
    description: str = ""
    implementation_steps: list[str] = Field(default_factory=list)
    timeline: str = ""
    investment_range: str = ""
    roi_estimate: str = ""
    related_services: list[str] = Field(default_factory=list)
    value_lever: Literal["Revenue Side", "Cost Side", "Both"] | None = None


class OpportunityResult(BaseModel):
    """Container for opportunity recommendations."""

    opportunities: list[Opportunity] = Field(default_factory=list)
    top_three_immediate_actions: list[str] = Field(default_factory=list)


class EbitdaNode(BaseModel):
    """Single node in the EBITDA decomposition tree."""

    id: str
    label: str
    type: Literal["revenue", "cost", "margin", "subtotal"]
    value_range: str | None = None
    percentage_of_parent: float | None = None
    parent_id: str | None = None
    description: str = ""
    linked_opportunity_indices: list[int] = Field(default_factory=list)
    children: list[EbitdaNode] = Field(default_factory=list)


class EbitdaTreeResult(BaseModel):
    """EBITDA decomposition tree mapping AI opportunities to P&L line items."""

    summary: str = ""
    revenue_estimate: str = ""
    ebitda_estimate: str = ""
    nodes: list[EbitdaNode] = Field(default_factory=list)


class Company(BaseModel):
    """Full company entity combining profile, risk, and opportunities."""

    model_config = {"arbitrary_types_allowed": True}

    id: str = ""
    scan_id: str = ""
    org_id: str = ""
    company_name: str = ""
    url: str = ""
    actual_url: str = ""
    profile: CompanyProfile | None = None
    risk_assessment: RiskAssessment | None = None
    opportunity_result: OpportunityResult | None = None
    ebitda_tree: EbitdaTreeResult | None = None
    error: str | None = None
    analyzed_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    # Transient fields for pipeline execution (not persisted)
    scraped_text: str = Field(default="", exclude=True)
    scraped_links: list[dict[str, str]] = Field(default_factory=list, exclude=True)
    scraped_title: str = Field(default="", exclude=True)

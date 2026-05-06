"""Pydantic models for the Janus PE Risk Assessment domain.

Ported from pe-scan/src/lib/ai/prompts.ts interfaces (lines 179-237).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from src.models.model_strategy_map import (
    StrategyMap,  # noqa: TC001  pydantic field annotation needs runtime resolution
)


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
    rationale: str = ""


class RiskAssessment(BaseModel):
    """Overall risk analysis with per-category scores."""

    risk_scores: list[RiskScore] = Field(default_factory=list)
    overall_score: float = 0.0
    tier: Literal["low", "moderate", "high", "critical"] = "low"
    top_risks: list[str] = Field(default_factory=list)
    analysis_summary: str = ""


class Opportunity(BaseModel):
    """AI opportunity recommendation."""

    title: str
    impact_rating: str = ""  # High | Medium | Low
    strategic_category: str = ""
    description: str = ""
    implementation_steps: list[str] = Field(default_factory=list)
    timeline: str = ""
    investment_range: str = ""
    roi_estimate: str = ""
    value_lever: Literal["Revenue Side", "Cost Side", "Both"] | None = None


class OpportunityResult(BaseModel):
    """Container for opportunity recommendations."""

    opportunities: list[Opportunity] = Field(default_factory=list)
    top_three_immediate_actions: list[str] = Field(default_factory=list)


class EbitdaNode(BaseModel):
    """Single node in the EBITDA decomposition tree.

    The optional ``confidence_level`` and ``confidence_basis`` fields surface the
    derivation provenance of leaf nodes — see
    ``src.pipeline.pipeline_steps.build_ebitda_tree`` and the
    ``ebitda-tree-confidence`` capability spec for the rules that produce them.
    Both are ``None`` for rollup/subtotal nodes (which inherit visually via their
    children's chips) and for any record stored before this field was introduced.
    """

    id: str
    label: str
    type: Literal["revenue", "cost", "margin", "subtotal"]
    value_range: str | None = None
    percentage_of_parent: float | None = None
    description: str = ""
    linked_opportunity_indices: list[int] = Field(default_factory=list)
    children: list[EbitdaNode] = Field(default_factory=list)
    confidence_level: Literal["high", "medium", "low"] | None = None
    confidence_basis: str | None = None


class EbitdaTreeResult(BaseModel):
    """EBITDA decomposition tree mapping AI opportunities to P&L line items."""

    summary: str = ""
    revenue_estimate: str = ""
    ebitda_estimate: str = ""
    nodes: list[EbitdaNode] = Field(default_factory=list)


class ValueChainStep(BaseModel):
    """Single step in a company's value chain."""

    id: str
    label: str
    description: str = ""
    category: Literal["primary", "support"] = "primary"
    risk_categories: list[str] = Field(default_factory=list)
    opportunity_indices: list[int] = Field(default_factory=list)


class ValueChainResult(BaseModel):
    """Value chain analysis mapping risks and opportunities to operational steps."""

    steps: list[ValueChainStep] = Field(default_factory=list)
    summary: str = ""


class Company(BaseModel):
    """Full company entity combining profile, risk, and opportunities."""

    model_config = {"arbitrary_types_allowed": True}

    id: str = ""
    scan_id: str = ""
    org_id: str = ""
    # Internal user id of the actor who triggered this company analysis.
    # Persisted as `created_by` on the company record; the activity feed
    # reads it for `analysis_completed` events. See
    # `openspec/changes/fix-actor-attribution/`.
    user_id: str = ""
    company_name: str = ""
    url: str = ""
    actual_url: str = ""
    profile: CompanyProfile | None = None
    risk_assessment: RiskAssessment | None = None
    opportunity_result: OpportunityResult | None = None
    ebitda_tree: EbitdaTreeResult | None = None
    value_chain: ValueChainResult | None = None
    strategy_map: StrategyMap | None = None
    error: str | None = None
    analyzed_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    # Transient fields for pipeline execution (not persisted)
    scraped_text: str = Field(default="", exclude=True)
    scraped_links: list[dict[str, str]] = Field(default_factory=list, exclude=True)
    scraped_title: str = Field(default="", exclude=True)
    document_text: str | None = Field(default=None, exclude=True)
    ranked_ideations: list[dict[str, Any]] = Field(default_factory=list, exclude=True)

"""Programmatic value chain builder — maps risks and opportunities to operational steps.

Builds a value chain from the company profile using business-model-specific templates.
Each step is linked to relevant risk categories and opportunities. No AI call needed.

Templates are defined in value_chain_templates.py (split for file size limit).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from src.models.model_company import ValueChainResult, ValueChainStep
from src.pipeline.pipeline_steps.value_chain_templates import (
    MODEL_KEYWORDS,
    TEMPLATES,
)

if TYPE_CHECKING:
    from src.models.model_company import CompanyProfile, Opportunity
    from src.pipeline.pipeline_steps.value_chain_templates import StepTemplate

logger = logging.getLogger(__name__)


def _resolve_template(business_model: str) -> tuple[str, list[StepTemplate]] | None:
    """Match a free-text business_model string to the closest template.

    Returns ``(template_key, steps)`` for a match, or ``None`` when no keyword in
    ``MODEL_KEYWORDS`` fires. There is deliberately NO default template — an
    unmatched model is reported as ungrounded by the builder, not fabricated as
    SaaS. See the value-chain-grounding spec.
    """
    lower = business_model.lower()
    for keywords, key in MODEL_KEYWORDS:
        for keyword in keywords:
            if keyword in lower:
                return key, TEMPLATES[key]
    return None


# ---------------------------------------------------------------------------
# Opportunity linking
# ---------------------------------------------------------------------------


def _link_opportunities(
    steps: list[ValueChainStep],
    template_steps: list[StepTemplate],
    opportunities: list[Opportunity],
) -> None:
    """Link opportunities to value chain steps by strategic_category + value_lever."""
    template_by_id = {t.id: t for t in template_steps}

    for step in steps:
        template = template_by_id.get(step.id)
        if not template:
            continue

        for opp_index, opportunity in enumerate(opportunities):
            if opportunity.strategic_category not in template.strategic_categories:
                continue
            if step.category == "support" and opportunity.value_lever == "Revenue Side":
                continue
            step.opportunity_indices.append(opp_index)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def build_programmatic_value_chain(
    profile: CompanyProfile,
    opportunities: list[Opportunity] | None = None,
) -> ValueChainResult:
    """Build a value chain from the company profile using business model templates.

    Each step is linked to relevant risk categories (static mapping) and
    opportunities (matched by strategic_category + value_lever).

    When ``business_model`` matches no template, returns an ungrounded placeholder
    result instead of fabricating a default SaaS value chain (value-chain-grounding
    spec).
    """
    resolved = _resolve_template(profile.business_model)
    if resolved is None:
        shown = profile.business_model.strip() or "unknown"
        reason = (
            f"Could not determine how this business operates from available public "
            f"sources (business model: {shown!r}). The operating model is mapped only "
            f"when it can be grounded in evidence."
        )
        logger.info(
            "Value chain ungrounded: business_model=%r matched no template — "
            "returning insufficient-data placeholder",
            profile.business_model,
        )
        return ValueChainResult(grounded=False, insufficient_data_reason=reason)

    template_key, template_steps = resolved

    logger.info(
        "Building value chain: business_model=%s template=%s steps=%d",
        profile.business_model,
        template_key,
        len(template_steps),
    )

    steps = [
        ValueChainStep(
            id=step.id,
            label=step.label,
            description=step.description,
            category=step.category,
            risk_categories=list(step.risk_categories),
        )
        for step in template_steps
    ]

    if opportunities:
        _link_opportunities(steps, template_steps, opportunities)

    primary_count = sum(1 for s in steps if s.category == "primary")
    support_count = sum(1 for s in steps if s.category == "support")

    summary = (
        f"{profile.company_name} value chain: {primary_count} primary activities "
        f"and {support_count} support activities based on {template_key} model"
    )

    provenance_basis = (
        f"Operating model derived from a {template_key} template "
        f"(matched on business model {profile.business_model!r})."
    )

    return ValueChainResult(
        steps=steps,
        summary=summary,
        provenance_basis=provenance_basis,
    )

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
    DEFAULT_TEMPLATE_KEY,
    MODEL_KEYWORDS,
    TEMPLATES,
)

if TYPE_CHECKING:
    from src.models.model_company import CompanyProfile, Opportunity
    from src.pipeline.pipeline_steps.value_chain_templates import StepTemplate

logger = logging.getLogger(__name__)


def _resolve_template(business_model: str) -> tuple[str, list[StepTemplate]]:
    """Match a free-text business_model string to the closest template."""
    lower = business_model.lower()
    for keywords, key in MODEL_KEYWORDS:
        for keyword in keywords:
            if keyword in lower:
                return key, TEMPLATES[key]
    return DEFAULT_TEMPLATE_KEY, TEMPLATES[DEFAULT_TEMPLATE_KEY]


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
    """
    template_key, template_steps = _resolve_template(profile.business_model)

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

    return ValueChainResult(steps=steps, summary=summary)

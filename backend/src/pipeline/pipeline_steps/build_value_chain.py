"""Value chain assembler — builds the operating model from researched facts.

Replaces the old business-model-template builder: the value-chain steps now come
from the decomposed research DAG's ``operating_steps`` answer (real activities for
this specific business — e.g. lead-gen → enrollment → negotiation → settlement →
servicing for a debt-settlement firm), not a generic SaaS/Professional-Services
template. Each step carries a provenance tier + deterministic confidence. See the
``value-chain-grounding`` + ``fact-provenance-labeling`` capabilities.

When the research can't support a grounded operating model, the report falls to
the "insufficient public data" placeholder per ``report-data-integrity``.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any, Literal

from src.models.model_company import ValueChainResult, ValueChainStep
from src.pipeline.pipeline_steps._provenance import confidence_from_provenance

if TYPE_CHECKING:
    from src.models.model_literals import ProvenanceTier
    from src.pipeline.pipeline_steps._financial_research import FinancialResearchFacts

logger = logging.getLogger(__name__)


def _slug(label: str, fallback: str) -> str:
    """Derive a stable step id from a free-text label."""
    slug = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")
    return slug or fallback


def _steps(
    items: list[dict[str, Any]],
    category: Literal["primary", "support"],
    provenance: ProvenanceTier,
    confidence: Literal["high", "medium", "low"],
    basis: str,
) -> list[ValueChainStep]:
    """Build ValueChainStep objects from researched {label, description} items."""
    steps: list[ValueChainStep] = []
    for index, item in enumerate(items):
        label = str(item.get("label", "Activity"))
        steps.append(
            ValueChainStep(
                id=_slug(label, f"{category}_{index}"),
                label=label,
                description=str(item.get("description", "")),
                category=category,
                confidence_level=confidence,
                confidence_basis=basis,
                provenance=provenance,
            )
        )
    return steps


def assemble_value_chain(  # noqa: NAMING001  "assemble" is a verb; validator list is partial
    facts: FinancialResearchFacts, company_name: str
) -> ValueChainResult:
    """Assemble the value chain from the researched operating-model steps.

    Returns the insufficient-data placeholder when the research produced no
    operating steps. Confidence is deterministic from the operating-model
    provenance tier (downgraded if the revenue model was judged implausible).
    """
    operating = facts.operating_steps
    primary_items = operating.get("primary_steps", [])
    support_items = operating.get("support_steps", [])
    if not primary_items and not support_items:
        return ValueChainResult(
            grounded=False,
            insufficient_data_reason=(
                "Could not determine how this business operates from available public "
                "sources; the operating model is shown only when it can be grounded."
            ),
        )

    provenance: ProvenanceTier = operating.get("provenance", "industry_typical")
    basis = str(operating.get("basis", ""))
    confidence = confidence_from_provenance(provenance, plausible=facts.revenue_model_plausible)

    steps = [
        *_steps(primary_items, "primary", provenance, confidence, basis),
        *_steps(support_items, "support", provenance, confidence, basis),
    ]
    primary_count = sum(1 for step in steps if step.category == "primary")
    support_count = len(steps) - primary_count
    summary = (
        f"{company_name} value chain: {primary_count} primary activities and "
        f"{support_count} support activities for a {facts.company_type}."
    )
    provenance_basis = basis or f"Operating model researched for a {facts.company_type}."
    logger.info(
        "Assembled value chain: company_type=%s primary=%d support=%d provenance=%s",
        facts.company_type,
        primary_count,
        support_count,
        provenance,
    )
    return ValueChainResult(
        steps=steps,
        summary=summary,
        grounded=True,
        provenance_basis=provenance_basis,
    )

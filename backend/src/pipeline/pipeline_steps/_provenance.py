"""Deterministic provenance → confidence rules for researched facts.

Owns the pure, auditable mapping from a fact's provenance tier (and an optional
adversarial plausibility verdict) to a confidence level, plus reconciliation of
a model-declared tier against whether a real citation actually exists. Confidence
is NEVER AI-self-rated — same reproducible philosophy as the original
``ebitda-tree-confidence`` labels. See the ``fact-provenance-labeling`` capability.

Module-private to the financial-research pipeline.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from src.models.model_literals import ProvenanceTier

ConfidenceLevel = Literal["high", "medium", "low"]

# Base confidence by provenance tier (before any plausibility downgrade).
_TIER_CONFIDENCE: dict[str, ConfidenceLevel] = {
    "disclosed": "high",
    "industry_typical": "medium",
    "derived_estimate": "low",
}

# Single-notch downgrade ladder for an implausible adversarial verdict.
_DOWNGRADE: dict[ConfidenceLevel, ConfidenceLevel] = {
    "high": "medium",
    "medium": "low",
    "low": "low",
}


def confidence_from_provenance(tier: ProvenanceTier, *, plausible: bool = True) -> ConfidenceLevel:
    """Map a provenance tier to a deterministic confidence level.

    ``disclosed`` → high, ``industry_typical`` → medium, ``derived_estimate`` →
    low. An implausible adversarial verdict (``plausible=False``) downgrades one
    notch but never raises confidence. The result is a pure function of its
    inputs — identical inputs always produce the same level.
    """
    base = _TIER_CONFIDENCE[tier]
    return _DOWNGRADE[base] if not plausible else base


def reconcile_provenance(declared_tier: ProvenanceTier, *, has_citation: bool) -> ProvenanceTier:
    """Reconcile a model-declared provenance tier against reality.

    A fact the model claims is ``disclosed`` MUST carry a citation; if none
    exists, it is downgraded to ``industry_typical`` (a value the model knows but
    cannot source). Other tiers pass through unchanged. This prevents an
    unsourced number from being presented with the authority of a cited fact.
    """
    if declared_tier == "disclosed" and not has_citation:
        return "industry_typical"
    return declared_tier

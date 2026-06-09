"""Tests for the deterministic provenance → confidence rules.

Pins the fact-provenance-labeling contract: confidence is a pure function of
the provenance tier (+ plausibility verdict), never AI-self-rated, and a
claimed-disclosed fact without a citation is downgraded.
"""

from __future__ import annotations

from src.pipeline.pipeline_steps._provenance import (
    confidence_from_provenance,
    reconcile_provenance,
)


class TestConfidenceFromProvenance:
    def test_tier_mapping(self):
        assert confidence_from_provenance("disclosed") == "high"
        assert confidence_from_provenance("industry_typical") == "medium"
        assert confidence_from_provenance("derived_estimate") == "low"

    def test_implausible_downgrades_one_notch(self):
        assert confidence_from_provenance("disclosed", plausible=False) == "medium"
        assert confidence_from_provenance("industry_typical", plausible=False) == "low"
        assert confidence_from_provenance("derived_estimate", plausible=False) == "low"

    def test_deterministic_same_inputs_same_output(self):
        assert confidence_from_provenance("disclosed") == confidence_from_provenance("disclosed")

    def test_plausibility_never_raises_confidence(self):
        order = {"low": 0, "medium": 1, "high": 2}
        for tier in ("disclosed", "industry_typical", "derived_estimate"):
            implausible = order[confidence_from_provenance(tier, plausible=False)]
            plausible = order[confidence_from_provenance(tier)]
            assert implausible <= plausible


class TestReconcileProvenance:
    def test_disclosed_without_citation_downgraded(self):
        assert reconcile_provenance("disclosed", has_citation=False) == "industry_typical"

    def test_disclosed_with_citation_kept(self):
        assert reconcile_provenance("disclosed", has_citation=True) == "disclosed"

    def test_other_tiers_pass_through(self):
        assert reconcile_provenance("industry_typical", has_citation=False) == "industry_typical"
        assert reconcile_provenance("derived_estimate", has_citation=True) == "derived_estimate"

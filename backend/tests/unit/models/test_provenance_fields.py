"""Tests for the additive provenance fields on EBITDA/value-chain models.

Pins: new provenance fields default to absent (so pre-change records deserialize
unchanged) and accept the researched-pipeline shape when present.
"""

from __future__ import annotations

from src.models.model_company import Citation, EbitdaNode, ValueChainStep


class TestEbitdaNodeProvenance:
    def test_defaults_absent(self):
        node = EbitdaNode(id="revenue", label="Total Revenue", type="revenue")
        assert node.provenance is None
        assert node.citations == []

    def test_legacy_payload_deserializes(self):
        # A node stored before provenance fields existed.
        node = EbitdaNode.model_validate(
            {
                "id": "revenue",
                "label": "Total Revenue",
                "type": "revenue",
                "value_range": "$5M-$20M",
                "description": "Total annual revenue",
                "children": [],
            }
        )
        assert node.provenance is None
        assert node.citations == []

    def test_researched_node_carries_provenance_and_citation(self):
        node = EbitdaNode(
            id="revenue",
            label="Total Revenue",
            type="revenue",
            value_range="~$90M",
            confidence_level="high",
            confidence_basis="Reported in 2024 press release.",
            provenance="disclosed",
            citations=[Citation(url="https://example.com/pr", title="2024 results")],
        )
        assert node.provenance == "disclosed"
        assert node.citations[0].url == "https://example.com/pr"


class TestValueChainStepProvenance:
    def test_defaults_absent(self):
        step = ValueChainStep(id="intake", label="Client Intake")
        assert step.provenance is None
        assert step.citations == []
        assert step.confidence_level is None

    def test_legacy_payload_deserializes(self):
        step = ValueChainStep.model_validate(
            {
                "id": "intake",
                "label": "Client Intake",
                "description": "Screen prospects",
                "category": "primary",
                "risk_categories": [],
                "opportunity_indices": [],
            }
        )
        assert step.provenance is None
        assert step.citations == []

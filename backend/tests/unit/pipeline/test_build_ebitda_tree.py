"""Tests for the EBITDA tree assembler (assemble_ebitda_tree over researched facts)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from src.models.model_company import EbitdaTreeResult
from src.pipeline.pipeline_steps._financial_research import FinancialResearchFacts
from src.pipeline.pipeline_steps.build_ebitda_tree import (
    _format_currency,
    _format_range,
    assemble_ebitda_tree,
)


def _facts(**over: Any) -> FinancialResearchFacts:
    base: dict[str, Any] = {
        "company_type": "consumer debt-settlement firm",
        "revenue_model": {
            "revenue_model": "Success fee on enrolled debt",
            "fee_structure": "15-25% of enrolled debt",
            "provenance": "industry_typical",
            "basis": "industry knowledge",
        },
        "disclosed_figures": {"found": False, "figures": []},
        "scale_signals": {"signals": ["265+ staff"], "employee_estimate": "~265", "basis": "site"},
        "revenue_mix": {
            "streams": [{"label": "Success fees", "pct": 95}, {"label": "Ancillary", "pct": 5}],
            "provenance": "industry_typical",
            "basis": "success-fee model",
        },
        "margins": {
            "gross_margin_low": 40,
            "gross_margin_high": 60,
            "ebitda_margin_low": 15,
            "ebitda_margin_high": 30,
            "provenance": "industry_typical",
            "basis": "benchmark",
        },
        "revenue_range": {
            "revenue_low_usd": 60_000_000,
            "revenue_high_usd": 120_000_000,
            "provenance": "derived_estimate",
            "basis": "~265 staff x rev/head",
            "source_url": "",
        },
        "cost_drivers": {
            "cogs_items": [{"label": "Negotiation labour", "pct": 70}],
            "opex_items": [{"label": "Marketing & lead-gen", "pct": 60}],
            "provenance": "industry_typical",
            "basis": "model",
        },
        "operating_steps": {
            "primary_steps": [{"label": "Enrollment", "description": "Sign up"}],
            "support_steps": [{"label": "Compliance", "description": "Stay compliant"}],
            "provenance": "industry_typical",
            "basis": "model",
        },
        "revenue_model_plausible": True,
        "citations": {},
    }
    base.update(over)
    return FinancialResearchFacts(**base)


class TestAssembleEbitdaTree:
    def test_five_root_nodes(self):
        result = assemble_ebitda_tree(_facts(), "Century Support Services, LLC")
        assert result.grounded is True
        assert [n.id for n in result.nodes] == ["revenue", "cogs", "gross_profit", "opex", "ebitda"]

    def test_revenue_estimate_from_researched_range(self):
        result = assemble_ebitda_tree(_facts(), "Century")
        assert result.revenue_estimate == "$60M-$120M"

    def test_no_template_artifacts_uses_researched_mix(self):
        result = assemble_ebitda_tree(_facts(), "Century")
        labels = [c.label for c in result.nodes[0].children]
        assert "Success fees" in labels
        assert "Subscriptions" not in labels
        assert "Project-Based Revenue" not in labels
        # COGS uses researched cost drivers, not template R&D/cloud.
        cogs_labels = [c.label for c in result.nodes[1].children]
        assert "Negotiation labour" in cogs_labels

    def test_ebitda_estimate_uses_researched_margins(self):
        result = assemble_ebitda_tree(_facts(), "Century")
        assert "15-30% margin" in result.ebitda_estimate

    def test_derived_estimate_revenue_is_low_confidence(self):
        result = assemble_ebitda_tree(_facts(), "Century")
        revenue = result.nodes[0]
        assert revenue.provenance == "derived_estimate"
        assert revenue.confidence_level == "low"
        assert revenue.citations == []

    def test_disclosed_revenue_is_high_confidence_with_citation(self):
        facts = _facts(
            revenue_range={
                "revenue_low_usd": 90_000_000,
                "revenue_high_usd": 90_000_000,
                "provenance": "disclosed",
                "basis": "2024 press release",
                "source_url": "https://example.com/pr",
            },
            citations={"revenue_range": [SimpleNamespace(url="https://example.com/pr", title="PR")]},
        )
        result = assemble_ebitda_tree(facts, "Century")
        revenue = result.nodes[0]
        assert revenue.provenance == "disclosed"
        assert revenue.confidence_level == "high"
        assert revenue.citations[0].url == "https://example.com/pr"

    def test_claimed_disclosed_without_citation_downgraded(self):
        facts = _facts(
            revenue_range={
                "revenue_low_usd": 90_000_000,
                "revenue_high_usd": 100_000_000,
                "provenance": "disclosed",
                "basis": "claim",
                "source_url": "",
            },
            citations={},
        )
        result = assemble_ebitda_tree(facts, "Century")
        assert result.nodes[0].provenance == "industry_typical"
        assert result.nodes[0].confidence_level == "medium"

    def test_invalid_range_renders_placeholder(self):
        facts = _facts(
            revenue_range={
                "revenue_low_usd": 0,
                "revenue_high_usd": 0,
                "provenance": "derived_estimate",
                "basis": "no signal",
                "source_url": "",
            }
        )
        result = assemble_ebitda_tree(facts, "Century")
        assert result.grounded is False
        assert result.nodes == []
        assert result.insufficient_data_reason


class TestFormatHelpers:
    def test_currency(self):
        assert _format_currency(90_000_000) == "$90M"
        assert _format_currency(2_000_000_000) == "$2B"

    def test_range(self):
        assert _format_range(60_000_000, 120_000_000) == "$60M-$120M"


class TestEbitdaTreeBackwardCompat:
    def test_legacy_payload_deserializes(self):
        result = EbitdaTreeResult.model_validate(
            {"summary": "x", "revenue_estimate": "$5M", "ebitda_estimate": "$1M", "nodes": []}
        )
        assert result.grounded is True
        assert result.insufficient_data_reason is None

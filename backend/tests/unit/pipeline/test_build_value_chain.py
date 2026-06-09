"""Tests for the value chain assembler (assemble_value_chain over researched facts)."""

from __future__ import annotations

from typing import Any

from src.models.model_company import ValueChainResult
from src.pipeline.pipeline_steps._financial_research import FinancialResearchFacts
from src.pipeline.pipeline_steps.build_value_chain import assemble_value_chain


def _facts(**over: Any) -> FinancialResearchFacts:
    base: dict[str, Any] = {
        "company_type": "consumer debt-settlement firm",
        "revenue_model": {
            "revenue_model": "Success fee",
            "fee_structure": "15-25%",
            "provenance": "industry_typical",
            "basis": "x",
        },
        "disclosed_figures": {"found": False, "figures": []},
        "scale_signals": {"signals": [], "employee_estimate": "~265", "basis": "x"},
        "revenue_mix": {"streams": [], "provenance": "industry_typical", "basis": "x"},
        "margins": {
            "gross_margin_low": 40,
            "gross_margin_high": 60,
            "ebitda_margin_low": 15,
            "ebitda_margin_high": 30,
            "provenance": "industry_typical",
            "basis": "x",
        },
        "revenue_range": {
            "revenue_low_usd": 60_000_000,
            "revenue_high_usd": 120_000_000,
            "provenance": "derived_estimate",
            "basis": "x",
            "source_url": "",
        },
        "cost_drivers": {
            "cogs_items": [],
            "opex_items": [],
            "provenance": "industry_typical",
            "basis": "x",
        },
        "operating_steps": {
            "primary_steps": [
                {"label": "Lead generation", "description": "Attract debtors"},
                {"label": "Enrollment", "description": "Sign up clients"},
                {"label": "Creditor negotiation", "description": "Negotiate settlements"},
                {"label": "Settlement", "description": "Execute settlements"},
            ],
            "support_steps": [{"label": "Compliance", "description": "Regulatory"}],
            "provenance": "industry_typical",
            "basis": "debt-settlement operating model",
        },
        "revenue_model_plausible": True,
        "citations": {},
    }
    base.update(over)
    return FinancialResearchFacts(**base)


class TestAssembleValueChain:
    def test_uses_researched_operating_steps(self):
        result = assemble_value_chain(_facts(), "Century")
        assert result.grounded is True
        labels = [s.label for s in result.steps]
        assert "Creditor negotiation" in labels
        # Not the generic SaaS / Professional-Services template steps.
        assert "Renewal & Expansion" not in labels
        assert "Proposal & Scoping" not in labels

    def test_primary_and_support_categories(self):
        result = assemble_value_chain(_facts(), "Century")
        primary = [s for s in result.steps if s.category == "primary"]
        support = [s for s in result.steps if s.category == "support"]
        assert len(primary) == 4
        assert len(support) == 1

    def test_disclosed_steps_cite_the_company_website(self):
        # A site-grounded "disclosed" operating model gets the company URL as its
        # citation so the tier carries a source (fact-provenance-labeling).
        facts = _facts(
            operating_steps={
                "primary_steps": [{"label": "Enrollment", "description": "Sign up"}],
                "support_steps": [],
                "provenance": "disclosed",
                "basis": "Based on the website's described flow",
            }
        )
        result = assemble_value_chain(facts, "Century", "https://www.centuryss.com/")
        step = result.steps[0]
        assert step.provenance == "disclosed"
        assert step.confidence_level == "high"
        assert step.citations[0].url == "https://www.centuryss.com/"
        assert step.citations[0].title == "Company website"

    def test_non_disclosed_steps_have_no_citation(self):
        # industry_typical fixture → no citation even when a URL is available.
        result = assemble_value_chain(_facts(), "Century", "https://www.centuryss.com/")
        assert result.steps[0].provenance == "industry_typical"
        assert result.steps[0].citations == []

    def test_disclosed_without_url_downgrades_to_industry_typical(self):
        # No URL to cite → an unsourced "disclosed" claim is downgraded rather
        # than emitted citation-less (same reconcile rule as the EBITDA node).
        facts = _facts(
            operating_steps={
                "primary_steps": [{"label": "Enrollment", "description": "Sign up"}],
                "support_steps": [],
                "provenance": "disclosed",
                "basis": "site flow",
            }
        )
        result = assemble_value_chain(facts, "Century", company_url="")
        step = result.steps[0]
        assert step.provenance == "industry_typical"
        assert step.confidence_level == "medium"
        assert step.citations == []

    def test_steps_carry_provenance_and_confidence(self):
        result = assemble_value_chain(_facts(), "Century")
        step = result.steps[0]
        assert step.provenance == "industry_typical"
        assert step.confidence_level == "medium"
        assert result.provenance_basis

    def test_no_operating_steps_renders_placeholder(self):
        facts = _facts(
            operating_steps={
                "primary_steps": [],
                "support_steps": [],
                "provenance": "industry_typical",
                "basis": "",
            }
        )
        result = assemble_value_chain(facts, "Century")
        assert result.grounded is False
        assert result.steps == []
        assert result.insufficient_data_reason


class TestValueChainBackwardCompat:
    def test_legacy_payload_deserializes(self):
        result = ValueChainResult.model_validate({"steps": [], "summary": "x"})
        assert result.grounded is True
        assert result.provenance_basis is None

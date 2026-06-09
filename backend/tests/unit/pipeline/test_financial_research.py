"""Tests for the decomposed financial-research orchestrator (the question DAG).

Mocks the shared AI-call functions so we exercise the round structure, the
R1→R2 dependency wiring, web-search source capture, and the verification verdict
without real model calls.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from src.pipeline.pipeline_steps import _financial_research as fr

# Canned content per question label (only the keys the orchestrator reads matter).
_CONTENT: dict[str, dict[str, Any]] = {
    "company_type": {"company_type": "consumer debt-settlement firm", "basis": "site"},
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
        "basis": "model",
    },
    "margin_band": {
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
        "basis": "265 staff x rev/head",
        "source_url": "",
    },
    "cost_drivers": {
        "cogs_items": [{"label": "Negotiation labour", "pct": 70}],
        "opex_items": [{"label": "Marketing", "pct": 60}],
        "provenance": "industry_typical",
        "basis": "model",
    },
    "operating_steps": {
        "primary_steps": [{"label": "Enrollment", "description": "Sign up clients"}],
        "support_steps": [{"label": "Compliance", "description": "Stay compliant"}],
        "provenance": "industry_typical",
        "basis": "model",
    },
    "verify_revenue_model": {"plausible": True, "reason": "matches site"},
}


def _fake_structured(*, label: str, **_: Any):
    return label, _CONTENT[label], 0.1, MagicMock()


def _fake_grounded(*, label: str, **_: Any):
    sources = [MagicMock()] if label == "revenue_range" else []
    return label, _CONTENT[label], 0.1, MagicMock(), sources


def _run():
    with (
        patch.object(fr, "run_structured_ai_call", side_effect=_fake_structured),
        patch.object(fr, "run_grounded_ai_call", side_effect=_fake_grounded),
    ):
        return fr.run_financial_research(
            MagicMock(),
            company_name="Century Support Services, LLC",
            url="https://centuryss.com",
            industry="Consumer debt settlement",
            scraped_text="debt relief, free assessment, 265+ teammates",
        )


class TestRunFinancialResearch:
    def test_returns_assembled_facts(self):
        facts = _run()
        assert facts.company_type == "consumer debt-settlement firm"
        assert facts.revenue_model["revenue_model"] == "Success fee on enrolled debt"
        assert facts.revenue_mix["streams"][0]["label"] == "Success fees"
        assert facts.revenue_range["revenue_low_usd"] == 60_000_000
        assert facts.revenue_model_plausible is True

    def test_no_saas_or_template_artifacts(self):
        facts = _run()
        labels = [s["label"].lower() for s in facts.revenue_mix["streams"]]
        assert not any("subscription" in label for label in labels)
        assert not any("retainer" in label or "project-based" in label for label in labels)

    def test_grounded_questions_capture_sources(self):
        facts = _run()
        # revenue_range searched and returned a source; it is captured as a citation.
        assert "revenue_range" in facts.citations
        assert len(facts.citations["revenue_range"]) == 1
        # disclosed_figures returned no sources → not in citations.
        assert "disclosed_figures" not in facts.citations

    def test_grounded_calls_used_for_quantitative_questions_only(self):
        with (
            patch.object(fr, "run_structured_ai_call", side_effect=_fake_structured) as structured,
            patch.object(fr, "run_grounded_ai_call", side_effect=_fake_grounded) as grounded,
        ):
            fr.run_financial_research(
                MagicMock(),
                company_name="X",
                url="u",
                industry="i",
                scraped_text="t",
            )
        grounded_labels = {call.kwargs["label"] for call in grounded.call_args_list}
        structured_labels = {call.kwargs["label"] for call in structured.call_args_list}
        assert grounded_labels == {"disclosed_figures", "revenue_range"}
        assert "company_type" in structured_labels
        assert "revenue_model" in structured_labels
        assert grounded_labels.isdisjoint(structured_labels)

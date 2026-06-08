"""Tests for the ResearchFinancials pipeline step.

Covers the success path (grounded tree + value chain, opportunities linked, both
progress questions marked), the implausible-model path, and the soft-fail path —
all without real AI calls (the research orchestrator is mocked).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from signalfield_core.exceptions.base import EngineError

from src.models.model_company import Opportunity
from src.pipeline.pipeline_steps import research_financials as rf
from src.pipeline.pipeline_steps._financial_research import FinancialResearchFacts


def _facts(*, plausible: bool = True) -> FinancialResearchFacts:
    return FinancialResearchFacts(
        company_type="consumer debt-settlement firm",
        revenue_model={"revenue_model": "Success fee", "fee_structure": "15-25%",
                       "provenance": "industry_typical", "basis": "x"},
        disclosed_figures={"found": False, "figures": []},
        scale_signals={"signals": [], "employee_estimate": "~265", "basis": "x"},
        revenue_mix={"streams": [{"label": "Success fees", "pct": 100}],
                     "provenance": "industry_typical", "basis": "x"},
        margins={"gross_margin_low": 40, "gross_margin_high": 60, "ebitda_margin_low": 15,
                 "ebitda_margin_high": 30, "provenance": "industry_typical", "basis": "x"},
        revenue_range={"revenue_low_usd": 60_000_000, "revenue_high_usd": 120_000_000,
                       "provenance": "derived_estimate", "basis": "x", "source_url": ""},
        cost_drivers={"cogs_items": [{"label": "Labour", "pct": 100}], "opex_items": [],
                      "provenance": "industry_typical", "basis": "x"},
        operating_steps={"primary_steps": [{"label": "Enrollment", "description": "d"}],
                         "support_steps": [], "provenance": "industry_typical", "basis": "x"},
        revenue_model_plausible=plausible,
    )


def _make_step(*, opportunities: list[Opportunity] | None = None) -> tuple[Any, Any]:
    step = rf.ResearchFinancials(ai_client_factory=MagicMock())
    accessor = MagicMock()
    company = accessor.company
    company.company_name = "Century Support Services, LLC"
    company.actual_url = "https://centuryss.com"
    company.url = "https://centuryss.com"
    company.profile = MagicMock(industry="Consumer debt settlement")
    company.opportunity_result = MagicMock(opportunities=opportunities or [])
    accessor.get_scraped_text.return_value = "debt relief content"
    accessor.get_document_text.return_value = None
    step.entity_accessor = accessor
    step.request_executor = MagicMock()
    return step, accessor


class TestResearchFinancials:
    def test_success_path_sets_grounded_surfaces(self):
        step, accessor = _make_step(
            opportunities=[Opportunity(title="AI intake", value_lever="Cost Side")]
        )
        with patch.object(rf, "run_financial_research", return_value=_facts(plausible=True)):
            step.execute()
        ebitda = accessor.set_ebitda_tree.call_args[0][0]
        value_chain = accessor.set_value_chain.call_args[0][0]
        assert ebitda.grounded is True
        assert value_chain.grounded is True
        # Opportunities linked to revenue/cost nodes.
        assert ebitda.nodes[1].linked_opportunity_indices == [0]  # cost node, Cost Side opp
        step.request_executor.mark_question_complete.assert_any_call("generate_ebitda_tree")
        step.request_executor.mark_question_complete.assert_any_call("compute_value_chain")

    def test_implausible_model_renders_placeholders(self):
        step, accessor = _make_step()
        with patch.object(rf, "run_financial_research", return_value=_facts(plausible=False)):
            step.execute()
        assert accessor.set_ebitda_tree.call_args[0][0].grounded is False
        assert accessor.set_value_chain.call_args[0][0].grounded is False

    def test_research_failure_soft_fails_to_placeholders(self):
        step, accessor = _make_step()
        with patch.object(rf, "run_financial_research", side_effect=EngineError("rate limit")):
            step.execute()
        assert accessor.set_ebitda_tree.call_args[0][0].grounded is False
        assert accessor.set_value_chain.call_args[0][0].grounded is False
        # Both questions still marked so the analysis persists + progresses.
        step.request_executor.mark_question_complete.assert_any_call("generate_ebitda_tree")

    def test_missing_profile_raises(self):
        step, accessor = _make_step()
        accessor.company.profile = None
        with pytest.raises(ValueError, match="profile missing"):
            step.execute()

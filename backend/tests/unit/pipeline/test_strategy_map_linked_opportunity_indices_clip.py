"""Assembly-level clipping of out-of-range ``linked_opportunity_indices``.

Added by Phase 1b of ``redesign-analysis-visuals``. The per-call schemas
only constrain index items to ``minimum: 0`` — they have no view of the
actual opportunity count for a given scan. ``assemble_strategy_map``
clips any index that's outside ``[0, opportunity_count)`` after the
seven-step generation, then logs a warning so the operator can spot AI
drift in production.

These tests pin the contract:

  - Indices outside the range are removed from the assembled output.
  - In-range indices flow through untouched.
  - A negative ``opportunity_count`` raises (programming error, not AI
    error — the strategy-map step only assembles when an opportunity
    result exists, so the count must be non-negative by construction).
  - The clip emits a warning per affected objective (so the operator
    can grep production logs for ``out-of-range linked_opportunity_indices``).
"""

from __future__ import annotations

import logging
from typing import Any

import pytest

from src.pipeline.pipeline_steps._strategy_map_assembly import assemble_strategy_map

_RATIONALE = "Synthesised from public materials for the test fixture."
_DEFINITION = (
    "We will grow same-segment revenue by deepening engagement with "
    "current customers and entering adjacent markets, with year-over-year "
    "revenue growth as the primary measure of expansion success."
)
_CUSTOMER_DEFINITION = (
    "I rely on this brand for fast, friendly service and quality products. "
    "I value the consistent in-store experience and the friendly associates "
    "who treat me as a regular."
)
_INTERNAL_DEFINITION = (
    "We will create and improve fresh food and beverage offers that "
    "differentiate the brand and grow basket size, with regular product "
    "platform reviews and rapid in-market iteration."
)
_CAPACITY_DEFINITION = (
    "We will invest in associate development through structured training, "
    "succession planning, and a culture of ownership across the network."
)


def _financial_objective(*, id_: str, title: str, indices: list[int]) -> dict[str, Any]:
    return {
        "id": id_,
        "title": title,
        "definition": _DEFINITION,
        "category": "revenue_growth",
        "confidence": "HIGH",
        "rationale_source": None,
        "linked_opportunity_indices": indices,
    }


def _customer_objective(*, id_: str, title: str, indices: list[int]) -> dict[str, Any]:
    return {
        "id": id_,
        "title": title,
        "definition": _CUSTOMER_DEFINITION,
        "panel": "consumer",
        "confidence": "HIGH",
        "rationale_source": None,
        "linked_opportunity_indices": indices,
    }


def _internal_objective(*, id_: str, title: str, indices: list[int]) -> dict[str, Any]:
    return {
        "id": id_,
        "title": title,
        "definition": _INTERNAL_DEFINITION,
        "category": "innovation",
        "confidence": "HIGH",
        "rationale_source": None,
        "linked_opportunity_indices": indices,
    }


def _capacity_objective(*, id_: str, title: str, indices: list[int]) -> dict[str, Any]:
    return {
        "id": id_,
        "title": title,
        "definition": _CAPACITY_DEFINITION,
        "confidence": "MEDIUM",
        "rationale_source": None,
        "linked_opportunity_indices": indices,
    }


def _build_inputs(
    *,
    financial_target_indices: list[int],
    customer_target_indices: list[int],
    internal_target_indices: list[int],
    capacity_target_indices: list[int],
) -> dict[str, Any]:
    """Build a complete set of step-output dicts that ``assemble_strategy_map``
    consumes. The model enforces min-length on every perspective list, so
    we pad each perspective with empty-index siblings around the single
    "target" objective whose ``linked_opportunity_indices`` the tests
    inspect.

    The target objective is always at position 0 within its perspective.
    """
    return {
        "vision": {
            "statement": "Be the most appetizing convenience retailer.",
            "synthesised": False,
            "rationale": _RATIONALE,
        },
        "mission": {
            "statement": "Provide convenient food, beverages, and fuel to commuters.",
            "synthesised": False,
            "rationale": _RATIONALE,
        },
        "value_proposition": {
            "primary": "customer_intimacy",
            "secondary": None,
            "rationale": _RATIONALE,
            "exemplar_company": "Wawa",
        },
        "financial": {
            "objectives": [
                _financial_objective(
                    id_="F1", title="Grow profitable revenue", indices=financial_target_indices
                ),
                _financial_objective(id_="F2", title="Drive operational efficiency", indices=[]),
                _financial_objective(id_="F3", title="Maximise return on capital", indices=[]),
            ]
        },
        "customer": {
            "objectives": [
                _customer_objective(
                    id_="C1",
                    title="Serve fresh products in a friendly environment",
                    indices=customer_target_indices,
                ),
                _customer_objective(id_="C2", title="Recognise loyalty and reward it", indices=[]),
                _customer_objective(
                    id_="C3", title="Make my visit fast and convenient", indices=[]
                ),
            ]
        },
        "internal_processes": {
            "themes": [
                {
                    "name": "Grow Through Foodservice",
                    "supports_financial_objectives": ["F1"],
                    "objectives": [
                        _internal_objective(
                            id_="I1.1",
                            title="Develop signature food offers",
                            indices=internal_target_indices,
                        ),
                    ],
                },
                {
                    "name": "Deliver Convenience and Value",
                    "supports_financial_objectives": ["F2"],
                    "objectives": [
                        _internal_objective(
                            id_="I2.1", title="Improve process throughput", indices=[]
                        ),
                    ],
                },
            ]
        },
        "organizational_capacity": {
            "people": _capacity_objective(
                id_="O.P",
                title="Develop associates as brand ambassadors",
                indices=capacity_target_indices,
            ),
            "technology": _capacity_objective(
                id_="O.T", title="Deliver reliable systems and data", indices=[]
            ),
            "culture": _capacity_objective(
                id_="O.C", title="Live our values in every interaction", indices=[]
            ),
        },
        "core_values": {
            "values": ["Care for customers", "Respect for associates", "Continuous improvement"],
            "synthesised": True,
            "rationale": _RATIONALE,
        },
        "finale": {
            "strategicPriorities": [
                {
                    "name": "Grow Through Foodservice",
                    "result": "Best-in-class signature food platform driving growth.",
                },
                {
                    "name": "Deliver Convenience and Value",
                    "result": "Industry-leading customer perception of speed and value.",
                },
            ],
            # Strategy-map model requires at least 5 arrows. These are
            # not what these tests cover; we pin a canonical chain so the
            # assembly Pydantic validation passes.
            "arrows": [
                {"from": "O.P", "to": "I1.1", "hypothesis": "People enable execution."},
                {"from": "O.T", "to": "I1.1", "hypothesis": "Tech enables execution."},
                {"from": "I1.1", "to": "C1", "hypothesis": "Signature offers delight customers."},
                {"from": "I2.1", "to": "F2", "hypothesis": "Process improvements raise margin."},
                {"from": "C1", "to": "F1", "hypothesis": "Loyal customers drive revenue."},
            ],
        },
    }


class TestClipLinkedOpportunityIndices:
    def test_in_range_indices_pass_through_untouched(self) -> None:
        # All indices are within [0, opportunity_count). Nothing should
        # be clipped, no warning should fire.
        inputs = _build_inputs(
            financial_target_indices=[0, 2],
            customer_target_indices=[1],
            internal_target_indices=[0, 1, 3],
            capacity_target_indices=[2],
        )
        strategy_map = assemble_strategy_map(**inputs, opportunity_count=5)

        assert strategy_map.financial.objectives[0].linked_opportunity_indices == [0, 2]
        assert strategy_map.customer.objectives[0].linked_opportunity_indices == [1]
        assert strategy_map.internal_processes.themes[0].objectives[
            0
        ].linked_opportunity_indices == [
            0,
            1,
            3,
        ]
        assert strategy_map.organizational_capacity.people.linked_opportunity_indices == [2]

    def test_out_of_range_indices_are_dropped(self) -> None:
        # 99 is past the array end; should be dropped from each
        # objective. In-range siblings (0, 1, 2) survive.
        inputs = _build_inputs(
            financial_target_indices=[0, 99, 2],
            customer_target_indices=[5, 1],  # 5 == opportunity_count → out of range
            internal_target_indices=[100, 0],
            capacity_target_indices=[50, 2],
        )
        strategy_map = assemble_strategy_map(**inputs, opportunity_count=5)

        assert strategy_map.financial.objectives[0].linked_opportunity_indices == [0, 2]
        assert strategy_map.customer.objectives[0].linked_opportunity_indices == [1]
        assert strategy_map.internal_processes.themes[0].objectives[
            0
        ].linked_opportunity_indices == [0]
        assert strategy_map.organizational_capacity.people.linked_opportunity_indices == [2]

    def test_empty_lists_pass_through_untouched(self) -> None:
        inputs = _build_inputs(
            financial_target_indices=[],
            customer_target_indices=[],
            internal_target_indices=[],
            capacity_target_indices=[],
        )
        strategy_map = assemble_strategy_map(**inputs, opportunity_count=10)

        assert strategy_map.financial.objectives[0].linked_opportunity_indices == []
        assert strategy_map.customer.objectives[0].linked_opportunity_indices == []
        assert (
            strategy_map.internal_processes.themes[0].objectives[0].linked_opportunity_indices == []
        )
        assert strategy_map.organizational_capacity.people.linked_opportunity_indices == []

    def test_zero_opportunities_clips_everything(self) -> None:
        # Pathological-but-valid: AI emitted indices even though the
        # analysis has zero opportunities. Every index is dropped.
        inputs = _build_inputs(
            financial_target_indices=[0],
            customer_target_indices=[1],
            internal_target_indices=[2],
            capacity_target_indices=[3],
        )
        strategy_map = assemble_strategy_map(**inputs, opportunity_count=0)

        assert strategy_map.financial.objectives[0].linked_opportunity_indices == []
        assert strategy_map.customer.objectives[0].linked_opportunity_indices == []
        assert (
            strategy_map.internal_processes.themes[0].objectives[0].linked_opportunity_indices == []
        )
        assert strategy_map.organizational_capacity.people.linked_opportunity_indices == []

    def test_negative_opportunity_count_raises(self) -> None:
        # Programming error — the strategy-map step only assembles when
        # an opportunity result exists, so the count must be non-negative
        # by construction. Fail loudly if a caller ever violates that.
        inputs = _build_inputs(
            financial_target_indices=[],
            customer_target_indices=[],
            internal_target_indices=[],
            capacity_target_indices=[],
        )
        with pytest.raises(ValueError, match="non-negative"):
            assemble_strategy_map(**inputs, opportunity_count=-1)

    def test_clip_emits_warning_log(self, caplog: pytest.LogCaptureFixture) -> None:
        # Each affected objective emits a warning so operators can grep
        # for `out-of-range linked_opportunity_indices` in production
        # logs. Multiple drops on the same objective produce a single
        # warning listing all dropped indices.
        inputs = _build_inputs(
            financial_target_indices=[0, 99, 100],
            customer_target_indices=[],
            internal_target_indices=[],
            capacity_target_indices=[],
        )
        with caplog.at_level(logging.WARNING):
            assemble_strategy_map(**inputs, opportunity_count=5)

        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warnings) == 1, "expected one warning per affected objective"
        message = warnings[0].getMessage()
        assert "out-of-range" in message
        assert "[99, 100]" in message
        assert "F1" in message
        assert "opportunity_count=5" in message

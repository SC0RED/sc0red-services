"""Tests for the decomposed arrows + priorities + gaps module.

Covers ``_strategy_map_arrows.enumerate_arrow_pairs`` and
``run_decomposed_arrows_and_gaps`` end-to-end with a mocked AI call
layer. Pins:
  - Candidate pair enumeration across the causal hierarchy.
  - Internal-to-internal cross-theme pairs are excluded (Open Question §3).
  - Yes/no filtering: only enables=true survives into the arrows list.
  - Priorities and gaps are passed through unchanged.
  - Per-call labels follow the ``ai_call_arrow_{from_id}_{to_id}``,
    ``ai_call_priorities``, ``ai_call_gaps`` convention.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from src.pipeline.pipeline_steps._strategy_map_arrows import (
    enumerate_arrow_pairs,
    run_decomposed_arrows_and_gaps,
)
from src.pipeline.step_timer import StepTimer


def _make_step_with_canned_responses(
    responses_by_label: dict[str, dict[str, Any]],
) -> MagicMock:
    step = MagicMock()

    def fake_run_ai_call(
        _user_prompt: str,
        _schema: dict[str, Any],
        _system_prompt: str,
        label: str,
    ) -> tuple[str, dict[str, Any], float]:
        return label, responses_by_label[label], 0.5

    step._run_ai_call.side_effect = fake_run_ai_call
    return step


def _fixture_perspectives() -> tuple[
    dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]
]:
    """Realistic fixture: 3 financial, 4 customer, 2 themes x 2 internal, 3 capacity."""
    financial = {
        "objectives": [
            {"id": "F1", "title": "Grow revenue"},
            {"id": "F2", "title": "Drive efficiency"},
            {"id": "F3", "title": "Maximise ROIC"},
        ]
    }
    customer = {
        "objectives": [
            {"id": "C1", "title": "Want fresh products"},
            {"id": "C2", "title": "Want loyalty"},
            {"id": "C3", "title": "Want speed"},
            {"id": "C4", "title": "Want care"},
        ]
    }
    internal_processes = {
        "themes": [
            {
                "name": "Differentiate",
                "supports_financial_objectives": ["F1"],
                "objectives": [
                    {"id": "I1.1", "title": "Build brand"},
                    {"id": "I1.2", "title": "Innovate menu"},
                ],
            },
            {
                "name": "Streamline",
                "supports_financial_objectives": ["F2"],
                "objectives": [
                    {"id": "I2.1", "title": "Cut waste"},
                    {"id": "I2.2", "title": "Automate orders"},
                ],
            },
        ]
    }
    organizational_capacity = {
        "people": {"id": "O.P", "title": "Develop talent"},
        "technology": {"id": "O.T", "title": "Modernise systems"},
        "culture": {"id": "O.C", "title": "Live values"},
    }
    return financial, customer, internal_processes, organizational_capacity


class TestEnumerateArrowPairs:
    def test_includes_all_three_causal_levels(self) -> None:
        financial, customer, internal_processes, capacity = _fixture_perspectives()
        pairs = enumerate_arrow_pairs(
            financial=financial,
            customer=customer,
            internal_processes=internal_processes,
            organizational_capacity=capacity,
        )

        # Capacity (3) x Internal (4) = 12 pairs
        # Internal (4) x Customer (4) = 16 pairs
        # Customer (4) x Financial (3) = 12 pairs
        # Total = 40 pairs.
        assert len(pairs) == 40

        capacity_to_internal = {(p[0], p[2]) for p in pairs if p[0] in ("O.P", "O.T", "O.C")}
        assert ("O.P", "I1.1") in capacity_to_internal
        assert ("O.P", "I2.2") in capacity_to_internal

        internal_to_customer = {
            (p[0], p[2]) for p in pairs if p[0].startswith("I") and p[2].startswith("C")
        }
        assert ("I1.1", "C1") in internal_to_customer
        assert ("I2.2", "C4") in internal_to_customer

        customer_to_financial = {
            (p[0], p[2]) for p in pairs if p[0].startswith("C") and p[2].startswith("F")
        }
        assert ("C1", "F1") in customer_to_financial
        assert ("C4", "F3") in customer_to_financial

    def test_excludes_internal_to_internal_cross_theme_arrows(self) -> None:
        """Open Question §3: first cut excludes internal-internal pairs."""
        financial, customer, internal_processes, capacity = _fixture_perspectives()
        pairs = enumerate_arrow_pairs(
            financial=financial,
            customer=customer,
            internal_processes=internal_processes,
            organizational_capacity=capacity,
        )

        for from_id, _from_title, to_id, _to_title in pairs:
            assert not (from_id.startswith("I") and to_id.startswith("I")), (
                f"Internal-to-internal pair leaked: {from_id} -> {to_id}"
            )

    def test_excludes_reverse_causal_pairs(self) -> None:
        """Direction MUST be forward in the causal hierarchy."""
        financial, customer, internal_processes, capacity = _fixture_perspectives()
        pairs = enumerate_arrow_pairs(
            financial=financial,
            customer=customer,
            internal_processes=internal_processes,
            organizational_capacity=capacity,
        )

        for from_id, _from_title, to_id, _to_title in pairs:
            # No financial-as-source pairs (financial is the terminal).
            assert not from_id.startswith("F"), (
                f"Financial-as-source pair leaked: {from_id} -> {to_id}"
            )
            # No capacity-as-target pairs (capacity is the root).
            assert not to_id.startswith("O."), (
                f"Capacity-as-target pair leaked: {from_id} -> {to_id}"
            )

    def test_pairs_carry_titles(self) -> None:
        financial, customer, internal_processes, capacity = _fixture_perspectives()
        pairs = enumerate_arrow_pairs(
            financial=financial,
            customer=customer,
            internal_processes=internal_processes,
            organizational_capacity=capacity,
        )
        # Every tuple has the (from_id, from_title, to_id, to_title) shape.
        for pair in pairs:
            assert len(pair) == 4
            assert all(isinstance(field, str) for field in pair)


class TestRunDecomposedArrowsAndGaps:
    def _build_responses(self) -> dict[str, dict[str, Any]]:
        """Cover all 40 candidate pairs + priorities + gaps."""
        financial, customer, internal_processes, capacity = _fixture_perspectives()
        pairs = enumerate_arrow_pairs(
            financial=financial,
            customer=customer,
            internal_processes=internal_processes,
            organizational_capacity=capacity,
        )

        responses: dict[str, dict[str, Any]] = {}
        # Half enable, half don't — exercises the filtering logic.
        for index, (from_id, _from_title, to_id, _to_title) in enumerate(pairs):
            label = f"arrow_{from_id}_{to_id}"
            if index % 2 == 0:
                responses[label] = {
                    "enables": True,
                    "hypothesis": (
                        f"Mechanism: {from_id} drives a specific outcome that "
                        f"materially advances {to_id}."
                    ),
                }
            else:
                responses[label] = {"enables": False, "hypothesis": None}

        responses["priorities"] = {
            "strategicPriorities": [
                {"name": "Differentiate", "result": "Best-in-class brand and menu innovation."},
                {"name": "Streamline", "result": "Industry-leading cost-per-transaction."},
            ]
        }
        responses["gaps"] = {
            "whatsMissing": [
                {
                    "id": "G1",
                    "title": "Cultural commitments not published",
                    "description": (
                        "The company has not published explicit cultural commitments. "
                        "Public materials emphasise customer focus but not the underlying values."
                    ),
                    "deepDiveFraming": (
                        "A Vector Advisory deep-dive would interview leadership and frontline "
                        "associates to articulate the working culture."
                    ),
                    "relatedObjectiveIds": ["O.C"],
                },
                {
                    "id": "G2",
                    "title": "Channel strategy unclear",
                    "description": (
                        "The company sells through both direct retail and franchise channels "
                        "but the strategic balance is not visible in public materials."
                    ),
                    "deepDiveFraming": (
                        "A Vector Advisory deep-dive would map channel economics across the "
                        "go-to-market."
                    ),
                    "relatedObjectiveIds": ["C2"],
                },
            ]
        }
        return responses

    def test_only_enables_true_pairs_become_arrows(self) -> None:
        responses = self._build_responses()
        financial, customer, internal_processes, capacity = _fixture_perspectives()
        step = _make_step_with_canned_responses(responses)
        timer = StepTimer("GenerateStrategyMap")

        result = run_decomposed_arrows_and_gaps(
            step,  # type: ignore[arg-type]
            system_prompt="<system prompt>",
            context={"company_name": "Acme"},
            timer=timer,
            financial=financial,
            customer=customer,
            internal_processes=internal_processes,
            organizational_capacity=capacity,
        )

        # 40 candidate pairs, half enabled → 20 arrows in the assembled output.
        assert len(result["arrows"]) == 20
        # Every arrow has the expected shape.
        for arrow in result["arrows"]:
            assert set(arrow.keys()) == {"from", "to", "hypothesis"}
            assert arrow["hypothesis"] is not None
            assert "Mechanism:" in arrow["hypothesis"]

    def test_priorities_and_gaps_passed_through_unchanged(self) -> None:
        responses = self._build_responses()
        financial, customer, internal_processes, capacity = _fixture_perspectives()
        step = _make_step_with_canned_responses(responses)
        timer = StepTimer("GenerateStrategyMap")

        result = run_decomposed_arrows_and_gaps(
            step,  # type: ignore[arg-type]
            system_prompt="<system prompt>",
            context={"company_name": "Acme"},
            timer=timer,
            financial=financial,
            customer=customer,
            internal_processes=internal_processes,
            organizational_capacity=capacity,
        )

        assert result["strategicPriorities"] == responses["priorities"]["strategicPriorities"]
        assert result["whatsMissing"] == responses["gaps"]["whatsMissing"]

    def test_per_pair_labels_follow_convention(self) -> None:
        responses = self._build_responses()
        financial, customer, internal_processes, capacity = _fixture_perspectives()
        step = _make_step_with_canned_responses(responses)
        timer = StepTimer("GenerateStrategyMap")

        run_decomposed_arrows_and_gaps(
            step,  # type: ignore[arg-type]
            system_prompt="<system prompt>",
            context={"company_name": "Acme"},
            timer=timer,
            financial=financial,
            customer=customer,
            internal_processes=internal_processes,
            organizational_capacity=capacity,
        )

        timings = timer.to_details()["GenerateStrategyMap.timings"]
        # Every yes/no call has a per-pair label.
        per_pair_labels = [label for label in timings if label.startswith("ai_call_arrow_")]
        assert len(per_pair_labels) == 40
        # Spot-check a few specific labels.
        assert "ai_call_arrow_O.P_I1.1" in timings
        assert "ai_call_arrow_C1_F1" in timings
        # Holistic labels present.
        assert "ai_call_priorities" in timings
        assert "ai_call_gaps" in timings
        # Legacy monolithic label absent.
        assert "ai_call_arrows_and_gaps" not in timings

    def test_enables_true_with_null_hypothesis_raises(self) -> None:
        """Schema-contract guard: enables=true requires a non-null hypothesis."""
        import pytest

        financial, customer, internal_processes, capacity = _fixture_perspectives()
        pairs = enumerate_arrow_pairs(
            financial=financial,
            customer=customer,
            internal_processes=internal_processes,
            organizational_capacity=capacity,
        )
        # All pairs return enables=true + hypothesis=null. Assembly must
        # raise before the resulting dicts hit ``assemble_strategy_map``
        # (which would have surfaced a confusing Pydantic ValidationError
        # against the non-nullable ``Arrow.hypothesis`` field).
        responses: dict[str, dict[str, Any]] = {
            f"arrow_{from_id}_{to_id}": {"enables": True, "hypothesis": None}
            for from_id, _ft, to_id, _tt in pairs
        }
        responses["priorities"] = {"strategicPriorities": []}
        responses["gaps"] = {"whatsMissing": []}

        step = _make_step_with_canned_responses(responses)
        timer = StepTimer("GenerateStrategyMap")

        with pytest.raises(ValueError, match="hypothesis=null"):
            run_decomposed_arrows_and_gaps(
                step,  # type: ignore[arg-type]
                system_prompt="<system prompt>",
                context={"company_name": "Acme"},
                timer=timer,
                financial=financial,
                customer=customer,
                internal_processes=internal_processes,
                organizational_capacity=capacity,
            )

    def test_missing_enables_field_raises_keyerror(self) -> None:
        """Fail-fast guard: a response missing the required ``enables`` field raises."""
        import pytest

        financial, customer, internal_processes, capacity = _fixture_perspectives()
        pairs = enumerate_arrow_pairs(
            financial=financial,
            customer=customer,
            internal_processes=internal_processes,
            organizational_capacity=capacity,
        )
        # First pair returns a response without ``enables`` — the AI
        # produced an off-contract response. We want a loud KeyError
        # rather than silent treatment as "not enabled".
        responses: dict[str, dict[str, Any]] = {
            f"arrow_{from_id}_{to_id}": {"enables": False, "hypothesis": None}
            for from_id, _ft, to_id, _tt in pairs
        }
        first_from_id, _, first_to_id, _ = pairs[0]
        responses[f"arrow_{first_from_id}_{first_to_id}"] = {"hypothesis": "x"}
        responses["priorities"] = {"strategicPriorities": []}
        responses["gaps"] = {"whatsMissing": []}

        step = _make_step_with_canned_responses(responses)
        timer = StepTimer("GenerateStrategyMap")

        with pytest.raises(KeyError, match="enables"):
            run_decomposed_arrows_and_gaps(
                step,  # type: ignore[arg-type]
                system_prompt="<system prompt>",
                context={"company_name": "Acme"},
                timer=timer,
                financial=financial,
                customer=customer,
                internal_processes=internal_processes,
                organizational_capacity=capacity,
            )

    def test_fires_one_call_per_pair_plus_two_holistic(self) -> None:
        responses = self._build_responses()
        financial, customer, internal_processes, capacity = _fixture_perspectives()
        step = _make_step_with_canned_responses(responses)
        timer = StepTimer("GenerateStrategyMap")

        run_decomposed_arrows_and_gaps(
            step,  # type: ignore[arg-type]
            system_prompt="<system prompt>",
            context={"company_name": "Acme"},
            timer=timer,
            financial=financial,
            customer=customer,
            internal_processes=internal_processes,
            organizational_capacity=capacity,
        )

        # 40 pairs + 1 priorities + 1 gaps = 42 calls.
        assert step._run_ai_call.call_count == 42

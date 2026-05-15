"""Tests for the decomposed vision/mission + value-proposition module.

Covers ``_strategy_map_synthesis.run_decomposed_vision_mission`` and
``run_decomposed_value_proposition`` end-to-end with a mocked AI call
layer. Pins:
  - Per-call label routing (each sub-call's label appears in the timer).
  - Assembly merging (text + synth fields stitch back into the expected
    dict shapes).
  - Hybrid-secondary handling (secondary is honoured only when
    primary == hybrid).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from src.pipeline.pipeline_steps._strategy_map_synthesis import (
    _render,
    _schema,
    run_decomposed_value_proposition,
    run_decomposed_vision_mission,
)
from src.pipeline.pipeline_steps.ai_call import TokenCounts
from src.pipeline.step_timer import StepTimer

# Per-call token counts the mocked ``_run_ai_call`` reports. Token telemetry
# pinning lives in ``test_step_timer.py``; these fixtures only need a real
# ``TokenCounts`` instance so ``timer.record_tokens(...)`` doesn't trip on a
# MagicMock attribute. The exact numbers are irrelevant here.
_CANNED_TOKEN_COUNTS = TokenCounts(input_tokens=100, output_tokens=50, cached_input_tokens=80)


def _make_step_with_canned_responses(
    responses_by_label: dict[str, dict[str, Any]],
) -> MagicMock:
    """Stub a GenerateStrategyMap whose ``_run_ai_call`` returns canned data."""
    step = MagicMock()

    def fake_run_ai_call(
        _user_prompt: str,
        _schema: dict[str, Any],
        _system_prompt: str,
        label: str,
    ) -> tuple[str, dict[str, Any], float, TokenCounts]:
        return label, responses_by_label[label], 0.5, _CANNED_TOKEN_COUNTS

    step._run_ai_call.side_effect = fake_run_ai_call
    return step


class TestRenderAndSchemaHelpers:
    def test_render_substitutes_known_placeholders(self) -> None:
        rendered = _render("vision_text", {"company_name": "Acme"})
        assert "Acme" in rendered

    def test_render_replaces_unknown_placeholders_with_unknown_marker(self) -> None:
        rendered = _render("vision_text", {})
        assert "(unknown)" in rendered

    def test_schema_caches_lookups(self) -> None:
        first = _schema("vision_text")
        second = _schema("vision_text")
        assert first is second


class TestRunDecomposedVisionMission:
    def _build_responses(self) -> dict[str, dict[str, Any]]:
        return {
            "vision_text": {"statement": "To be the most appetizing convenience retailer."},
            "mission_text": {"statement": "Provide convenient, appetizing food and fuel."},
            "vision_synth": {
                "synthesised": False,
                "rationale": "Verbatim from the company's 2024 strategy deck.",
            },
            "mission_synth": {
                "synthesised": True,
                "rationale": "Synthesised from store-locator and brand materials.",
            },
        }

    def test_merges_text_and_synth_fields(self) -> None:
        step = _make_step_with_canned_responses(self._build_responses())
        timer = StepTimer("GenerateStrategyMap")

        vision, mission = run_decomposed_vision_mission(
            step,  # type: ignore[arg-type]
            system_prompt="<system prompt>",
            context={"company_name": "Acme"},
            timer=timer,
        )

        assert vision == {
            "statement": "To be the most appetizing convenience retailer.",
            "synthesised": False,
            "rationale": "Verbatim from the company's 2024 strategy deck.",
        }
        assert mission == {
            "statement": "Provide convenient, appetizing food and fuel.",
            "synthesised": True,
            "rationale": "Synthesised from store-locator and brand materials.",
        }

    def test_records_four_per_call_labels(self) -> None:
        step = _make_step_with_canned_responses(self._build_responses())
        timer = StepTimer("GenerateStrategyMap")

        run_decomposed_vision_mission(
            step,  # type: ignore[arg-type]
            system_prompt="<system prompt>",
            context={"company_name": "Acme"},
            timer=timer,
        )

        details = timer.to_details()
        timings = details["GenerateStrategyMap.timings"]
        assert "ai_call_vision_text" in timings
        assert "ai_call_mission_text" in timings
        assert "ai_call_vision_synth" in timings
        assert "ai_call_mission_synth" in timings
        # And NOT the legacy monolithic label.
        assert "ai_call_vision_mission" not in timings

    def test_fires_four_ai_calls(self) -> None:
        step = _make_step_with_canned_responses(self._build_responses())
        timer = StepTimer("GenerateStrategyMap")

        run_decomposed_vision_mission(
            step,  # type: ignore[arg-type]
            system_prompt="<system prompt>",
            context={"company_name": "Acme"},
            timer=timer,
        )

        assert step._run_ai_call.call_count == 4


class TestRunDecomposedValueProposition:
    def _base_responses(self) -> dict[str, dict[str, Any]]:
        return {
            "vp_primary": {"primary": "customer_intimacy"},
            "vp_secondary": {"secondary": "operational_excellence"},
            "vp_exemplar": {"exemplar_company": "Home Depot"},
            "vp_rationale": {
                "rationale": (
                    "Materials emphasise solution-fit (project guidance) across categories."
                )
            },
        }

    def test_assembles_dict_in_expected_shape(self) -> None:
        step = _make_step_with_canned_responses(self._base_responses())
        timer = StepTimer("GenerateStrategyMap")

        result = run_decomposed_value_proposition(
            step,  # type: ignore[arg-type]
            system_prompt="<system prompt>",
            context={"company_name": "Acme"},
            timer=timer,
        )

        assert result == {
            "primary": "customer_intimacy",
            "secondary": None,
            "rationale": "Materials emphasise solution-fit (project guidance) across categories.",
            "exemplar_company": "Home Depot",
        }

    def test_secondary_populated_only_when_primary_is_hybrid(self) -> None:
        responses = self._base_responses()
        responses["vp_primary"] = {"primary": "hybrid"}
        step = _make_step_with_canned_responses(responses)
        timer = StepTimer("GenerateStrategyMap")

        result = run_decomposed_value_proposition(
            step,  # type: ignore[arg-type]
            system_prompt="<system prompt>",
            context={"company_name": "Acme"},
            timer=timer,
        )

        assert result["primary"] == "hybrid"
        assert result["secondary"] == "operational_excellence"

    def test_secondary_discarded_when_primary_not_hybrid(self) -> None:
        # vp_secondary still ran, but the assembly discards it. This is the
        # tradeoff in design Decision §2: always run for tighter latency,
        # discard when not needed.
        for primary in ("operational_excellence", "customer_intimacy", "product_leadership"):
            responses = self._base_responses()
            responses["vp_primary"] = {"primary": primary}
            step = _make_step_with_canned_responses(responses)
            timer = StepTimer("GenerateStrategyMap")

            result = run_decomposed_value_proposition(
                step,  # type: ignore[arg-type]
                system_prompt="<system prompt>",
                context={"company_name": "Acme"},
                timer=timer,
            )

            assert result["secondary"] is None, f"primary={primary} should null secondary"

    def test_records_four_per_call_labels(self) -> None:
        step = _make_step_with_canned_responses(self._base_responses())
        timer = StepTimer("GenerateStrategyMap")

        run_decomposed_value_proposition(
            step,  # type: ignore[arg-type]
            system_prompt="<system prompt>",
            context={"company_name": "Acme"},
            timer=timer,
        )

        details = timer.to_details()
        timings = details["GenerateStrategyMap.timings"]
        assert "ai_call_vp_primary" in timings
        assert "ai_call_vp_secondary" in timings
        assert "ai_call_vp_exemplar" in timings
        assert "ai_call_vp_rationale" in timings
        assert "ai_call_value_proposition" not in timings

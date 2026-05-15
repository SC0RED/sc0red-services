"""Direct tests for the decomposed perspectives orchestration helpers.

Covers ``_strategy_map_perspectives.py`` and ``_strategy_map_perspective_rounds.py``
end-to-end with a mocked AI call layer. The full integration test
(P1.7.4) is deferred — these tests pin orchestration mechanics
(label-keyed result routing, ID assignment, sibling-text formatting)
without hitting real OpenAI.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.pipeline.pipeline_steps import _strategy_map_perspectives as perspectives
from src.pipeline.pipeline_steps._strategy_map_perspective_rounds import (
    run_round2_details_and_internal_titles,
    run_round3_internal_details,
)
from src.pipeline.pipeline_steps._strategy_map_perspective_rounds import _format_siblings
from src.pipeline.pipeline_steps._strategy_map_perspectives import (
    _format_capacity_titles,
    _render,
    _schema,
    generate_perspectives_decomposed,
)
from src.pipeline.pipeline_steps.ai_call import TokenCounts

# Per-call token counts the mocked ``_run_ai_call`` reports. The exact
# numbers are irrelevant for these tests; token-telemetry pinning lives in
# ``test_step_timer.py``.
_CANNED_TOKEN_COUNTS = TokenCounts(input_tokens=100, output_tokens=50, cached_input_tokens=80)


def _make_step_with_canned_responses(
    responses_by_label: dict[str, dict[str, Any]],
) -> MagicMock:
    """Stub a GenerateStrategyMap whose ``_run_ai_call`` returns canned data.

    `responses_by_label[label]` is the ``content`` returned for that
    label. Each call returns the standard ``(label, content, elapsed,
    token_counts)`` 4-tuple.
    """
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
        rendered = _render("round1_titles_financial", {"company_name": "Acme"})
        assert "Acme" in rendered

    def test_render_replaces_unknown_placeholders_with_unknown_marker(self) -> None:
        # When a placeholder isn't in context, the existing render_template
        # behaviour replaces it with `(unknown)` — pin that.
        rendered = _render("round1_titles_financial", {})
        assert "(unknown)" in rendered

    def test_schema_caches_lookups(self) -> None:
        first = _schema("financial_titles")
        second = _schema("financial_titles")
        # Same object identity — confirms the module-level cache.
        assert first is second


class TestFormatters:
    def test_format_siblings_excludes_current_index(self) -> None:
        # Each detail call's prompt must list the OTHER titles only; the
        # title being elaborated is NOT a "sibling to differentiate from".
        assert _format_siblings(["a", "b", "c"], current_index=0) == "- b\n- c"
        assert _format_siblings(["a", "b", "c"], current_index=1) == "- a\n- c"
        assert _format_siblings(["a", "b", "c"], current_index=2) == "- a\n- b"

    def test_format_siblings_returns_none_marker_when_only_one_title(self) -> None:
        # Single-title perspectives get a sentinel "(none)" rather than
        # an empty string, so the prompt template's `{sibling_titles}`
        # substitution stays sane.
        assert _format_siblings(["only"], current_index=0) == "(none)"

    def test_format_capacity_titles_uses_capitalised_bucket_labels(self) -> None:
        text = _format_capacity_titles(
            {"people": "Develop talent", "technology": "Modernise systems", "culture": "Live values"}
        )
        assert "- People: Develop talent" in text
        assert "- Technology: Modernise systems" in text
        assert "- Culture: Live values" in text


class TestGeneratePerspectivesDecomposedEndToEnd:
    """Wire all three rounds together against a mock AI factory.

    Builds a ``responses_by_label`` map covering every call the
    orchestration makes (Round 1: 4, Round 2: 13, Round 3: 9 = 26 calls
    in this fixture's shape) and verifies the assembled output.
    """

    def _build_responses(self) -> dict[str, dict[str, Any]]:
        return {
            # ── Round 1 ──
            "titles_financial": {
                "titles": ["Grow revenue", "Drive efficiency", "Maximise ROIC"]
            },
            "titles_customer": {
                "titles": ["Want fresh products", "Want loyalty", "Want speed"]
            },
            "themes_internal": {
                "themes": [
                    {"name": "Differentiate", "supports_financial_objectives": ["F1"]},
                    {"name": "Streamline", "supports_financial_objectives": ["F2"]},
                ]
            },
            "titles_capacity": {
                "people": "Develop talent",
                "technology": "Modernise systems",
                "culture": "Live values",
            },
            # ── Round 2 — financial details ──
            "detail_financial_F1": {
                "definition": "We will grow revenue by deepening engagement with current customers and expanding into adjacent segments through cross-sell programmes that emphasise lifetime value over single-transaction revenue.",
                "category": "revenue_growth",
                "confidence": "HIGH",
                "rationale_source": "EBITDA branch",
            },
            "detail_financial_F2": {
                "definition": "We will drive operational efficiency by automating routine processes and consolidating systems so back-office costs grow slower than revenue, freeing capital for reinvestment in front-line capabilities.",
                "category": "productivity",
                "confidence": "MEDIUM",
                "rationale_source": "EBITDA branch",
            },
            "detail_financial_F3": {
                "definition": "We will maximise return on invested capital by allocating capital to the highest-return store formats, retiring underperformers, and applying disciplined hurdles to all new investment.",
                "category": "productivity",
                "confidence": "MEDIUM",
                "rationale_source": "Industry pattern",
            },
            # ── Round 2 — customer details ──
            "detail_customer_C1": {
                "definition": "I rely on this brand for fresh, locally relevant products that surprise me on every visit and reinforce why I choose this store over the alternatives nearby.",
                "panel": "consumer",
                "confidence": "HIGH",
                "rationale_source": "Profile",
            },
            "detail_customer_C2": {
                "definition": "I expect the loyalty programme to recognise my repeat visits and reward me with tangible benefits that match the depth of my engagement with the brand over time.",
                "panel": "consumer",
                "confidence": "MEDIUM",
                "rationale_source": "Opportunities",
            },
            "detail_customer_C3": {
                "definition": "I want to get in, get what I need, and get out without friction or excessive dwell time, regardless of how busy the store is at any given moment of any visit.",
                "panel": "consumer",
                "confidence": "HIGH",
                "rationale_source": None,
            },
            # ── Round 2 — capacity details ──
            "detail_capacity_people": {
                "definition": "We will invest in associate development through structured training programmes, customer-service rituals, and visible career pathways that reward demonstrated capability over tenure alone.",
                "confidence": "MEDIUM",
                "rationale_source": "Profile",
            },
            "detail_capacity_technology": {
                "definition": "We will deliver reliable systems and insight through modern data infrastructure, automated alerting on operational anomalies, and self-service analytics for store managers.",
                "confidence": "HIGH",
                "rationale_source": "Tech signals",
            },
            "detail_capacity_culture": {
                "definition": "We will live our values in every customer interaction by reinforcing them at hire, in onboarding, and through visible leadership behaviours that frontline associates emulate.",
                "confidence": "LOW",
                "rationale_source": None,
            },
            # ── Round 2 — internal-process titles per theme ──
            "titles_internal_T1": {
                "titles": ["Develop signature offers", "Refresh ambience"],
            },
            "titles_internal_T2": {
                "titles": ["Improve E2E throughput"],
            },
            # ── Round 2 — core values ──
            "core_values": {
                "values": ["Care", "Respect", "Continuous improvement"],
                "synthesised": True,
                "rationale": "Synthesised from public materials emphasising customer-first messaging.",
            },
            # ── Round 3 — internal-process per-objective details ──
            "detail_internal_T1_O1": {
                "definition": "We will continuously develop signature fresh-food and beverage offers that differentiate from category competitors by emphasising local sourcing and quarterly menu refreshes.",
                "category": "innovation",
                "confidence": "HIGH",
                "rationale_source": "Value chain",
            },
            "detail_internal_T1_O2": {
                "definition": "We will refresh in-store ambience and visual merchandising on a managed cadence so the brand remains visually current without disrupting the operational rhythm of stores.",
                "category": "innovation",
                "confidence": "MEDIUM",
                "rationale_source": "Opportunities",
            },
            "detail_internal_T2_O1": {
                "definition": "We will continuously improve end-to-end operational throughput by reducing handoff friction across functions, cutting cycle times on routine work, and standardising the highest-leverage processes.",
                "category": "operational_excellence",
                "confidence": "HIGH",
                "rationale_source": "Value chain",
            },
        }

    def test_assembles_full_perspective_payload(self) -> None:
        # Reset the schema cache so this test is deterministic across runs.
        perspectives._SCHEMA_CACHE.clear()
        responses = self._build_responses()
        step = _make_step_with_canned_responses(responses)
        timer = MagicMock()

        financial, customer, internal, capacity, core_values = generate_perspectives_decomposed(
            step,
            system_prompt="sys",
            # vision/mission must be in context — the round-runner uses
            # hard-key access (no .get default) so missing them surfaces
            # as a KeyError rather than a silently empty AI prompt.
            context={
                "company_name": "Acme",
                "vision_statement": "Test vision statement",
                "mission_statement": "Test mission statement",
            },
            timer=timer,
        )

        # Financial: 3 objectives with F1/F2/F3 IDs.
        assert [o["id"] for o in financial["objectives"]] == ["F1", "F2", "F3"]
        assert financial["objectives"][0]["title"] == "Grow revenue"
        assert financial["objectives"][0]["category"] == "revenue_growth"

        # Customer: 3 objectives with C1/C2/C3.
        assert [o["id"] for o in customer["objectives"]] == ["C1", "C2", "C3"]
        assert customer["objectives"][0]["panel"] == "consumer"

        # Internal: 2 themes; theme 1 has 2 objectives (I1.1, I1.2), theme 2 has 1 (I2.1).
        assert len(internal["themes"]) == 2
        assert [o["id"] for o in internal["themes"][0]["objectives"]] == ["I1.1", "I1.2"]
        assert [o["id"] for o in internal["themes"][1]["objectives"]] == ["I2.1"]

        # Capacity: bucket-keyed with O.P / O.T / O.C.
        assert capacity["people"]["id"] == "O.P"
        assert capacity["technology"]["id"] == "O.T"
        assert capacity["culture"]["id"] == "O.C"

        # Core values pass-through.
        assert core_values["values"] == ["Care", "Respect", "Continuous improvement"]

        # Timer recorded all 21 unique labels (4 round-1 + 14 round-2 +
        # 3 round-3-objs in our fixture; round-3 has T1.O1, T1.O2, T2.O1).
        recorded_labels = {call.args[0] for call in timer.record.call_args_list}
        assert "ai_call_titles_financial" in recorded_labels
        assert "ai_call_detail_financial_F1" in recorded_labels
        assert "ai_call_detail_internal_T1_O1" in recorded_labels
        assert "ai_call_core_values" in recorded_labels

    def test_calls_progress_emitter_at_phase_boundaries(self) -> None:
        # Phase 2 of strategy-map-on-demand observability: the
        # decomposed orchestration emits a progress event after each
        # round so the frontend can drive a moving bar. Three boundaries
        # in this fixture: after Round 1 (titles), after Round 2
        # (details + per-theme titles + core values), after Round 3
        # (internal per-objective details).
        perspectives._SCHEMA_CACHE.clear()
        responses = self._build_responses()
        step = _make_step_with_canned_responses(responses)
        timer = MagicMock()
        progress_emitter = MagicMock()

        generate_perspectives_decomposed(
            step,
            system_prompt="sys",
            context={
                "company_name": "Acme",
                "vision_statement": "Test vision",
                "mission_statement": "Test mission",
            },
            timer=timer,
            progress_emitter=progress_emitter,
        )

        # Three calls, in monotonically increasing percentage order.
        # The exact percentages are tuned to spread roughly uniformly
        # over the typical wall-clock budget; the test pins the count
        # and ordering, not the literals (which the design comment
        # documents and a future tweak might adjust).
        assert progress_emitter.call_count == 3
        percentages = [call.args[0] for call in progress_emitter.call_args_list]
        assert percentages == sorted(percentages), (
            "progress percentages must be monotonically non-decreasing across rounds"
        )
        assert all(0 < p < 100 for p in percentages), (
            "in-flight percentages must be strictly between 0 and 100"
        )

    def test_progress_emitter_is_optional(self) -> None:
        # Tests + any future caller that doesn't care about progress
        # should be able to omit the emitter without orchestration
        # changes. The default ``None`` skips emission.
        perspectives._SCHEMA_CACHE.clear()
        responses = self._build_responses()
        step = _make_step_with_canned_responses(responses)
        timer = MagicMock()

        # Must NOT raise — progress emission is opt-in.
        generate_perspectives_decomposed(
            step,
            system_prompt="sys",
            context={
                "company_name": "Acme",
                "vision_statement": "Test vision",
                "mission_statement": "Test mission",
            },
            timer=timer,
        )

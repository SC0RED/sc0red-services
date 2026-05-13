"""Dispatch-only tests for the decomposed Phase 1 feature flag.

The full integration test for the decomposed path (P1.7.4 in the
optimize-strategy-map-latency tasks) is deferred to a follow-up — it
needs a deterministic mock AI factory across ~25 calls. These tests
focus on the dispatch wiring: confirms the env var routes execution
to the right code path without exercising the full chain.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.facades.company_accessor import CompanyAccessor
from src.models.model_company import (
    Company,
    CompanyProfile,
    Opportunity,
    OpportunityResult,
    RiskAssessment,
    RiskScore,
)
from src.pipeline.pipeline_steps.generate_strategy_map import (
    DECOMPOSED_FLAG_ENV_VAR,
    DECOMPOSED_SYNTHESIS_FLAG_ENV_VAR,
    GenerateStrategyMap,
    _decomposed_path_enabled,
    _decomposed_synthesis_enabled,
)


def _make_accessor() -> CompanyAccessor:
    company = Company(
        url="https://example.com",
        company_name="Acme",
        profile=CompanyProfile(
            company_name="Acme",
            industry="Retail",
            industry_sector="Specialty",
            business_model="B2C",
            description="A retailer.",
            products_services=["Coffee", "Bakery"],
            target_market="Suburban commuters",
            company_size="medium",
            revenue_model="direct sales",
        ),
        risk_assessment=RiskAssessment(
            risk_scores=[RiskScore(category="competitive_displacement", score=5.0, rationale="r")],
            overall_score=5.0,
            tier="moderate",
        ),
        opportunity_result=OpportunityResult(
            opportunities=[
                Opportunity(
                    title="Roll out loyalty",
                    impact_rating="High",
                    strategic_category="Customer Experience",
                    description="x",
                    implementation_steps=["a"],
                    timeline="Quick Win",
                    investment_range="$100K",
                    roi_estimate="20%",
                    value_lever="Revenue Side",
                )
            ]
        ),
    )
    return CompanyAccessor(company)


class TestDecomposedFlagEnv:
    def test_default_is_off(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(DECOMPOSED_FLAG_ENV_VAR, raising=False)
        assert _decomposed_path_enabled() is False

    def test_enabled_only_for_exact_string_one(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Exact-match check ('1' only). 'true', 'yes', etc. are NOT enough —
        # the flag is meant to be a deliberate ops-set toggle, not a
        # truthy guess.
        for value in ("1",):
            monkeypatch.setenv(DECOMPOSED_FLAG_ENV_VAR, value)
            assert _decomposed_path_enabled() is True

        for value in ("0", "true", "yes", "on", "True", ""):
            monkeypatch.setenv(DECOMPOSED_FLAG_ENV_VAR, value)
            assert _decomposed_path_enabled() is False


class TestDispatchRouting:
    """Exercises ``execute()`` at the dispatch level, mocking the heavy work.

    The Steps 1, 2, 7 calls + the perspective routing are all mocked so
    the tests focus on which branch (legacy vs decomposed) gets taken.
    """

    def _make_step(self) -> tuple[GenerateStrategyMap, MagicMock]:
        ai_factory = MagicMock()
        step = GenerateStrategyMap(ai_client_factory=ai_factory)
        step.entity_accessor = _make_accessor()  # type: ignore[assignment]
        step.request_executor = MagicMock()
        return step, ai_factory

    @patch("src.pipeline.pipeline_steps.generate_strategy_map.assemble_strategy_map")
    @patch("src.pipeline.pipeline_steps.generate_strategy_map.extract_core_values")
    @patch("src.pipeline.pipeline_steps.generate_strategy_map.run_step_7_arrows_and_gaps")
    @patch("src.pipeline.pipeline_steps.generate_strategy_map.run_steps_3_through_6_in_parallel")
    @patch("src.pipeline.pipeline_steps.generate_strategy_map.run_step_2_value_proposition")
    @patch("src.pipeline.pipeline_steps.generate_strategy_map.run_step_1_vision_mission")
    def test_flag_off_takes_legacy_parallel_path(
        self,
        mock_step1: MagicMock,
        mock_step2: MagicMock,
        mock_steps_3_6: MagicMock,
        mock_step7: MagicMock,
        mock_extract_core_values: MagicMock,
        mock_assemble: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv(DECOMPOSED_FLAG_ENV_VAR, raising=False)

        # Stub returns just enough for execute() to complete.
        mock_step1.return_value = ({"statement": "v"}, {"statement": "m"})
        mock_step2.return_value = {"primary": "operational_excellence"}
        mock_steps_3_6.return_value = {
            "financial": {"objectives": []},
            "customer": {"objectives": []},
            "internal_processes": {"themes": []},
            "organizational_capacity": {
                "people": {},
                "technology": {},
                "culture": {},
                "coreValues": {},
            },
        }
        mock_extract_core_values.return_value = {}
        mock_step7.return_value = {"strategicPriorities": [], "arrows": []}
        mock_assemble.return_value = MagicMock()

        step, _ = self._make_step()
        step.execute()

        mock_steps_3_6.assert_called_once()  # Legacy path was taken.

    @patch("src.pipeline.pipeline_steps.generate_strategy_map.assemble_strategy_map")
    @patch("src.pipeline.pipeline_steps.generate_strategy_map.run_step_7_arrows_and_gaps")
    @patch("src.pipeline.pipeline_steps.generate_strategy_map.run_steps_3_through_6_in_parallel")
    @patch("src.pipeline.pipeline_steps.generate_strategy_map.run_step_2_value_proposition")
    @patch("src.pipeline.pipeline_steps.generate_strategy_map.run_step_1_vision_mission")
    # Patch the SOURCE module's symbol, not the importer's. The dispatch
    # uses a lazy `from ... import generate_perspectives_decomposed`
    # inside `execute()`; the resolved name is never bound on
    # `generate_strategy_map`'s module namespace, so patching there
    # would silently no-op. Patching the source works because Python
    # caches the source module, so any later `from ... import` sees
    # the patched function.
    @patch(
        "src.pipeline.pipeline_steps._strategy_map_perspectives.generate_perspectives_decomposed"
    )
    def test_flag_on_calls_decomposed_orchestrator(
        self,
        mock_decomposed: MagicMock,
        mock_step1: MagicMock,
        mock_step2: MagicMock,
        mock_steps_3_6_legacy: MagicMock,
        mock_step7: MagicMock,
        mock_assemble: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv(DECOMPOSED_FLAG_ENV_VAR, "1")

        mock_step1.return_value = ({"statement": "v"}, {"statement": "m"})
        mock_step2.return_value = {"primary": "operational_excellence"}
        # Decomposed orchestrator returns the 5-tuple matching its signature.
        mock_decomposed.return_value = (
            {"objectives": []},
            {"objectives": []},
            {"themes": []},
            {"people": {}, "technology": {}, "culture": {}},
            {},
        )
        mock_step7.return_value = {"strategicPriorities": [], "arrows": []}
        mock_assemble.return_value = MagicMock()

        step, _ = self._make_step()
        step.execute()

        mock_decomposed.assert_called_once()
        # Legacy path MUST NOT run when the flag is ON.
        mock_steps_3_6_legacy.assert_not_called()


class TestDecomposedSynthesisFlagEnv:
    """Phase 2 flag: layered on top of Phase 1."""

    def test_default_is_off(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(DECOMPOSED_SYNTHESIS_FLAG_ENV_VAR, raising=False)
        assert _decomposed_synthesis_enabled() is False

    def test_enabled_only_for_exact_string_one(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for value in ("1",):
            monkeypatch.setenv(DECOMPOSED_SYNTHESIS_FLAG_ENV_VAR, value)
            assert _decomposed_synthesis_enabled() is True

        for value in ("0", "true", "yes", "on", "True", ""):
            monkeypatch.setenv(DECOMPOSED_SYNTHESIS_FLAG_ENV_VAR, value)
            assert _decomposed_synthesis_enabled() is False


class TestPhase2FlagLayering:
    """Tasks 5.4.1 - 5.4.4: flag-layering matrix for ``execute()``.

    Verifies the matrix in design Decision §4:
    - Both off → monolithic.
    - Phase 1 only → Phase 1.
    - Both on → Phase 1 + Phase 2.
    - Phase 2 only → ValueError raised before any AI call.
    """

    def _make_step(self) -> GenerateStrategyMap:
        ai_factory = MagicMock()
        step = GenerateStrategyMap(ai_client_factory=ai_factory)
        step.entity_accessor = _make_accessor()  # type: ignore[assignment]
        step.request_executor = MagicMock()
        return step

    def test_synthesis_flag_without_phase1_raises(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Phase 2 on, Phase 1 off → must raise before any AI call.
        monkeypatch.delenv(DECOMPOSED_FLAG_ENV_VAR, raising=False)
        monkeypatch.setenv(DECOMPOSED_SYNTHESIS_FLAG_ENV_VAR, "1")

        step = self._make_step()
        with pytest.raises(ValueError, match="DECOMPOSED_SYNTHESIS"):
            step.execute()

        # Confirm no AI call was attempted — the ai_client_factory's
        # ``get_client`` method should never have been touched.
        ai_factory = step._ai_client_factory  # type: ignore[attr-defined]
        ai_factory.get_client.assert_not_called()

    @patch("src.pipeline.pipeline_steps.generate_strategy_map.assemble_strategy_map")
    @patch("src.pipeline.pipeline_steps.generate_strategy_map.run_step_7_arrows_and_gaps")
    @patch("src.pipeline.pipeline_steps.generate_strategy_map.run_step_2_value_proposition")
    @patch("src.pipeline.pipeline_steps.generate_strategy_map.run_step_1_vision_mission")
    @patch(
        "src.pipeline.pipeline_steps._strategy_map_perspectives.generate_perspectives_decomposed"
    )
    def test_phase1_only_runs_phase1_paths(
        self,
        mock_decomposed: MagicMock,
        mock_step1: MagicMock,
        mock_step2: MagicMock,
        mock_step7: MagicMock,
        mock_assemble: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv(DECOMPOSED_FLAG_ENV_VAR, "1")
        monkeypatch.delenv(DECOMPOSED_SYNTHESIS_FLAG_ENV_VAR, raising=False)

        mock_step1.return_value = ({"statement": "v"}, {"statement": "m"})
        mock_step2.return_value = {"primary": "operational_excellence"}
        mock_decomposed.return_value = (
            {"objectives": []},
            {"objectives": []},
            {"themes": []},
            {"people": {}, "technology": {}, "culture": {}},
            {},
        )
        mock_step7.return_value = {"strategicPriorities": [], "arrows": []}
        mock_assemble.return_value = MagicMock()

        step = self._make_step()
        step.execute()

        # Phase 1 monolithic Step 1, Step 2, Step 7 all ran.
        mock_step1.assert_called_once()
        mock_step2.assert_called_once()
        mock_step7.assert_called_once()
        mock_decomposed.assert_called_once()

    @patch("src.pipeline.pipeline_steps.generate_strategy_map.assemble_strategy_map")
    @patch("src.pipeline.pipeline_steps.generate_strategy_map.run_step_7_arrows_and_gaps")
    @patch("src.pipeline.pipeline_steps.generate_strategy_map.run_step_2_value_proposition")
    @patch("src.pipeline.pipeline_steps.generate_strategy_map.run_step_1_vision_mission")
    @patch("src.pipeline.pipeline_steps._strategy_map_arrows.run_decomposed_arrows_and_priorities")
    @patch("src.pipeline.pipeline_steps._strategy_map_synthesis.run_decomposed_value_proposition")
    @patch("src.pipeline.pipeline_steps._strategy_map_synthesis.run_decomposed_vision_mission")
    @patch(
        "src.pipeline.pipeline_steps._strategy_map_perspectives.generate_perspectives_decomposed"
    )
    def test_both_flags_on_runs_phase1_plus_phase2(
        self,
        mock_decomposed_perspectives: MagicMock,
        mock_decomposed_vm: MagicMock,
        mock_decomposed_vp: MagicMock,
        mock_decomposed_arrows: MagicMock,
        mock_step1: MagicMock,
        mock_step2: MagicMock,
        mock_step7: MagicMock,
        mock_assemble: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv(DECOMPOSED_FLAG_ENV_VAR, "1")
        monkeypatch.setenv(DECOMPOSED_SYNTHESIS_FLAG_ENV_VAR, "1")

        mock_decomposed_vm.return_value = ({"statement": "v"}, {"statement": "m"})
        mock_decomposed_vp.return_value = {"primary": "operational_excellence"}
        mock_decomposed_perspectives.return_value = (
            {"objectives": []},
            {"objectives": []},
            {"themes": []},
            {"people": {}, "technology": {}, "culture": {}},
            {},
        )
        mock_decomposed_arrows.return_value = {
            "strategicPriorities": [],
            "arrows": [],
        }
        mock_assemble.return_value = MagicMock()

        step = self._make_step()
        step.execute()

        # Phase 2 paths ran.
        mock_decomposed_vm.assert_called_once()
        mock_decomposed_vp.assert_called_once()
        mock_decomposed_arrows.assert_called_once()
        # Phase 1 perspectives ran.
        mock_decomposed_perspectives.assert_called_once()
        # Phase 1 monolithic paths MUST NOT run when Phase 2 is also on.
        mock_step1.assert_not_called()
        mock_step2.assert_not_called()
        mock_step7.assert_not_called()

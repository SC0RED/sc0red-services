"""End-to-end integration test for the decomposed strategy-map pipeline.

Runs ``GenerateStrategyMap.execute()`` using a fixture ``Company``
populated with realistic profile / risks / opportunities / EBITDA /
value-chain inputs. The ``_run_ai_call`` layer is mocked to return
canned responses for every expected per-call label, covering:

- 4 vision/mission sub-calls (text + synth-yes/no per side).
- 4 value-proposition sub-calls (primary + secondary + exemplar + rationale).
- The Phase 1 perspective orchestrator (mocked at the import site).
- N per-pair arrow yes/no calls (computed from the fixture's pair count).
- 1 holistic priorities call.

The test asserts:
- The assembled ``StrategyMap`` validates against the Pydantic shape.
- The ``GenerateStrategyMap.timings`` detail block contains the expected
  per-call labels and no legacy monolithic labels.
- All four vision/mission labels are present.
- All four value-proposition labels are present.
- N per-pair arrow labels + holistic priorities label are present.
- The ``ai_call_gaps`` label is absent (removed under
  ``redesign-strategy-map`` Phase 2).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from signalfield_core.utilities.future_manager import FutureManagerError

from src.facades.company_accessor import CompanyAccessor
from src.models.model_company import (
    Company,
    CompanyProfile,
    Opportunity,
    OpportunityResult,
    RiskAssessment,
    RiskScore,
)
from src.pipeline.pipeline_steps._strategy_map_arrows import enumerate_arrow_pairs
from src.pipeline.pipeline_steps.ai_call import TokenCounts
from src.pipeline.pipeline_steps.generate_strategy_map import GenerateStrategyMap

# Per-call token counts the mocked ``_run_ai_call`` reports. Token telemetry
# pinning lives in ``test_step_timer.py``; this fixture only needs a real
# ``TokenCounts`` instance so ``timer.record_tokens(...)`` doesn't trip on a
# MagicMock attribute. The exact numbers are irrelevant for integration
# scenarios.
_CANNED_TOKEN_COUNTS = TokenCounts(input_tokens=100, output_tokens=50, cached_input_tokens=80)


def _make_accessor() -> CompanyAccessor:
    company = Company(
        url="https://example.com",
        company_name="Acme Retail",
        profile=CompanyProfile(
            company_name="Acme Retail",
            industry="Retail",
            industry_sector="Specialty",
            business_model="B2C",
            description="A specialty retailer.",
            products_services=["Coffee", "Bakery", "Sandwiches"],
            target_market="Suburban commuters",
            company_size="medium",
            revenue_model="direct sales",
        ),
        risk_assessment=RiskAssessment(
            risk_scores=[
                RiskScore(category="competitive_displacement", score=5.0, rationale="r1"),
                RiskScore(category="margin_compression", score=6.0, rationale="r2"),
            ],
            overall_score=5.5,
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
                ),
            ]
        ),
    )
    return CompanyAccessor(company)


def _build_phase1_perspective_results() -> tuple[
    dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]
]:
    """Return the 5-tuple shape ``generate_perspectives_decomposed`` produces."""
    financial = {
        "objectives": [
            {
                "id": "F1",
                "title": "Grow revenue in core markets",
                "definition": (
                    "Drive same-store revenue growth in existing geographies through "
                    "channel optimisation and assortment refresh."
                ),
                "category": "revenue_growth",
                "confidence": "HIGH",
                "rationale_source": None,
            },
            {
                "id": "F2",
                "title": "Improve operating efficiency",
                "definition": (
                    "Reduce cost per transaction across the store network via "
                    "automation and process simplification."
                ),
                "category": "productivity",
                "confidence": "MEDIUM",
                "rationale_source": None,
            },
            {
                "id": "F3",
                "title": "Maximise return on invested capital",
                "definition": (
                    "Allocate growth capital to highest-IRR opportunities and "
                    "discipline underperforming locations."
                ),
                "category": "productivity",
                "confidence": "MEDIUM",
                "rationale_source": None,
            },
        ]
    }
    customer = {
        "objectives": [
            {
                "id": "C1",
                "title": "I want fresh, high-quality products every visit",
                "definition": (
                    "Customers consistently find appealing fresh products that "
                    "match advertised quality standards across the visit window."
                ),
                "panel": "consumer",
                "confidence": "HIGH",
                "rationale_source": None,
            },
            {
                "id": "C2",
                "title": "I want recognition and rewards for loyalty",
                "definition": (
                    "Customers feel meaningfully recognised for repeat patronage and "
                    "receive valuable rewards proportional to their engagement."
                ),
                "panel": "consumer",
                "confidence": "MEDIUM",
                "rationale_source": None,
            },
            {
                "id": "C3",
                "title": "I want speed and convenience at every touchpoint",
                "definition": (
                    "Customers complete their typical transaction quickly with minimal "
                    "friction across order, payment, and pickup."
                ),
                "panel": "consumer",
                "confidence": "HIGH",
                "rationale_source": None,
            },
            {
                "id": "C4",
                "title": "I want associates who genuinely care",
                "definition": (
                    "Customers experience friendly, knowledgeable associates who "
                    "show they care about the customer's outcome."
                ),
                "panel": "consumer",
                "confidence": "MEDIUM",
                "rationale_source": None,
            },
        ]
    }
    internal_processes = {
        "themes": [
            {
                "name": "Differentiate",
                "supports_financial_objectives": ["F1"],
                "objectives": [
                    {
                        "id": "I1.1",
                        "title": "Build brand and product innovation",
                        "definition": (
                            "Develop and launch signature products that differentiate "
                            "the brand in core categories."
                        ),
                        "category": "innovation",
                        "confidence": "MEDIUM",
                        "rationale_source": None,
                    },
                    {
                        "id": "I1.2",
                        "title": "Refresh assortment continuously",
                        "definition": (
                            "Maintain a continuously refreshed assortment that responds "
                            "to seasonal demand and local preference."
                        ),
                        "category": "customer_management",
                        "confidence": "MEDIUM",
                        "rationale_source": None,
                    },
                ],
            },
            {
                "name": "Streamline",
                "supports_financial_objectives": ["F2"],
                "objectives": [
                    {
                        "id": "I2.1",
                        "title": "Cut waste across the supply chain",
                        "definition": (
                            "Reduce shrink and waste across procurement, logistics, "
                            "and store operations."
                        ),
                        "category": "operational_excellence",
                        "confidence": "MEDIUM",
                        "rationale_source": None,
                    },
                    {
                        "id": "I2.2",
                        "title": "Automate ordering and replenishment",
                        "definition": (
                            "Deploy automated demand forecasting and replenishment "
                            "to reduce manual ordering overhead."
                        ),
                        "category": "operational_excellence",
                        "confidence": "LOW",
                        "rationale_source": None,
                    },
                ],
            },
        ]
    }
    organizational_capacity = {
        "people": {
            "id": "O.P",
            "title": "Develop and retain customer-facing talent",
            "definition": (
                "Invest in associate development to build the customer-facing "
                "capabilities required by the differentiation strategy."
            ),
            "confidence": "MEDIUM",
            "rationale_source": None,
        },
        "technology": {
            "id": "O.T",
            "title": "Modernise the digital ordering and loyalty platform",
            "definition": (
                "Build a modern digital ordering and loyalty platform that supports "
                "the omnichannel customer journey."
            ),
            "confidence": "MEDIUM",
            "rationale_source": None,
        },
        "culture": {
            "id": "O.C",
            "title": "Live customer-centric cultural values",
            "definition": (
                "Embed customer-centric values in day-to-day operations and leadership behaviours."
            ),
            "confidence": "LOW",
            "rationale_source": None,
        },
    }
    core_values = {
        "values": ["Quality", "Speed", "Care"],
        "synthesised": True,
        "rationale": "Synthesised from public-facing brand materials.",
    }
    return financial, customer, internal_processes, organizational_capacity, core_values


def _build_phase2_canned_responses(
    financial: dict[str, Any],
    customer: dict[str, Any],
    internal_processes: dict[str, Any],
    organizational_capacity: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Build the canned ``_run_ai_call`` responses for the synthesis calls.

    The Phase 1 perspectives orchestrator is mocked at module level, so
    we only need canned responses for the synthesis + arrows calls:
      - 4 vision/mission sub-calls.
      - 4 value-proposition sub-calls.
      - N arrow yes/no sub-calls (from enumerate_arrow_pairs).
      - 1 priorities.
    """
    responses: dict[str, dict[str, Any]] = {
        # Vision/Mission bank.
        "vision_text": {"statement": "To be the most appetizing convenience retailer."},
        "mission_text": {
            "statement": "Provide convenient, appetizing food, beverage, and fuel experiences."
        },
        "vision_synth": {
            "synthesised": False,
            "rationale": "Verbatim from the company's 2024 strategy deck.",
        },
        "mission_synth": {
            "synthesised": True,
            "rationale": "Synthesised from store-locator and brand materials.",
        },
        # Value Proposition bank.
        "vp_primary": {"primary": "hybrid"},
        "vp_secondary": {"secondary": "operational_excellence"},
        "vp_exemplar": {
            "exemplar_company": "Mobil North American Marketing & Refining (HBR 2000 case)"
        },
        "vp_rationale": {
            "rationale": (
                "Public materials emphasise customer experience (clean stores, friendly "
                "associates, signature products) AND operational efficiency."
            )
        },
        # Priorities (gaps removed under redesign-strategy-map Phase 2).
        "priorities": {
            "strategicPriorities": [
                {
                    "name": "Differentiate",
                    "result": "Best-in-class signature products that drive same-store growth.",
                },
                {
                    "name": "Streamline",
                    "result": "Industry-leading cost-per-transaction across the store network.",
                },
            ]
        },
    }

    # Arrow yes/no calls — one per candidate pair.
    pairs = enumerate_arrow_pairs(
        financial=financial,
        customer=customer,
        internal_processes=internal_processes,
        organizational_capacity=organizational_capacity,
    )
    # 1-in-5 enable rate keeps the assembled arrows list within the
    # ``StrategyMap.arrows`` Pydantic constraint (max_length=12). Real-
    # world runs may need a stricter arrow_yesno prompt (or a post-filter)
    # to keep enable rate down — flagged as a follow-up to the eval gate.
    for index, (from_id, _from_title, to_id, _to_title) in enumerate(pairs):
        label = f"arrow_{from_id}_{to_id}"
        if index % 5 == 0:
            responses[label] = {
                "enables": True,
                "hypothesis": (
                    f"Mechanism: investing in {from_id} drives a specific outcome "
                    f"that advances {to_id} in the strategy map."
                ),
            }
        else:
            responses[label] = {"enables": False, "hypothesis": None}

    return responses


class TestSynthesisDecompositionIntegration:
    """Full execute() — decomposed path, no feature flags."""

    @patch(
        "src.pipeline.pipeline_steps.generate_strategy_map.generate_perspectives_decomposed"
    )
    def test_assembles_validated_strategy_map(
        self,
        mock_phase1_perspectives: MagicMock,
    ) -> None:
        # Phase 1 perspectives mocked — Phase 2 work runs end-to-end.
        financial, customer, internal_processes, capacity, core_values = (
            _build_phase1_perspective_results()
        )
        mock_phase1_perspectives.return_value = (
            financial,
            customer,
            internal_processes,
            capacity,
            core_values,
        )

        # Phase 2 sub-calls served via the canned AI factory.
        responses = _build_phase2_canned_responses(
            financial, customer, internal_processes, capacity
        )

        def fake_run_ai_call(
            _user_prompt: str,
            _schema: dict[str, Any],
            _system_prompt: str,
            label: str,
        ) -> tuple[str, dict[str, Any], float, TokenCounts]:
            return label, responses[label], 0.5, _CANNED_TOKEN_COUNTS

        ai_factory = MagicMock()
        accessor = _make_accessor()
        step = GenerateStrategyMap(ai_client_factory=ai_factory)
        step.entity_accessor = accessor  # type: ignore[assignment]
        step.request_executor = MagicMock()
        step._run_ai_call = MagicMock(side_effect=fake_run_ai_call)  # type: ignore[method-assign]

        step.execute()

        # Pydantic-validated StrategyMap landed on the accessor.
        assert accessor.company.strategy_map is not None

        # Details payload includes the timings block.
        add_details_calls = step.request_executor.add_details.call_args_list
        timings_calls = [
            call
            for call in add_details_calls
            if "GenerateStrategyMap.timings" in (call.args[0] if call.args else {})
        ]
        assert len(timings_calls) == 1
        timings = timings_calls[0].args[0]["GenerateStrategyMap.timings"]

        # 4 vision/mission sub-call labels.
        for label in (
            "ai_call_vision_text",
            "ai_call_mission_text",
            "ai_call_vision_synth",
            "ai_call_mission_synth",
        ):
            assert label in timings, f"missing {label}"

        # 4 value-proposition sub-call labels.
        for label in (
            "ai_call_vp_primary",
            "ai_call_vp_secondary",
            "ai_call_vp_exemplar",
            "ai_call_vp_rationale",
        ):
            assert label in timings, f"missing {label}"

        # Holistic priorities. ``ai_call_gaps`` was removed end-to-end
        # by the ``redesign-strategy-map`` Phase 2 change.
        assert "ai_call_priorities" in timings
        assert "ai_call_gaps" not in timings

        # N per-pair arrow labels.
        pairs = enumerate_arrow_pairs(
            financial=financial,
            customer=customer,
            internal_processes=internal_processes,
            organizational_capacity=capacity,
        )
        per_pair_labels = [k for k in timings if k.startswith("ai_call_arrow_")]
        assert len(per_pair_labels) == len(pairs)

        # Legacy monolithic labels absent.
        for legacy_label in (
            "ai_call_vision_mission",
            "ai_call_value_proposition",
            "ai_call_arrows_and_gaps",
        ):
            assert legacy_label not in timings, f"legacy label {legacy_label} leaked"

        # Token-count keys present per call. Pins the end-to-end wiring from
        # the SDK's ``StructuredResponse`` (input_tokens / output_tokens /
        # cached_input_tokens) → ``run_structured_ai_call`` (4-tuple return)
        # → ``StepTimer.record_tokens`` → the emitted CloudWatch payload.
        # A regression that drops ``timer.record_tokens(...)`` from any one
        # of the four strategy-map sub-modules trips this assertion even
        # when every other AI-call label still lands.
        for prefix in ("tokens_in_", "tokens_out_", "cached_tokens_"):
            matching_keys = [k for k in timings if k.startswith(prefix)]
            assert matching_keys, f"no {prefix}* keys in timings — record_tokens() missed"
            # Same per-call coverage as the elapsed entries — one token-keyed
            # entry per AI-call label.
            for label in ("ai_call_vision_text", "ai_call_vp_primary"):
                assert f"{prefix}{label}" in timings, f"missing {prefix}{label}"


class TestPrerequisiteValidation:
    """Prereq gates degrade gracefully (no map, no exception).

    When upstream pipeline output is missing (profile, risk assessment,
    opportunities), ``GenerateStrategyMap`` is a soft-fail step — it
    logs the gap, sets ``strategy_map=None`` on the accessor, and lets
    ``PersistResults`` save the rest of the analysis. The user gets
    every other artifact even when the map could not be produced.

    Programming errors (``AttributeError`` etc.) still propagate so
    SQS retries and CloudWatch surfaces the stack trace.
    """

    def _make_step(self) -> tuple[GenerateStrategyMap, CompanyAccessor, MagicMock]:
        ai_factory = MagicMock()
        accessor = _make_accessor()
        step = GenerateStrategyMap(ai_client_factory=ai_factory)
        step.entity_accessor = accessor  # type: ignore[assignment]
        step.request_executor = MagicMock()
        return step, accessor, ai_factory

    def test_missing_profile_skips_generation_and_clears_map(self) -> None:
        step, accessor, ai_factory = self._make_step()
        accessor.company.profile = None

        # Soft-fail: ``execute()`` returns normally, AI client untouched.
        step.execute()

        ai_factory.get_client.assert_not_called()
        assert accessor.company.strategy_map is None
        # The step still completes (degraded) — progress advances.
        step.request_executor.mark_question_complete.assert_called_with(
            "generate_strategy_map"
        )

    def test_missing_risk_assessment_skips_generation_and_clears_map(self) -> None:
        step, accessor, ai_factory = self._make_step()
        accessor.company.risk_assessment = None

        step.execute()

        ai_factory.get_client.assert_not_called()
        assert accessor.company.strategy_map is None

    def test_missing_opportunities_skips_generation_and_clears_map(self) -> None:
        step, accessor, ai_factory = self._make_step()
        accessor.company.opportunity_result = None

        step.execute()

        ai_factory.get_client.assert_not_called()
        assert accessor.company.strategy_map is None


class TestDomainErrorDegradesGracefully:
    """AI domain failures leave the analysis intact with no strategy map.

    The ``GenerateStrategyMap`` step is inline in the scan pipeline
    (per ``redesign-strategy-map`` Phase 4). To preserve the failure
    isolation the old dedicated worker provided, domain errors
    (``EngineError`` / ``FutureManagerError`` / ``ValueError`` /
    ``RuntimeError``) are caught inside the step. The user's risk
    scores, opportunities, EBITDA tree, and value chain are then
    persisted by ``PersistResults`` and the strategy-map slot on the
    analysis page simply doesn't render.
    """

    @patch(
        "src.pipeline.pipeline_steps.generate_strategy_map.generate_perspectives_decomposed"
    )
    def test_synthesis_runtime_error_is_caught_and_map_is_cleared(
        self,
        mock_phase1_perspectives: MagicMock,
    ) -> None:
        # Phase 1 perspectives never reached — synthesis (Step 1) fails first.
        # We still mock it so the test fails loud if the failure mode regresses.
        financial, customer, internal_processes, capacity, core_values = (
            _build_phase1_perspective_results()
        )
        mock_phase1_perspectives.return_value = (
            financial,
            customer,
            internal_processes,
            capacity,
            core_values,
        )

        def fake_run_ai_call(
            _user_prompt: str,
            _schema: dict[str, Any],
            _system_prompt: str,
            label: str,
        ) -> tuple[str, dict[str, Any], float, TokenCounts]:
            if label == "mission_text":
                msg = "simulated AI failure"
                raise RuntimeError(msg)
            return (
                label,
                {"statement": "v", "synthesised": False, "rationale": "r"},
                0.1,
                _CANNED_TOKEN_COUNTS,
            )

        ai_factory = MagicMock()
        accessor = _make_accessor()
        step = GenerateStrategyMap(ai_client_factory=ai_factory)
        step.entity_accessor = accessor  # type: ignore[assignment]
        step.request_executor = MagicMock()
        step._run_ai_call = MagicMock(side_effect=fake_run_ai_call)  # type: ignore[method-assign]

        # Soft-fail: ``execute()`` returns normally; the strategy map
        # on the accessor is ``None`` so ``PersistResults`` skips it.
        step.execute()

        assert accessor.company.strategy_map is None
        # ``add_details`` still ran once with a ``GenerateStrategyMap.timings``
        # block — the ``finally`` clause guarantees telemetry on the
        # degraded path.
        add_details_calls = step.request_executor.add_details.call_args_list
        timings_calls = [
            call
            for call in add_details_calls
            if "GenerateStrategyMap.timings" in (call.args[0] if call.args else {})
        ]
        assert len(timings_calls) == 1
        timings = timings_calls[0].args[0]["GenerateStrategyMap.timings"]
        assert "total" in timings
        # mission_text raised → its timing was NOT recorded.
        assert "ai_call_mission_text" not in timings
        # Step completion still fires so the progress bar advances.
        step.request_executor.mark_question_complete.assert_called_with(
            "generate_strategy_map"
        )

    def test_malformed_ai_response_key_error_is_caught_and_map_is_cleared(self) -> None:
        """A ``KeyError`` raised when accessing AI response data (e.g.
        ``vision_data["statement"]`` against a malformed response) is a
        DOMAIN error, not a programming bug — the AI returned a dict
        that doesn't conform to its schema. The soft-fail catches it
        and degrades. This guards the catch list against drift.
        """
        ai_factory = MagicMock()
        accessor = _make_accessor()
        step = GenerateStrategyMap(ai_client_factory=ai_factory)
        step.entity_accessor = accessor  # type: ignore[assignment]
        step.request_executor = MagicMock()

        def fake_run_ai_call(
            _user_prompt: str,
            _schema: dict[str, Any],
            _system_prompt: str,
            label: str,
        ) -> tuple[str, dict[str, Any], float]:
            # Return a dict missing the ``statement`` key that the
            # synthesis caller subscripts. ``vision_data["statement"]``
            # raises ``KeyError`` outside any ``FutureManager`` block.
            return label, {"synthesised": False, "rationale": "r"}, 0.1

        step._run_ai_call = MagicMock(side_effect=fake_run_ai_call)  # type: ignore[method-assign]

        step.execute()

        assert accessor.company.strategy_map is None
        step.request_executor.mark_question_complete.assert_called_with(
            "generate_strategy_map"
        )

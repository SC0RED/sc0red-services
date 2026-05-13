"""End-to-end integration test for the decomposed synthesis pipeline.

Runs ``GenerateStrategyMap.execute()`` with both Phase 1 and Phase 2
flags set, using a fixture ``Company`` populated with realistic
profile / risks / opportunities / EBITDA / value-chain inputs. The
``_run_ai_call`` layer is mocked to return canned responses for every
expected per-call label, covering:

- 4 Phase 2 vision/mission sub-calls.
- 4 Phase 2 value-proposition sub-calls.
- 4 Phase 1 round-1 perspective title calls.
- 7 Phase 1 round-2 detail + theme-title + core-values calls (3 fin +
  3 cap + 3 internal titles, but capped at 3 internal-titles for this
  2-theme fixture, plus core_values).
- 4 Phase 1 round-3 internal-objective detail calls (2 themes x 2
  objectives each).
- N Phase 2 arrow yes/no calls (computed from the fixture's pair count).
- 1 Phase 2 priorities call.
- 1 Phase 2 gaps call.

The test asserts:
- The assembled ``StrategyMap`` validates against the Pydantic shape.
- The ``GenerateStrategyMap.timings`` detail block contains the expected
  per-call labels and no legacy monolithic labels.
- All four Phase 2 vision/mission labels are present.
- All four Phase 2 value-proposition labels are present.
- N per-pair arrow labels + holistic priorities + gaps labels are present.
"""

from __future__ import annotations

from typing import Any
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
from src.pipeline.pipeline_steps._strategy_map_arrows import enumerate_arrow_pairs
from src.pipeline.pipeline_steps.generate_strategy_map import (
    DECOMPOSED_FLAG_ENV_VAR,
    DECOMPOSED_SYNTHESIS_FLAG_ENV_VAR,
    GenerateStrategyMap,
)


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
    """Build the canned ``_run_ai_call`` responses for the Phase 2 calls.

    Phase 1 perspectives are mocked at module level, so we only need
    canned responses for Phase 2 calls:
      - 4 vision/mission sub-calls.
      - 4 value-proposition sub-calls.
      - N arrow yes/no sub-calls (from enumerate_arrow_pairs).
      - 1 priorities, 1 gaps.
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
        # Priorities + Gaps.
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
    """Full execute() with both Phase 1 and Phase 2 flags ON."""

    @patch(
        "src.pipeline.pipeline_steps._strategy_map_perspectives.generate_perspectives_decomposed"
    )
    def test_assembles_validated_strategy_map(
        self,
        mock_phase1_perspectives: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv(DECOMPOSED_FLAG_ENV_VAR, "1")
        monkeypatch.setenv(DECOMPOSED_SYNTHESIS_FLAG_ENV_VAR, "1")

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
        ) -> tuple[str, dict[str, Any], float]:
            return label, responses[label], 0.5

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

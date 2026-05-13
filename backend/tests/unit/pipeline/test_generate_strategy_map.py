"""Tests for GenerateStrategyMap pipeline step.

Mocks the AI client factory so the step can be exercised end-to-end
without real LLM calls. Each of the 7 steps in the chain returns a
canned response from the mock; the test asserts the assembled
StrategyMap is well-formed and persisted on the accessor.

Tests cover:
- happy path with full pipeline output (verifies assembly, schema
  conformance, and that all 7 step responses are consumed)
- prerequisites missing (profile / risk assessment / opportunities)
- malformed AI responses (missing required keys per step)
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.facades.company_accessor import CompanyAccessor
from src.models.model_company import (
    Company,
    CompanyProfile,
    EbitdaNode,
    EbitdaTreeResult,
    Opportunity,
    OpportunityResult,
    RiskAssessment,
    RiskScore,
    ValueChainResult,
    ValueChainStep,
)
from src.models.model_strategy_map import StrategyMap
from src.pipeline.pipeline_steps.generate_strategy_map import GenerateStrategyMap

# ── Canned AI responses for each of the 7 steps ─────────────────────────────


def _step1_response() -> dict:
    return {
        "vision": {
            "statement": "To be the most appetizing convenience retailer",
            "synthesised": False,
            "rationale": "Verbatim from the company's published brand materials.",
        },
        "mission": {
            "statement": "Provide convenient food, beverages, and fuel to commuters.",
            "synthesised": True,
            "rationale": "Synthesised from store-locator and brand materials.",
        },
    }


def _step2_response() -> dict:
    return {
        "primary": "customer_intimacy",
        "secondary": None,
        "rationale": (
            "Public materials emphasise associate friendliness and brand-experience "
            "differentiation, with operational efficiency framed as a supporting "
            "capability rather than the primary value proposition."
        ),
        "exemplar_company": "Wawa",
    }


def _step3_response() -> dict:
    return {
        "objectives": [
            {
                "id": "F1",
                "title": "Grow profitable revenue across markets",
                "definition": (
                    "We will grow same-segment revenue by deepening engagement "
                    "with current customers and entering adjacent markets, with "
                    "year-over-year revenue growth as the primary measure of "
                    "expansion success."
                ),
                "category": "revenue_growth",
                "confidence": "HIGH",
                "rationale_source": "EBITDA tree revenue branch shows 12% YoY growth.",
            },
            {
                "id": "F2",
                "title": "Drive operational efficiency",
                "definition": (
                    "We will improve cost-to-serve metrics by automating routine "
                    "operations, reducing waste in supply chain, and optimising "
                    "labour scheduling against actual demand patterns."
                ),
                "category": "productivity",
                "confidence": "MEDIUM",
                "rationale_source": "Industry pattern; cost-side EBITDA branch.",
            },
            {
                "id": "F3",
                "title": "Maximise return on invested capital",
                "definition": (
                    "We will allocate capital toward the highest-return store "
                    "formats and geographies, retiring or repositioning stores "
                    "below threshold IRR within a defined refresh cycle."
                ),
                "category": "productivity",
                "confidence": "MEDIUM",
                "rationale_source": "Inferred from typical PE-owned retail strategy.",
            },
        ]
    }


def _step4_response() -> dict:
    return {
        "objectives": [
            {
                "id": "C1",
                "title": "Offer me fresh products in a friendly environment",
                "definition": (
                    "I rely on this brand for fast, friendly service and quality "
                    "products. I value the consistent in-store experience and "
                    "the friendly associates who treat me as a regular."
                ),
                "panel": "consumer",
                "confidence": "HIGH",
                "rationale_source": "Customer testimonials emphasise these themes.",
            },
            {
                "id": "C2",
                "title": "Recognise my loyalty and reward me for it",
                "definition": (
                    "I expect the loyalty programme to acknowledge my repeated "
                    "visits with meaningful rewards that I actually use, not "
                    "just promotional clutter."
                ),
                "panel": "consumer",
                "confidence": "MEDIUM",
                "rationale_source": "Industry-standard expectation for retail.",
            },
            {
                "id": "C3",
                "title": "Make my visit fast and convenient",
                "definition": (
                    "I want to get in, get what I need, and get out. The store "
                    "layout, checkout speed, and service at the counter all "
                    "contribute to whether I'll stop here next time."
                ),
                "panel": "consumer",
                "confidence": "HIGH",
                "rationale_source": "Convenience-retail value proposition.",
            },
        ]
    }


def _step5_response() -> dict:
    return {
        "themes": [
            {
                "name": "Grow Through Foodservice",
                "supports_financial_objectives": ["F1"],
                "objectives": [
                    {
                        "id": "I1.1",
                        "title": "Develop signature food and beverage offers",
                        "definition": (
                            "We will create and improve fresh food and beverage "
                            "offers that differentiate the brand and grow basket "
                            "size, with regular product platform reviews."
                        ),
                        "category": "innovation",
                        "confidence": "HIGH",
                    },
                    {
                        "id": "I1.2",
                        "title": "Communicate the fresh-and-inviting message",
                        "definition": (
                            "We will deploy multi-channel marketing that "
                            "communicates the freshness and quality of our "
                            "offer to existing customers and prospects."
                        ),
                        "category": "customer_management",
                        "confidence": "MEDIUM",
                    },
                ],
            },
            {
                "name": "Deliver Convenience and Value",
                "supports_financial_objectives": ["F1", "F2"],
                "objectives": [
                    {
                        "id": "I2.1",
                        "title": "Improve end-to-end process throughput",
                        "definition": (
                            "We will continuously improve the throughput, "
                            "quality, and cost of our end-to-end processes "
                            "through a disciplined data-driven approach."
                        ),
                        "category": "operational_excellence",
                        "confidence": "HIGH",
                    }
                ],
            },
        ]
    }


def _step6_response() -> dict:
    return {
        "people": {
            "id": "O.P",
            "title": "Develop our associates as brand ambassadors",
            "definition": (
                "We will invest in associate development through structured "
                "training, succession planning, and a culture of ownership "
                "that translates into the in-store experience our customers "
                "value."
            ),
            "confidence": "MEDIUM",
            "rationale_source": "Careers page emphasises associate ownership.",
        },
        "technology": {
            "id": "O.T",
            "title": "Deliver reliable systems and data-driven insight",
            "definition": (
                "We will provide consistently reliable technical products "
                "and support services, valuable insights for forward-looking "
                "decisions, and cost-effective and innovative solutions."
            ),
            "confidence": "MEDIUM",
            "rationale_source": "Industry pattern; no specific tech-stack signals.",
        },
        "culture": {
            "id": "O.C",
            "title": "Live our values in every interaction",
            "definition": (
                "Our values are the foundation of how we work. We will live "
                "them consistently across the organisation, embedding them "
                "in hiring, performance management, recognition, and "
                "decision-making."
            ),
            "confidence": "LOW",
            "rationale_source": "Values implied but not explicitly published.",
        },
        "coreValues": {
            "values": [
                "Care for customers",
                "Respect for associates",
                "Continuous improvement",
                "Community presence",
            ],
            "synthesised": True,
            "rationale": "Synthesised from public brand materials.",
        },
    }


def _step7_response() -> dict:
    return {
        "strategicPriorities": [
            {
                "name": "Grow Through Foodservice",
                "result": "Best-in-class signature food platform driving same-store growth.",
            },
            {
                "name": "Deliver Convenience and Value",
                "result": "Industry-leading customer perception of speed and value.",
            },
        ],
        "arrows": [
            {
                "from": "O.P",
                "to": "I1.1",
                "hypothesis": (
                    "Investing in associate development (O.P) enables higher-"
                    "quality execution of new food platforms (I1.1)."
                ),
            },
            {
                "from": "I1.1",
                "to": "C1",
                "hypothesis": (
                    "Signature food platforms (I1.1) drive the customer "
                    "perception of fresh, friendly experience (C1)."
                ),
            },
            {
                "from": "C1",
                "to": "F1",
                "hypothesis": (
                    "A delighted, returning customer (C1) drives same-store "
                    "revenue growth (F1) through frequency and basket size."
                ),
            },
            {
                "from": "I2.1",
                "to": "F2",
                "hypothesis": (
                    "Process improvements (I2.1) lower cost-to-serve, "
                    "directly contributing to operational efficiency (F2)."
                ),
            },
            {
                "from": "O.T",
                "to": "I2.1",
                "hypothesis": (
                    "Reliable systems and data-driven insight (O.T) enable "
                    "the disciplined process improvement programme (I2.1)."
                ),
            },
        ],
    }


# ── Test fixtures ───────────────────────────────────────────────────────────


def _make_company() -> Company:
    company = Company(url="https://example.com", company_name="Test Corp")
    company.scraped_text = "Convenience retailer focused on fresh food and friendly service."
    company.profile = CompanyProfile(
        company_name="Test Corp",
        industry="convenience retail",
        business_model="retail with foodservice and fuel",
        description="Convenience stores in the U.S. mid-Atlantic region.",
        tech_signals=["POS systems", "loyalty app"],
    )
    company.risk_assessment = RiskAssessment(
        risk_scores=[
            RiskScore(category="competitive_displacement", score=6, rationale="Local competition."),
            RiskScore(category="talent_workforce", score=5, rationale="Tight labour market."),
            RiskScore(category="customer_behavior", score=4, rationale="Shifting demographics."),
        ],
        overall_score=5.0,
        tier="moderate",
        top_risks=["competitive_displacement"],
        analysis_summary="Moderate risk profile.",
    )
    company.opportunity_result = OpportunityResult(
        opportunities=[
            Opportunity(
                title="Loyalty programme refresh",
                strategic_category="Operational Efficiency",
                value_lever="Revenue Side",
                impact_rating="High",
            ),
            Opportunity(
                title="Refrigeration upgrades",
                strategic_category="Operational Efficiency",
                value_lever="Cost Side",
                impact_rating="Medium",
            ),
        ],
        top_three_immediate_actions=["Action 1", "Action 2", "Action 3"],
    )
    company.ebitda_tree = EbitdaTreeResult(
        summary="Convenience-retail EBITDA tree.",
        revenue_estimate="$3-5B",
        ebitda_estimate="$200-400M",
        nodes=[
            EbitdaNode(
                id="root",
                label="Revenue",
                type="revenue",
                value_range="$3-5B",
                description="Top-line revenue",
                linked_opportunity_indices=[0],
            )
        ],
    )
    company.value_chain = ValueChainResult(
        steps=[
            ValueChainStep(
                id="ops",
                label="Store Operations",
                description="In-store service",
                category="primary",
                risk_categories=["talent_workforce"],
                opportunity_indices=[0],
            )
        ],
        summary="Value chain emphasises store operations.",
    )
    return company


def _make_mock_factory() -> MagicMock:
    """AI factory whose successive calls return the 7 canned responses.

    Step 1 fires once, Step 2 once, Steps 3-6 in parallel (any order
    among themselves), Step 7 once. We map by label inside the
    `query_structured` side-effect via the system prompt's role —
    but simpler: drive responses by call-count ordering.

    Actually the cleanest approach: side-effect the response based on
    the user prompt content. Each template produces a recognisable
    fragment.
    """
    mock_factory = MagicMock()
    mock_client = MagicMock()
    mock_factory.get_client.return_value = mock_client

    def respond(input_text: str, json_schema: dict) -> MagicMock:
        del json_schema  # validated separately by Pydantic; not used here
        response = MagicMock()
        response.metadata = {"tokens": 100}
        # Match on the unique "## Step N — Title" header at the top
        # of each template, NOT on body content (templates reference
        # earlier steps in their body, e.g. Step 6 says "from Step 5",
        # so a substring match on "Step 5" anywhere in the prompt
        # would falsely fire for Step 6's prompt).
        if "## Step 1 — Vision and Mission" in input_text:
            response.content = _step1_response()
        elif "## Step 2 — Customer Value Proposition" in input_text:
            response.content = _step2_response()
        elif "## Step 3 — Financial Perspective" in input_text:
            response.content = _step3_response()
        elif "## Step 4 — Customer Perspective" in input_text:
            response.content = _step4_response()
        elif "## Step 5 — Internal Processes" in input_text:
            response.content = _step5_response()
        elif "## Step 6 — Organizational Capacity" in input_text:
            response.content = _step6_response()
        elif "## Step 7 — Arrows and" in input_text:
            response.content = _step7_response()
        else:
            msg = f"Unrecognised step prompt:\n{input_text[:500]}"
            raise AssertionError(msg)
        return response

    mock_client.query_structured.side_effect = respond
    return mock_factory


# ── Tests ────────────────────────────────────────────────────────────────────


class TestGenerateStrategyMap:
    def test_happy_path_produces_validated_strategy_map(self):
        company = _make_company()
        accessor = CompanyAccessor(company)

        step = GenerateStrategyMap(ai_client_factory=_make_mock_factory())
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        step.execute()

        assert company.strategy_map is not None
        assert isinstance(company.strategy_map, StrategyMap)

    def test_strategy_map_has_all_perspectives(self):
        company = _make_company()
        accessor = CompanyAccessor(company)

        step = GenerateStrategyMap(ai_client_factory=_make_mock_factory())
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        step.execute()
        sm = company.strategy_map
        assert sm is not None
        assert len(sm.financial.objectives) == 3
        assert len(sm.customer.objectives) == 3
        assert len(sm.internal_processes.themes) == 2
        assert sm.organizational_capacity.people.id == "O.P"
        assert sm.organizational_capacity.technology.id == "O.T"
        assert sm.organizational_capacity.culture.id == "O.C"

    def test_strategy_map_includes_arrows(self):
        company = _make_company()
        accessor = CompanyAccessor(company)

        step = GenerateStrategyMap(ai_client_factory=_make_mock_factory())
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        step.execute()
        sm = company.strategy_map
        assert sm is not None
        assert len(sm.arrows) >= 5
        # Arrows reference real objective IDs
        all_ids = {sm.organizational_capacity.people.id, sm.organizational_capacity.technology.id, sm.organizational_capacity.culture.id}
        all_ids.update(o.id for o in sm.financial.objectives)
        all_ids.update(o.id for o in sm.customer.objectives)
        for theme in sm.internal_processes.themes:
            all_ids.update(o.id for o in theme.objectives)
        for arrow in sm.arrows:
            assert arrow.from_id in all_ids
            assert arrow.to_id in all_ids

    def test_missing_profile_raises(self):
        company = _make_company()
        company.profile = None
        accessor = CompanyAccessor(company)

        step = GenerateStrategyMap(ai_client_factory=_make_mock_factory())
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        with pytest.raises(ValueError, match="profile missing"):
            step.execute()

    def test_missing_risk_assessment_raises(self):
        company = _make_company()
        company.risk_assessment = None
        accessor = CompanyAccessor(company)

        step = GenerateStrategyMap(ai_client_factory=_make_mock_factory())
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        with pytest.raises(ValueError, match="risk assessment missing"):
            step.execute()

    def test_missing_opportunities_raises(self):
        company = _make_company()
        company.opportunity_result = None
        accessor = CompanyAccessor(company)

        step = GenerateStrategyMap(ai_client_factory=_make_mock_factory())
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        with pytest.raises(ValueError, match="opportunity result missing"):
            step.execute()

    def test_step_1_missing_vision_raises(self):
        company = _make_company()
        accessor = CompanyAccessor(company)

        # Mock that returns Step 1 content without the `vision` key.
        mock_factory = MagicMock()
        mock_client = MagicMock()
        mock_factory.get_client.return_value = mock_client
        bad_response = MagicMock()
        bad_response.content = {"mission": _step1_response()["mission"]}
        bad_response.metadata = {}
        mock_client.query_structured.return_value = bad_response

        step = GenerateStrategyMap(ai_client_factory=mock_factory)
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        with pytest.raises(ValueError, match="Step 1 response missing"):
            step.execute()


class TestGenerateStrategyMapTelemetry:
    """Per ai-strategy-map spec: GenerateStrategyMap emits per-AI-call timings.

    Pattern matches `ParallelProfileRiskAndIdeation` and `DetailOpportunities`:
    a `StepTimer` records each AI call's elapsed wall-clock under labels prefixed
    with `ai_call_`, plus a `total` entry, and the dict is emitted via
    `request_executor.add_details(...)` keyed `GenerateStrategyMap.timings`.
    """

    @staticmethod
    def _captured_timings(executor: MagicMock) -> dict[str, float]:
        """Pull the timings dict out of the (one) `add_details` call."""
        executor.add_details.assert_called_once()
        payload = executor.add_details.call_args.args[0]
        assert "GenerateStrategyMap.timings" in payload, (
            f"Expected key 'GenerateStrategyMap.timings' in details payload; "
            f"got keys={list(payload.keys())}"
        )
        return payload["GenerateStrategyMap.timings"]

    def test_emits_timings_detail_block(self):
        """Happy path: one add_details call with the canonical key."""
        company = _make_company()
        accessor = CompanyAccessor(company)

        step = GenerateStrategyMap(ai_client_factory=_make_mock_factory())
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        step.execute()

        timings = self._captured_timings(step._request_executor)
        assert "total" in timings
        assert timings["total"] > 0

    def test_records_one_entry_per_ai_call_today(self):
        """Today's call shape: 7 calls → 7 `ai_call_*` entries plus `total`."""
        company = _make_company()
        accessor = CompanyAccessor(company)

        step = GenerateStrategyMap(ai_client_factory=_make_mock_factory())
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        step.execute()

        timings = self._captured_timings(step._request_executor)
        ai_call_keys = {k for k in timings if k.startswith("ai_call_")}
        # Step 1 + Step 2 + Steps 3-6 (4 perspectives) + Step 7 = 7 calls.
        assert len(ai_call_keys) == 7, (
            f"Expected 7 ai_call_* entries, got {len(ai_call_keys)}: {ai_call_keys}"
        )

    def test_label_naming_convention(self):
        """Labels must match the `parallel_profile_risk` style: ``ai_call_{descriptor}``."""
        company = _make_company()
        accessor = CompanyAccessor(company)

        step = GenerateStrategyMap(ai_client_factory=_make_mock_factory())
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        step.execute()

        timings = self._captured_timings(step._request_executor)
        expected = {
            "ai_call_vision_mission",
            "ai_call_value_proposition",
            "ai_call_financial",
            "ai_call_customer",
            "ai_call_internal_processes",
            "ai_call_organizational_capacity",
            "ai_call_arrows_and_gaps",
        }
        present = {k for k in timings if k.startswith("ai_call_")}
        assert present == expected, f"missing={expected - present}, extra={present - expected}"

    def test_emits_partial_timings_on_failure(self):
        """Per spec scenario: failed call still emits the partial timings block."""
        company = _make_company()
        accessor = CompanyAccessor(company)

        # Mock that returns Step 1 successfully, then raises on Step 2.
        mock_factory = MagicMock()
        mock_client = MagicMock()
        mock_factory.get_client.return_value = mock_client

        call_log: list[str] = []

        def respond(input_text: str, json_schema: dict) -> MagicMock:
            del json_schema
            if "## Step 1 — Vision and Mission" in input_text:
                call_log.append("step_1")
                response = MagicMock()
                response.content = _step1_response()
                response.metadata = {}
                return response
            if "## Step 2 — Customer Value Proposition" in input_text:
                call_log.append("step_2")
                msg = "simulated AI failure"
                raise RuntimeError(msg)
            msg = f"Unexpected prompt:\n{input_text[:200]}"
            raise AssertionError(msg)

        mock_client.query_structured.side_effect = respond

        step = GenerateStrategyMap(ai_client_factory=mock_factory)
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        with pytest.raises(RuntimeError, match="simulated AI failure"):
            step.execute()

        # Step 1 succeeded → its timing recorded; Step 2 raised → no entry.
        # Either way, add_details fires once on the way out via the finally block.
        timings = self._captured_timings(step._request_executor)
        assert "ai_call_vision_mission" in timings
        assert "ai_call_value_proposition" not in timings
        assert "total" in timings
        assert call_log == ["step_1", "step_2"]

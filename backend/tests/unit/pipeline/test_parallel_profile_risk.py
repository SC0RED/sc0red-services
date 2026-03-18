"""Tests for ParallelProfileRiskAndIdeation composite pipeline step."""

from unittest.mock import MagicMock, call

import pytest
from signalfield_core.models.enums import Precision, ReasoningEffort, Verbosity

from src.facades.company_accessor import CompanyAccessor
from src.models.model_company import Company, RiskScore
from src.pipeline.pipeline_steps.assess_risk import (
    RISK_BATCH_A_CATEGORIES,
    RISK_BATCH_B_CATEGORIES,
    RISK_SYSTEM_PROMPT,
)
from src.pipeline.pipeline_steps.extract_profile import PROFILE_SYSTEM_PROMPT
from src.pipeline.pipeline_steps.ideate_opportunities import IDEATION_SYSTEM_PROMPT
from src.pipeline.pipeline_steps.parallel_profile_risk import (
    ParallelProfileRiskAndIdeation,
    compute_risk_aggregates,
)

_PROFILE_RESPONSE = {
    "company_name": "Acme Corp",
    "industry": "B2B SaaS - HR Technology",
    "industry_sector": "Technology",
    "business_model": "SaaS",
    "description": "HR platform for mid-market",
    "products_services": ["ATS", "Payroll"],
    "target_market": "Mid-market companies",
    "company_size": "Mid-market 200-1000",
    "revenue_model": "subscription",
    "tech_signals": ["React", "AWS"],
    "competitive_positioning": "AI-first HR",
    "ai_maturity": "Partial adoption",
    "key_risks_visible": [],
}

_RISK_BATCH_A_RESPONSE = {
    "risk_scores": [
        {
            "category": "competitive_displacement",
            "score": 8,
            "rationale": "High competition from AI-native HR platforms",
        },
        {
            "category": "technology_obsolescence",
            "score": 6,
            "rationale": "Some legacy tech but modernizing",
        },
        {
            "category": "customer_behavior",
            "score": 5,
            "rationale": "Moderate shift to AI-first tools",
        },
        {
            "category": "margin_compression",
            "score": 4,
            "rationale": "Some pressure from low-cost AI alternatives",
        },
    ],
}

_RISK_BATCH_B_RESPONSE = {
    "risk_scores": [
        {
            "category": "talent_workforce",
            "score": 7,
            "rationale": "AI automating HR functions they sell",
        },
        {
            "category": "regulatory_compliance",
            "score": 3,
            "rationale": "Low regulatory pressure currently",
        },
        {
            "category": "supply_chain",
            "score": 2,
            "rationale": "Minimal supply chain exposure as SaaS",
        },
        {
            "category": "data_ip",
            "score": 5,
            "rationale": "Moderate risk around HR data moats",
        },
    ],
}


def _make_ideation_response(category_id: str) -> dict:
    return {
        "title": f"AI opportunity for {category_id}",
        "description": f"Deploy AI to address {category_id} risk",
        "value_lever": "Revenue Side",
        "strategic_category": "Competitive Moat",
        "impact_rating": "High",
    }


class TestParallelProfileRiskAndIdeation:
    def _make_mock_factory(
        self,
        profile_data: dict = _PROFILE_RESPONSE,
        risk_batch_a_data: dict = _RISK_BATCH_A_RESPONSE,
        risk_batch_b_data: dict = _RISK_BATCH_B_RESPONSE,
    ) -> MagicMock:
        """Create a mock AIClientFactory routing by system prompt.

        Routes: profile → profile_data, risk → risk batches, ideation → ideation responses.
        """
        mock_factory = MagicMock()

        # Profile client
        profile_client = MagicMock()
        profile_response = MagicMock()
        profile_response.content = profile_data
        profile_response.metadata = {"tokens": 100}
        profile_client.query_structured.return_value = profile_response

        # Risk clients (dispatched by call order)
        risk_call_count = {"count": 0}

        risk_client_a = MagicMock()
        risk_response_a = MagicMock()
        risk_response_a.content = risk_batch_a_data
        risk_response_a.metadata = {"tokens": 80}
        risk_client_a.query_structured.return_value = risk_response_a

        risk_client_b = MagicMock()
        risk_response_b = MagicMock()
        risk_response_b.content = risk_batch_b_data
        risk_response_b.metadata = {"tokens": 80}
        risk_client_b.query_structured.return_value = risk_response_b

        # Ideation client — returns different titles by inspecting prompt
        ideation_client = MagicMock()

        def ideation_query_side_effect(*, input_text, json_schema):
            # Extract category from prompt text (e.g., "RISK CATEGORY: competitive_displacement")
            for cat in [
                "competitive_displacement", "technology_obsolescence",
                "customer_behavior", "margin_compression",
                "talent_workforce", "regulatory_compliance",
                "supply_chain", "data_ip",
            ]:
                if f"RISK CATEGORY: {cat}" in input_text:
                    response = MagicMock()
                    response.content = _make_ideation_response(cat)
                    response.metadata = {"tokens": 50}
                    return response
            response = MagicMock()
            response.content = _make_ideation_response("unknown")
            response.metadata = {"tokens": 50}
            return response

        ideation_client.query_structured.side_effect = ideation_query_side_effect

        def get_client_side_effect(**kwargs):
            instructions = kwargs.get("instructions", "")
            if instructions == PROFILE_SYSTEM_PROMPT:
                return profile_client
            if instructions == RISK_SYSTEM_PROMPT:
                risk_call_count["count"] += 1
                if risk_call_count["count"] == 1:
                    return risk_client_a
                return risk_client_b
            if instructions == IDEATION_SYSTEM_PROMPT:
                return ideation_client
            return MagicMock()

        mock_factory.get_client.side_effect = get_client_side_effect
        return mock_factory

    def _make_accessor(
        self,
        scraped_text: str = "Acme Corp is an HR technology company...",
        url: str = "https://acme.com",
        document_text: str | None = None,
    ) -> CompanyAccessor:
        company = Company(url=url)
        company.scraped_text = scraped_text
        if document_text:
            company.document_text = document_text
        return CompanyAccessor(company)

    def test_successful_parallel_execution(self):
        mock_factory = self._make_mock_factory()
        accessor = self._make_accessor()

        step = ParallelProfileRiskAndIdeation(ai_client_factory=mock_factory)
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        step.execute()

        # Profile is set
        assert accessor.company.profile is not None
        assert accessor.company.profile.company_name == "Acme Corp"
        assert accessor.company.profile.industry == "B2B SaaS - HR Technology"

        # Risk assessment is set with all 8 scores merged
        assert accessor.company.risk_assessment is not None
        assert len(accessor.company.risk_assessment.risk_scores) == 8

        # Aggregates are computed programmatically
        assert accessor.company.risk_assessment.overall_score == 5.0
        assert accessor.company.risk_assessment.tier == "moderate"
        assert accessor.company.risk_assessment.top_risks == [
            "competitive_displacement",
            "talent_workforce",
            "technology_obsolescence",
        ]

        # Ranked ideations are stored
        ranked = accessor.get_ranked_ideations()
        assert len(ranked) > 0
        assert len(ranked) <= 5  # max_count default
        for ideation in ranked:
            assert "title" in ideation
            assert "risk_category" in ideation
            assert "top_three_immediate_actions" in ideation

        # All three questions marked complete
        calls = step._request_executor.mark_question_complete.call_args_list
        completed = {c[0][0] for c in calls}
        assert "extract_profile" in completed
        assert "assess_risk" in completed
        assert "ideate_opportunities" in completed

        # Details added (timings)
        step._request_executor.add_details.assert_called_once()
        details = step._request_executor.add_details.call_args[0][0]
        assert "ParallelProfileRiskAndIdeation.timings" in details

    def test_eleven_ai_clients_created(self):
        mock_factory = self._make_mock_factory()
        accessor = self._make_accessor()

        step = ParallelProfileRiskAndIdeation(ai_client_factory=mock_factory)
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        step.execute()

        # get_client called 11 times: 1 profile + 2 risk + 8 ideation
        assert mock_factory.get_client.call_count == 11

    def test_correct_system_prompts_used(self):
        mock_factory = self._make_mock_factory()
        accessor = self._make_accessor()

        step = ParallelProfileRiskAndIdeation(ai_client_factory=mock_factory)
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        step.execute()

        # Check system prompts used
        calls = mock_factory.get_client.call_args_list
        instructions = [c.kwargs["instructions"] for c in calls]

        assert instructions.count(PROFILE_SYSTEM_PROMPT) == 1
        assert instructions.count(RISK_SYSTEM_PROMPT) == 2
        assert instructions.count(IDEATION_SYSTEM_PROMPT) == 8

    def test_includes_document_text_in_prompts(self):
        mock_factory = self._make_mock_factory()
        accessor = self._make_accessor(document_text="Investment memo: Revenue is $50M annually.")

        step = ParallelProfileRiskAndIdeation(ai_client_factory=mock_factory)
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        step.execute()

        # Check profile AI call received prompt with document text
        profile_client = mock_factory.get_client(instructions=PROFILE_SYSTEM_PROMPT)
        profile_prompt = profile_client.query_structured.call_args[1]["input_text"]
        assert "SUPPLEMENTARY DOCUMENTS" in profile_prompt
        assert "Investment memo" in profile_prompt

    def test_incomplete_profile_raises(self):
        mock_factory = self._make_mock_factory(
            profile_data={
                "company_name": "",
                "industry": "",
            }
        )
        accessor = self._make_accessor()

        step = ParallelProfileRiskAndIdeation(ai_client_factory=mock_factory)
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        with pytest.raises(ValueError, match="incomplete data"):
            step.execute()

    def test_empty_risk_scores_raises(self):
        mock_factory = self._make_mock_factory(
            risk_batch_a_data={"risk_scores": []},
            risk_batch_b_data={"risk_scores": []},
        )
        accessor = self._make_accessor()

        step = ParallelProfileRiskAndIdeation(ai_client_factory=mock_factory)
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        with pytest.raises(ValueError, match="no risk scores"):
            step.execute()

    def test_no_ai_factory_raises(self):
        accessor = self._make_accessor()

        step = ParallelProfileRiskAndIdeation(ai_client_factory=None)
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        with pytest.raises(RuntimeError, match="AI client factory not configured"):
            step.execute()

    def test_ai_call_failure_propagates(self):
        from signalfield_core.utilities.future_manager import FutureManagerError

        mock_factory = MagicMock()
        mock_client = MagicMock()
        mock_factory.get_client.return_value = mock_client
        mock_client.query_structured.side_effect = RuntimeError("API down")

        accessor = self._make_accessor()

        step = ParallelProfileRiskAndIdeation(ai_client_factory=mock_factory)
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        with pytest.raises(FutureManagerError):
            step.execute()

    def test_uses_actual_url_when_available(self):
        mock_factory = self._make_mock_factory()
        company = Company(url="https://original.com")
        company.scraped_text = "Some content"
        company.actual_url = "https://resolved.com"
        accessor = CompanyAccessor(company)

        step = ParallelProfileRiskAndIdeation(ai_client_factory=mock_factory)
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        step.execute()

        # The profile prompt should contain the resolved URL
        profile_client = mock_factory.get_client(instructions=PROFILE_SYSTEM_PROMPT)
        profile_prompt = profile_client.query_structured.call_args[1]["input_text"]
        assert "https://resolved.com" in profile_prompt

    def test_risk_batch_prompts_contain_correct_categories(self):
        mock_factory = MagicMock()

        risk_prompts: list[str] = []

        profile_client = MagicMock()
        profile_response = MagicMock()
        profile_response.content = _PROFILE_RESPONSE
        profile_response.metadata = {"tokens": 100}
        profile_client.query_structured.return_value = profile_response

        def capture_risk_query(**kwargs):
            risk_prompts.append(kwargs.get("input_text", ""))
            response = MagicMock()
            response.content = {"risk_scores": [
                {"category": f"cat_{len(risk_prompts)}_a", "score": 5, "rationale": "r"},
                {"category": f"cat_{len(risk_prompts)}_b", "score": 4, "rationale": "r"},
            ]}
            response.metadata = {"tokens": 80}
            return response

        risk_client = MagicMock()
        risk_client.query_structured.side_effect = capture_risk_query

        ideation_client = MagicMock()
        ideation_response = MagicMock()
        ideation_response.content = _make_ideation_response("test")
        ideation_response.metadata = {"tokens": 50}
        ideation_client.query_structured.return_value = ideation_response

        def get_client_side_effect(**kwargs):
            instructions = kwargs.get("instructions", "")
            if instructions == PROFILE_SYSTEM_PROMPT:
                return profile_client
            if instructions == RISK_SYSTEM_PROMPT:
                return risk_client
            return ideation_client

        mock_factory.get_client.side_effect = get_client_side_effect
        accessor = self._make_accessor()

        step = ParallelProfileRiskAndIdeation(ai_client_factory=mock_factory)
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        step.execute()

        assert len(risk_prompts) == 2
        all_prompts = " ".join(risk_prompts)
        for category in RISK_BATCH_A_CATEGORIES:
            assert category in all_prompts
        for category in RISK_BATCH_B_CATEGORIES:
            assert category in all_prompts

    def test_timings_include_all_calls(self):
        mock_factory = self._make_mock_factory()
        accessor = self._make_accessor()

        step = ParallelProfileRiskAndIdeation(ai_client_factory=mock_factory)
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        step.execute()

        details = step._request_executor.add_details.call_args[0][0]
        timings = details["ParallelProfileRiskAndIdeation.timings"]
        assert "ai_call_extract_profile" in timings
        assert "ai_call_assess_risk_batch_a" in timings
        assert "ai_call_assess_risk_batch_b" in timings
        # At least some ideation timings
        assert "ai_call_ideation_competitive_displacement" in timings

    def test_ideation_deduplication_works(self):
        """When ideations have overlapping titles, duplicates are removed."""
        mock_factory = MagicMock()

        profile_client = MagicMock()
        profile_response = MagicMock()
        profile_response.content = _PROFILE_RESPONSE
        profile_response.metadata = {"tokens": 100}
        profile_client.query_structured.return_value = profile_response

        risk_call_count = {"count": 0}
        risk_client_a = MagicMock()
        risk_response_a = MagicMock()
        risk_response_a.content = _RISK_BATCH_A_RESPONSE
        risk_response_a.metadata = {"tokens": 80}
        risk_client_a.query_structured.return_value = risk_response_a

        risk_client_b = MagicMock()
        risk_response_b = MagicMock()
        risk_response_b.content = _RISK_BATCH_B_RESPONSE
        risk_response_b.metadata = {"tokens": 80}
        risk_client_b.query_structured.return_value = risk_response_b

        # All ideations return the same title — should dedup to 1
        ideation_client = MagicMock()
        ideation_response = MagicMock()
        ideation_response.content = {
            "title": "Deploy AI chatbot for customer support",
            "description": "Build a customer-facing chatbot",
            "value_lever": "Revenue Side",
            "strategic_category": "Competitive Moat",
            "impact_rating": "High",
        }
        ideation_response.metadata = {"tokens": 50}
        ideation_client.query_structured.return_value = ideation_response

        def get_client_side_effect(**kwargs):
            instructions = kwargs.get("instructions", "")
            if instructions == PROFILE_SYSTEM_PROMPT:
                return profile_client
            if instructions == RISK_SYSTEM_PROMPT:
                risk_call_count["count"] += 1
                if risk_call_count["count"] == 1:
                    return risk_client_a
                return risk_client_b
            return ideation_client

        mock_factory.get_client.side_effect = get_client_side_effect
        accessor = self._make_accessor()

        step = ParallelProfileRiskAndIdeation(ai_client_factory=mock_factory)
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        step.execute()

        ranked = accessor.get_ranked_ideations()
        # All 8 had same title → dedup to 1
        assert len(ranked) == 1

    def test_top_three_actions_derived(self):
        mock_factory = self._make_mock_factory()
        accessor = self._make_accessor()

        step = ParallelProfileRiskAndIdeation(ai_client_factory=mock_factory)
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        step.execute()

        ranked = accessor.get_ranked_ideations()
        assert len(ranked) > 0
        # Each ranked ideation carries top_three_immediate_actions
        actions = ranked[0]["top_three_immediate_actions"]
        assert isinstance(actions, list)
        assert len(actions) <= 3


class TestComputeRiskAggregates:
    def test_computes_overall_score_as_mean(self):
        scores = [
            RiskScore(category="a", score=8, rationale="high"),
            RiskScore(category="b", score=4, rationale="low"),
            RiskScore(category="c", score=6, rationale="mid"),
        ]
        result = compute_risk_aggregates(scores, "TestCo")
        assert result.overall_score == 6.0

    def test_tier_critical(self):
        scores = [RiskScore(category=f"cat_{i}", score=9, rationale="r") for i in range(4)]
        result = compute_risk_aggregates(scores, "TestCo")
        assert result.tier == "critical"

    def test_tier_high(self):
        scores = [RiskScore(category=f"cat_{i}", score=7, rationale="r") for i in range(4)]
        result = compute_risk_aggregates(scores, "TestCo")
        assert result.tier == "high"

    def test_tier_moderate(self):
        scores = [RiskScore(category=f"cat_{i}", score=5, rationale="r") for i in range(4)]
        result = compute_risk_aggregates(scores, "TestCo")
        assert result.tier == "moderate"

    def test_tier_low(self):
        scores = [RiskScore(category=f"cat_{i}", score=2, rationale="r") for i in range(4)]
        result = compute_risk_aggregates(scores, "TestCo")
        assert result.tier == "low"

    def test_top_risks_sorted_by_score_descending(self):
        scores = [
            RiskScore(category="low", score=2, rationale="r"),
            RiskScore(category="high", score=9, rationale="r"),
            RiskScore(category="mid", score=5, rationale="r"),
            RiskScore(category="very_high", score=10, rationale="r"),
        ]
        result = compute_risk_aggregates(scores, "TestCo")
        assert result.top_risks == ["very_high", "high", "mid"]

    def test_analysis_summary_contains_company_name_and_tier(self):
        scores = [
            RiskScore(category="competitive_displacement", score=9, rationale="r"),
            RiskScore(category="technology_obsolescence", score=8, rationale="r"),
            RiskScore(category="talent_workforce", score=7, rationale="r"),
            RiskScore(category="margin_compression", score=6, rationale="r"),
        ]
        result = compute_risk_aggregates(scores, "Acme Corp")
        assert "Acme Corp" in result.analysis_summary
        assert "high" in result.analysis_summary
        assert "competitive_displacement" in result.analysis_summary

    def test_empty_scores_raises(self):
        with pytest.raises(ValueError, match="empty risk_scores"):
            compute_risk_aggregates([], "TestCo")

    def test_all_8_scores_merged(self):
        scores = [
            RiskScore(category=cat, score=5, rationale="r")
            for cat in RISK_BATCH_A_CATEGORIES + RISK_BATCH_B_CATEGORIES
        ]
        result = compute_risk_aggregates(scores, "TestCo")
        assert len(result.risk_scores) == 8
        assert result.overall_score == 5.0

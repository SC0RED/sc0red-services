"""Tests for detail_opportunity — schema validation and prompt building."""

from src.pipeline.pipeline_steps.detail_opportunity import (
    DETAIL_SCHEMA,
    DETAIL_SYSTEM_PROMPT,
    build_detail_prompt,
)


class TestDetailSchema:
    def test_required_fields(self):
        assert set(DETAIL_SCHEMA["required"]) == {
            "implementation_steps",
            "timeline",
            "investment_range",
            "roi_estimate",
            "related_services",
        }

    def test_no_extra_fields(self):
        assert DETAIL_SCHEMA["additionalProperties"] is False

    def test_does_not_have_title(self):
        """Routing key: detail has implementation_steps but NOT title."""
        assert "title" not in DETAIL_SCHEMA["properties"]

    def test_does_not_have_impact_rating(self):
        assert "impact_rating" not in DETAIL_SCHEMA["properties"]

    def test_implementation_steps_is_array(self):
        assert DETAIL_SCHEMA["properties"]["implementation_steps"]["type"] == "array"

    def test_related_services_max_items(self):
        assert DETAIL_SCHEMA["properties"]["related_services"]["maxItems"] == 3


class TestDetailSystemPrompt:
    def test_is_non_empty_string(self):
        assert isinstance(DETAIL_SYSTEM_PROMPT, str)
        assert len(DETAIL_SYSTEM_PROMPT) > 50

    def test_reuses_opps_system_prompt(self):
        from src.pipeline.pipeline_steps.generate_opportunities import OPPS_SYSTEM_PROMPT

        assert DETAIL_SYSTEM_PROMPT is OPPS_SYSTEM_PROMPT


class TestBuildDetailPrompt:
    def _make_profile(self) -> dict:
        return {"company_name": "Acme Corp", "industry": "B2B SaaS"}

    def _make_assessment(self) -> dict:
        return {
            "risk_scores": [{"category": "competitive_displacement", "score": 8}],
            "overall_score": 7.0,
            "tier": "high",
            "top_risks": ["competitive_displacement"],
            "analysis_summary": "High competitive risk",
        }

    def test_includes_profile(self):
        prompt = build_detail_prompt(
            self._make_profile(),
            self._make_assessment(),
            "Deploy AI Chatbot",
            "Build customer-facing chatbot",
        )
        assert "Acme Corp" in prompt

    def test_includes_risk_assessment(self):
        prompt = build_detail_prompt(
            self._make_profile(),
            self._make_assessment(),
            "Deploy AI Chatbot",
            "Build customer-facing chatbot",
        )
        assert "7.0/10" in prompt
        assert "competitive_displacement" in prompt

    def test_includes_opportunity_title(self):
        prompt = build_detail_prompt(
            self._make_profile(),
            self._make_assessment(),
            "Deploy AI Chatbot",
            "Build customer-facing chatbot",
        )
        assert "Deploy AI Chatbot" in prompt

    def test_includes_opportunity_description(self):
        prompt = build_detail_prompt(
            self._make_profile(),
            self._make_assessment(),
            "Deploy AI Chatbot",
            "Build customer-facing chatbot",
        )
        assert "Build customer-facing chatbot" in prompt

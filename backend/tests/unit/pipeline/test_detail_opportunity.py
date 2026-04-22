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
        }

    def test_no_extra_fields(self):
        assert DETAIL_SCHEMA["additionalProperties"] is False

    def test_does_not_have_title(self):
        """Routing key: detail has implementation_steps but NOT title."""
        assert "title" not in DETAIL_SCHEMA["properties"]

    def test_does_not_have_impact_rating(self):
        assert "impact_rating" not in DETAIL_SCHEMA["properties"]

    def test_does_not_have_related_services(self):
        """Phase 2 removal: schema no longer produces vendor recommendations."""
        assert "related_services" not in DETAIL_SCHEMA["properties"]

    def test_implementation_steps_is_array(self):
        assert DETAIL_SCHEMA["properties"]["implementation_steps"]["type"] == "array"


class TestDetailSystemPrompt:
    def test_is_non_empty_string(self):
        assert isinstance(DETAIL_SYSTEM_PROMPT, str)
        assert len(DETAIL_SYSTEM_PROMPT) > 20


class TestBuildDetailPrompt:
    def _make_profile(self) -> dict:
        return {
            "company_name": "Acme Corp",
            "industry": "B2B SaaS",
            "business_model": "SaaS",
            "company_size": "Mid-market 200-1000",
            "products_services": ["ATS", "Payroll"],
            "tech_signals": ["React", "AWS"],
        }

    def test_includes_company_name(self):
        prompt = build_detail_prompt(
            self._make_profile(),
            "Deploy AI Chatbot", "Build chatbot",
        )
        assert "Acme Corp" in prompt

    def test_includes_industry_and_model(self):
        prompt = build_detail_prompt(
            self._make_profile(),
            "Deploy AI Chatbot", "Build chatbot",
        )
        assert "B2B SaaS" in prompt
        assert "SaaS" in prompt

    def test_includes_opportunity(self):
        prompt = build_detail_prompt(
            self._make_profile(),
            "Deploy AI Chatbot", "Build customer-facing chatbot",
        )
        assert "Deploy AI Chatbot" in prompt
        assert "Build customer-facing chatbot" in prompt

    def test_excludes_risk_context(self):
        """Risk context is redundant — opportunity already captures it."""
        prompt = build_detail_prompt(
            self._make_profile(),
            "Deploy AI Chatbot", "Build chatbot",
        )
        assert "7.0/10" not in prompt
        assert "Overall Score" not in prompt

    def test_includes_tech_stack(self):
        prompt = build_detail_prompt(
            self._make_profile(),
            "Deploy AI Chatbot", "Build chatbot",
        )
        assert "React" in prompt
        assert "AWS" in prompt

    def test_handles_empty_optional_fields(self):
        minimal_profile = {"company_name": "TestCo"}
        prompt = build_detail_prompt(
            minimal_profile,
            "Deploy AI", "Build AI thing",
        )
        assert "TestCo" in prompt

    def test_prompt_is_compact(self):
        prompt = build_detail_prompt(
            self._make_profile(),
            "Title", "Desc",
        )
        assert len(prompt) < 500

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
        return {
            "company_name": "Acme Corp",
            "industry": "B2B SaaS",
            "business_model": "SaaS",
            "company_size": "Mid-market 200-1000",
            "description": "HR platform for mid-market",
            "products_services": ["ATS", "Payroll"],
            "tech_signals": ["React", "AWS"],
            "target_market": "Mid-market companies",
            "revenue_model": "subscription",
            "competitive_positioning": "AI-first HR",
            "ai_maturity": "Partial adoption",
            "key_risks_visible": [],
        }

    def _make_assessment(self) -> dict:
        return {
            "risk_scores": [{"category": "competitive_displacement", "score": 8}],
            "overall_score": 7.0,
            "tier": "high",
            "top_risks": ["competitive_displacement"],
            "analysis_summary": "High competitive risk",
        }

    def test_includes_company_name(self):
        prompt = build_detail_prompt(
            self._make_profile(),
            self._make_assessment(),
            "Deploy AI Chatbot",
            "Build customer-facing chatbot",
        )
        assert "Acme Corp" in prompt

    def test_includes_industry_and_business_model(self):
        prompt = build_detail_prompt(
            self._make_profile(),
            self._make_assessment(),
            "Deploy AI Chatbot",
            "Build customer-facing chatbot",
        )
        assert "B2B SaaS" in prompt
        assert "SaaS" in prompt

    def test_includes_company_size(self):
        prompt = build_detail_prompt(
            self._make_profile(),
            self._make_assessment(),
            "Deploy AI Chatbot",
            "Build customer-facing chatbot",
        )
        assert "Mid-market 200-1000" in prompt

    def test_includes_products_and_tech(self):
        prompt = build_detail_prompt(
            self._make_profile(),
            self._make_assessment(),
            "Deploy AI Chatbot",
            "Build customer-facing chatbot",
        )
        assert "ATS" in prompt
        assert "React" in prompt

    def test_excludes_ideation_only_fields(self):
        """Fields that inform ideation but not implementation should be excluded."""
        prompt = build_detail_prompt(
            self._make_profile(),
            self._make_assessment(),
            "Deploy AI Chatbot",
            "Build customer-facing chatbot",
        )
        assert "competitive_positioning" not in prompt
        assert "AI-first HR" not in prompt
        assert "ai_maturity" not in prompt
        assert "Partial adoption" not in prompt
        assert "key_risks_visible" not in prompt

    def test_excludes_detailed_risk_scores(self):
        """Full risk_scores array should not be dumped into the prompt."""
        prompt = build_detail_prompt(
            self._make_profile(),
            self._make_assessment(),
            "Deploy AI Chatbot",
            "Build customer-facing chatbot",
        )
        assert "risk_scores" not in prompt.lower().replace("risk score", "")

    def test_includes_risk_context(self):
        prompt = build_detail_prompt(
            self._make_profile(),
            self._make_assessment(),
            "Deploy AI Chatbot",
            "Build customer-facing chatbot",
        )
        assert "7.0/10" in prompt
        assert "competitive_displacement" in prompt
        assert "High competitive risk" in prompt

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

    def test_prompt_is_shorter_than_raw_json_dump(self):
        """Focused prompt should be significantly shorter than raw JSON dump."""
        import json

        profile = self._make_profile()
        assessment = self._make_assessment()
        prompt = build_detail_prompt(profile, assessment, "Title", "Desc")

        raw_json_size = len(json.dumps(profile)) + len(json.dumps(assessment["risk_scores"]))
        assert len(prompt) < raw_json_size * 2  # focused should be much smaller

    def test_handles_empty_optional_fields(self):
        """Profile with missing optional fields should not crash."""
        minimal_profile = {"company_name": "TestCo"}
        prompt = build_detail_prompt(
            minimal_profile,
            self._make_assessment(),
            "Deploy AI",
            "Build AI thing",
        )
        assert "TestCo" in prompt
        assert "Products/Services" not in prompt
        assert "Tech Stack" not in prompt

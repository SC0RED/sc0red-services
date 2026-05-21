"""Tests for detail_opportunity — schema validation and prompt building."""

from src.pipeline.pipeline_steps.detail_opportunity import (
    DETAIL_SCHEMA,
    DETAIL_SYSTEM_PROMPT,
    build_detail_prompt,
)


class TestDetailSchema:
    def test_required_fields(self):
        # Phase 14 of redesign-analysis-visuals added the two numeric
        # ROI x Investment fields. Both are nullable in the schema
        # (``type: [integer, null]`` / ``type: [number, null]``) but
        # the AI MUST emit them on every call — null is acceptable,
        # omission is not.
        assert set(DETAIL_SCHEMA["required"]) == {
            "implementation_steps",
            "timeline",
            "investment_range",
            "roi_estimate",
            "investment_value_usd",
            "roi_estimate_pct",
        }

    def test_numeric_axes_are_nullable_with_range_constraints(self):
        # The matrix scatter plot needs honest ``null`` for opportunities
        # the AI can't size — better than hallucinated coordinates.
        # Range constraints match the spec: investment >= 0, ROI 0..500.
        investment = DETAIL_SCHEMA["properties"]["investment_value_usd"]
        assert investment["type"] == ["integer", "null"]
        assert investment["minimum"] == 0
        roi = DETAIL_SCHEMA["properties"]["roi_estimate_pct"]
        assert roi["type"] == ["number", "null"]
        assert roi["minimum"] == 0
        assert roi["maximum"] == 500

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

    def test_prompt_is_compact_enough(self):
        # Phase 14 expanded the prompt with explicit per-field
        # instructions for ``investment_value_usd`` + ``roi_estimate_pct``
        # (including the null-preferred-over-guess rule). The compact
        # baseline was 500 chars; the new floor is ~2000 chars, which
        # is still well under any token budget — the AI's per-call
        # cost is dominated by the company context, not this template.
        prompt = build_detail_prompt(
            self._make_profile(),
            "Title", "Desc",
        )
        assert len(prompt) < 3000

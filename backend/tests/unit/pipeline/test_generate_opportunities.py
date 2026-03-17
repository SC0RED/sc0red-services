"""Tests for opportunity generation constants, schemas, and prompt builders."""

from src.pipeline.pipeline_steps.generate_opportunities import (
    OPPS_SYSTEM_PROMPT,
    build_context_block,
    build_high_priority_prompt,
    build_opportunity,
    build_strategic_prompt,
)


class TestBuildOpportunity:
    def test_builds_opportunity_from_dict(self):
        data = {
            "title": "Deploy AI Chatbot",
            "impact_rating": "High",
            "strategic_category": "Competitive Moat",
            "description": "Build a customer-facing AI chatbot",
            "implementation_steps": ["Step 1", "Step 2", "Step 3"],
            "timeline": "Medium-term (3-9 months)",
            "investment_range": "$100K-$500K",
            "roi_estimate": "30% improvement in support efficiency",
            "related_services": ["Accenture - AI strategy"],
            "value_lever": "Both",
        }
        opp = build_opportunity(data)
        assert opp.title == "Deploy AI Chatbot"
        assert opp.impact_rating == "High"
        assert opp.value_lever == "Both"
        assert len(opp.implementation_steps) == 3

    def test_builds_opportunity_with_minimal_fields(self):
        data = {"title": "Quick Win", "value_lever": "Cost Side"}
        opp = build_opportunity(data)
        assert opp.title == "Quick Win"
        assert opp.value_lever == "Cost Side"


class TestPromptBuilders:
    def test_context_block_includes_profile_and_scores(self):
        profile = {"company_name": "Acme", "industry": "Tech"}
        assessment = {
            "risk_scores": [{"category": "data_ip", "score": 5}],
            "overall_score": 5.0,
            "tier": "moderate",
            "top_risks": ["data_ip"],
            "analysis_summary": "Moderate risk",
        }
        context = build_context_block(profile, assessment)
        assert "Acme" in context
        assert "data_ip" in context
        assert "5.0/10" in context

    def test_high_priority_prompt_includes_actions_instruction(self):
        assessment = {
            "risk_scores": [],
            "overall_score": 5.0,
            "tier": "moderate",
            "top_risks": ["data_ip"],
            "analysis_summary": "Test summary",
        }
        prompt = build_high_priority_prompt({}, assessment, ["data_ip"])
        assert "top_three_immediate_actions" in prompt
        assert "2-3 high-priority" in prompt

    def test_strategic_prompt_excludes_actions_instruction(self):
        assessment = {
            "risk_scores": [],
            "overall_score": 5.0,
            "tier": "moderate",
            "top_risks": ["data_ip"],
            "analysis_summary": "Test summary",
        }
        prompt = build_strategic_prompt({}, assessment, ["data_ip"])
        assert "Do NOT include top_three_immediate_actions" in prompt
        assert "1-2 strategic" in prompt

    def test_high_priority_prompt_includes_focus_categories(self):
        assessment = {
            "risk_scores": [],
            "overall_score": 7.0,
            "tier": "high",
            "top_risks": ["competitive_displacement", "technology_obsolescence"],
            "analysis_summary": "High risk",
        }
        prompt = build_high_priority_prompt(
            {"company_name": "Test"},
            assessment,
            ["competitive_displacement", "technology_obsolescence"],
        )
        assert "competitive_displacement" in prompt
        assert "technology_obsolescence" in prompt
        assert "highest-priority" in prompt.lower()

    def test_strategic_prompt_includes_focus_categories(self):
        assessment = {
            "risk_scores": [],
            "overall_score": 5.0,
            "tier": "moderate",
            "top_risks": ["data_ip"],
            "analysis_summary": "Test",
        }
        prompt = build_strategic_prompt(
            {"company_name": "Test"},
            assessment,
            ["margin_compression", "customer_behavior"],
        )
        assert "margin_compression" in prompt
        assert "customer_behavior" in prompt
        assert "strategic" in prompt.lower()


class TestSchemas:
    def test_system_prompt_is_non_empty_string(self):
        assert isinstance(OPPS_SYSTEM_PROMPT, str)
        assert len(OPPS_SYSTEM_PROMPT) > 50

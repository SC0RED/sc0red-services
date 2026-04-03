"""Tests for opportunity generation shared constants and helpers."""

from src.pipeline.pipeline_steps.generate_opportunities import (
    STRATEGIC_CATEGORIES_INSTRUCTIONS,
    build_opportunity,
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


class TestSharedConstants:
    def test_strategic_categories_lists_five(self):
        assert "Competitive Moat" in STRATEGIC_CATEGORIES_INSTRUCTIONS
        assert "Revenue Capture" in STRATEGIC_CATEGORIES_INSTRUCTIONS
        assert "Market Expansion" in STRATEGIC_CATEGORIES_INSTRUCTIONS
        assert "Operational Efficiency" in STRATEGIC_CATEGORIES_INSTRUCTIONS
        assert "Talent Strategy" in STRATEGIC_CATEGORIES_INSTRUCTIONS

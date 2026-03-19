"""Tests for risk scoring calibration guide content."""

from src.pipeline.ai_guides.risk_scoring_guide import RISK_SCORING_GUIDE

_ALL_RISK_CATEGORIES = [
    "competitive_displacement",
    "technology_obsolescence",
    "customer_behavior",
    "margin_compression",
    "talent_workforce",
    "regulatory_compliance",
    "supply_chain",
    "data_ip",
]


class TestRiskScoringGuide:
    def test_guide_is_substantial(self):
        assert isinstance(RISK_SCORING_GUIDE, str)
        assert len(RISK_SCORING_GUIDE) > 200

    def test_contains_score_range_anchors(self):
        assert "9-10" in RISK_SCORING_GUIDE
        assert "7-8" in RISK_SCORING_GUIDE
        assert "5-6" in RISK_SCORING_GUIDE
        assert "3-4" in RISK_SCORING_GUIDE
        assert "1-2" in RISK_SCORING_GUIDE

    def test_contains_all_eight_risk_categories(self):
        for category in _ALL_RISK_CATEGORIES:
            assert category in RISK_SCORING_GUIDE, f"Missing category: {category}"

    def test_contains_anti_pattern_section(self):
        assert "Anti-Pattern" in RISK_SCORING_GUIDE
        assert "Middle-clustering" in RISK_SCORING_GUIDE or "middle" in RISK_SCORING_GUIDE.lower()

    def test_contains_observable_proxy_patterns(self):
        assert "Observable" in RISK_SCORING_GUIDE
        assert "Job posting" in RISK_SCORING_GUIDE or "job posting" in RISK_SCORING_GUIDE.lower()

"""Tests for ideation quality guide content."""

from src.pipeline.ai_guides.ideation_guide import IDEATION_GUIDE

_STRATEGIC_CATEGORIES = [
    "Competitive Moat",
    "Revenue Capture",
    "Market Expansion",
    "Operational Efficiency",
    "Talent Strategy",
]


class TestIdeationGuide:
    def test_guide_is_substantial(self):
        assert isinstance(IDEATION_GUIDE, str)
        assert len(IDEATION_GUIDE) > 200

    def test_contains_specificity_standards(self):
        assert "Specificity" in IDEATION_GUIDE or "specificity" in IDEATION_GUIDE.lower()
        assert "Weak" in IDEATION_GUIDE
        assert "Strong" in IDEATION_GUIDE

    def test_contains_observable_signal_guidance(self):
        assert "observable" in IDEATION_GUIDE.lower()
        assert "Job posting" in IDEATION_GUIDE or "job posting" in IDEATION_GUIDE.lower()

    def test_contains_anti_patterns(self):
        assert "Anti-Pattern" in IDEATION_GUIDE
        assert "Leverage AI" in IDEATION_GUIDE or "buzzword" in IDEATION_GUIDE.lower()

    def test_contains_all_five_strategic_categories(self):
        for category in _STRATEGIC_CATEGORIES:
            assert category in IDEATION_GUIDE, f"Missing strategic category: {category}"

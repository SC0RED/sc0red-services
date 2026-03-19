"""Tests for EBITDA estimation guide content."""

from src.pipeline.ai_guides.ebitda_estimation_guide import EBITDA_ESTIMATION_GUIDE

_BUSINESS_MODELS = [
    "SaaS",
    "Professional Services",
    "E-commerce",
    "Manufacturing",
    "Financial Services",
]


class TestEbitdaEstimationGuide:
    def test_guide_is_substantial(self):
        assert isinstance(EBITDA_ESTIMATION_GUIDE, str)
        assert len(EBITDA_ESTIMATION_GUIDE) > 200

    def test_contains_industry_benchmarks(self):
        assert "Gross Margin" in EBITDA_ESTIMATION_GUIDE
        assert "EBITDA Margin" in EBITDA_ESTIMATION_GUIDE
        assert "Revenue per Employee" in EBITDA_ESTIMATION_GUIDE or "Revenue/Employee" in EBITDA_ESTIMATION_GUIDE

    def test_contains_observable_proxies(self):
        assert "Observable" in EBITDA_ESTIMATION_GUIDE
        assert "Employee count" in EBITDA_ESTIMATION_GUIDE or "employee count" in EBITDA_ESTIMATION_GUIDE.lower()

    def test_contains_business_model_types(self):
        for model in _BUSINESS_MODELS:
            assert model in EBITDA_ESTIMATION_GUIDE, f"Missing business model: {model}"

    def test_contains_anti_patterns(self):
        assert "Anti-Pattern" in EBITDA_ESTIMATION_GUIDE
        assert "range" in EBITDA_ESTIMATION_GUIDE.lower()

    def test_contains_tree_structure_templates(self):
        assert "Subscriptions" in EBITDA_ESTIMATION_GUIDE or "subscription" in EBITDA_ESTIMATION_GUIDE.lower()
        assert "R&D" in EBITDA_ESTIMATION_GUIDE or "Research" in EBITDA_ESTIMATION_GUIDE

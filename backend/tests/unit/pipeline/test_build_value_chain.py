"""Tests for the programmatic value chain builder."""

from src.models.model_company import CompanyProfile, Opportunity, ValueChainResult
from src.pipeline.pipeline_steps.build_value_chain import build_programmatic_value_chain


def _make_profile(business_model: str = "SaaS") -> CompanyProfile:
    return CompanyProfile(
        company_name="Test Corp",
        industry="Technology",
        business_model=business_model,
    )


def _make_opportunities() -> list[Opportunity]:
    return [
        Opportunity(
            title="AI Chatbot",
            strategic_category="Competitive Moat",
            value_lever="Revenue Side",
        ),
        Opportunity(
            title="Automate Support",
            strategic_category="Operational Efficiency",
            value_lever="Cost Side",
        ),
    ]


class TestBuildProgrammaticValueChain:
    def test_returns_value_chain_result(self):
        result = build_programmatic_value_chain(_make_profile())
        assert isinstance(result, ValueChainResult)

    def test_saas_has_primary_and_support_steps(self):
        result = build_programmatic_value_chain(_make_profile("SaaS"))
        primary = [s for s in result.steps if s.category == "primary"]
        support = [s for s in result.steps if s.category == "support"]
        assert len(primary) == 6
        assert len(support) == 2

    def test_services_template(self):
        result = build_programmatic_value_chain(_make_profile("Professional Services"))
        labels = [s.label for s in result.steps]
        assert "Project Delivery" in labels
        assert "Knowledge Management" in labels

    def test_ecommerce_template(self):
        result = build_programmatic_value_chain(_make_profile("E-commerce"))
        labels = [s.label for s in result.steps]
        assert "Order Fulfillment" in labels

    def test_manufacturing_template(self):
        result = build_programmatic_value_chain(_make_profile("Manufacturing"))
        labels = [s.label for s in result.steps]
        assert "Production / Assembly" in labels
        assert "Raw Material Procurement" in labels

    def test_financial_services_template(self):
        result = build_programmatic_value_chain(_make_profile("Fintech"))
        labels = [s.label for s in result.steps]
        assert "Onboarding & KYC" in labels

    def test_unknown_defaults_to_saas(self):
        result = build_programmatic_value_chain(_make_profile("Unknown Model"))
        labels = [s.label for s in result.steps]
        assert "Renewal & Expansion" in labels

    def test_steps_have_risk_categories(self):
        result = build_programmatic_value_chain(_make_profile())
        for step in result.steps:
            assert len(step.risk_categories) > 0

    def test_opportunities_linked_to_steps(self):
        opportunities = _make_opportunities()
        result = build_programmatic_value_chain(
            _make_profile(), opportunities=opportunities
        )
        # At least one step should have linked opportunities
        all_indices = []
        for step in result.steps:
            all_indices.extend(step.opportunity_indices)
        assert len(all_indices) > 0

    def test_summary_contains_company_name(self):
        result = build_programmatic_value_chain(_make_profile())
        assert "Test Corp" in result.summary

    def test_summary_contains_template_name(self):
        result = build_programmatic_value_chain(_make_profile())
        assert "saas" in result.summary

    def test_no_opportunities_produces_empty_indices(self):
        result = build_programmatic_value_chain(_make_profile())
        for step in result.steps:
            assert step.opportunity_indices == []

    def test_all_templates_produce_valid_chains(self):
        for model in ["SaaS", "Consulting", "E-commerce", "Manufacturing", "Fintech"]:
            result = build_programmatic_value_chain(_make_profile(model))
            assert len(result.steps) >= 5
            assert result.summary

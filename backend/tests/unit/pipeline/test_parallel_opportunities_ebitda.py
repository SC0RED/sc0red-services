"""Tests for ParallelOpportunityDetailsAndEbitda composite pipeline step."""

from unittest.mock import MagicMock

import pytest

from src.facades.company_accessor import CompanyAccessor
from src.models.model_company import (
    Company,
    CompanyProfile,
    EbitdaTreeResult,
    RiskAssessment,
    RiskScore,
)
from src.pipeline.pipeline_steps.parallel_opportunities_ebitda import (
    ParallelOpportunityDetailsAndEbitda,
    link_opportunities_to_ebitda_nodes,
)


def _make_ranked_ideation(
    title: str = "Deploy AI Chatbot",
    value_lever: str = "Both",
    risk_category: str = "competitive_displacement",
    impact_rating: str = "High",
    top_actions: list[str] | None = None,
) -> dict:
    return {
        "title": title,
        "description": "Build a customer-facing AI chatbot",
        "value_lever": value_lever,
        "strategic_category": "Competitive Moat",
        "impact_rating": impact_rating,
        "risk_category": risk_category,
        "top_three_immediate_actions": top_actions or ["Action 1", "Action 2", "Action 3"],
    }


def _make_detail_response() -> dict:
    return {
        "implementation_steps": ["Step 1", "Step 2", "Step 3"],
        "timeline": "Medium-term (3-9 months)",
        "investment_range": "$100K-$500K",
        "roi_estimate": "30% improvement in support efficiency",
        "related_services": ["Accenture - AI strategy"],
    }


def _make_company_with_profile_risk_and_ideations(
    ideation_count: int = 3,
) -> Company:
    company = Company(url="https://example.com")
    company.profile = CompanyProfile(
        company_name="Test Corp",
        industry="SaaS",
        industry_sector="Technology",
        business_model="SaaS",
        company_size="Mid-market 200-1000",
    )
    company.risk_assessment = RiskAssessment(
        risk_scores=[
            RiskScore(category="competitive_displacement", score=8),
            RiskScore(category="technology_obsolescence", score=7),
            RiskScore(category="talent_workforce", score=6),
        ],
        overall_score=7.0,
        tier="high",
        top_risks=[
            "competitive_displacement",
            "technology_obsolescence",
            "talent_workforce",
        ],
        analysis_summary="High competitive risk",
    )
    # Simulate ranked ideations from Level 1
    categories = [
        "competitive_displacement",
        "technology_obsolescence",
        "talent_workforce",
        "margin_compression",
        "customer_behavior",
    ]
    company.ranked_ideations = [
        _make_ranked_ideation(
            title=f"AI Opportunity {i + 1}",
            value_lever=["Revenue Side", "Cost Side", "Both"][i % 3],
            risk_category=categories[i],
        )
        for i in range(ideation_count)
    ]
    return company


def _make_mock_factory() -> MagicMock:
    """Create a mock AIClientFactory that returns detail responses."""
    mock_factory = MagicMock()
    mock_client = MagicMock()
    mock_factory.get_client.return_value = mock_client

    detail_response = MagicMock()
    detail_response.content = _make_detail_response()
    detail_response.metadata = {"tokens": 80}
    mock_client.query_structured.return_value = detail_response

    return mock_factory


class TestParallelOpportunityDetailsAndEbitda:
    def test_successful_parallel_execution_with_three_ideations(self):
        mock_factory = _make_mock_factory()
        company = _make_company_with_profile_risk_and_ideations(ideation_count=3)
        accessor = CompanyAccessor(company)

        step = ParallelOpportunityDetailsAndEbitda(ai_client_factory=mock_factory)
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        step.execute()

        # Check opportunities merged from ideation + detail
        result = accessor.company.opportunity_result
        assert result is not None
        assert len(result.opportunities) == 3
        assert result.opportunities[0].title == "AI Opportunity 1"
        assert result.opportunities[1].title == "AI Opportunity 2"
        assert result.opportunities[2].title == "AI Opportunity 3"

        # Detail fields are present
        for opp in result.opportunities:
            assert len(opp.implementation_steps) == 3
            assert opp.timeline == "Medium-term (3-9 months)"
            assert opp.investment_range == "$100K-$500K"
            assert opp.roi_estimate == "30% improvement in support efficiency"

        # Ideation fields preserved
        assert result.opportunities[0].value_lever == "Revenue Side"
        assert result.opportunities[1].value_lever == "Cost Side"
        assert result.opportunities[2].value_lever == "Both"

        # Top actions from ranked ideations
        assert result.top_three_immediate_actions == ["Action 1", "Action 2", "Action 3"]

        # EBITDA tree built programmatically
        ebitda = accessor.company.ebitda_tree
        assert ebitda is not None
        assert isinstance(ebitda, EbitdaTreeResult)
        assert "Test Corp" in ebitda.summary
        assert len(ebitda.nodes) == 5  # revenue, cogs, gross_profit, opex, ebitda

        # Only detail AI calls — no EBITDA AI call
        assert mock_factory.get_client.call_count == 3

        # Both questions marked complete
        calls = step._request_executor.mark_question_complete.call_args_list
        completed = {c[0][0] for c in calls}
        assert "generate_opportunities" in completed
        assert "generate_ebitda_tree" in completed

    def test_ebitda_tree_is_programmatic_not_ai(self):
        """EBITDA tree should be built without any AI call."""
        mock_factory = _make_mock_factory()
        company = _make_company_with_profile_risk_and_ideations(ideation_count=3)
        accessor = CompanyAccessor(company)

        step = ParallelOpportunityDetailsAndEbitda(ai_client_factory=mock_factory)
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        step.execute()

        # Only 3 AI calls (detail only), not 4 (detail + EBITDA)
        assert mock_factory.get_client.call_count == 3

        # EBITDA tree should still be populated
        ebitda = accessor.company.ebitda_tree
        assert ebitda is not None
        assert ebitda.revenue_estimate
        assert ebitda.ebitda_estimate

    def test_successful_with_five_ideations(self):
        mock_factory = _make_mock_factory()
        company = _make_company_with_profile_risk_and_ideations(ideation_count=5)
        accessor = CompanyAccessor(company)

        step = ParallelOpportunityDetailsAndEbitda(ai_client_factory=mock_factory)
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        step.execute()

        result = accessor.company.opportunity_result
        assert result is not None
        assert len(result.opportunities) == 5

        # 5 detail AI calls only
        assert mock_factory.get_client.call_count == 5

    def test_ebitda_nodes_linked_to_opportunities(self):
        mock_factory = _make_mock_factory()
        company = _make_company_with_profile_risk_and_ideations(ideation_count=3)
        accessor = CompanyAccessor(company)

        step = ParallelOpportunityDetailsAndEbitda(ai_client_factory=mock_factory)
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        step.execute()

        ebitda = accessor.company.ebitda_tree
        assert ebitda is not None

        # Opp 0 = Revenue Side, Opp 1 = Cost Side, Opp 2 = Both
        revenue_node = ebitda.nodes[0]  # revenue type
        assert 0 in revenue_node.linked_opportunity_indices  # Revenue Side
        assert 2 in revenue_node.linked_opportunity_indices  # Both

        cogs_node = ebitda.nodes[1]  # cost type
        assert 1 in cogs_node.linked_opportunity_indices  # Cost Side
        assert 2 in cogs_node.linked_opportunity_indices  # Both

    def test_timings_include_ebitda_build(self):
        mock_factory = _make_mock_factory()
        company = _make_company_with_profile_risk_and_ideations(ideation_count=1)
        accessor = CompanyAccessor(company)

        step = ParallelOpportunityDetailsAndEbitda(ai_client_factory=mock_factory)
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        step.execute()

        details = step._request_executor.add_details.call_args[0][0]
        timings = details["ParallelOpportunityDetailsAndEbitda.timings"]
        assert "build_ebitda_tree" in timings
        assert "ai_call_detail_0" in timings

    def test_missing_profile_raises(self):
        company = Company(url="https://example.com")
        company.risk_assessment = RiskAssessment(overall_score=5.0)
        accessor = CompanyAccessor(company)

        step = ParallelOpportunityDetailsAndEbitda(ai_client_factory=MagicMock())
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        with pytest.raises(ValueError, match="profile or risk assessment missing"):
            step.execute()

    def test_missing_risk_assessment_raises(self):
        company = Company(url="https://example.com")
        company.profile = CompanyProfile(company_name="Test", industry="Tech")
        accessor = CompanyAccessor(company)

        step = ParallelOpportunityDetailsAndEbitda(ai_client_factory=MagicMock())
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        with pytest.raises(ValueError, match="profile or risk assessment missing"):
            step.execute()

    def test_missing_factory_raises(self):
        company = _make_company_with_profile_risk_and_ideations()
        accessor = CompanyAccessor(company)

        step = ParallelOpportunityDetailsAndEbitda(ai_client_factory=None)
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        with pytest.raises(RuntimeError, match="AI client factory not configured"):
            step.execute()

    def test_no_ranked_ideations_raises(self):
        company = _make_company_with_profile_risk_and_ideations()
        company.ranked_ideations = []  # Empty ideations
        accessor = CompanyAccessor(company)

        step = ParallelOpportunityDetailsAndEbitda(ai_client_factory=MagicMock())
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        with pytest.raises(ValueError, match="No ranked ideations"):
            step.execute()

    def test_ai_call_failure_propagates(self):
        from signalfield_core.utilities.future_manager import FutureManagerError

        mock_factory = MagicMock()
        mock_client = MagicMock()
        mock_factory.get_client.return_value = mock_client
        mock_client.query_structured.side_effect = RuntimeError("AI service unavailable")

        company = _make_company_with_profile_risk_and_ideations()
        accessor = CompanyAccessor(company)

        step = ParallelOpportunityDetailsAndEbitda(ai_client_factory=mock_factory)
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        with pytest.raises(FutureManagerError):
            step.execute()


class TestLinkOpportunitiesToEbitdaNodes:
    def _make_nodes(self):
        from src.models.model_company import EbitdaNode

        revenue = EbitdaNode(id="rev", label="Revenue", type="revenue", description="Revenue")
        cost = EbitdaNode(id="cost", label="COGS", type="cost", description="Cost")
        subtotal = EbitdaNode(id="ebitda", label="EBITDA", type="subtotal", description="EBITDA")
        return [revenue, cost, subtotal]

    def test_revenue_side_links_to_revenue_nodes(self):
        from src.models.model_company import Opportunity

        opps = [Opportunity(title="Rev Opp", value_lever="Revenue Side")]
        nodes = self._make_nodes()

        link_opportunities_to_ebitda_nodes(opps, nodes)

        assert nodes[0].linked_opportunity_indices == [0]
        assert nodes[1].linked_opportunity_indices == []
        assert nodes[2].linked_opportunity_indices == [0]

    def test_cost_side_links_to_cost_nodes(self):
        from src.models.model_company import Opportunity

        opps = [Opportunity(title="Cost Opp", value_lever="Cost Side")]
        nodes = self._make_nodes()

        link_opportunities_to_ebitda_nodes(opps, nodes)

        assert nodes[0].linked_opportunity_indices == []
        assert nodes[1].linked_opportunity_indices == [0]
        assert nodes[2].linked_opportunity_indices == [0]

    def test_both_links_to_all_nodes(self):
        from src.models.model_company import Opportunity

        opps = [Opportunity(title="Both Opp", value_lever="Both")]
        nodes = self._make_nodes()

        link_opportunities_to_ebitda_nodes(opps, nodes)

        assert nodes[0].linked_opportunity_indices == [0]
        assert nodes[1].linked_opportunity_indices == [0]
        assert nodes[2].linked_opportunity_indices == [0]

    def test_multiple_opportunities_mixed_levers(self):
        from src.models.model_company import Opportunity

        opps = [
            Opportunity(title="Rev", value_lever="Revenue Side"),
            Opportunity(title="Cost", value_lever="Cost Side"),
            Opportunity(title="Both", value_lever="Both"),
        ]
        nodes = self._make_nodes()

        link_opportunities_to_ebitda_nodes(opps, nodes)

        assert nodes[0].linked_opportunity_indices == [0, 2]
        assert nodes[1].linked_opportunity_indices == [1, 2]
        assert sorted(nodes[2].linked_opportunity_indices) == [0, 1, 2]

    def test_nested_children_are_linked(self):
        from src.models.model_company import EbitdaNode, Opportunity

        child = EbitdaNode(id="subs", label="Subscriptions", type="revenue", description="SaaS")
        parent = EbitdaNode(
            id="rev",
            label="Revenue",
            type="revenue",
            description="Revenue",
            children=[child],
        )

        opps = [Opportunity(title="Rev Opp", value_lever="Revenue Side")]
        link_opportunities_to_ebitda_nodes(opps, [parent])

        assert parent.linked_opportunity_indices == [0]
        assert child.linked_opportunity_indices == [0]

    def test_margin_node_links_like_subtotal(self):
        from src.models.model_company import EbitdaNode, Opportunity

        margin = EbitdaNode(
            id="gross_margin", label="Gross Margin", type="margin", description="Gross margin"
        )
        opps = [
            Opportunity(title="Rev Opp", value_lever="Revenue Side"),
            Opportunity(title="Cost Opp", value_lever="Cost Side"),
        ]
        link_opportunities_to_ebitda_nodes(opps, [margin])

        assert sorted(margin.linked_opportunity_indices) == [0, 1]

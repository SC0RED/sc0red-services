"""Tests for ParallelOpportunitiesAndEbitda composite pipeline step."""

from unittest.mock import MagicMock

import pytest
from signalfield_core.models.enums import Precision, ReasoningEffort, Verbosity

from src.facades.company_accessor import CompanyAccessor
from src.models.model_company import (
    Company,
    CompanyProfile,
    EbitdaTreeResult,
    RiskAssessment,
    RiskScore,
)
from src.pipeline.pipeline_steps.generate_opportunities import OPPS_SYSTEM_PROMPT
from src.pipeline.pipeline_steps.parallel_opportunities_ebitda import (
    ParallelOpportunitiesAndEbitda,
    link_opportunities_to_ebitda_nodes,
)


def _make_opportunity_data(
    title: str = "Deploy AI Chatbot",
    value_lever: str = "Both",
) -> dict:
    return {
        "title": title,
        "impact_rating": "High",
        "strategic_category": "Competitive Moat",
        "description": "Build a customer-facing AI chatbot",
        "implementation_steps": ["Step 1", "Step 2", "Step 3"],
        "timeline": "Medium-term (3-9 months)",
        "investment_range": "$100K-$500K",
        "roi_estimate": "30% improvement in support efficiency",
        "related_services": ["Accenture - AI strategy"],
        "value_lever": value_lever,
    }


def _make_company_with_profile_and_risk() -> Company:
    company = Company(url="https://example.com")
    company.profile = CompanyProfile(
        company_name="Test Corp",
        industry="SaaS",
        industry_sector="Technology",
        business_model="SaaS",
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
    return company


def _make_mock_factory(
    high_priority_data: dict,
    strategic_data: dict,
    ebitda_data: dict,
) -> MagicMock:
    """Create a mock AIClientFactory that dispatches by schema.

    Routes responses based on whether the schema requires top_three_immediate_actions
    (high-priority), nodes (EBITDA tree), or neither (strategic).
    """
    mock_factory = MagicMock()
    mock_client = MagicMock()
    mock_factory.get_client.return_value = mock_client

    response_high = MagicMock()
    response_high.content = high_priority_data
    response_high.metadata = {"tokens": 100}
    response_strategic = MagicMock()
    response_strategic.content = strategic_data
    response_strategic.metadata = {"tokens": 80}
    response_ebitda = MagicMock()
    response_ebitda.content = ebitda_data
    response_ebitda.metadata = {"tokens": 120}

    def dispatch_by_schema(*, input_text, json_schema):
        if "top_three_immediate_actions" in json_schema.get("required", []):
            return response_high
        if "nodes" in json_schema.get("properties", {}):
            return response_ebitda
        return response_strategic

    mock_client.query_structured.side_effect = dispatch_by_schema
    return mock_factory


_MOCK_EBITDA_RESPONSE = {
    "summary": "SaaS model with subscription revenue",
    "revenue_estimate": "$10M-$50M",
    "ebitda_estimate": "$2M-$8M",
    "nodes": [
        {
            "id": "revenue",
            "label": "Total Revenue",
            "type": "revenue",
            "value_range": "$10M-$50M",
            "percentage_of_parent": None,
            "description": "Total revenue",
            "children": [
                {
                    "id": "subs",
                    "label": "Subscriptions",
                    "type": "revenue",
                    "value_range": "$8M-$40M",
                    "percentage_of_parent": 80,
                    "description": "SaaS subscriptions",
                    "children": [],
                },
            ],
        },
        {
            "id": "cogs",
            "label": "COGS",
            "type": "cost",
            "value_range": "$3M-$15M",
            "percentage_of_parent": None,
            "description": "Cost of goods sold",
            "children": [],
        },
        {
            "id": "ebitda",
            "label": "EBITDA",
            "type": "subtotal",
            "value_range": "$2M-$8M",
            "percentage_of_parent": None,
            "description": "Earnings",
            "children": [],
        },
    ],
}


class TestParallelOpportunitiesAndEbitda:
    def test_successful_parallel_execution(self):
        high_priority_data = {
            "opportunities": [
                _make_opportunity_data("AI Chatbot", "Revenue Side"),
                _make_opportunity_data("Tech Upgrade", "Cost Side"),
            ],
            "top_three_immediate_actions": ["Action 1", "Action 2", "Action 3"],
        }
        strategic_data = {
            "opportunities": [
                _make_opportunity_data("Compliance Bot", "Both"),
            ],
        }
        mock_factory = _make_mock_factory(high_priority_data, strategic_data, _MOCK_EBITDA_RESPONSE)

        company = _make_company_with_profile_and_risk()
        accessor = CompanyAccessor(company)

        step = ParallelOpportunitiesAndEbitda(ai_client_factory=mock_factory)
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        step.execute()

        # Check opportunities
        result = accessor.company.opportunity_result
        assert result is not None
        assert len(result.opportunities) == 3
        assert result.opportunities[0].title == "AI Chatbot"
        assert result.opportunities[1].title == "Tech Upgrade"
        assert result.opportunities[2].title == "Compliance Bot"
        assert result.top_three_immediate_actions == ["Action 1", "Action 2", "Action 3"]

        # Check EBITDA tree
        ebitda = accessor.company.ebitda_tree
        assert ebitda is not None
        assert isinstance(ebitda, EbitdaTreeResult)
        assert ebitda.summary == "SaaS model with subscription revenue"
        assert ebitda.revenue_estimate == "$10M-$50M"
        assert len(ebitda.nodes) == 3

        # Check EBITDA nodes are linked to opportunities
        revenue_node = ebitda.nodes[0]
        assert 0 in revenue_node.linked_opportunity_indices  # AI Chatbot = Revenue Side
        assert 2 in revenue_node.linked_opportunity_indices  # Compliance Bot = Both

        cost_node = ebitda.nodes[1]
        assert 1 in cost_node.linked_opportunity_indices  # Tech Upgrade = Cost Side
        assert 2 in cost_node.linked_opportunity_indices  # Compliance Bot = Both

        # 3 AI calls (high-priority, strategic, ebitda)
        assert mock_factory.get_client.call_count == 3
        mock_factory.get_client.assert_any_call(
            verbosity=Verbosity.MEDIUM,
            reasoning_effort=ReasoningEffort.LOW,
            precision=Precision.STANDARD,
            instructions=OPPS_SYSTEM_PROMPT,
        )

        # Both questions marked complete
        calls = step._request_executor.mark_question_complete.call_args_list
        completed = {c[0][0] for c in calls}
        assert "generate_opportunities" in completed
        assert "generate_ebitda_tree" in completed

    def test_top_actions_come_from_high_priority_call(self):
        high_priority_data = {
            "opportunities": [_make_opportunity_data()],
            "top_three_immediate_actions": ["Urgent 1", "Urgent 2", "Urgent 3"],
        }
        strategic_data = {"opportunities": [_make_opportunity_data("Strategic Opp")]}
        mock_factory = _make_mock_factory(high_priority_data, strategic_data, _MOCK_EBITDA_RESPONSE)

        company = _make_company_with_profile_and_risk()
        accessor = CompanyAccessor(company)

        step = ParallelOpportunitiesAndEbitda(ai_client_factory=mock_factory)
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        step.execute()

        result = accessor.company.opportunity_result
        assert result is not None
        assert result.top_three_immediate_actions == ["Urgent 1", "Urgent 2", "Urgent 3"]

    def test_missing_profile_raises(self):
        company = Company(url="https://example.com")
        company.risk_assessment = RiskAssessment(overall_score=5.0)
        accessor = CompanyAccessor(company)

        step = ParallelOpportunitiesAndEbitda(ai_client_factory=MagicMock())
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        with pytest.raises(ValueError, match="profile or risk assessment missing"):
            step.execute()

    def test_missing_risk_assessment_raises(self):
        company = Company(url="https://example.com")
        company.profile = CompanyProfile(company_name="Test", industry="Tech")
        accessor = CompanyAccessor(company)

        step = ParallelOpportunitiesAndEbitda(ai_client_factory=MagicMock())
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        with pytest.raises(ValueError, match="profile or risk assessment missing"):
            step.execute()

    def test_missing_factory_raises(self):
        company = _make_company_with_profile_and_risk()
        accessor = CompanyAccessor(company)

        step = ParallelOpportunitiesAndEbitda(ai_client_factory=None)
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        with pytest.raises(RuntimeError, match="AI client factory not configured"):
            step.execute()

    def test_ai_call_failure_propagates(self):
        from signalfield_core.utilities.future_manager import FutureManagerError

        mock_factory = MagicMock()
        mock_client = MagicMock()
        mock_factory.get_client.return_value = mock_client
        mock_client.query_structured.side_effect = RuntimeError("AI service unavailable")

        company = _make_company_with_profile_and_risk()
        accessor = CompanyAccessor(company)

        step = ParallelOpportunitiesAndEbitda(ai_client_factory=mock_factory)
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        with pytest.raises(FutureManagerError):
            step.execute()


class TestLinkOpportunitiesToEbitdaNodes:
    def _make_nodes(self):
        """Build a simple EBITDA tree: revenue, cost, subtotal."""
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

        assert nodes[0].linked_opportunity_indices == [0]  # revenue
        assert nodes[1].linked_opportunity_indices == []  # cost
        assert nodes[2].linked_opportunity_indices == [0]  # subtotal (gets revenue)

    def test_cost_side_links_to_cost_nodes(self):
        from src.models.model_company import Opportunity

        opps = [Opportunity(title="Cost Opp", value_lever="Cost Side")]
        nodes = self._make_nodes()

        link_opportunities_to_ebitda_nodes(opps, nodes)

        assert nodes[0].linked_opportunity_indices == []  # revenue
        assert nodes[1].linked_opportunity_indices == [0]  # cost
        assert nodes[2].linked_opportunity_indices == [0]  # subtotal (gets cost)

    def test_both_links_to_all_nodes(self):
        from src.models.model_company import Opportunity

        opps = [Opportunity(title="Both Opp", value_lever="Both")]
        nodes = self._make_nodes()

        link_opportunities_to_ebitda_nodes(opps, nodes)

        assert nodes[0].linked_opportunity_indices == [0]  # revenue
        assert nodes[1].linked_opportunity_indices == [0]  # cost
        assert nodes[2].linked_opportunity_indices == [0]  # subtotal

    def test_multiple_opportunities_mixed_levers(self):
        from src.models.model_company import Opportunity

        opps = [
            Opportunity(title="Rev", value_lever="Revenue Side"),
            Opportunity(title="Cost", value_lever="Cost Side"),
            Opportunity(title="Both", value_lever="Both"),
        ]
        nodes = self._make_nodes()

        link_opportunities_to_ebitda_nodes(opps, nodes)

        assert nodes[0].linked_opportunity_indices == [0, 2]  # revenue: Rev + Both
        assert nodes[1].linked_opportunity_indices == [1, 2]  # cost: Cost + Both
        assert sorted(nodes[2].linked_opportunity_indices) == [0, 1, 2]  # subtotal: all

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

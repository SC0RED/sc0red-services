"""Tests for ComputeEbitdaTree pipeline step."""

from unittest.mock import MagicMock

import pytest

from src.facades.company_accessor import CompanyAccessor
from src.models.model_company import (
    Company,
    CompanyProfile,
    EbitdaTreeResult,
    Opportunity,
    OpportunityResult,
)
from src.pipeline.pipeline_steps.compute_ebitda_tree import (
    ComputeEbitdaTree,
    link_opportunities_to_ebitda_nodes,
)


class TestComputeEbitdaTree:
    def _make_company(self, with_opportunities: bool = True) -> Company:
        company = Company(url="https://example.com")
        company.profile = CompanyProfile(
            company_name="Test Corp",
            industry="SaaS",
            business_model="SaaS",
            company_size="Mid-market 200-1000",
        )
        if with_opportunities:
            company.opportunity_result = OpportunityResult(
                opportunities=[
                    Opportunity(title="Rev Opp", value_lever="Revenue Side"),
                    Opportunity(title="Cost Opp", value_lever="Cost Side"),
                ],
            )
        return company

    def test_builds_ebitda_tree(self):
        company = self._make_company()
        accessor = CompanyAccessor(company)

        step = ComputeEbitdaTree()
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        step.execute()

        ebitda = accessor.company.ebitda_tree
        assert ebitda is not None
        assert isinstance(ebitda, EbitdaTreeResult)
        assert len(ebitda.nodes) == 5
        assert "Test Corp" in ebitda.summary

    def test_links_opportunities_to_nodes(self):
        company = self._make_company(with_opportunities=True)
        accessor = CompanyAccessor(company)

        step = ComputeEbitdaTree()
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        step.execute()

        ebitda = accessor.company.ebitda_tree
        revenue_node = ebitda.nodes[0]
        assert 0 in revenue_node.linked_opportunity_indices  # Revenue Side

        cost_node = ebitda.nodes[1]
        assert 1 in cost_node.linked_opportunity_indices  # Cost Side

    def test_works_without_opportunities(self):
        company = self._make_company(with_opportunities=False)
        accessor = CompanyAccessor(company)

        step = ComputeEbitdaTree()
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        step.execute()

        ebitda = accessor.company.ebitda_tree
        assert ebitda is not None
        for node in ebitda.nodes:
            assert node.linked_opportunity_indices == []

    def test_missing_profile_raises(self):
        company = Company(url="https://example.com")
        accessor = CompanyAccessor(company)

        step = ComputeEbitdaTree()
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        with pytest.raises(ValueError, match="profile missing"):
            step.execute()

    def test_marks_question_complete(self):
        company = self._make_company()
        accessor = CompanyAccessor(company)

        step = ComputeEbitdaTree()
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        step.execute()

        calls = step._request_executor.mark_question_complete.call_args_list
        completed = {c[0][0] for c in calls}
        assert "generate_ebitda_tree" in completed


class TestLinkOpportunitiesToEbitdaNodes:
    def _make_nodes(self):
        from src.models.model_company import EbitdaNode

        revenue = EbitdaNode(id="rev", label="Revenue", type="revenue", description="Revenue")
        cost = EbitdaNode(id="cost", label="COGS", type="cost", description="Cost")
        subtotal = EbitdaNode(id="ebitda", label="EBITDA", type="subtotal", description="EBITDA")
        return [revenue, cost, subtotal]

    def test_revenue_side_links_to_revenue_nodes(self):
        opps = [Opportunity(title="Rev Opp", value_lever="Revenue Side")]
        nodes = self._make_nodes()
        link_opportunities_to_ebitda_nodes(opps, nodes)
        assert nodes[0].linked_opportunity_indices == [0]
        assert nodes[1].linked_opportunity_indices == []
        assert nodes[2].linked_opportunity_indices == [0]

    def test_cost_side_links_to_cost_nodes(self):
        opps = [Opportunity(title="Cost Opp", value_lever="Cost Side")]
        nodes = self._make_nodes()
        link_opportunities_to_ebitda_nodes(opps, nodes)
        assert nodes[0].linked_opportunity_indices == []
        assert nodes[1].linked_opportunity_indices == [0]

    def test_both_links_to_all_nodes(self):
        opps = [Opportunity(title="Both Opp", value_lever="Both")]
        nodes = self._make_nodes()
        link_opportunities_to_ebitda_nodes(opps, nodes)
        assert nodes[0].linked_opportunity_indices == [0]
        assert nodes[1].linked_opportunity_indices == [0]
        assert nodes[2].linked_opportunity_indices == [0]

"""Tests for GenerateEbitdaTree pipeline step."""

from unittest.mock import MagicMock

import pytest
from signalfield_core.models.enums import Precision, ReasoningEffort, Verbosity

from src.facades.company_accessor import CompanyAccessor
from src.models.model_company import (
    Company,
    CompanyProfile,
    EbitdaTreeResult,
    Opportunity,
    OpportunityResult,
    RiskAssessment,
    RiskScore,
)
from src.pipeline.pipeline_steps.generate_ebitda_tree import (
    _SYSTEM_PROMPT,
    GenerateEbitdaTree,
    _build_ebitda_node,
)

_MOCK_AI_RESPONSE = {
    "summary": "SaaS model with subscription revenue and moderate EBITDA margins.",
    "revenue_estimate": "$10M-$50M",
    "ebitda_estimate": "$2M-$8M",
    "nodes": [
        {
            "id": "revenue",
            "label": "Total Revenue",
            "type": "revenue",
            "value_range": "$10M-$50M",
            "percentage_of_parent": None,
            "description": "Total subscription and services revenue",
            "linked_opportunity_indices": [],
            "children": [
                {
                    "id": "subscriptions",
                    "label": "Subscription Revenue",
                    "type": "revenue",
                    "value_range": "$8M-$40M",
                    "percentage_of_parent": 80,
                    "description": "Annual SaaS subscriptions",
                    "linked_opportunity_indices": [0],
                    "children": [],
                },
            ],
        },
        {
            "id": "ebitda",
            "label": "EBITDA",
            "type": "subtotal",
            "value_range": "$2M-$8M",
            "description": "Earnings before interest, taxes, depreciation and amortisation",
            "linked_opportunity_indices": [0],
            "children": [],
        },
    ],
}


def _make_company_with_opportunities() -> Company:
    return Company(
        id="comp-1",
        url="https://example.com",
        profile=CompanyProfile(
            company_name="Test Corp",
            industry="SaaS",
            industry_sector="Technology",
        ),
        risk_assessment=RiskAssessment(
            risk_scores=[
                RiskScore(category="competitive_displacement", score=7),
            ],
            overall_score=5.0,
            tier="moderate",
            top_risks=["competitive_displacement"],
            analysis_summary="Moderate risk",
        ),
        opportunity_result=OpportunityResult(
            opportunities=[
                Opportunity(
                    title="Deploy AI Automation",
                    value_lever="Cost Side",
                ),
            ],
            top_three_immediate_actions=["Action 1"],
        ),
    )


class TestBuildEbitdaNode:
    def test_builds_flat_node(self):
        node = _build_ebitda_node(
            {
                "id": "revenue",
                "label": "Total Revenue",
                "type": "revenue",
                "description": "All revenue",
                "linked_opportunity_indices": [0, 1],
                "children": [],
            }
        )
        assert node.id == "revenue"
        assert node.type == "revenue"
        assert node.linked_opportunity_indices == [0, 1]
        assert node.children == []

    def test_builds_nested_nodes(self):
        node = _build_ebitda_node(
            {
                "id": "revenue",
                "label": "Revenue",
                "type": "revenue",
                "description": "Top",
                "linked_opportunity_indices": [],
                "children": [
                    {
                        "id": "subs",
                        "label": "Subscriptions",
                        "type": "revenue",
                        "description": "SaaS subs",
                        "linked_opportunity_indices": [0],
                        "children": [],
                    },
                ],
            }
        )
        assert len(node.children) == 1
        assert node.children[0].id == "subs"
        assert node.children[0].linked_opportunity_indices == [0]


class TestGenerateEbitdaTree:
    def test_execute_sets_ebitda_tree(self):
        company = _make_company_with_opportunities()
        accessor = CompanyAccessor(company)

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = _MOCK_AI_RESPONSE
        mock_response.metadata = {"tokens": 100}
        mock_client.query_structured.return_value = mock_response

        mock_factory = MagicMock()
        mock_factory.get_client.return_value = mock_client

        step = GenerateEbitdaTree(ai_client_factory=mock_factory)
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        step.execute()

        result = accessor.company.ebitda_tree
        assert result is not None
        assert isinstance(result, EbitdaTreeResult)
        assert result.summary == "SaaS model with subscription revenue and moderate EBITDA margins."
        assert result.revenue_estimate == "$10M-$50M"
        assert result.ebitda_estimate == "$2M-$8M"
        assert len(result.nodes) == 2
        assert result.nodes[0].id == "revenue"
        assert len(result.nodes[0].children) == 1
        assert result.nodes[0].children[0].linked_opportunity_indices == [0]
        step._request_executor.mark_question_complete.assert_called_with("generate_ebitda_tree")
        mock_factory.get_client.assert_called_once_with(
            verbosity=Verbosity.MEDIUM,
            reasoning_effort=ReasoningEffort.LOW,
            precision=Precision.STANDARD,
            instructions=_SYSTEM_PROMPT,
        )

    def test_execute_missing_profile_raises(self):
        company = Company(id="comp-1", url="https://example.com")
        accessor = CompanyAccessor(company)

        step = GenerateEbitdaTree(ai_client_factory=MagicMock())
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        with pytest.raises(ValueError, match="profile, risk assessment, or opportunities missing"):
            step.execute()

    def test_execute_missing_opportunities_raises(self):
        company = Company(
            id="comp-1",
            url="https://example.com",
            profile=CompanyProfile(company_name="Test", industry="Tech"),
            risk_assessment=RiskAssessment(
                risk_scores=[RiskScore(category="data_ip", score=3)],
                overall_score=3.0,
                tier="low",
            ),
        )
        accessor = CompanyAccessor(company)

        step = GenerateEbitdaTree(ai_client_factory=MagicMock())
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        with pytest.raises(ValueError, match="opportunities missing"):
            step.execute()

    def test_execute_no_factory_raises(self):
        company = _make_company_with_opportunities()
        accessor = CompanyAccessor(company)

        step = GenerateEbitdaTree(ai_client_factory=None)
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        with pytest.raises(RuntimeError, match="AI client factory not configured"):
            step.execute()

"""Tests for ComputeValueChain pipeline step."""

from unittest.mock import MagicMock

import pytest

from src.facades.company_accessor import CompanyAccessor
from src.models.model_company import (
    Company,
    CompanyProfile,
    Opportunity,
    OpportunityResult,
    ValueChainResult,
)
from src.pipeline.pipeline_steps.compute_value_chain import ComputeValueChain


class TestComputeValueChain:
    def _make_company(self, with_opportunities: bool = True) -> Company:
        company = Company(url="https://example.com")
        company.profile = CompanyProfile(
            company_name="Test Corp",
            industry="SaaS",
            business_model="SaaS",
        )
        if with_opportunities:
            company.opportunity_result = OpportunityResult(
                opportunities=[
                    Opportunity(title="AI Chatbot", strategic_category="Competitive Moat", value_lever="Revenue Side"),
                ],
            )
        return company

    def test_builds_value_chain(self):
        company = self._make_company()
        accessor = CompanyAccessor(company)

        step = ComputeValueChain()
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        step.execute()

        assert company.value_chain is not None
        assert isinstance(company.value_chain, ValueChainResult)
        assert len(company.value_chain.steps) > 0

    def test_links_opportunities(self):
        company = self._make_company(with_opportunities=True)
        accessor = CompanyAccessor(company)

        step = ComputeValueChain()
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        step.execute()

        all_indices = []
        for value_step in company.value_chain.steps:
            all_indices.extend(value_step.opportunity_indices)
        assert len(all_indices) > 0

    def test_works_without_opportunities(self):
        company = self._make_company(with_opportunities=False)
        accessor = CompanyAccessor(company)

        step = ComputeValueChain()
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        step.execute()

        assert company.value_chain is not None
        for value_step in company.value_chain.steps:
            assert value_step.opportunity_indices == []

    def test_missing_profile_raises(self):
        company = Company(url="https://example.com")
        accessor = CompanyAccessor(company)

        step = ComputeValueChain()
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        with pytest.raises(ValueError, match="profile missing"):
            step.execute()

    def test_marks_question_complete(self):
        company = self._make_company()
        accessor = CompanyAccessor(company)

        step = ComputeValueChain()
        step._entity_accessor = accessor
        step._request_executor = MagicMock()

        step.execute()

        calls = step._request_executor.mark_question_complete.call_args_list
        completed = {c[0][0] for c in calls}
        assert "compute_value_chain" in completed

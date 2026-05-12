"""Tests for ``hydrate_company_for_strategy_map`` — the persistence-to-Pydantic
conversion that the on-demand strategy-map worker uses to reconstruct the
in-memory ``Company`` shape ``GenerateStrategyMap`` expects.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from src.handlers._strategy_map_hydration import (
    StrategyMapHydrationError,
    hydrate_company_for_strategy_map,
)


def _make_storage(
    *,
    company_record: dict[str, Any] | None,
    assessments: list[dict[str, Any]] | None = None,
    risk_scores: list[dict[str, Any]] | None = None,
    opportunities: list[dict[str, Any]] | None = None,
    ebitda_tree: dict[str, Any] | None = None,
    value_chain: dict[str, Any] | None = None,
) -> MagicMock:
    storage = MagicMock()
    company_repo = MagicMock()
    company_repo.get_by_id.return_value = company_record
    storage.create_company_repository.return_value = company_repo

    assessment_repo = MagicMock()
    assessment_repo.find_by_company.return_value = assessments or []
    assessment_repo.get_risk_scores.return_value = risk_scores or []
    assessment_repo.get_opportunities.return_value = opportunities or []
    assessment_repo.get_ebitda_tree.return_value = ebitda_tree
    assessment_repo.get_value_chain.return_value = value_chain
    storage.create_assessment_repository.return_value = assessment_repo

    return storage


class TestHydrationFailureModes:
    def test_raises_when_company_record_missing(self):
        storage = _make_storage(company_record=None)
        with pytest.raises(StrategyMapHydrationError, match="not found"):
            hydrate_company_for_strategy_map(storage, "ana-missing")

    def test_raises_when_no_assessment_exists(self):
        storage = _make_storage(
            company_record={"id": "ana-1", "company_name": "Acme", "industry": "Tech"},
            assessments=[],
        )
        with pytest.raises(StrategyMapHydrationError, match="no assessment record"):
            hydrate_company_for_strategy_map(storage, "ana-1")


class TestHydrationHappyPath:
    def test_full_population_reconstructs_company_pydantic_model(self):
        company_record = {
            "id": "ana-1",
            "scan_id": "scan-1",
            "org_id": "org-1",
            "created_by": "user-1",
            "company_name": "Acme Corp",
            "company_url": "https://acme.example",
            "industry": "Technology",
            "industry_sector": "SaaS",
            "business_model": "B2B SaaS",
            "company_size": "Mid-market 200-1000",
            "overall_risk_score": 6.5,
            "risk_tier": "high",
        }
        assessments = [{"id": "assess-1", "created_at": "2026-01-01T00:00:00Z"}]
        risk_scores = [
            {"category": "data_ip", "score": 7, "rationale": "weak protections"},
            {"category": "automation", "score": 5, "rationale": "manual workflows"},
        ]
        opportunities = [
            {
                "title": "AI customer support",
                "impact_rating": "High",
                "strategic_category": "Operational Efficiency",
                "description": "Automate Tier 1 support with an LLM agent",
                "implementation_steps": ["scope", "build", "deploy"],
                "timeline": "6 months",
                "investment_range": "$200K-$500K",
                "roi_estimate": "12-month payback",
                "value_lever": "Cost Side",
            }
        ]
        ebitda_tree = {
            "treeData": [{"id": "rev", "label": "Revenue", "type": "revenue", "description": "x"}],
            "revenueEstimate": "$10M",
            "ebitdaEstimate": "$2M",
            "businessModelSummary": "Recurring SaaS",
        }
        value_chain = {
            "summary": "Two-step value chain",
            "steps": [
                {"id": "s1", "label": "Acquire", "category": "primary", "description": "..."},
                {"id": "s2", "label": "Serve", "category": "support", "description": "..."},
            ],
        }

        storage = _make_storage(
            company_record=company_record,
            assessments=assessments,
            risk_scores=risk_scores,
            opportunities=opportunities,
            ebitda_tree=ebitda_tree,
            value_chain=value_chain,
        )

        company = hydrate_company_for_strategy_map(storage, "ana-1")

        # Top-level identity fields
        assert company.id == "ana-1"
        assert company.scan_id == "scan-1"
        assert company.user_id == "user-1"
        assert company.company_name == "Acme Corp"

        # Profile reconstructed from company record
        assert company.profile is not None
        assert company.profile.company_name == "Acme Corp"
        assert company.profile.industry == "Technology"
        assert company.profile.business_model == "B2B SaaS"
        assert company.profile.company_size == "Mid-market 200-1000"

        # Risk assessment with both per-category rows + overall score
        assert company.risk_assessment is not None
        assert len(company.risk_assessment.risk_scores) == 2
        assert company.risk_assessment.overall_score == 6.5
        assert company.risk_assessment.tier == "high"
        # First per-category score has the expected category + rationale
        assert company.risk_assessment.risk_scores[0].category == "data_ip"
        assert company.risk_assessment.risk_scores[0].rationale == "weak protections"

        # Opportunities
        assert company.opportunity_result is not None
        assert len(company.opportunity_result.opportunities) == 1
        opp = company.opportunity_result.opportunities[0]
        assert opp.title == "AI customer support"
        assert opp.value_lever == "Cost Side"
        assert opp.implementation_steps == ["scope", "build", "deploy"]

        # EBITDA tree (camelCase API shape converted back to snake_case Pydantic)
        assert company.ebitda_tree is not None
        assert company.ebitda_tree.summary == "Recurring SaaS"
        assert company.ebitda_tree.revenue_estimate == "$10M"
        assert company.ebitda_tree.ebitda_estimate == "$2M"
        assert len(company.ebitda_tree.nodes) == 1
        assert company.ebitda_tree.nodes[0].id == "rev"

        # Value chain
        assert company.value_chain is not None
        assert company.value_chain.summary == "Two-step value chain"
        assert len(company.value_chain.steps) == 2

    def test_missing_optional_subrecords_yield_none_fields(self):
        """When opportunities / ebitda / value chain are absent, the corresponding
        Pydantic fields are None (not an empty container) — preserves the same
        shape ``GenerateStrategyMap`` sees for partial pipeline runs."""
        company_record = {
            "id": "ana-2",
            "company_name": "Beta",
            "industry": "Tech",
            "company_size": "Small 50-200",
        }
        storage = _make_storage(
            company_record=company_record,
            assessments=[{"id": "assess-2", "created_at": "2026-01-01T00:00:00Z"}],
            risk_scores=[{"category": "data_ip", "score": 5, "rationale": "..."}],
            # No opportunities / ebitda / value_chain
        )

        company = hydrate_company_for_strategy_map(storage, "ana-2")

        assert company.opportunity_result is None
        assert company.ebitda_tree is None
        assert company.value_chain is None
        # Risk assessment still reconstructed from the single score row
        assert company.risk_assessment is not None
        assert len(company.risk_assessment.risk_scores) == 1

    def test_assessments_sorted_newest_first(self):
        """When multiple assessments exist (re-analyse race), hydration uses the
        most-recent one — same rule as ``analysis_payload``."""
        company_record = {"id": "ana-3", "company_name": "Gamma", "industry": "Tech"}
        assessments = [
            {"id": "old", "created_at": "2025-01-01T00:00:00Z"},
            {"id": "new", "created_at": "2026-06-01T00:00:00Z"},
            {"id": "middle", "created_at": "2025-08-01T00:00:00Z"},
        ]
        storage = _make_storage(
            company_record=company_record,
            assessments=assessments,
            risk_scores=[{"category": "x", "score": 1, "rationale": "..."}],
        )

        hydrate_company_for_strategy_map(storage, "ana-3")

        # The repo getters were called with the newest assessment id ("new")
        assessment_repo = storage.create_assessment_repository.return_value
        # All four sub-record getters use the same id parameter
        for getter_name in (
            "get_risk_scores",
            "get_opportunities",
            "get_ebitda_tree",
            "get_value_chain",
        ):
            getter = getattr(assessment_repo, getter_name)
            called_with = getter.call_args.args[0]
            assert called_with == "new", (
                f"{getter_name} was called with {called_with!r}, expected 'new'"
            )

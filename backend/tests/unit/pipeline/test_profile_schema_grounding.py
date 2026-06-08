"""Tests for profile-extraction grounding (company-profile-grounding spec).

Guards the contract that existing-fact fields are grounded or explicitly
``unknown``, and that the schema's ``company_size`` enum stays aligned with the
EBITDA size map so a validly-extracted size can never silently default.
"""

from src.models.model_company import CompanyProfile
from src.pipeline.pipeline_steps._ebitda_templates import _SIZE_TO_EMPLOYEES
from src.pipeline.pipeline_steps.build_ebitda_tree import build_programmatic_ebitda_tree
from src.pipeline.pipeline_steps.build_value_chain import build_programmatic_value_chain
from src.pipeline.pipeline_steps.extract_profile import (
    PROFILE_SCHEMA,
    PROFILE_SYSTEM_PROMPT,
)


class TestCompanySizeEnumAlignment:
    def test_company_size_enum_matches_size_map_plus_unknown(self):
        enum = PROFILE_SCHEMA["properties"]["company_size"]["enum"]
        # Every non-"unknown" enum value must be a key the size map understands —
        # this is the regression guard for the original "Enterprise 1000+" mismatch.
        size_values = [value for value in enum if value != "unknown"]
        assert set(size_values) == set(_SIZE_TO_EMPLOYEES.keys())
        assert "unknown" in enum

    def test_schema_no_longer_offers_unmappable_enterprise_band(self):
        enum = PROFILE_SCHEMA["properties"]["company_size"]["enum"]
        assert "Enterprise 1000+" not in enum


class TestGroundingInstructions:
    def test_system_prompt_requires_unknown_for_ungrounded_facts(self):
        prompt = PROFILE_SYSTEM_PROMPT.lower()
        assert "unknown" in prompt
        assert "business_model" in PROFILE_SYSTEM_PROMPT
        assert "revenue_model" in PROFILE_SYSTEM_PROMPT
        assert "company_size" in PROFILE_SYSTEM_PROMPT

    def test_fact_fields_instruct_unknown_fallback(self):
        for field in ("business_model", "revenue_model"):
            description = PROFILE_SCHEMA["properties"][field]["description"]
            assert "unknown" in description.lower()


class TestUnknownFlowsToPlaceholder:
    """An ``unknown`` business model must suppress both FACT surfaces."""

    def _profile(self) -> CompanyProfile:
        return CompanyProfile(
            company_name="Mystery Co",
            industry="Unknown",
            business_model="unknown",
            company_size="unknown",
        )

    def test_unknown_business_model_suppresses_ebitda(self):
        result = build_programmatic_ebitda_tree(self._profile())
        assert result.grounded is False
        assert result.nodes == []

    def test_unknown_business_model_suppresses_value_chain(self):
        result = build_programmatic_value_chain(self._profile())
        assert result.grounded is False
        assert result.steps == []

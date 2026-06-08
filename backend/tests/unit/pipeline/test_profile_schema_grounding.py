"""Tests for profile-extraction grounding (company-profile-grounding spec).

Guards the contract that existing-fact fields are grounded or explicitly
``unknown``. (The old size-map alignment guard was retired with the EBITDA
templates — financials are now AI-researched, not derived from a size map.)
"""

from src.pipeline.pipeline_steps.extract_profile import (
    PROFILE_SCHEMA,
    PROFILE_SYSTEM_PROMPT,
)


class TestGroundingInstructions:
    def test_system_prompt_requires_unknown_for_ungrounded_facts(self):
        assert "unknown" in PROFILE_SYSTEM_PROMPT.lower()
        assert "business_model" in PROFILE_SYSTEM_PROMPT
        assert "revenue_model" in PROFILE_SYSTEM_PROMPT
        assert "company_size" in PROFILE_SYSTEM_PROMPT

    def test_fact_fields_instruct_unknown_fallback(self):
        for field in ("business_model", "revenue_model"):
            description = PROFILE_SCHEMA["properties"][field]["description"]
            assert "unknown" in description.lower()


class TestCompanySizeEnum:
    def test_company_size_allows_unknown(self):
        enum = PROFILE_SCHEMA["properties"]["company_size"]["enum"]
        assert "unknown" in enum

    def test_company_size_drops_unmappable_legacy_band(self):
        # The original SaaS-default bug stemmed from "Enterprise 1000+" not
        # matching the size map; that value must not reappear.
        enum = PROFILE_SCHEMA["properties"]["company_size"]["enum"]
        assert "Enterprise 1000+" not in enum

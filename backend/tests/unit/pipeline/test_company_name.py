"""Tests for the never-blank company-name resolver."""

import pytest

from src.pipeline.company_name import resolve_company_name


class TestResolveCompanyName:
    def test_prefers_clean_extracted_name(self):
        assert resolve_company_name("Acme Corp", "Seed Co", "https://acme.com") == "Acme Corp"

    @pytest.mark.parametrize(
        "placeholder",
        ["unknown", "Unknown", "  UNKNOWN ", "n/a", "none", "null", "untitled", ""],
    )
    def test_falls_back_to_seed_when_extracted_is_placeholder(self, placeholder):
        # Regression (millerenv.com): extraction punted to "unknown"/blank.
        assert (
            resolve_company_name(placeholder, "Miller Environmental Group", "")
            == "Miller Environmental Group"
        )

    def test_falls_back_to_domain_when_extracted_and_seed_blank(self):
        assert resolve_company_name("unknown", "", "https://www.millerenv.com/") == "Millerenv"

    def test_last_resort_returns_url_not_unknown(self):
        # Host "a.io" stem is too short to derive a name → bare URL, never "unknown".
        assert resolve_company_name("", "", "https://a.io") == "https://a.io"

    def test_last_resort_returns_placeholder_when_everything_empty(self):
        assert resolve_company_name("unknown", "", "") == "Unnamed company"

    def test_strips_and_compares_case_insensitively(self):
        assert resolve_company_name("  Acme  ", "Seed", "https://x.com") == "Acme"

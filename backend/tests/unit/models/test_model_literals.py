"""Tests for model literals and constants."""

from src.models.model_literals import RISK_SCOPE_DISPLAY, RISK_SCOPE_NAMES


class TestRiskScopeNames:
    def test_has_eight_scopes(self):
        assert len(RISK_SCOPE_NAMES) == 8

    def test_expected_scopes(self):
        expected = {
            "competitive_displacement",
            "technology_obsolescence",
            "talent_workforce",
            "margin_compression",
            "customer_behavior",
            "regulatory_compliance",
            "supply_chain",
            "data_ip",
        }
        assert set(RISK_SCOPE_NAMES) == expected


class TestRiskScopeDisplay:
    def test_has_all_scopes(self):
        assert set(RISK_SCOPE_DISPLAY.keys()) == set(RISK_SCOPE_NAMES)

    def test_each_scope_has_name_and_description(self):
        for scope, display in RISK_SCOPE_DISPLAY.items():
            assert "name" in display, f"{scope} missing 'name'"
            assert "description" in display, f"{scope} missing 'description'"
            assert isinstance(display["name"], str)
            assert isinstance(display["description"], str)

"""Tests for RiskScopeManager."""

import pytest

from src.models.model_literals import RISK_SCOPE_NAMES
from src.utilities.scope_manager import RiskScopeManager


class TestRiskScopeManager:
    def test_valid_scope_creation(self):
        for scope in RISK_SCOPE_NAMES:
            manager = RiskScopeManager(scope)
            assert manager is not None

    def test_invalid_scope_raises(self):
        with pytest.raises((ValueError, KeyError)):
            RiskScopeManager("nonexistent_scope")

    def test_get_role_identity_returns_string(self):
        manager = RiskScopeManager("competitive_displacement")
        identity = manager.get_role_identity()
        assert isinstance(identity, str)
        assert len(identity) > 10

    def test_get_context_description_returns_string(self):
        manager = RiskScopeManager("technology_obsolescence")
        context = manager.get_context_description()
        assert isinstance(context, str)
        assert len(context) > 10

    def test_get_target_type_returns_string(self):
        manager = RiskScopeManager("talent_workforce")
        target = manager.get_target_type()
        assert isinstance(target, str)
        assert len(target) > 0

    def test_get_assessment_type_description_returns_string(self):
        manager = RiskScopeManager("margin_compression")
        description = manager.get_assessment_type_description()
        assert isinstance(description, str)
        assert len(description) > 0

    def test_all_scopes_have_complete_config(self):
        for scope in RISK_SCOPE_NAMES:
            manager = RiskScopeManager(scope)
            assert manager.get_role_identity()
            assert manager.get_context_description()
            assert manager.get_target_type()
            assert manager.get_assessment_type_description()

    def test_different_scopes_have_different_identities(self):
        identities = set()
        for scope in RISK_SCOPE_NAMES:
            manager = RiskScopeManager(scope)
            identities.add(manager.get_role_identity())
        assert len(identities) == 8

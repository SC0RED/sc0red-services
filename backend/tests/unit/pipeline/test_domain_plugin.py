"""Tests for PERiskAssessmentPlugin."""

from unittest.mock import MagicMock

from src.domain.pe_risk_assessment_plugin import PERiskAssessmentPlugin
from src.facades.company_accessor import CompanyAccessor
from src.models.model_company import Company
from src.models.model_literals import RISK_SCOPE_NAMES


class TestPERiskAssessmentPlugin:
    def test_domain_name(self):
        plugin = PERiskAssessmentPlugin()
        assert plugin.domain_name == "pe_risk_assessment"

    def test_event_source(self):
        plugin = PERiskAssessmentPlugin()
        assert plugin.event_source == "signalfield.sc0red_services"

    def test_get_scope_names(self):
        plugin = PERiskAssessmentPlugin()
        scopes = plugin.get_scope_names()
        assert len(scopes) == 8
        assert set(scopes) == set(RISK_SCOPE_NAMES)

    def test_get_scope_configuration(self):
        plugin = PERiskAssessmentPlugin()
        for scope in RISK_SCOPE_NAMES:
            config = plugin.get_scope_configuration(scope)
            assert config is not None
            assert config.get_role_identity()
            assert config.get_context_description()

    def test_create_entity_accessor_with_company(self):
        plugin = PERiskAssessmentPlugin()
        company = Company(url="https://example.com", id="test-id")
        accessor = plugin.create_entity_accessor(company=company)
        assert isinstance(accessor, CompanyAccessor)
        assert accessor.get_entity_id() == "test-id"

    def test_create_entity_accessor_without_company(self):
        plugin = PERiskAssessmentPlugin()
        accessor = plugin.create_entity_accessor()
        assert isinstance(accessor, CompanyAccessor)

    def test_get_assessment_types(self):
        plugin = PERiskAssessmentPlugin()
        types = plugin.get_assessment_types()
        assert "company_analysis" in types
        assert "portfolio_scan" in types

    def test_register_data_strategies(self):
        plugin = PERiskAssessmentPlugin()
        registry = MagicMock()
        plugin.register_data_strategies(registry)
        assert registry.register.call_count == 3
        registered_names = [call[0][0] for call in registry.register.call_args_list]
        assert "web_scrape" in registered_names
        assert "url_resolution" in registered_names
        assert "portfolio_discovery" in registered_names

    def test_register_data_strategies_factories_are_callable(self):
        plugin = PERiskAssessmentPlugin()
        registry = MagicMock()
        plugin.register_data_strategies(registry)
        # Each registered factory should be callable
        for call in registry.register.call_args_list:
            factory = call[0][1]
            strategy = factory({})
            assert strategy is not None

    def test_create_entity_accessor_with_non_company(self):
        plugin = PERiskAssessmentPlugin()
        accessor = plugin.create_entity_accessor(company="not a company")
        assert isinstance(accessor, CompanyAccessor)
        assert accessor.company.url == ""

"""Tests for Sc0redServicesFactoriesFactory."""

import pytest
from unittest.mock import MagicMock, patch

from src.models.model_event import Sc0redServicesEvent
from src.pipeline.factories_factory import Sc0redServicesFactoriesFactory, _initialize_ai_client_factory


class TestSc0redServicesFactoriesFactory:
    @patch("src.pipeline.factories_factory._initialize_ai_client_factory")
    @patch("src.pipeline.factories_factory.CompanyAnalysisFactory")
    def test_create_company_analysis(self, mock_factory_cls, mock_init_ai):
        mock_ai_factory = MagicMock()
        mock_init_ai.return_value = mock_ai_factory
        mock_executor = MagicMock()
        mock_factory_cls.return_value.execute_pipeline.return_value = mock_executor

        ff = Sc0redServicesFactoriesFactory()
        event = Sc0redServicesEvent(
            request_id="req-1",
            request_type="company_analysis",
            url="https://example.com",
            tenant_id="tenant-1",
        )
        result = ff.create_and_execute(event)
        assert result is mock_executor
        mock_factory_cls.assert_called_once()
        call_kwargs = mock_factory_cls.call_args[1]
        assert call_kwargs["ai_client_factory"] is mock_ai_factory

    @patch("src.pipeline.factories_factory._initialize_ai_client_factory")
    @patch("src.pipeline.factories_factory.PortfolioScanFactory")
    def test_create_portfolio_scan(self, mock_factory_cls, mock_init_ai):
        mock_init_ai.return_value = MagicMock()
        mock_executor = MagicMock()
        mock_factory_cls.return_value.execute_pipeline.return_value = mock_executor

        ff = Sc0redServicesFactoriesFactory()
        event = Sc0redServicesEvent(
            request_id="req-1",
            request_type="portfolio_scan",
            url="https://pefirm.com",
            tenant_id="tenant-1",
        )
        result = ff.create_and_execute(event)
        assert result is mock_executor
        mock_factory_cls.assert_called_once()

    @patch("src.pipeline.factories_factory._initialize_ai_client_factory")
    @patch("src.pipeline.factories_factory.CompanyAnalysisFactory")
    def test_passes_repos_to_company_factory(self, mock_factory_cls, mock_init_ai):
        mock_init_ai.return_value = MagicMock()
        mock_executor = MagicMock()
        mock_factory_cls.return_value.execute_pipeline.return_value = mock_executor

        company_repo = MagicMock()
        assessment_repo = MagicMock()
        ff = Sc0redServicesFactoriesFactory(
            company_repo=company_repo,
            assessment_repo=assessment_repo,
        )
        event = Sc0redServicesEvent(
            request_id="req-1",
            request_type="company_analysis",
            url="https://example.com",
            tenant_id="tenant-1",
        )
        ff.create_and_execute(event)

        call_kwargs = mock_factory_cls.call_args[1]
        assert call_kwargs["company_repo"] is company_repo
        assert call_kwargs["assessment_repo"] is assessment_repo


class TestInitializeAiClientFactory:
    @patch("src.pipeline.factories_factory.AnthropicResource")
    @patch("src.pipeline.factories_factory.AIClientFactory")
    @patch("src.pipeline.factories_factory.CompositeServiceOps")
    def test_anthropic_initialized_when_key_present(
        self, mock_ops, mock_factory_cls, mock_anthropic, monkeypatch
    ):
        monkeypatch.setenv("AI_PROVIDER", "anthropic")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
        mock_anthropic.is_initialized.return_value = False

        _initialize_ai_client_factory()

        mock_anthropic.initialize.assert_called_once_with({"anthropic_api_key": "sk-test-key"})

    @patch("src.pipeline.factories_factory.AnthropicResource")
    @patch("src.pipeline.factories_factory.AIClientFactory")
    @patch("src.pipeline.factories_factory.CompositeServiceOps")
    def test_anthropic_raises_when_key_missing(
        self, mock_ops, mock_factory_cls, mock_anthropic, monkeypatch
    ):
        monkeypatch.setenv("AI_PROVIDER", "anthropic")
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY must be set"):
            _initialize_ai_client_factory()

    @patch("src.pipeline.factories_factory.OpenAIResource")
    @patch("src.pipeline.factories_factory.AIClientFactory")
    @patch("src.pipeline.factories_factory.CompositeServiceOps")
    def test_openai_initialized_when_key_present(
        self, mock_ops, mock_factory_cls, mock_openai, monkeypatch
    ):
        monkeypatch.setenv("AI_PROVIDER", "openai")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-test-key")
        mock_openai.is_initialized.return_value = False

        _initialize_ai_client_factory()

        mock_openai.initialize.assert_called_once_with({"openai_api_key": "sk-openai-test-key"})

    @patch("src.pipeline.factories_factory.OpenAIResource")
    @patch("src.pipeline.factories_factory.AIClientFactory")
    @patch("src.pipeline.factories_factory.CompositeServiceOps")
    def test_openai_raises_when_key_missing(
        self, mock_ops, mock_factory_cls, mock_openai, monkeypatch
    ):
        monkeypatch.setenv("AI_PROVIDER", "openai")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        with pytest.raises(RuntimeError, match="OPENAI_API_KEY must be set"):
            _initialize_ai_client_factory()

    @patch("src.pipeline.factories_factory.AnthropicResource")
    @patch("src.pipeline.factories_factory.AIClientFactory")
    @patch("src.pipeline.factories_factory.CompositeServiceOps")
    def test_already_initialized_resource_not_reinitialzed(
        self, mock_ops, mock_factory_cls, mock_anthropic, monkeypatch
    ):
        monkeypatch.setenv("AI_PROVIDER", "anthropic")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
        mock_anthropic.is_initialized.return_value = True

        _initialize_ai_client_factory()

        mock_anthropic.initialize.assert_not_called()

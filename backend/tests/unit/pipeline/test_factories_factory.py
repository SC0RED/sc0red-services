"""Tests for JanusFactoriesFactory."""

from unittest.mock import MagicMock, patch

from src.models.model_event import JanusEvent
from src.pipeline.factories_factory import JanusFactoriesFactory


class TestJanusFactoriesFactory:
    @patch("src.pipeline.factories_factory.CompanyAnalysisFactory")
    def test_create_company_analysis(self, mock_factory_cls):
        mock_executor = MagicMock()
        mock_factory_cls.return_value.execute_pipeline.return_value = mock_executor

        ff = JanusFactoriesFactory()
        event = JanusEvent(
            request_id="req-1",
            request_type="company_analysis",
            url="https://example.com",
            tenant_id="tenant-1",
        )
        result = ff.create_and_execute(event)
        assert result is mock_executor
        mock_factory_cls.assert_called_once()

    @patch("src.pipeline.factories_factory.PortfolioScanFactory")
    def test_create_portfolio_scan(self, mock_factory_cls):
        mock_executor = MagicMock()
        mock_factory_cls.return_value.execute_pipeline.return_value = mock_executor

        ff = JanusFactoriesFactory()
        event = JanusEvent(
            request_id="req-1",
            request_type="portfolio_scan",
            url="https://pefirm.com",
            tenant_id="tenant-1",
        )
        result = ff.create_and_execute(event)
        assert result is mock_executor
        mock_factory_cls.assert_called_once()

    @patch("src.pipeline.factories_factory.CompanyAnalysisFactory")
    def test_passes_repos_to_company_factory(self, mock_factory_cls):
        mock_executor = MagicMock()
        mock_factory_cls.return_value.execute_pipeline.return_value = mock_executor

        company_repo = MagicMock()
        assessment_repo = MagicMock()
        ff = JanusFactoriesFactory(
            company_repo=company_repo,
            assessment_repo=assessment_repo,
        )
        event = JanusEvent(
            request_id="req-1",
            request_type="company_analysis",
            url="https://example.com",
            tenant_id="tenant-1",
        )
        ff.create_and_execute(event)

        call_kwargs = mock_factory_cls.call_args[1]
        assert call_kwargs["company_repo"] is company_repo
        assert call_kwargs["assessment_repo"] is assessment_repo

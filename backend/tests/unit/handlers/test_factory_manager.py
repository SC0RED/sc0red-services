"""Tests for FactoryManager."""

from unittest.mock import MagicMock, patch

from src.handlers.factory_manager import FactoryManager


class TestFactoryManager:
    def _make_manager(self):
        storage = MagicMock()
        return FactoryManager(storage=storage), storage

    def test_storage_property(self):
        manager, storage = self._make_manager()
        assert manager.storage is storage

    @patch("src.handlers.factory_manager.JanusFactoriesFactory")
    def test_run_company_analysis(self, mock_factory_cls):
        mock_executor = MagicMock()
        mock_executor.details = {"key": "value"}
        mock_executor.step_timings = {"step1": 1.5}
        mock_executor.exceptions = []
        mock_factory_cls.return_value.create_and_execute.return_value = mock_executor

        storage = MagicMock()
        manager = FactoryManager(storage=storage)

        result = manager.run_company_analysis(
            url="https://example.com",
            org_id="org-1",
            user_id="user-1",
            scan_id="scan-1",
            company_name="Test",
        )
        assert "request_id" in result
        assert result["details"] == {"key": "value"}
        assert result["step_timings"] == {"step1": 1.5}
        assert result["exceptions"] == []

    @patch("src.handlers.factory_manager.JanusFactoriesFactory")
    def test_run_portfolio_discovery(self, mock_factory_cls):
        mock_executor = MagicMock()
        mock_executor.details = {"portfolio_companies": []}
        mock_executor.step_timings = {}
        mock_executor.exceptions = []
        mock_factory_cls.return_value.create_and_execute.return_value = mock_executor

        storage = MagicMock()
        manager = FactoryManager(storage=storage)

        result = manager.run_portfolio_discovery(
            url="https://pefirm.com",
            org_id="org-1",
            user_id="user-1",
            scan_id="scan-1",
        )
        assert "request_id" in result
        assert result["details"] == {"portfolio_companies": []}

    @patch("src.handlers.factory_manager.JanusFactoriesFactory")
    def test_run_company_analysis_with_exceptions(self, mock_factory_cls):
        mock_executor = MagicMock()
        mock_executor.details = {}
        mock_executor.step_timings = {}
        mock_executor.exceptions = [ValueError("test error")]
        mock_factory_cls.return_value.create_and_execute.return_value = mock_executor

        storage = MagicMock()
        manager = FactoryManager(storage=storage)

        result = manager.run_company_analysis(
            url="https://example.com",
            org_id="org-1",
            user_id="user-1",
            scan_id="scan-1",
        )
        assert result["exceptions"] == ["test error"]

"""Tests for SQS Worker Lambda entry point."""

from unittest.mock import MagicMock, patch

import src.handlers.worker_handler_entry as module
from src.handlers.worker_handler_entry import handle_worker_event


class TestHandleWorkerEvent:
    @patch("src.handlers.worker_handler_entry._get_storage")
    @patch("src.handlers.worker_handler_entry.SQSHandler")
    def test_routes_to_sqs_handler(self, mock_handler_cls, mock_storage):
        mock_storage.return_value = MagicMock()
        mock_handler_instance = MagicMock()
        mock_handler_instance.handle.return_value = {"batchItemFailures": []}
        mock_handler_cls.return_value = mock_handler_instance

        event = {"Records": [{"eventSource": "aws:sqs", "body": "{}"}]}
        result = handle_worker_event(event, None)

        assert "batchItemFailures" in result
        mock_handler_instance.handle.assert_called_once_with(event)

    @patch("src.handlers.worker_handler_entry._get_storage")
    @patch("src.handlers.worker_handler_entry.SQSHandler")
    def test_returns_batch_failures(self, mock_handler_cls, mock_storage):
        mock_storage.return_value = MagicMock()
        mock_handler_cls.return_value.handle.return_value = {
            "batchItemFailures": [{"itemIdentifier": "msg-1"}]
        }

        event = {"Records": [{"eventSource": "aws:sqs", "body": "{}"}]}
        result = handle_worker_event(event, None)

        assert len(result["batchItemFailures"]) == 1
        assert result["batchItemFailures"][0]["itemIdentifier"] == "msg-1"


class TestStepFunctionsInvocation:
    @patch("src.handlers.factory_manager.FactoryManager")
    @patch("src.handlers.worker_handler_entry._get_storage")
    def test_step_functions_event_processes_company(self, mock_storage, mock_fm_cls):
        mock_storage_instance = MagicMock()
        mock_storage.return_value = mock_storage_instance
        mock_fm = MagicMock()
        mock_fm_cls.return_value = mock_fm

        event = {
            "source": "step_functions",
            "url": "https://acme.com",
            "company_name": "Acme",
            "org_id": "org-1",
            "user_id": "user-1",
            "scan_id": "scan-1",
            "request_id": "req-1",
        }

        result = handle_worker_event(event, None)

        assert result["status"] == "processed"
        mock_fm.run_company_analysis.assert_called_once()
        # Identity-at-start write happened
        company_repo = mock_storage_instance.create_company_repository.return_value
        company_repo.update.assert_called_once()
        identity = company_repo.update.call_args[0][1]
        assert identity["id"] == "req-1"
        assert identity["company_name"] == "Acme"

    @patch("src.handlers.factory_manager.FactoryManager")
    @patch("src.handlers.worker_handler_entry._get_storage")
    def test_step_functions_domain_error_returns_failed(self, mock_storage, mock_fm_cls):
        mock_storage.return_value = MagicMock()
        mock_fm_cls.return_value.run_company_analysis.side_effect = ValueError("bad url")

        event = {
            "source": "step_functions",
            "url": "https://bad.com",
            "company_name": "Bad",
            "org_id": "org-1",
            "user_id": "user-1",
            "scan_id": "scan-1",
            "request_id": "req-1",
        }

        result = handle_worker_event(event, None)

        assert result["status"] == "failed"
        assert "bad url" in result["error"]

    @patch("src.handlers.factory_manager.FactoryManager")
    @patch("src.handlers.worker_handler_entry._get_storage")
    def test_step_functions_programming_error_propagates(self, mock_storage, mock_fm_cls):
        mock_storage.return_value = MagicMock()
        mock_fm_cls.return_value.run_company_analysis.side_effect = AttributeError("bug")

        event = {
            "source": "step_functions",
            "url": "https://buggy.com",
            "company_name": "Buggy",
            "org_id": "org-1",
            "user_id": "user-1",
            "scan_id": "scan-1",
            "request_id": "req-1",
        }

        import pytest

        with pytest.raises(AttributeError, match="bug"):
            handle_worker_event(event, None)

    @patch("src.handlers.worker_handler_entry._get_storage")
    @patch("src.handlers.worker_handler_entry.SQSHandler")
    def test_sqs_event_still_works(self, mock_handler_cls, mock_storage):
        """SQS events are NOT affected by the Step Functions path."""
        mock_storage.return_value = MagicMock()
        mock_handler_cls.return_value.handle.return_value = {"batchItemFailures": []}

        event = {"Records": [{"eventSource": "aws:sqs", "body": "{}"}]}
        result = handle_worker_event(event, None)

        assert "batchItemFailures" in result
        mock_handler_cls.return_value.handle.assert_called_once()


class TestGetStorageSingleton:
    def setup_method(self):
        module._storage = None

    def teardown_method(self):
        module._storage = None

    @patch("src.handlers.worker_handler_entry.DynamoDBStorageProvider")
    def test_creates_singleton(self, mock_provider_cls):
        mock_instance = MagicMock()
        mock_provider_cls.return_value = mock_instance

        from src.handlers.worker_handler_entry import _get_storage

        first = _get_storage()
        second = _get_storage()

        assert first is second
        mock_provider_cls.assert_called_once()

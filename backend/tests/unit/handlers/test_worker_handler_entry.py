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

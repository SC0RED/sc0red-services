"""Tests for API Gateway Lambda entry point."""

from unittest.mock import MagicMock, patch

import pytest

import src.handlers.api_handler_entry as module
from src.handlers.api_handler_entry import handle_api_event


class TestHandleApiEvent:
    @patch("src.handlers.api_handler_entry._get_storage")
    @patch("src.handlers.api_handler_entry.APIGatewayHandler")
    def test_routes_to_api_gateway_handler(self, mock_handler_cls, mock_storage):
        mock_storage.return_value = MagicMock()
        mock_handler_instance = MagicMock()
        mock_handler_instance.handle.return_value = {"statusCode": 200, "body": "{}"}
        mock_handler_cls.return_value = mock_handler_instance

        event = {"httpMethod": "GET", "path": "/api/analyses"}
        result = handle_api_event(event, None)

        assert result["statusCode"] == 200
        mock_handler_instance.handle.assert_called_once_with(event)

    @patch("src.handlers.api_handler_entry._get_storage")
    @patch("src.handlers.api_handler_entry.APIGatewayHandler")
    def test_unhandled_error_propagates(self, mock_handler_cls, mock_storage):
        mock_storage.return_value = MagicMock()
        mock_handler_cls.return_value.handle.side_effect = RuntimeError("Unexpected failure")

        event = {"httpMethod": "GET", "path": "/api/health"}
        with pytest.raises(RuntimeError, match="Unexpected failure"):
            handle_api_event(event, None)


class TestGetStorageSingleton:
    def setup_method(self):
        module._storage = None

    def teardown_method(self):
        module._storage = None

    @patch("src.handlers.api_handler_entry.DynamoDBStorageProvider")
    def test_creates_singleton(self, mock_provider_cls):
        mock_instance = MagicMock()
        mock_provider_cls.return_value = mock_instance

        from src.handlers.api_handler_entry import _get_storage

        first = _get_storage()
        second = _get_storage()

        assert first is second
        mock_provider_cls.assert_called_once()

    @patch("src.handlers.api_handler_entry.DynamoDBStorageProvider")
    def test_storage_init_failure_propagates(self, mock_provider_cls):
        mock_provider_cls.side_effect = RuntimeError("no table")

        from src.handlers.api_handler_entry import _get_storage

        with pytest.raises(RuntimeError, match="no table"):
            _get_storage()

"""Tests for Lambda handler routing."""

import json
from unittest.mock import MagicMock, patch

from src.handlers.handler import _detect_event_type, _is_api_gateway_event, _is_sqs_event


class TestEventDetection:
    def test_is_api_gateway_event_with_http_method(self):
        event = {"httpMethod": "GET", "path": "/api/analyses"}
        assert _is_api_gateway_event(event) is True

    def test_is_api_gateway_event_with_request_context(self):
        event = {"requestContext": {"stage": "prod"}}
        assert _is_api_gateway_event(event) is True

    def test_is_api_gateway_event_false(self):
        event = {"Records": [{"eventSource": "aws:sqs"}]}
        assert _is_api_gateway_event(event) is False

    def test_is_sqs_event(self):
        event = {"Records": [{"eventSource": "aws:sqs", "body": "{}"}]}
        assert _is_sqs_event(event) is True

    def test_is_sqs_event_empty_records(self):
        event = {"Records": []}
        assert _is_sqs_event(event) is False

    def test_is_sqs_event_wrong_source(self):
        event = {"Records": [{"eventSource": "aws:s3"}]}
        assert _is_sqs_event(event) is False


class TestDetectEventType:
    def test_api_gateway_type(self):
        event = {"httpMethod": "POST", "path": "/api/scan/start"}
        result = _detect_event_type(event)
        assert "API Gateway" in result
        assert "POST" in result

    def test_sqs_type(self):
        event = {"Records": [{"eventSource": "aws:sqs"}, {"eventSource": "aws:sqs"}]}
        result = _detect_event_type(event)
        assert "SQS" in result
        assert "2 records" in result

    def test_unknown_type(self):
        event = {"something": "else"}
        assert _detect_event_type(event) == "Unknown"


class TestHandlerRouting:
    @patch("src.handlers.handler._get_storage")
    @patch("src.handlers.handler.APIGatewayHandler")
    def test_routes_to_api_gateway(self, mock_handler_cls, mock_storage):
        from src.handlers.handler import handler

        mock_storage.return_value = MagicMock()
        mock_handler_instance = MagicMock()
        mock_handler_instance.handle.return_value = {"statusCode": 200, "body": "{}"}
        mock_handler_cls.return_value = mock_handler_instance

        event = {"httpMethod": "GET", "path": "/api/analyses"}
        result = handler(event, None)

        assert result["statusCode"] == 200
        mock_handler_instance.handle.assert_called_once_with(event)

    @patch("src.handlers.handler._get_storage")
    @patch("src.handlers.handler.SQSHandler")
    def test_routes_to_sqs(self, mock_handler_cls, mock_storage):
        from src.handlers.handler import handler

        mock_storage.return_value = MagicMock()
        mock_handler_instance = MagicMock()
        mock_handler_instance.handle.return_value = {"batchItemFailures": []}
        mock_handler_cls.return_value = mock_handler_instance

        event = {"Records": [{"eventSource": "aws:sqs", "body": "{}"}]}
        result = handler(event, None)

        assert "batchItemFailures" in result

    @patch("src.handlers.handler._get_storage")
    def test_unknown_event_returns_400(self, mock_storage):
        from src.handlers.handler import handler

        mock_storage.return_value = MagicMock()

        event = {"unknown": "event"}
        result = handler(event, None)

        assert result["statusCode"] == 400
        body = json.loads(result["body"])
        assert "error" in body

    @patch("src.handlers.handler._get_storage")
    @patch("src.handlers.handler.APIGatewayHandler")
    def test_critical_error_returns_500(self, mock_handler_cls, mock_storage):
        from src.handlers.handler import handler

        mock_storage.return_value = MagicMock()
        mock_handler_cls.return_value.handle.side_effect = RuntimeError("Critical failure")

        event = {"httpMethod": "GET", "path": "/api/analyses"}
        result = handler(event, None)

        assert result["statusCode"] == 500
        body = json.loads(result["body"])
        assert "Critical failure" in body["error"]

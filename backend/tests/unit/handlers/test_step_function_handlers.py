"""Tests for Step Function batch coordinator handlers."""

import os
from unittest.mock import MagicMock, patch

import pytest

from src.handlers.step_function_handlers import (
    handle_check_wave,
    handle_mark_complete,
    handle_send_wave,
)


@pytest.fixture(autouse=True)
def _set_worker_function_name():
    with patch.dict(os.environ, {"WORKER_FUNCTION_NAME": "janus-worker-test"}):
        import src.handlers.step_function_handlers as mod
        mod._WORKER_FUNCTION_NAME = "janus-worker-test"
        yield
        mod._WORKER_FUNCTION_NAME = ""


class TestSendWaveMissingEnv:
    def test_raises_when_worker_function_name_missing(self):
        import src.handlers.step_function_handlers as mod

        original = mod._WORKER_FUNCTION_NAME
        mod._WORKER_FUNCTION_NAME = ""
        try:
            with pytest.raises(RuntimeError, match="WORKER_FUNCTION_NAME not set"):
                handle_send_wave({"companies": [], "wave_size": 1, "scan_id": "", "org_id": "", "user_id": ""}, None)
        finally:
            mod._WORKER_FUNCTION_NAME = original


class TestHandleSendWave:
    @patch("src.handlers.step_function_handlers.boto3")
    def test_dispatches_wave_and_returns_remaining(self, mock_boto3):
        mock_lambda = MagicMock()
        mock_boto3.client.return_value = mock_lambda

        event = {
            "companies": [
                {"name": "Co1", "url": "https://co1.com", "analysis_id": "a-1"},
                {"name": "Co2", "url": "https://co2.com", "analysis_id": "a-2"},
                {"name": "Co3", "url": "https://co3.com", "analysis_id": "a-3"},
            ],
            "wave_size": 2,
            "scan_id": "scan-1",
            "org_id": "org-1",
            "user_id": "user-1",
        }

        result = handle_send_wave(event, None)

        # Wave of 2 dispatched
        assert mock_lambda.invoke.call_count == 2
        assert result["wave_company_ids"] == ["a-1", "a-2"]
        assert result["remaining_count"] == 1
        assert len(result["remaining_companies"]) == 1
        assert result["remaining_companies"][0]["analysis_id"] == "a-3"
        # Passthrough fields
        assert result["scan_id"] == "scan-1"
        assert result["wave_size"] == 2

    @patch("src.handlers.step_function_handlers.boto3")
    def test_last_wave_has_zero_remaining(self, mock_boto3):
        mock_boto3.client.return_value = MagicMock()

        event = {
            "companies": [
                {"name": "Co1", "url": "https://co1.com", "analysis_id": "a-1"},
            ],
            "wave_size": 4,
            "scan_id": "scan-1",
            "org_id": "org-1",
            "user_id": "user-1",
        }

        result = handle_send_wave(event, None)

        assert result["remaining_count"] == 0
        assert result["remaining_companies"] == []
        assert result["wave_company_ids"] == ["a-1"]

    @patch("src.handlers.step_function_handlers.boto3")
    def test_invokes_worker_with_correct_payload(self, mock_boto3):
        mock_lambda = MagicMock()
        mock_boto3.client.return_value = mock_lambda

        event = {
            "companies": [
                {"name": "Acme", "url": "https://acme.com", "analysis_id": "a-1"},
            ],
            "wave_size": 1,
            "scan_id": "scan-1",
            "org_id": "org-1",
            "user_id": "user-1",
        }

        handle_send_wave(event, None)

        call_kwargs = mock_lambda.invoke.call_args[1]
        assert call_kwargs["InvocationType"] == "Event"
        import json

        payload = json.loads(call_kwargs["Payload"])
        assert payload["source"] == "step_functions"
        assert payload["url"] == "https://acme.com"
        assert payload["company_name"] == "Acme"
        assert payload["request_id"] == "a-1"
        assert payload["scan_id"] == "scan-1"


class TestHandleCheckWave:
    @patch("src.handlers.step_function_handlers.DynamoDBStorageProvider")
    def test_wave_done_when_all_resolved(self, mock_storage_cls):
        mock_repo = MagicMock()
        mock_repo.get_by_ids.return_value = [
            {"analyzed_at": "2026-01-01"},
            {"error": "failed"},
        ]
        mock_storage_cls.return_value.create_company_repository.return_value = mock_repo

        event = {
            "wave_company_ids": ["a-1", "a-2"],
            "scan_id": "scan-1",
            "remaining_companies": [],
            "remaining_count": 0,
        }

        result = handle_check_wave(event, None)

        assert result["wave_done"] is True

    @patch("src.handlers.step_function_handlers.DynamoDBStorageProvider")
    def test_wave_not_done_when_some_pending(self, mock_storage_cls):
        mock_repo = MagicMock()
        mock_repo.get_by_ids.return_value = [
            {"analyzed_at": "2026-01-01"},
            {},  # no analyzed_at, no error
        ]
        mock_storage_cls.return_value.create_company_repository.return_value = mock_repo

        event = {
            "wave_company_ids": ["a-1", "a-2"],
            "scan_id": "scan-1",
            "remaining_companies": [{"analysis_id": "a-3"}],
            "remaining_count": 1,
        }

        result = handle_check_wave(event, None)

        assert result["wave_done"] is False
        # Passthrough preserved
        assert result["remaining_count"] == 1


class TestHandleMarkComplete:
    @patch("src.handlers.step_function_handlers.notify_progress")
    @patch("src.handlers.step_function_handlers.DynamoDBStorageProvider")
    def test_updates_scan_and_notifies(self, mock_storage_cls, mock_notify):
        mock_scan_repo = MagicMock()
        mock_storage_cls.return_value.create_scan_repository.return_value = mock_scan_repo

        result = handle_mark_complete({"scan_id": "scan-1"}, None)

        mock_scan_repo.update.assert_called_once_with(
            "scan-1", {"status": "complete", "progress": 100}
        )
        mock_notify.assert_called_once_with(
            scan_id="scan-1",
            progress=100,
            label="Analysis complete!",
            status="complete",
        )
        assert result["status"] == "complete"

"""Tests for SQSHandler."""

import json
import pytest
from unittest.mock import MagicMock

from src.handlers.sqs_handler import SQSHandler

_BASE_MESSAGE = {
    "url": "https://example.com",
    "org_id": "org-1",
    "user_id": "user-1",
    "scan_id": "scan-1",
    "company_name": "Test Co",
    "request_id": "analysis-id-1",
}


class TestSQSHandler:
    def _make_handler(self):
        storage = MagicMock()
        handler = SQSHandler(storage=storage)
        handler._factory_manager = MagicMock()
        return handler, storage

    def _make_scan_repo(self, storage, scan_record: dict, resolved_companies: int = 0):
        """Set up scan_repo and company_repo mocks for completion-check logic."""
        scan_repo = MagicMock()
        scan_repo.get_by_id.return_value = scan_record
        linked = [{"company_id": f"co-{i}"} for i in range(resolved_companies)]
        scan_repo.get_scan_companies.return_value = linked
        storage.create_scan_repository.return_value = scan_repo

        company_repo = MagicMock()
        company_repo.get_by_id.return_value = {"overall_risk_score": 7.5}
        storage.create_company_repository.return_value = company_repo

        return scan_repo, company_repo

    def test_handle_empty_records(self):
        handler, _ = self._make_handler()
        result = handler.handle({"Records": []})
        assert result == {"batchItemFailures": []}

    def test_handle_single_message(self):
        handler, storage = self._make_handler()
        self._make_scan_repo(storage, {"progress": 30, "total_companies": 1}, resolved_companies=1)

        result = handler.handle(
            {
                "Records": [
                    {
                        "messageId": "msg-1",
                        "body": json.dumps(_BASE_MESSAGE),
                    }
                ],
            }
        )
        assert result == {"batchItemFailures": []}
        handler._factory_manager.run_company_analysis.assert_called_once()

    def test_handle_multiple_messages(self):
        handler, storage = self._make_handler()
        self._make_scan_repo(storage, {"progress": 50, "total_companies": 2}, resolved_companies=2)

        result = handler.handle(
            {
                "Records": [
                    {
                        "messageId": "msg-1",
                        "body": json.dumps(
                            {**_BASE_MESSAGE, "request_id": "id-1", "url": "https://a.com"}
                        ),
                    },
                    {
                        "messageId": "msg-2",
                        "body": json.dumps(
                            {**_BASE_MESSAGE, "request_id": "id-2", "url": "https://b.com"}
                        ),
                    },
                ],
            }
        )
        assert result == {"batchItemFailures": []}
        assert handler._factory_manager.run_company_analysis.call_count == 2

    def test_handle_message_processing_error_reports_failure(self):
        handler, _storage = self._make_handler()
        handler._factory_manager.run_company_analysis.side_effect = RuntimeError("fail")

        result = handler.handle(
            {
                "Records": [
                    {
                        "messageId": "msg-fail",
                        "body": json.dumps(_BASE_MESSAGE),
                    }
                ],
            }
        )
        assert result == {"batchItemFailures": [{"itemIdentifier": "msg-fail"}]}

    def test_process_message_marks_scan_complete_when_all_resolved(self):
        handler, storage = self._make_handler()
        self._make_scan_repo(
            storage,
            {"progress": 80, "total_companies": 2},
            resolved_companies=2,
        )

        handler._process_message({**_BASE_MESSAGE, "scan_id": "scan-1"})

        scan_repo = storage.create_scan_repository.return_value
        scan_repo.update.assert_called_once_with("scan-1", {"status": "complete", "progress": 100})

    def test_process_message_updates_progress_when_not_all_resolved(self):
        handler, storage = self._make_handler()
        self._make_scan_repo(
            storage,
            {"progress": 10, "total_companies": 4},
            resolved_companies=1,
        )

        handler._process_message({**_BASE_MESSAGE, "scan_id": "scan-1"})

        scan_repo = storage.create_scan_repository.return_value
        call_args = scan_repo.update.call_args[0]
        assert call_args[1].get("status") != "complete"
        assert call_args[1]["progress"] < 100

    def test_process_message_passes_request_id_to_factory(self):
        handler, storage = self._make_handler()
        self._make_scan_repo(storage, {"progress": 10, "total_companies": 1}, resolved_companies=1)

        handler._process_message({**_BASE_MESSAGE, "request_id": "specific-id"})

        handler._factory_manager.run_company_analysis.assert_called_once_with(
            url=_BASE_MESSAGE["url"],
            org_id=_BASE_MESSAGE["org_id"],
            user_id=_BASE_MESSAGE["user_id"],
            scan_id=_BASE_MESSAGE["scan_id"],
            company_name=_BASE_MESSAGE["company_name"],
            request_id="specific-id",
        )

    def test_process_message_raises_when_scan_not_found(self):
        handler, storage = self._make_handler()
        scan_repo = MagicMock()
        scan_repo.get_by_id.return_value = None
        storage.create_scan_repository.return_value = scan_repo

        with pytest.raises(RuntimeError, match="not found after analysis"):
            handler._process_message(_BASE_MESSAGE)

    def test_process_message_raises_on_missing_request_id(self):
        handler, _storage = self._make_handler()
        message = {k: v for k, v in _BASE_MESSAGE.items() if k != "request_id"}

        with pytest.raises(KeyError):
            handler._process_message(message)

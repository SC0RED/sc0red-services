"""Tests for SQSHandler."""

import json
from unittest.mock import MagicMock

from src.handlers.sqs_handler import SQSHandler


class TestSQSHandler:
    def _make_handler(self):
        storage = MagicMock()
        handler = SQSHandler(storage=storage)
        handler._factory_manager = MagicMock()
        return handler, storage

    def test_handle_empty_records(self):
        handler, _ = self._make_handler()
        result = handler.handle({"Records": []})
        assert result == {"batchItemFailures": []}

    def test_handle_single_message(self):
        handler, storage = self._make_handler()
        scan_repo = MagicMock()
        scan_repo.get_by_id.return_value = {"progress": 30}
        storage.create_scan_repository.return_value = scan_repo
        handler._factory_manager.run_company_analysis.return_value = {"request_id": "r-1"}

        result = handler.handle(
            {
                "Records": [
                    {
                        "body": json.dumps(
                            {
                                "url": "https://example.com",
                                "org_id": "org-1",
                                "user_id": "user-1",
                                "scan_id": "scan-1",
                                "company_name": "Test Co",
                            }
                        ),
                    }
                ],
            }
        )
        assert result == {"batchItemFailures": []}
        handler._factory_manager.run_company_analysis.assert_called_once()
        scan_repo.update.assert_called_once()

    def test_handle_multiple_messages(self):
        handler, storage = self._make_handler()
        scan_repo = MagicMock()
        scan_repo.get_by_id.return_value = {"progress": 50}
        storage.create_scan_repository.return_value = scan_repo
        handler._factory_manager.run_company_analysis.return_value = {}

        result = handler.handle(
            {
                "Records": [
                    {"body": json.dumps({"url": "https://a.com", "scan_id": "s-1"})},
                    {"body": json.dumps({"url": "https://b.com", "scan_id": "s-1"})},
                ],
            }
        )
        assert result == {"batchItemFailures": []}
        assert handler._factory_manager.run_company_analysis.call_count == 2

    def test_handle_message_processing_error(self):
        handler, _storage = self._make_handler()
        handler._factory_manager.run_company_analysis.side_effect = RuntimeError("fail")

        result = handler.handle(
            {
                "Records": [{"body": json.dumps({"url": "https://a.com", "scan_id": "s-1"})}],
            }
        )
        # Should not raise, returns empty failures
        assert result == {"batchItemFailures": []}

    def test_process_message_updates_scan_progress(self):
        handler, storage = self._make_handler()
        scan_repo = MagicMock()
        scan_repo.get_by_id.return_value = {"progress": 80}
        storage.create_scan_repository.return_value = scan_repo
        handler._factory_manager.run_company_analysis.return_value = {}

        handler._process_message(
            {
                "url": "https://example.com",
                "org_id": "org-1",
                "user_id": "user-1",
                "scan_id": "scan-1",
            }
        )
        # Progress capped at 95
        scan_repo.update.assert_called_once_with("scan-1", {"progress": 90})

    def test_process_message_caps_progress_at_95(self):
        handler, storage = self._make_handler()
        scan_repo = MagicMock()
        scan_repo.get_by_id.return_value = {"progress": 93}
        storage.create_scan_repository.return_value = scan_repo
        handler._factory_manager.run_company_analysis.return_value = {}

        handler._process_message(
            {
                "url": "https://example.com",
                "scan_id": "scan-1",
            }
        )
        scan_repo.update.assert_called_once_with("scan-1", {"progress": 95})

    def test_process_message_scan_not_found(self):
        handler, storage = self._make_handler()
        scan_repo = MagicMock()
        scan_repo.get_by_id.return_value = None
        storage.create_scan_repository.return_value = scan_repo
        handler._factory_manager.run_company_analysis.return_value = {}

        # Should not raise even if scan not found
        handler._process_message({"url": "https://example.com", "scan_id": "s-1"})
        scan_repo.update.assert_not_called()

"""Tests for SQSHandler."""

import json
import pytest
from unittest.mock import MagicMock, call

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

    def test_pipeline_error_records_failure_and_does_not_retry(self):
        """Pipeline errors are recorded on the company and scan — not retried via SQS."""
        handler, storage = self._make_handler()
        handler._factory_manager.run_company_analysis.side_effect = RuntimeError("AI provider boom")
        self._make_scan_repo(storage, {"progress": 10, "total_companies": 1}, resolved_companies=0)
        # After recording the error, the company_repo.get_by_id returns a record with error
        company_repo = storage.create_company_repository.return_value
        company_repo.get_by_id.return_value = {"error": "AI provider boom"}

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
        # No batch item failures — message is consumed, not retried
        assert result == {"batchItemFailures": []}

        # Error was patched onto the company record (not a full overwrite)
        company_repo.update.assert_called_once_with(
            "analysis-id-1", {"id": "analysis-id-1", "error": "AI provider boom"}
        )

    def test_pipeline_error_marks_single_scan_complete_with_error(self):
        """A single-company scan that fails should still be marked complete."""
        handler, storage = self._make_handler()
        handler._factory_manager.run_company_analysis.side_effect = RuntimeError("timeout")
        scan_repo, company_repo = self._make_scan_repo(
            storage, {"progress": 10, "total_companies": 1}, resolved_companies=1
        )
        # After failure, company has error field
        company_repo.get_by_id.return_value = {"error": "timeout"}

        handler._process_message(_BASE_MESSAGE)

        company_repo.update.assert_called_once_with(
            "analysis-id-1", {"id": "analysis-id-1", "error": "timeout"}
        )
        scan_repo.update.assert_called_once_with("scan-1", {"status": "complete", "progress": 100, "completed_count": 1})

    def test_json_parse_error_reports_batch_failure(self):
        """Malformed JSON in the SQS body is a transient issue — report for retry."""
        handler, _ = self._make_handler()

        result = handler.handle(
            {
                "Records": [
                    {
                        "messageId": "msg-bad-json",
                        "body": "not valid json",
                    }
                ],
            }
        )
        assert result == {"batchItemFailures": [{"itemIdentifier": "msg-bad-json"}]}

    def test_process_message_marks_scan_complete_when_all_resolved(self):
        handler, storage = self._make_handler()
        self._make_scan_repo(
            storage,
            {"progress": 80, "total_companies": 2},
            resolved_companies=2,
        )

        handler._process_message({**_BASE_MESSAGE, "scan_id": "scan-1"})

        scan_repo = storage.create_scan_repository.return_value
        scan_repo.update.assert_called_once_with("scan-1", {"status": "complete", "progress": 100, "completed_count": 2})

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

    def test_record_failure_scan_not_found_propagates_to_batch_failure(self):
        """If _record_failure can't find the scan, the error propagates and SQS retries."""
        handler, storage = self._make_handler()
        handler._factory_manager.run_company_analysis.side_effect = RuntimeError("AI error")

        company_repo = MagicMock()
        storage.create_company_repository.return_value = company_repo

        scan_repo = MagicMock()
        scan_repo.get_by_id.return_value = None
        storage.create_scan_repository.return_value = scan_repo

        result = handler.handle(
            {
                "Records": [
                    {
                        "messageId": "msg-orphan",
                        "body": json.dumps(_BASE_MESSAGE),
                    }
                ],
            }
        )
        # Infrastructure failure → SQS retries
        assert result == {"batchItemFailures": [{"itemIdentifier": "msg-orphan"}]}

    def test_process_message_raises_on_missing_request_id(self):
        handler, _storage = self._make_handler()
        message = {k: v for k, v in _BASE_MESSAGE.items() if k != "request_id"}

        with pytest.raises(KeyError):
            handler._process_message(message)


class TestSQSHandlerReanalysis:
    def _make_handler(self):
        storage = MagicMock()
        handler = SQSHandler(storage=storage)
        handler._factory_manager = MagicMock()
        return handler, storage

    def test_reanalysis_fetches_documents_and_runs_pipeline(self):
        handler, storage = self._make_handler()
        assessment_repo = MagicMock()
        assessment_repo.find_by_company.return_value = [{"id": "assess-1"}]
        assessment_repo.get_combined_document_text.return_value = "Document content here"
        storage.create_assessment_repository.return_value = assessment_repo

        # Mock scan repo for _update_scan_progress
        scan_repo = MagicMock()
        scan_repo.get_by_id.return_value = {"total_companies": 1}
        scan_repo.get_scan_companies.return_value = [{"company_id": "a-1"}]
        storage.create_scan_repository.return_value = scan_repo
        company_repo = MagicMock()
        company_repo.get_by_id.return_value = {"overall_risk_score": 5.0}
        storage.create_company_repository.return_value = company_repo

        message = {
            "reanalyze": True,
            "analysis_id": "a-1",
            "url": "https://test.com",
            "org_id": "org-1",
            "user_id": "user-1",
            "scan_id": "scan-1",
            "request_id": "a-1",
        }
        handler._process_message(message)

        handler._factory_manager.run_company_analysis.assert_called_once_with(
            url="https://test.com",
            org_id="org-1",
            user_id="user-1",
            scan_id="scan-1",
            request_id="a-1",
            document_text="Document content here",
        )

    def test_reanalysis_without_documents(self):
        handler, storage = self._make_handler()
        assessment_repo = MagicMock()
        assessment_repo.find_by_company.return_value = [{"id": "assess-1"}]
        assessment_repo.get_combined_document_text.return_value = ""
        storage.create_assessment_repository.return_value = assessment_repo

        # Mock scan repo for _update_scan_progress
        scan_repo = MagicMock()
        scan_repo.get_by_id.return_value = {"total_companies": 1}
        scan_repo.get_scan_companies.return_value = [{"company_id": "a-1"}]
        storage.create_scan_repository.return_value = scan_repo
        company_repo = MagicMock()
        company_repo.get_by_id.return_value = {"overall_risk_score": 5.0}
        storage.create_company_repository.return_value = company_repo

        message = {
            "reanalyze": True,
            "analysis_id": "a-1",
            "url": "https://test.com",
            "org_id": "org-1",
            "user_id": "user-1",
            "scan_id": "scan-1",
            "request_id": "a-1",
        }
        handler._process_message(message)

        handler._factory_manager.run_company_analysis.assert_called_once_with(
            url="https://test.com",
            org_id="org-1",
            user_id="user-1",
            scan_id="scan-1",
            request_id="a-1",
            document_text=None,
        )

    def test_reanalysis_pipeline_failure_records_error_and_preserves_old_results(self):
        handler, storage = self._make_handler()
        handler._factory_manager.run_company_analysis.side_effect = RuntimeError("boom")
        assessment_repo = MagicMock()
        assessment_repo.find_by_company.return_value = [{"id": "assess-1"}]
        assessment_repo.get_combined_document_text.return_value = ""
        storage.create_assessment_repository.return_value = assessment_repo
        company_repo = MagicMock()
        storage.create_company_repository.return_value = company_repo

        # Set up scan repo for _update_scan_progress call on failure
        scan_repo = MagicMock()
        scan_repo.get_by_id.return_value = {"total_companies": 1}
        scan_repo.get_scan_companies.return_value = [{"company_id": "a-1"}]
        storage.create_scan_repository.return_value = scan_repo
        company_repo.get_by_id.return_value = {"error": "boom"}

        message = {
            "reanalyze": True,
            "analysis_id": "a-1",
            "url": "https://test.com",
            "org_id": "org-1",
            "user_id": "user-1",
            "scan_id": "scan-1",
            "request_id": "a-1",
        }
        handler._process_message(message)

        company_repo.update.assert_called_once_with("a-1", {"error": "boom"})
        # Old results should NOT be deleted when pipeline fails
        assessment_repo.delete_analysis_results.assert_not_called()
        # Scan progress should still be updated so scan doesn't get stuck
        scan_repo.update.assert_called_once()

    def test_reanalysis_deletes_old_results_via_repository(self):
        handler, storage = self._make_handler()
        assessment_repo = MagicMock()
        assessment_repo.find_by_company.return_value = [{"id": "assess-1"}]
        assessment_repo.get_combined_document_text.return_value = "doc text"
        storage.create_assessment_repository.return_value = assessment_repo

        # Mock scan repo for _update_scan_progress
        scan_repo = MagicMock()
        scan_repo.get_by_id.return_value = {"total_companies": 1}
        scan_repo.get_scan_companies.return_value = [{"company_id": "a-1"}]
        storage.create_scan_repository.return_value = scan_repo
        company_repo = MagicMock()
        company_repo.get_by_id.return_value = {"overall_risk_score": 5.0}
        storage.create_company_repository.return_value = company_repo

        message = {
            "reanalyze": True,
            "analysis_id": "a-1",
            "url": "https://test.com",
            "org_id": "org-1",
            "user_id": "user-1",
            "scan_id": "scan-1",
            "request_id": "a-1",
        }
        handler._process_message(message)

        assessment_repo.delete_analysis_results.assert_called_once_with("assess-1")

    def test_reanalysis_with_empty_scan_id_skips_progress_update(self):
        """Standalone re-analyses (no portfolio scan) should not call _update_scan_progress."""
        handler, storage = self._make_handler()
        assessment_repo = MagicMock()
        assessment_repo.find_by_company.return_value = [{"id": "assess-1"}]
        assessment_repo.get_combined_document_text.return_value = "doc text"
        storage.create_assessment_repository.return_value = assessment_repo

        message = {
            "reanalyze": True,
            "analysis_id": "a-1",
            "url": "https://test.com",
            "org_id": "org-1",
            "user_id": "user-1",
            "scan_id": "",
            "request_id": "a-1",
        }
        handler._process_message(message)

        # scan_id is "" → _update_scan_progress should NOT be called
        storage.create_scan_repository.assert_not_called()

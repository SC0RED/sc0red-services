"""Tests for SQSHandler."""

import json
from unittest.mock import MagicMock, call, patch

import pytest

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

        # Identity was written first, then error was patched on failure
        company_repo.update.assert_any_call(
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

        company_repo.update.assert_any_call(
            "analysis-id-1", {"id": "analysis-id-1", "error": "timeout"}
        )
        scan_repo.update.assert_called_once_with(
            "scan-1", {"status": "complete", "progress": 100, "completed_count": 1}
        )

    def test_identity_written_before_pipeline_survives_failure(self):
        """Company name + URL are persisted before the pipeline runs, so failures
        still have identity for display and retry."""
        handler, storage = self._make_handler()
        handler._factory_manager.run_company_analysis.side_effect = RuntimeError("scrape blocked")
        self._make_scan_repo(storage, {"progress": 10, "total_companies": 1}, resolved_companies=0)
        company_repo = storage.create_company_repository.return_value
        company_repo.get_by_id.return_value = {"error": "scrape blocked"}

        handler.handle(
            {
                "Records": [
                    {
                        "messageId": "msg-1",
                        "body": json.dumps(_BASE_MESSAGE),
                    }
                ],
            }
        )

        # First update: identity (before pipeline)
        identity_call = company_repo.update.call_args_list[0]
        assert identity_call[0][0] == "analysis-id-1"
        identity_data = identity_call[0][1]
        assert identity_data["company_name"] == "Test Co"
        assert identity_data["company_url"] == "https://example.com"
        assert identity_data["scan_id"] == "scan-1"
        assert identity_data["org_id"] == "org-1"

        # Second update: error (after pipeline failure)
        error_call = company_repo.update.call_args_list[1]
        assert error_call[0][1] == {"id": "analysis-id-1", "error": "scrape blocked"}

    def test_programming_error_caught_and_recorded(self):
        """Programming errors (AttributeError, etc.) are caught, recorded as failures,
        and the message is consumed — no SQS retry, no starving other messages."""
        handler, storage = self._make_handler()
        handler._factory_manager.run_company_analysis.side_effect = AttributeError(
            "'NoneType' object has no attribute 'get'"
        )
        self._make_scan_repo(storage, {"progress": 10, "total_companies": 2}, resolved_companies=0)
        company_repo = storage.create_company_repository.return_value
        company_repo.get_by_id.return_value = {"error": "'NoneType' object has no attribute 'get'"}

        result = handler.handle(
            {
                "Records": [
                    {
                        "messageId": "msg-attr-err",
                        "body": json.dumps(_BASE_MESSAGE),
                    }
                ],
            }
        )

        # Message consumed — no batch item failures (no SQS retry)
        assert result == {"batchItemFailures": []}
        # Error recorded on the company record
        company_repo.update.assert_any_call(
            "analysis-id-1",
            {"id": "analysis-id-1", "error": "'NoneType' object has no attribute 'get'"},
        )

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
        scan_repo.update.assert_called_once_with(
            "scan-1", {"status": "complete", "progress": 100, "completed_count": 2}
        )

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

    @patch("src.handlers.sqs_handler.notify_progress")
    def test_per_company_complete_event_sent_on_success(self, mock_notify):
        """Successful company analysis sends a per-company status=complete AppSync event."""
        handler, storage = self._make_handler()
        self._make_scan_repo(storage, {"progress": 80, "total_companies": 2}, resolved_companies=2)

        handler._process_message({**_BASE_MESSAGE, "scan_id": "scan-1"})

        # First call: per-company complete (with company_id)
        mock_notify.assert_any_call(
            scan_id="scan-1",
            progress=100,
            label="Analysis complete",
            status="complete",
            company_id="analysis-id-1",
        )
        # Second call: scan-level complete (all companies resolved)
        mock_notify.assert_any_call(
            scan_id="scan-1",
            progress=100,
            label="Analysis complete!",
            status="complete",
        )

    @patch("src.handlers.sqs_handler.notify_progress")
    def test_per_company_complete_event_when_scan_not_finished(self, mock_notify):
        """Per-company complete fires even when the overall scan isn't done yet."""
        handler, storage = self._make_handler()
        self._make_scan_repo(storage, {"progress": 10, "total_companies": 4}, resolved_companies=1)

        handler._process_message({**_BASE_MESSAGE, "scan_id": "scan-1"})

        # Per-company complete event still fires
        mock_notify.assert_called_once_with(
            scan_id="scan-1",
            progress=100,
            label="Analysis complete",
            status="complete",
            company_id="analysis-id-1",
        )

    @patch("src.handlers.sqs_handler.notify_progress")
    def test_per_company_failed_event_sent_on_failure(self, mock_notify):
        """Failed company analysis sends a per-company status=failed AppSync event."""
        handler, storage = self._make_handler()
        handler._factory_manager.run_company_analysis.side_effect = RuntimeError("scrape blocked")
        self._make_scan_repo(storage, {"progress": 10, "total_companies": 2}, resolved_companies=0)
        company_repo = storage.create_company_repository.return_value
        company_repo.get_by_id.return_value = {"error": "scrape blocked"}

        handler._process_message({**_BASE_MESSAGE, "scan_id": "scan-1"})

        mock_notify.assert_called_once_with(
            scan_id="scan-1",
            progress=0,
            label="Analysis failed: scrape blocked",
            status="failed",
            company_id="analysis-id-1",
        )


class TestSQSHandlerPortfolioDiscovery:
    """Portfolio discovery dispatch path — runs pipeline in the worker."""

    _PORTFOLIO_MESSAGE = {
        "type": "portfolio_discovery",
        "url": "https://perotjain.com",
        "org_id": "org-1",
        "user_id": "user-1",
        "scan_id": "scan-p1",
    }

    def _make_handler(self):
        storage = MagicMock()
        handler = SQSHandler(storage=storage)
        handler._factory_manager = MagicMock()
        return handler, storage

    def test_dispatch_routes_to_portfolio_discovery(self):
        handler, storage = self._make_handler()
        scan_repo = MagicMock()
        storage.create_scan_repository.return_value = scan_repo
        handler._factory_manager.run_portfolio_discovery.return_value = {
            "details": {"portfolio_companies": []},
        }

        handler._process_message(dict(self._PORTFOLIO_MESSAGE))

        handler._factory_manager.run_portfolio_discovery.assert_called_once_with(
            url="https://perotjain.com",
            org_id="org-1",
            user_id="user-1",
            scan_id="scan-p1",
        )
        handler._factory_manager.run_company_analysis.assert_not_called()

    def test_success_writes_awaiting_confirmation_and_companies(self):
        handler, storage = self._make_handler()
        scan_repo = MagicMock()
        storage.create_scan_repository.return_value = scan_repo
        companies = [
            {"name": "Co1", "url": "https://co1.com"},
            {"name": "Co2", "url": "https://co2.com"},
        ]
        handler._factory_manager.run_portfolio_discovery.return_value = {
            "details": {"portfolio_companies": companies},
        }

        handler._process_message(dict(self._PORTFOLIO_MESSAGE))

        # First update marks discovering at entry; second writes final results.
        assert scan_repo.update.call_args_list == [
            call("scan-p1", {"status": "discovering", "progress": 5}),
            call(
                "scan-p1",
                {
                    "status": "awaiting_confirmation",
                    "progress": 20,
                    "portfolio_companies": companies,
                },
            ),
        ]

    def test_success_persists_discovery_verdict_with_final_count(self):
        handler, storage = self._make_handler()
        scan_repo = MagicMock()
        storage.create_scan_repository.return_value = scan_repo
        companies = [{"name": "Co1", "url": "https://co1.com"}]
        handler._factory_manager.run_portfolio_discovery.return_value = {
            "details": {
                "portfolio_companies": companies,
                # discovery-time count (3) differs from the final list (1)
                "discovery_verdict": {
                    "method": "web_search",
                    "count": 3,
                    "completeness": "web_search_subset",
                    "available_actions": ["search_deeper", "upload_list"],
                },
            },
        }

        handler._process_message(dict(self._PORTFOLIO_MESSAGE))

        final_update = scan_repo.update.call_args_list[-1][0][1]
        verdict = final_update["discovery_verdict"]
        assert verdict["completeness"] == "web_search_subset"
        assert verdict["count"] == 1  # overridden to the final persisted count

    def test_domain_error_marks_scan_failed_and_does_not_retry(self):
        handler, storage = self._make_handler()
        scan_repo = MagicMock()
        storage.create_scan_repository.return_value = scan_repo
        handler._factory_manager.run_portfolio_discovery.side_effect = RuntimeError(
            "scrape blocked"
        )

        result = handler.handle(
            {
                "Records": [
                    {
                        "messageId": "msg-pd-1",
                        "body": json.dumps(self._PORTFOLIO_MESSAGE),
                    }
                ],
            }
        )

        # Message consumed, not retried — domain errors are user-visible, not bugs.
        assert result == {"batchItemFailures": []}
        # Final state is failed with error surfaced on the scan record.
        scan_repo.update.assert_any_call("scan-p1", {"status": "failed", "error": "scrape blocked"})

    def test_value_error_is_caught_as_domain_error(self):
        handler, storage = self._make_handler()
        scan_repo = MagicMock()
        storage.create_scan_repository.return_value = scan_repo
        handler._factory_manager.run_portfolio_discovery.side_effect = ValueError("No URL provided")

        handler._process_message(dict(self._PORTFOLIO_MESSAGE))

        scan_repo.update.assert_any_call(
            "scan-p1", {"status": "failed", "error": "No URL provided"}
        )

    def test_programming_error_propagates_for_sqs_retry(self):
        """Bugs (KeyError/AttributeError/TypeError) must propagate so SQS retries
        and the stack trace lands in CloudWatch."""
        handler, storage = self._make_handler()
        scan_repo = MagicMock()
        storage.create_scan_repository.return_value = scan_repo
        handler._factory_manager.run_portfolio_discovery.side_effect = KeyError("boom")

        result = handler.handle(
            {
                "Records": [
                    {
                        "messageId": "msg-pd-bug",
                        "body": json.dumps(self._PORTFOLIO_MESSAGE),
                    }
                ],
            }
        )

        assert result == {"batchItemFailures": [{"itemIdentifier": "msg-pd-bug"}]}
        failed_updates = [
            c for c in scan_repo.update.call_args_list if c[0][1].get("status") == "failed"
        ]
        assert failed_updates == []

    @patch("src.handlers.sqs_handler.notify_progress")
    def test_notifies_progress_on_entry_and_success(self, mock_notify):
        handler, storage = self._make_handler()
        scan_repo = MagicMock()
        storage.create_scan_repository.return_value = scan_repo
        handler._factory_manager.run_portfolio_discovery.return_value = {
            "details": {"portfolio_companies": []},
        }

        handler._process_message(dict(self._PORTFOLIO_MESSAGE))

        statuses = [kwargs["status"] for _, kwargs in mock_notify.call_args_list]
        assert statuses == ["discovering", "awaiting_confirmation"]

    @patch("src.handlers.sqs_handler.notify_progress")
    def test_notifies_progress_on_failure(self, mock_notify):
        handler, storage = self._make_handler()
        scan_repo = MagicMock()
        storage.create_scan_repository.return_value = scan_repo
        handler._factory_manager.run_portfolio_discovery.side_effect = RuntimeError("fail")

        handler._process_message(dict(self._PORTFOLIO_MESSAGE))

        statuses = [kwargs["status"] for _, kwargs in mock_notify.call_args_list]
        assert "failed" in statuses


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

    def test_reanalysis_programming_error_caught_and_recorded(self):
        """Programming errors during re-analysis are caught and recorded, not retried."""
        handler, storage = self._make_handler()
        handler._factory_manager.run_company_analysis.side_effect = AttributeError("broken")
        assessment_repo = MagicMock()
        assessment_repo.find_by_company.return_value = [{"id": "assess-1"}]
        assessment_repo.get_combined_document_text.return_value = ""
        storage.create_assessment_repository.return_value = assessment_repo
        company_repo = MagicMock()
        storage.create_company_repository.return_value = company_repo

        scan_repo = MagicMock()
        scan_repo.get_by_id.return_value = {"total_companies": 1}
        scan_repo.get_scan_companies.return_value = [{"company_id": "a-1"}]
        storage.create_scan_repository.return_value = scan_repo
        company_repo.get_by_id.return_value = {"error": "broken"}

        message = {
            "reanalyze": True,
            "analysis_id": "a-1",
            "url": "https://test.com",
            "org_id": "org-1",
            "user_id": "user-1",
            "scan_id": "scan-1",
            "request_id": "a-1",
        }

        # Should NOT raise — message consumed, not retried
        handler._process_message(message)

        company_repo.update.assert_called_once_with("a-1", {"error": "broken"})


class TestSQSHandlerPortfolioDeepen:
    """Customer-triggered deepen dispatch path."""

    _DEEPEN_MESSAGE = {
        "type": "portfolio_deepen",
        "url": "https://perotjain.com",
        "org_id": "org-1",
        "user_id": "user-1",
        "scan_id": "scan-d1",
    }

    def _make_handler(self):
        storage = MagicMock()
        handler = SQSHandler(storage=storage)
        handler._factory_manager = MagicMock()
        return handler, storage

    def test_dispatch_seeds_from_scan_and_runs_deepen(self):
        handler, storage = self._make_handler()
        scan_repo = MagicMock()
        seed = [{"name": "Known", "url": "https://known.com"}]
        scan_repo.get_by_id.return_value = {"portfolio_companies": seed}
        storage.create_scan_repository.return_value = scan_repo
        handler._factory_manager.run_portfolio_deepen.return_value = {
            "details": {"portfolio_companies": seed},
        }

        handler._process_message(dict(self._DEEPEN_MESSAGE))

        handler._factory_manager.run_portfolio_deepen.assert_called_once_with(
            url="https://perotjain.com",
            org_id="org-1",
            user_id="user-1",
            scan_id="scan-d1",
            seed_companies=seed,
        )
        handler._factory_manager.run_portfolio_discovery.assert_not_called()

    def test_success_writes_augmented_list(self):
        handler, storage = self._make_handler()
        scan_repo = MagicMock()
        seed = [{"name": "Known", "url": "https://known.com"}]
        scan_repo.get_by_id.return_value = {"portfolio_companies": seed}
        storage.create_scan_repository.return_value = scan_repo
        augmented = seed + [{"name": "Fresh", "url": "https://fresh.com"}]
        handler._factory_manager.run_portfolio_deepen.return_value = {
            "details": {"portfolio_companies": augmented},
        }

        handler._process_message(dict(self._DEEPEN_MESSAGE))

        final_update = scan_repo.update.call_args_list[-1]
        assert final_update == call(
            "scan-d1",
            {
                "status": "awaiting_confirmation",
                "progress": 20,
                "portfolio_companies": augmented,
            },
        )

    def test_domain_error_restores_prior_list(self):
        handler, storage = self._make_handler()
        scan_repo = MagicMock()
        seed = [{"name": "Known", "url": "https://known.com"}]
        scan_repo.get_by_id.return_value = {"portfolio_companies": seed}
        storage.create_scan_repository.return_value = scan_repo
        handler._factory_manager.run_portfolio_deepen.side_effect = RuntimeError("search down")

        # Must NOT raise — deepen failure is a no-op that keeps the prior list.
        handler._process_message(dict(self._DEEPEN_MESSAGE))

        final_update = scan_repo.update.call_args_list[-1]
        assert final_update == call(
            "scan-d1",
            {"status": "awaiting_confirmation", "progress": 20, "portfolio_companies": seed},
        )

    def test_engine_error_restores_prior_list(self):
        from signalfield_core.exceptions.base import EngineError

        handler, storage = self._make_handler()
        scan_repo = MagicMock()
        seed = [{"name": "Known", "url": "https://known.com"}]
        scan_repo.get_by_id.return_value = {"portfolio_companies": seed}
        storage.create_scan_repository.return_value = scan_repo
        handler._factory_manager.run_portfolio_deepen.side_effect = EngineError("provider down")

        # Provider failure must NOT strand the scan — restore the prior list.
        handler._process_message(dict(self._DEEPEN_MESSAGE))

        final_update = scan_repo.update.call_args_list[-1]
        assert final_update == call(
            "scan-d1",
            {"status": "awaiting_confirmation", "progress": 20, "portfolio_companies": seed},
        )

    def test_missing_scan_is_skipped(self):
        handler, storage = self._make_handler()
        scan_repo = MagicMock()
        scan_repo.get_by_id.return_value = None
        storage.create_scan_repository.return_value = scan_repo

        handler._process_message(dict(self._DEEPEN_MESSAGE))

        scan_repo.update.assert_not_called()
        handler._factory_manager.run_portfolio_deepen.assert_not_called()

    def test_programming_error_propagates(self):
        handler, storage = self._make_handler()
        scan_repo = MagicMock()
        scan_repo.get_by_id.return_value = {"portfolio_companies": []}
        storage.create_scan_repository.return_value = scan_repo
        handler._factory_manager.run_portfolio_deepen.side_effect = KeyError("boom")

        with pytest.raises(KeyError):
            handler._process_message(dict(self._DEEPEN_MESSAGE))

"""Tests for JanusRequestExecutor."""

import contextlib
from unittest.mock import MagicMock, patch

import pytest

from src.pipeline.request_executor import JanusRequestExecutor


def _make_mock_step(name):
    """Create a mock step with proper step_name() method."""
    step = MagicMock()
    step.step_name.return_value = name
    return step


class TestRequestExecutor:
    def test_create(self):
        executor = JanusRequestExecutor(
            tenant_id="tenant-1",
            request_id="req-1",
            pipeline=[],
        )
        assert executor.details == {}
        assert executor.step_timings == {}
        assert executor.exceptions == []

    def test_mark_question_complete(self):
        executor = JanusRequestExecutor("t", "r", [])
        executor.mark_question_complete("extract_profile")
        assert executor.is_question_complete("extract_profile") is True
        assert executor.is_question_complete("assess_risk") is False

    def test_mark_multiple_questions(self):
        executor = JanusRequestExecutor("t", "r", [])
        executor.mark_multiple_questions_complete(["step_1", "step_2", "step_3"])
        assert executor.is_question_complete("step_1") is True
        assert executor.is_question_complete("step_2") is True
        assert executor.is_question_complete("step_3") is True

    def test_add_details(self):
        executor = JanusRequestExecutor("t", "r", [])
        executor.add_details({"key_a": "value_a"})
        executor.add_details({"key_b": "value_b"})
        assert executor.details["key_a"] == "value_a"
        assert executor.details["key_b"] == "value_b"

    def test_execute_all_runs_steps(self):
        step1 = _make_mock_step("Step1")
        step2 = _make_mock_step("Step2")

        executor = JanusRequestExecutor("t", "r", [step1, step2])
        executor.execute_all()

        step1.execute.assert_called_once()
        step2.execute.assert_called_once()

    def test_execute_all_records_timings(self):
        step = _make_mock_step("MockStep")

        executor = JanusRequestExecutor("t", "r", [step])
        executor.execute_all()

        assert "MockStep" in executor.step_timings

    def test_execute_all_catches_exception(self):
        step = _make_mock_step("FailStep")
        step.execute.side_effect = ValueError("test error")

        executor = JanusRequestExecutor("t", "r", [step])

        with contextlib.suppress(ValueError):
            executor.execute_all()

        assert len(executor.exceptions) == 1

    def test_has_step(self):
        step = _make_mock_step("ExtractProfile")

        executor = JanusRequestExecutor("t", "r", [step])
        assert executor.has_step("ExtractProfile") is True
        assert executor.has_step("NonExistent") is False

    def test_add_step_after(self):
        step1 = _make_mock_step("Step1")
        step2 = _make_mock_step("Step2")
        new_step = _make_mock_step("NewStep")

        executor = JanusRequestExecutor("t", "r", [step1, step2])
        executor.add_step_after("Step1", new_step)

        assert executor.has_step("NewStep") is True

    def test_add_step_before(self):
        step1 = _make_mock_step("Step1")
        step2 = _make_mock_step("Step2")
        new_step = _make_mock_step("NewStep")

        executor = JanusRequestExecutor("t", "r", [step1, step2])
        executor.add_step_before("Step2", new_step)

        assert executor.has_step("NewStep") is True

    def test_add_step_after_not_found_raises(self):
        step1 = _make_mock_step("Step1")
        new_step = _make_mock_step("NewStep")

        executor = JanusRequestExecutor("t", "r", [step1])
        with pytest.raises(ValueError, match="not found"):
            executor.add_step_after("Nonexistent", new_step)

    def test_add_step_before_not_found_raises(self):
        step1 = _make_mock_step("Step1")
        new_step = _make_mock_step("NewStep")

        executor = JanusRequestExecutor("t", "r", [step1])
        with pytest.raises(ValueError, match="not found"):
            executor.add_step_before("Nonexistent", new_step)

    def test_add_step_after_with_entity_accessor(self):
        step1 = _make_mock_step("Step1")
        new_step = _make_mock_step("NewStep")

        executor = JanusRequestExecutor("t", "r", [step1])
        mock_accessor = MagicMock()
        executor._entity_accessor = mock_accessor

        executor.add_step_after("Step1", new_step)
        assert new_step.entity_accessor == mock_accessor

    def test_add_step_before_with_entity_accessor(self):
        step1 = _make_mock_step("Step1")
        new_step = _make_mock_step("NewStep")

        executor = JanusRequestExecutor("t", "r", [step1])
        mock_accessor = MagicMock()
        executor._entity_accessor = mock_accessor

        executor.add_step_before("Step1", new_step)
        assert new_step.entity_accessor == mock_accessor

    def test_propagate_entity_accessor(self):
        step1 = _make_mock_step("Step1")
        step2 = _make_mock_step("Step2")

        executor = JanusRequestExecutor("t", "r", [step1, step2])
        mock_accessor = MagicMock()
        executor.propagate_entity_accessor(mock_accessor)

        assert step1.entity_accessor == mock_accessor
        assert step2.entity_accessor == mock_accessor


class TestRequestExecutorAppSyncIntegration:
    @patch("src.pipeline.appsync_notifier.notify_progress")
    def test_mark_question_complete_calls_notify_progress(self, mock_notify: MagicMock) -> None:
        """When mark_question_complete is called with a known key, notify_progress fires."""
        company_repo = MagicMock()
        executor = JanusRequestExecutor(
            tenant_id="tenant-1",
            request_id="company-1",
            pipeline=[],
            company_repo=company_repo,
            scan_id="scan-1",
        )

        executor.mark_question_complete("extract_profile")

        mock_notify.assert_called_once_with(
            scan_id="scan-1",
            progress=30,
            label="Extracting company profile...",
            company_id="company-1",
        )

    @patch("src.pipeline.appsync_notifier.notify_progress")
    def test_mark_question_complete_skips_notify_for_unknown_key(self, mock_notify: MagicMock) -> None:
        """Unknown question keys should not trigger notify_progress."""
        executor = JanusRequestExecutor(
            tenant_id="tenant-1",
            request_id="company-1",
            pipeline=[],
            scan_id="scan-1",
        )

        executor.mark_question_complete("unknown_step")

        mock_notify.assert_not_called()

    @patch("src.pipeline.appsync_notifier.notify_progress")
    def test_mark_question_complete_skips_notify_without_scan_id(self, mock_notify: MagicMock) -> None:
        """When scan_id is empty, notify_progress should not be called."""
        company_repo = MagicMock()
        executor = JanusRequestExecutor(
            tenant_id="tenant-1",
            request_id="company-1",
            pipeline=[],
            company_repo=company_repo,
            scan_id="",
        )

        executor.mark_question_complete("extract_profile")

        mock_notify.assert_not_called()
        # But company repo should still be updated
        company_repo.update.assert_called_once()

    @patch("src.pipeline.appsync_notifier.notify_progress")
    def test_mark_question_complete_fires_for_generate_strategy_map(
        self, mock_notify: MagicMock
    ) -> None:
        """Regression: ``generate_strategy_map`` MUST be in _PROGRESS_MAP.

        Before this fix the strategy-map step's ``mark_question_complete`` call
        resolved to a missing _PROGRESS_MAP entry and silently fired no
        progress notification — the frontend never saw the step transition.
        """
        company_repo = MagicMock()
        executor = JanusRequestExecutor(
            tenant_id="tenant-1",
            request_id="company-1",
            pipeline=[],
            company_repo=company_repo,
            scan_id="scan-1",
        )

        executor.mark_question_complete("generate_strategy_map")

        mock_notify.assert_called_once()
        call_kwargs = mock_notify.call_args.kwargs
        assert call_kwargs["scan_id"] == "scan-1"
        assert call_kwargs["company_id"] == "company-1"
        # Position constraint: strategy-map must sit between
        # compute_value_chain (90) and persist_results (95).
        assert 90 < call_kwargs["progress"] < 95
        assert "strategy map" in call_kwargs["label"].lower()

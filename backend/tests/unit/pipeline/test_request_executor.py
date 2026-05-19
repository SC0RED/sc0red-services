"""Tests for Sc0redServicesRequestExecutor."""

import contextlib
import logging
from unittest.mock import MagicMock, patch

import pytest

from src.pipeline.request_executor import Sc0redServicesRequestExecutor, _format_timing_value


def _make_mock_step(name):
    """Create a mock step with proper step_name() method."""
    step = MagicMock()
    step.step_name.return_value = name
    return step


class TestRequestExecutor:
    def test_create(self):
        executor = Sc0redServicesRequestExecutor(
            tenant_id="tenant-1",
            request_id="req-1",
            pipeline=[],
        )
        assert executor.details == {}
        assert executor.step_timings == {}
        assert executor.exceptions == []

    def test_mark_question_complete(self):
        executor = Sc0redServicesRequestExecutor("t", "r", [])
        executor.mark_question_complete("extract_profile")
        assert executor.is_question_complete("extract_profile") is True
        assert executor.is_question_complete("assess_risk") is False

    def test_mark_multiple_questions(self):
        executor = Sc0redServicesRequestExecutor("t", "r", [])
        executor.mark_multiple_questions_complete(["step_1", "step_2", "step_3"])
        assert executor.is_question_complete("step_1") is True
        assert executor.is_question_complete("step_2") is True
        assert executor.is_question_complete("step_3") is True

    def test_add_details(self):
        executor = Sc0redServicesRequestExecutor("t", "r", [])
        executor.add_details({"key_a": "value_a"})
        executor.add_details({"key_b": "value_b"})
        assert executor.details["key_a"] == "value_a"
        assert executor.details["key_b"] == "value_b"

    def test_execute_all_runs_steps(self):
        step1 = _make_mock_step("Step1")
        step2 = _make_mock_step("Step2")

        executor = Sc0redServicesRequestExecutor("t", "r", [step1, step2])
        executor.execute_all()

        step1.execute.assert_called_once()
        step2.execute.assert_called_once()

    def test_execute_all_records_timings(self):
        step = _make_mock_step("MockStep")

        executor = Sc0redServicesRequestExecutor("t", "r", [step])
        executor.execute_all()

        assert "MockStep" in executor.step_timings

    def test_execute_all_catches_exception(self):
        step = _make_mock_step("FailStep")
        step.execute.side_effect = ValueError("test error")

        executor = Sc0redServicesRequestExecutor("t", "r", [step])

        with contextlib.suppress(ValueError):
            executor.execute_all()

        assert len(executor.exceptions) == 1

    def test_has_step(self):
        step = _make_mock_step("ExtractProfile")

        executor = Sc0redServicesRequestExecutor("t", "r", [step])
        assert executor.has_step("ExtractProfile") is True
        assert executor.has_step("NonExistent") is False

    def test_add_step_after(self):
        step1 = _make_mock_step("Step1")
        step2 = _make_mock_step("Step2")
        new_step = _make_mock_step("NewStep")

        executor = Sc0redServicesRequestExecutor("t", "r", [step1, step2])
        executor.add_step_after("Step1", new_step)

        assert executor.has_step("NewStep") is True

    def test_add_step_before(self):
        step1 = _make_mock_step("Step1")
        step2 = _make_mock_step("Step2")
        new_step = _make_mock_step("NewStep")

        executor = Sc0redServicesRequestExecutor("t", "r", [step1, step2])
        executor.add_step_before("Step2", new_step)

        assert executor.has_step("NewStep") is True

    def test_add_step_after_not_found_raises(self):
        step1 = _make_mock_step("Step1")
        new_step = _make_mock_step("NewStep")

        executor = Sc0redServicesRequestExecutor("t", "r", [step1])
        with pytest.raises(ValueError, match="not found"):
            executor.add_step_after("Nonexistent", new_step)

    def test_add_step_before_not_found_raises(self):
        step1 = _make_mock_step("Step1")
        new_step = _make_mock_step("NewStep")

        executor = Sc0redServicesRequestExecutor("t", "r", [step1])
        with pytest.raises(ValueError, match="not found"):
            executor.add_step_before("Nonexistent", new_step)

    def test_add_step_after_with_entity_accessor(self):
        step1 = _make_mock_step("Step1")
        new_step = _make_mock_step("NewStep")

        executor = Sc0redServicesRequestExecutor("t", "r", [step1])
        mock_accessor = MagicMock()
        executor._entity_accessor = mock_accessor

        executor.add_step_after("Step1", new_step)
        assert new_step.entity_accessor == mock_accessor

    def test_add_step_before_with_entity_accessor(self):
        step1 = _make_mock_step("Step1")
        new_step = _make_mock_step("NewStep")

        executor = Sc0redServicesRequestExecutor("t", "r", [step1])
        mock_accessor = MagicMock()
        executor._entity_accessor = mock_accessor

        executor.add_step_before("Step1", new_step)
        assert new_step.entity_accessor == mock_accessor

    def test_propagate_entity_accessor(self):
        step1 = _make_mock_step("Step1")
        step2 = _make_mock_step("Step2")

        executor = Sc0redServicesRequestExecutor("t", "r", [step1, step2])
        mock_accessor = MagicMock()
        executor.propagate_entity_accessor(mock_accessor)

        assert step1.entity_accessor == mock_accessor
        assert step2.entity_accessor == mock_accessor


class TestRequestExecutorAppSyncIntegration:
    @patch("src.pipeline.appsync_notifier.notify_progress")
    def test_mark_question_complete_calls_notify_progress(self, mock_notify: MagicMock) -> None:
        """When mark_question_complete is called with a known key, notify_progress fires."""
        company_repo = MagicMock()
        executor = Sc0redServicesRequestExecutor(
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
        executor = Sc0redServicesRequestExecutor(
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
        executor = Sc0redServicesRequestExecutor(
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
    def test_mark_question_complete_emits_progress_for_strategy_map(
        self, mock_notify: MagicMock
    ) -> None:
        """Per ``redesign-strategy-map`` Phase 4, ``generate_strategy_map``
        is in the auto-pipeline again (the on-demand SQS worker was
        deleted in the same change). The ``_PROGRESS_MAP`` entry is
        therefore required — without it, the scan-progress bar would
        jump from ~75 % (``compute_value_chain``) to ~95 %
        (``persist_results``) with no label change for the 35 s
        strategy-map step.
        """
        company_repo = MagicMock()
        executor = Sc0redServicesRequestExecutor(
            tenant_id="tenant-1",
            request_id="company-1",
            pipeline=[],
            company_repo=company_repo,
            scan_id="scan-1",
        )

        executor.mark_question_complete("generate_strategy_map")

        mock_notify.assert_called_once()
        company_repo.update.assert_called_once()
        assert executor.is_question_complete("generate_strategy_map") is True


class TestFormatTimingValue:
    """Per-key formatting of ``{step}.timings`` entries in the summary log.

    Strategy-map token telemetry (shipped 2026-05-15) writes
    ``tokens_in_*`` / ``tokens_out_*`` / ``cached_tokens_*`` keys
    alongside the existing ``ai_call_*`` elapsed entries inside the
    same ``timings`` dict. Without per-key rendering, every value gets
    the elapsed-seconds format and integer token counts misleadingly
    print as ``12786.00s`` instead of ``12786 tokens``.
    """

    def test_elapsed_keys_render_as_seconds(self):
        assert _format_timing_value("ai_call_vision_text", 1.2345) == "1.23s"
        assert _format_timing_value("total", 28.4) == "28.40s"
        assert _format_timing_value("ai_call_arrow_O.P_I1.1", 0.0) == "0.00s"

    def test_token_keys_render_as_token_counts(self):
        assert _format_timing_value("tokens_in_ai_call_vision_text", 12786) == "12786 tokens"
        assert _format_timing_value("tokens_out_ai_call_vision_text", 74) == "74 tokens"
        assert _format_timing_value("cached_tokens_ai_call_priorities", 15360) == "15360 tokens"

    def test_zero_cached_tokens_renders_cleanly(self):
        """Cache-miss path: ``cached_tokens_* = 0`` reads as ``0 tokens``."""
        assert _format_timing_value("cached_tokens_ai_call_vp_primary", 0) == "0 tokens"

    def test_token_values_coerced_to_int(self):
        """If a float somehow lands in a token-keyed slot, render without decimals."""
        assert _format_timing_value("tokens_in_call_a", 12786.0) == "12786 tokens"

    def test_summary_log_renders_mixed_keys_correctly(self, caplog):
        """End-to-end: the summary log line contains both ``s`` and ``tokens`` formats."""
        executor = Sc0redServicesRequestExecutor("t", "r", [])
        executor.add_details(
            {
                "GenerateStrategyMap.timings": {
                    "ai_call_vision_text": 1.23,
                    "tokens_in_ai_call_vision_text": 12786,
                    "tokens_out_ai_call_vision_text": 74,
                    "cached_tokens_ai_call_vision_text": 0,
                    "total": 1.23,
                },
            }
        )
        with caplog.at_level(logging.INFO):
            executor.execute_all()
        summary = " ".join(record.getMessage() for record in caplog.records)
        assert "ai_call_vision_text: 1.23s" in summary
        assert "tokens_in_ai_call_vision_text: 12786 tokens" in summary
        assert "tokens_out_ai_call_vision_text: 74 tokens" in summary
        assert "cached_tokens_ai_call_vision_text: 0 tokens" in summary

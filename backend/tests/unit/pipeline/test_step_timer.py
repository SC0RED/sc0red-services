"""Tests for StepTimer performance instrumentation utility."""

import time

import pytest

from src.pipeline.pipeline_steps.ai_call import TokenCounts
from src.pipeline.step_timer import StepTimer


class TestStepTimer:
    def test_measure_records_elapsed_time(self):
        timer = StepTimer("TestStep")
        with timer.measure("operation"):
            time.sleep(0.01)

        details = timer.to_details()
        timings = details["TestStep.timings"]
        assert "operation" in timings
        assert timings["operation"] >= 0.01

    def test_record_stores_manual_timing(self):
        timer = StepTimer("TestStep")
        timer.record("ai_call", 42.5)

        details = timer.to_details()
        assert details["TestStep.timings"]["ai_call"] == 42.5

    def test_to_details_includes_total(self):
        timer = StepTimer("TestStep")
        with timer.measure("fast_op"):
            pass

        details = timer.to_details()
        assert "total" in details["TestStep.timings"]
        assert details["TestStep.timings"]["total"] >= 0

    def test_multiple_measurements(self):
        timer = StepTimer("Pipeline")
        with timer.measure("step_a"):
            time.sleep(0.01)
        with timer.measure("step_b"):
            time.sleep(0.01)
        timer.record("step_c", 1.5)

        timings = timer.to_details()["Pipeline.timings"]
        assert "step_a" in timings
        assert "step_b" in timings
        assert timings["step_c"] == 1.5
        assert timings["total"] >= timings["step_a"] + timings["step_b"]

    def test_details_key_format(self):
        timer = StepTimer("GenerateOpportunities")
        details = timer.to_details()
        assert "GenerateOpportunities.timings" in details

    def test_measure_records_timing_on_exception(self):
        timer = StepTimer("TestStep")
        with pytest.raises(ValueError, match="boom"):
            with timer.measure("failing_op"):
                raise ValueError("boom")

        timings = timer.to_details()["TestStep.timings"]
        assert "failing_op" in timings
        assert timings["failing_op"] >= 0


class TestStepTimerRecordTokens:
    """Per-call token-count recording (added 2026-05-15 for P1.6).

    Pair with ``timer.record(label, elapsed)`` at every strategy-map AI
    call site so each call's CloudWatch entry carries elapsed + three
    token-count keys.
    """

    def test_record_tokens_writes_three_keys(self):
        timer = StepTimer("GenerateStrategyMap")
        counts = TokenCounts(input_tokens=1450, output_tokens=220, cached_input_tokens=1320)
        timer.record_tokens("ai_call_vision_text", counts)

        timings = timer.to_details()["GenerateStrategyMap.timings"]
        assert timings["tokens_in_ai_call_vision_text"] == 1450
        assert timings["tokens_out_ai_call_vision_text"] == 220
        assert timings["cached_tokens_ai_call_vision_text"] == 1320

    def test_record_tokens_keys_are_ints_not_floats(self):
        """Token counts are emitted as ints; elapsed is the only float entry."""
        timer = StepTimer("Step")
        timer.record_tokens("call", TokenCounts(100, 50, 80))

        timings = timer.to_details()["Step.timings"]
        assert isinstance(timings["tokens_in_call"], int)
        assert isinstance(timings["tokens_out_call"], int)
        assert isinstance(timings["cached_tokens_call"], int)

    def test_record_and_record_tokens_share_label(self):
        """The same label keys all four entries — one ai_call_*, three tokens_*."""
        timer = StepTimer("Step")
        timer.record("ai_call_F1", 1.2)
        timer.record_tokens("ai_call_F1", TokenCounts(800, 120, 600))

        timings = timer.to_details()["Step.timings"]
        assert timings["ai_call_F1"] == 1.2
        assert timings["tokens_in_ai_call_F1"] == 800
        assert timings["tokens_out_ai_call_F1"] == 120
        assert timings["cached_tokens_ai_call_F1"] == 600

    def test_record_tokens_zero_cached_when_cache_missed(self):
        """``cached_input_tokens == 0`` records cleanly (cache miss / no cache surface)."""
        timer = StepTimer("Step")
        timer.record_tokens("ai_call_label", TokenCounts(1000, 200, 0))

        timings = timer.to_details()["Step.timings"]
        assert timings["cached_tokens_ai_call_label"] == 0
        assert timings["tokens_in_ai_call_label"] == 1000

    def test_multiple_calls_keep_separate_entries(self):
        timer = StepTimer("Step")
        timer.record_tokens("call_a", TokenCounts(100, 50, 80))
        timer.record_tokens("call_b", TokenCounts(200, 90, 150))

        timings = timer.to_details()["Step.timings"]
        assert timings["tokens_in_call_a"] == 100
        assert timings["tokens_in_call_b"] == 200
        assert timings["cached_tokens_call_a"] == 80
        assert timings["cached_tokens_call_b"] == 150

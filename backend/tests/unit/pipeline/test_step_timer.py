"""Tests for StepTimer performance instrumentation utility."""

import time

import pytest

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

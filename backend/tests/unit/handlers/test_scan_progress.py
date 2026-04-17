"""Tests for scan progress computation."""

from src.handlers.scan_handlers import _compute_scan_progress


class TestComputeScanProgress:
    def test_all_done_with_correct_total(self):
        analyses = [
            {"analyzedAt": "2026-01-01", "pipelineProgress": 100},
            {"analyzedAt": "2026-01-01", "pipelineProgress": 100},
        ]
        done, progress = _compute_scan_progress(analyses, 0, total_companies=2)
        assert done == 2
        assert progress == 100

    def test_partial_done_with_total_larger_than_analyses(self):
        """5 records exist and are done, but total_companies=6.
        The 6th company hasn't been picked up by the worker yet."""
        analyses = [{"analyzedAt": "2026-01-01"} for _ in range(5)]
        done, progress = _compute_scan_progress(analyses, 0, total_companies=6)
        assert done == 5
        assert progress == 83  # 500 // 6

    def test_no_analyses_returns_scan_progress(self):
        done, progress = _compute_scan_progress([], 50, total_companies=6)
        assert done == 0
        assert progress == 50

    def test_fallback_to_analyses_length_when_total_zero(self):
        """Standalone scans may have total_companies=0."""
        analyses = [{"analyzedAt": "2026-01-01", "pipelineProgress": 100}]
        done, progress = _compute_scan_progress(analyses, 0, total_companies=0)
        assert done == 1
        assert progress == 100

    def test_mixed_done_and_in_progress(self):
        analyses = [
            {"analyzedAt": "2026-01-01"},
            {"pipelineProgress": 50},
            {"pipelineProgress": 0},
        ]
        done, progress = _compute_scan_progress(analyses, 0, total_companies=5)
        # (100 + 50 + 0) // 5 = 30
        assert done == 1
        assert progress == 30

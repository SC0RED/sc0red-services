"""Tests for scan progress computation.

Analyses passed into ``compute_scan_progress`` always come from
``build_unified_analyses`` and carry an explicit ``state`` field; the
fixtures here mirror that shape.
"""

from src.utilities.scan_summary import compute_scan_progress, derive_progress_label


class TestComputeScanProgress:
    def test_all_done_with_correct_total(self):
        analyses = [
            {"state": "done", "analyzedAt": "2026-01-01", "pipelineProgress": 100},
            {"state": "done", "analyzedAt": "2026-01-01", "pipelineProgress": 100},
        ]
        done, progress = compute_scan_progress(analyses, 0, total_companies=2)
        assert done == 2
        assert progress == 100

    def test_partial_done_with_total_larger_than_analyses(self):
        """5 records exist and are done, but total_companies=6.

        The 6th company hasn't been picked up by the worker yet — under
        the new contract this would also be in ``analyses`` as a pending
        entry, but this test exercises the older shape where the unified
        builder hasn't yet padded the array.
        """
        analyses = [{"state": "done", "analyzedAt": "2026-01-01"} for _ in range(5)]
        done, progress = compute_scan_progress(analyses, 0, total_companies=6)
        assert done == 5
        assert progress == 83  # 500 // 6

    def test_no_analyses_returns_scan_progress(self):
        done, progress = compute_scan_progress([], 50, total_companies=6)
        assert done == 0
        assert progress == 50

    def test_fallback_to_analyses_length_when_total_zero(self):
        """Standalone scans may have total_companies=0."""
        analyses = [{"state": "done", "analyzedAt": "2026-01-01", "pipelineProgress": 100}]
        done, progress = compute_scan_progress(analyses, 0, total_companies=0)
        assert done == 1
        assert progress == 100

    def test_mixed_done_and_in_progress(self):
        analyses = [
            {"state": "done", "analyzedAt": "2026-01-01"},
            {"state": "scanning", "pipelineProgress": 50},
            {"state": "pending", "pipelineProgress": 0},
        ]
        done, progress = compute_scan_progress(analyses, 0, total_companies=5)
        # (100 + 50 + 0) // 5 = 30
        assert done == 1
        assert progress == 30

    def test_failed_state_counts_as_terminal(self):
        """Failed entries are terminal — they contribute 100 to progress."""
        analyses = [
            {"state": "done", "analyzedAt": "2026-01-01"},
            {"state": "failed", "error": "boom"},
            {"state": "scanning", "pipelineProgress": 50},
        ]
        done, progress = compute_scan_progress(analyses, 0, total_companies=3)
        assert done == 2  # done + failed
        # (100 + 100 + 50) // 3 = 83
        assert progress == 83


class TestDeriveProgressLabel:
    def test_no_in_progress_returns_fallback(self):
        analyses = [
            {"state": "done", "pipelineLabel": "Done"},
            {"state": "pending", "pipelineLabel": ""},
        ]
        assert derive_progress_label(analyses, "Starting…") == "Starting…"

    def test_furthest_scanning_company_wins(self):
        analyses = [
            {"state": "scanning", "pipelineProgress": 30, "pipelineLabel": "Scraping"},
            {"state": "scanning", "pipelineProgress": 70, "pipelineLabel": "Value chain"},
        ]
        assert derive_progress_label(analyses, "fallback") == "Value chain"

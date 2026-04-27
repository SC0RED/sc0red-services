"""Tests for the unified ``analyses[]`` builder used by GET /scan/{id}.

Covers the spec scenarios in
``openspec/changes/portfolio-scan-stable-cards/specs/async-portfolio-scan/spec.md``
and the design's state-derivation precedence (failed > done > scanning >
pending).
"""

from __future__ import annotations

from src.utilities.scan_summary import build_unified_analyses


def _link(
    *,
    company_id: str,
    company_name: str,
    company_url: str | None = None,
    order_index: int | None = None,
) -> dict[str, object]:
    """Build a minimal scan_company link dict for tests."""
    item: dict[str, object] = {
        "company_id": company_id,
        "company_name": company_name,
    }
    if company_url is not None:
        item["company_url"] = company_url
    if order_index is not None:
        item["order_index"] = order_index
    return item


def _record(
    *,
    company_id: str,
    company_name: str = "",
    company_url: str = "",
    pipeline_progress: int = 0,
    pipeline_label: str = "",
    analyzed_at: str | None = None,
    error: str | None = None,
    overall_risk_score: float | None = None,
    risk_tier: str | None = None,
) -> dict[str, object]:
    """Build a minimal companies-table record dict for tests."""
    record: dict[str, object] = {
        "id": company_id,
        "company_name": company_name,
        "company_url": company_url,
        "pipeline_progress": pipeline_progress,
        "pipeline_label": pipeline_label,
    }
    if analyzed_at is not None:
        record["analyzed_at"] = analyzed_at
    if error is not None:
        record["error"] = error
    if overall_risk_score is not None:
        record["overall_risk_score"] = overall_risk_score
    if risk_tier is not None:
        record["risk_tier"] = risk_tier
    return record


class TestBuildUnifiedAnalyses:
    """Spec: GET /scan/{id} returns a unified analyses array of length total_companies."""

    def test_all_pending_immediately_after_confirm(self) -> None:
        """50 links, 0 records → 50 pending entries."""
        links = [
            _link(
                company_id=f"id-{i}",
                company_name=f"Co {i}",
                company_url=f"https://co{i}.example.com",
                order_index=i,
            )
            for i in range(50)
        ]

        result = build_unified_analyses(links, [])

        assert len(result) == 50
        assert all(entry["state"] == "pending" for entry in result)
        assert all(entry["companyUrl"].startswith("https://") for entry in result)
        assert all(entry["overallRiskScore"] is None for entry in result)

    def test_mixed_states_with_record_present(self) -> None:
        """5 done + 10 scanning + 8 record-but-progress=0 + 27 no-record-yet."""
        links = [_link(company_id=f"id-{i}", company_name=f"Co {i}", order_index=i) for i in range(50)]

        records = []
        # 5 done
        for i in range(5):
            records.append(
                _record(
                    company_id=f"id-{i}",
                    analyzed_at="2026-04-25T10:00:00Z",
                    overall_risk_score=4.2,
                    risk_tier="moderate",
                )
            )
        # 10 scanning
        for i in range(5, 15):
            records.append(
                _record(
                    company_id=f"id-{i}",
                    pipeline_progress=50,
                    pipeline_label="Profiling risk...",
                )
            )
        # 8 record-but-progress=0 → still UI-pending
        for i in range(15, 23):
            records.append(_record(company_id=f"id-{i}", pipeline_progress=0))
        # ids 23..49 have no record at all → also UI-pending

        result = build_unified_analyses(links, records)

        states = [entry["state"] for entry in result]
        assert states.count("done") == 5
        assert states.count("scanning") == 10
        assert states.count("pending") == 35  # 8 + 27

    def test_failed_state_takes_precedence_over_progress(self) -> None:
        """A record with error set has state=failed even with analyzed_at."""
        link = _link(company_id="x", company_name="X", order_index=0)
        record = _record(
            company_id="x",
            error="boom",
            analyzed_at="2026-04-25T10:00:00Z",
            pipeline_progress=100,
        )

        result = build_unified_analyses([link], [record])

        assert result[0]["state"] == "failed"
        assert result[0]["error"] == "boom"

    def test_legacy_link_record_lacks_url_and_order_index(self) -> None:
        """Pre-deploy link records render without URL and sort by id."""
        links = [
            {"company_id": "id-b", "company_name": "B"},
            {"company_id": "id-a", "company_name": "A"},
        ]

        result = build_unified_analyses(links, [])

        # No order_index → sort falls back to id ascending
        assert [entry["id"] for entry in result] == ["id-a", "id-b"]
        assert all(entry["state"] == "pending" for entry in result)
        assert all(entry["companyUrl"] == "" for entry in result)
        assert all(entry["orderIndex"] is None for entry in result)

    def test_entries_sorted_by_order_index_ascending(self) -> None:
        """Submission-order is preserved regardless of input link order."""
        links = [
            _link(company_id="c", company_name="C", order_index=2),
            _link(company_id="a", company_name="A", order_index=0),
            _link(company_id="b", company_name="B", order_index=1),
        ]

        result = build_unified_analyses(links, [])

        assert [entry["id"] for entry in result] == ["a", "b", "c"]
        assert [entry["orderIndex"] for entry in result] == [0, 1, 2]

    def test_link_url_overrides_record_url(self) -> None:
        """The user-submitted URL on the link is authoritative over scraper-set URL."""
        link = _link(
            company_id="x",
            company_name="X",
            company_url="https://submitted.example.com",
            order_index=0,
        )
        record = _record(
            company_id="x",
            company_url="https://canonicalized.example.com",
            analyzed_at="2026-04-25T10:00:00Z",
        )

        result = build_unified_analyses([link], [record])

        assert result[0]["companyUrl"] == "https://submitted.example.com"

    def test_scanning_state_carries_pipeline_label(self) -> None:
        """Spec: each scanning entry exposes the pipeline label."""
        link = _link(company_id="x", company_name="X", order_index=0)
        record = _record(
            company_id="x",
            pipeline_progress=50,
            pipeline_label="Detailing opportunities...",
        )

        result = build_unified_analyses([link], [record])

        assert result[0]["state"] == "scanning"
        assert result[0]["pipelineLabel"] == "Detailing opportunities..."

    def test_mixed_legacy_and_new_links_sort_legacy_last(self) -> None:
        """Legacy links (no order_index) sort after new ones, by id within."""
        links = [
            _link(company_id="new-1", company_name="N1", order_index=1),
            {"company_id": "legacy-z", "company_name": "Lz"},
            _link(company_id="new-0", company_name="N0", order_index=0),
            {"company_id": "legacy-a", "company_name": "La"},
        ]

        result = build_unified_analyses(links, [])

        ids = [entry["id"] for entry in result]
        assert ids == ["new-0", "new-1", "legacy-a", "legacy-z"]

    def test_returns_one_entry_per_link_even_with_orphan_record(self) -> None:
        """A company record with no matching link is ignored (defensive)."""
        links = [_link(company_id="known", company_name="K", order_index=0)]
        records = [
            _record(company_id="known"),
            _record(company_id="orphan"),  # no matching link
        ]

        result = build_unified_analyses(links, records)

        assert len(result) == 1
        assert result[0]["id"] == "known"

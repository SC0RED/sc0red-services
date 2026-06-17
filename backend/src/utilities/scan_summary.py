"""Scan-summary helpers shared by GET /scan/{id} and the MCP ``get_scan`` tool.

``build_unified_analyses`` joins ``scan_company`` link records (always present
from confirm time) with ``companies`` records (created on first worker pickup),
producing one entry per link so the portfolio view shows *every* company card
from t=0, not just the ones already through SQS. Each entry carries an explicit
``state`` field — readers render off it instead of inferring lifecycle from
``overallRiskScore`` / ``analyzedAt`` / ``pipelineProgress`` null checks.

``compute_scan_progress`` / ``derive_progress_label`` are the canonical
live-progress computations over those entries. Workers update each company's
``pipeline_progress`` mid-run but NOT the scan record's ``progress`` (see
``request_executor._report_progress``), so any surface showing scan progress
MUST compute it here — both the HTTP handler and the MCP tool do, so they agree.
"""

from __future__ import annotations

from typing import Any


def compute_company_state(company: dict[str, Any]) -> str:
    """Return the lifecycle state of a company-record at this poll.

    States: ``"failed"`` > ``"done"`` > ``"scanning"`` > ``"pending"``.
    Order matters — a company with both ``error`` set and a stale
    ``analyzed_at`` is reported as failed, so the analyst sees an
    actionable signal rather than a misleading "done" card.
    """
    if company.get("error"):
        return "failed"
    if company.get("analyzed_at"):
        return "done"
    if company.get("pipeline_progress", 0) > 0:
        return "scanning"
    return "pending"


def build_company_summary(company: dict[str, Any]) -> dict[str, Any]:
    """Build a camelCase summary dict from a company DynamoDB record.

    Uses ``.get()`` because the record evolves through multiple pipeline
    phases:
        1. Identity write (``company_name``, ``company_url``, ``scan_id``,
           ``org_id``) at pipeline start.
        2. Progress updates (``pipeline_progress``, ``pipeline_label``)
           during execution.
        3. Full results (``risk_score``, ``analyzed_at``, etc.) after
           ``persist_results``.
    On failure, only phases 1-2 are present plus the ``error`` field.

    The ``orderIndex`` field is filled in by ``build_unified_analyses``
    from the corresponding ``scan_company`` link record; this function
    initializes it to ``None``.
    """
    return {
        "id": company.get("id", ""),
        "companyName": company.get("company_name", ""),
        "companyUrl": company.get("company_url", ""),
        "industry": company.get("industry", ""),
        "overallRiskScore": company.get("overall_risk_score"),
        "riskTier": company.get("risk_tier"),
        "error": company.get("error"),
        "analyzedAt": company.get("analyzed_at"),
        "pipelineProgress": company.get("pipeline_progress", 0),
        "pipelineLabel": company.get("pipeline_label", ""),
        "state": compute_company_state(company),
        "orderIndex": None,
    }


def _synthesize_pending_entry(link: dict[str, Any]) -> dict[str, Any]:
    """Build a pending analysis entry from a ``scan_company`` link record.

    Used for companies that have a link record (written at confirm time)
    but no ``companies`` record yet (worker hasn't picked them up).
    Legacy link records — written before the deploy that introduced the
    ``company_url`` and ``order_index`` fields — render with empty
    ``companyUrl`` and ``orderIndex=None``; the frontend's sort tolerates
    the latter.
    """
    return {
        "id": link.get("company_id", ""),
        "companyName": link.get("company_name", ""),
        "companyUrl": link.get("company_url", ""),
        "industry": "",
        "overallRiskScore": None,
        "riskTier": None,
        "error": None,
        "analyzedAt": None,
        "pipelineProgress": 0,
        "pipelineLabel": "",
        "state": "pending",
        "orderIndex": link.get("order_index"),
    }


def build_unified_analyses(
    scan_companies: list[dict[str, Any]],
    companies_batch: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge link records with company records into one entry per link.

    Always returns ``len(scan_companies)`` entries, sorted by
    ``order_index`` ascending. Legacy link records lacking
    ``order_index`` sort last (and among themselves by ``company_id``,
    matching the pre-change behavior). The link's ``company_url`` is
    treated as authoritative — it's exactly what the user submitted —
    and overrides any URL the scraper later set on the company record.
    """
    records_by_id = {c["id"]: c for c in companies_batch if c.get("id")}

    entries: list[dict[str, Any]] = []
    for link in scan_companies:
        company_id = link.get("company_id", "")
        record = records_by_id.get(company_id)
        if record is not None:
            entry = build_company_summary(record)
            entry["orderIndex"] = link.get("order_index")
            link_url = link.get("company_url")
            if link_url:
                entry["companyUrl"] = link_url
        else:
            entry = _synthesize_pending_entry(link)
        entries.append(entry)

    def _sort_key(entry: dict[str, Any]) -> tuple[int, int, str]:
        order_index = entry.get("orderIndex")
        if order_index is None:
            return (1, 0, str(entry.get("id", "")))
        return (0, int(order_index), "")

    entries.sort(key=_sort_key)
    return entries


def compute_scan_progress(
    analyses: list[dict[str, Any]],
    scan_progress: int,
    total_companies: int = 0,
) -> tuple[int, int]:
    """Return (done_count, computed_progress) from per-company pipeline progress.

    Live scan progress is derived from the per-company ``pipelineProgress`` —
    the workers update each company record as the pipeline advances but do NOT
    write the scan record's ``progress`` mid-run (see
    ``request_executor._report_progress``), so any reader showing scan progress
    MUST compute it here. Used by both GET /scan/{id} and the MCP ``get_scan``
    tool so they report identical progress.

    Uses ``total_companies`` (from the scan record, set at confirm time) as the
    denominator. Drives terminal-state detection off the explicit ``state``
    field set by ``build_unified_analyses`` rather than re-deriving from
    ``analyzedAt``/``error`` — the contract that ``state`` is authoritative
    means downstream logic should not duplicate the derivation.
    """
    if not analyses:
        return 0, scan_progress
    # Use the true total; fall back to len(analyses) for standalone scans
    # where total_companies may be 0 or absent.
    total = max(total_companies, len(analyses))
    done_count = sum(1 for a in analyses if a.get("state") in ("done", "failed"))
    company_progress_sum = sum(
        100 if a.get("state") in ("done", "failed") else a.get("pipelineProgress", 0)
        for a in analyses
    )
    return done_count, company_progress_sum // total


def derive_progress_label(  # noqa: NAMING001  derive is a verb; not in the checker's heuristic list
    analyses: list[dict[str, Any]],
    fallback_label: str,
) -> str:
    """Return the progress label from the most advanced in-progress company."""
    in_progress = [a for a in analyses if a.get("state") == "scanning"]
    if in_progress:
        furthest = max(in_progress, key=lambda a: a.get("pipelineProgress", 0))
        return str(furthest.get("pipelineLabel", fallback_label))
    return fallback_label

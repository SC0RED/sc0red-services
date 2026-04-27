"""Build the unified ``analyses[]`` array returned by GET /scan/{id}.

The portfolio view needs *every* company card visible from t=0, not just
the ones that have made it through SQS into the ``companies`` table.
This module joins ``scan_company`` link records (always present from
confirm time) with ``companies`` records (created on first worker
pickup), producing one entry per link.

Each entry carries an explicit ``state`` field — the frontend renders
directly off it instead of inferring lifecycle from
``overallRiskScore`` / ``analyzedAt`` / ``pipelineProgress`` null
checks.
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

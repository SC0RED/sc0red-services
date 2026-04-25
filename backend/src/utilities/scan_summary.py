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

from src.handlers.api_gateway_handler import build_company_summary


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

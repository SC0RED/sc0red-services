"""Private helpers for the MCP read tools.

Pure functions extracted from ``tools_read.py`` to keep that module under the
400-line limit. Module-private — imported only by ``tools_read.py``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.mcp.auth_context import AuthenticatedUser


def _verify_org_access(
    record: dict[str, Any] | None, user: AuthenticatedUser, label: str, record_id: str
) -> str | None:
    """Verify the record belongs to the authenticated user's org.

    Returns an error message if access denied, or None if OK.
    """
    if not record:
        return f"{label} {record_id} not found."
    if record.get("org_id") != user.org_id:
        return f"{label} {record_id} not found."
    return None


def _format_analysis_summary(company: dict[str, Any]) -> str:
    """Format a single company/analysis as concise text for LLM consumption."""
    return "\n".join(
        [
            f"**{company.get('company_name', 'Unknown')}**",
            f"URL: {company.get('company_url', 'N/A')}",
            f"Industry: {company.get('industry', 'N/A')}",
            f"Risk Score: {company.get('overall_risk_score', 'N/A')}/10",
            f"Risk Tier: {company.get('risk_tier', 'N/A')}",
            f"Analyzed: {company.get('analyzed_at', 'N/A')}",
        ]
    )


def _get_assessment_data(assessment_repo: Any, company_id: str) -> dict[str, Any]:
    """Load latest assessment data for a company. Mirrors handle_get_analysis."""
    assessments = assessment_repo.find_by_company(company_id)
    if not assessments:
        return {
            "risk_scores": [],
            "opportunities": [],
            "ebitda_tree": None,
            "value_chain": None,
            "documents": [],
        }

    assessments.sort(key=lambda a: a.get("created_at", ""), reverse=True)
    aid = assessments[0]["id"]

    return {
        "risk_scores": assessment_repo.get_risk_scores(aid),
        "opportunities": assessment_repo.get_opportunities(aid),
        "ebitda_tree": assessment_repo.get_ebitda_tree(aid),
        "value_chain": assessment_repo.get_value_chain(aid),
        "documents": assessment_repo.get_documents(aid),
    }


def _ungrounded_message(payload: dict[str, Any], heading: str, fallback: str) -> str | None:
    """Return the placeholder text for an ungrounded FACT surface, else None.

    Fact-vs-forecast data contract (report-data-integrity spec): when a FACT
    surface could not be grounded, surface the honest reason rather than empty
    "N/A" figures that read like a fabricated/missing model.
    """
    if payload.get("grounded") is not False:
        return None
    reason = payload.get("insufficientDataReason") or fallback
    return f"## {heading}\nNot available: {reason}"

"""MCP scan read tools — get_scan / list_scans.

Split out of ``tools_read`` (the 400-line cap) and grouped here because they
pair with the scan WRITE tools in ``tools_write``: ``get_scan`` is the bridge
between ``start_portfolio_scan`` and ``confirm_portfolio_scan`` (it lists the
discovered companies + their URLs to confirm). Same registration pattern as the
other read tools — explicit ``storage`` in, repos built once per registration.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.mcp._tools_read_helpers import (
    NO_SCANS_GUIDANCE,
    _format_scans,
    _verify_org_access,
)
from src.mcp.auth_context import get_authenticated_user
from src.utilities.scan_summary import (
    build_unified_analyses,
    compute_scan_progress,
    derive_progress_label,
)

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from src.repositories.dynamodb.provider import DynamoDBStorageProvider


def register_scan_read_tools(mcp: FastMCP, storage: DynamoDBStorageProvider) -> None:
    """Register the scan read tools on the server."""
    company_repo = storage.create_company_repository()
    scan_repo = storage.create_scan_repository()

    @mcp.tool()
    async def get_scan(scan_id: str) -> str:
        """Get scan details including status and linked analyses.

        Args:
            scan_id: The ID of the scan.
        """
        user = get_authenticated_user()
        scan = scan_repo.get_by_id(scan_id)
        if error := _verify_org_access(scan, user, "Scan", scan_id):
            return error
        if scan is None:
            # _verify_org_access returns an error when scan is None; this is
            # defensive narrowing for type checkers — unreachable at runtime.
            raise RuntimeError(f"scan {scan_id} vanished between access check and read")

        scan_companies = scan_repo.get_scan_companies(scan_id)
        company_ids = [sc["company_id"] for sc in scan_companies if sc.get("company_id")]
        companies_batch = company_repo.get_by_ids(company_ids) if company_ids else []
        analyses = build_unified_analyses(scan_companies, companies_batch)

        # Compute progress the same way GET /scan/{id} does — workers update each
        # company's pipeline_progress mid-run but NOT the scan record's progress
        # (see request_executor._report_progress), so reading the raw stored
        # progress would sit at the kickoff value (10%) until completion. Take
        # the higher of stored vs. computed so a finished scan still reads 100%.
        status = scan.get("status", "unknown")
        total_companies = scan.get("total_companies", 0)
        done_count, computed_progress = compute_scan_progress(
            analyses, scan.get("progress", 0), total_companies
        )
        if status == "running" and total_companies and done_count >= total_companies:
            status = "complete"
            computed_progress = 100
        progress = max(scan.get("progress", 0), computed_progress)
        progress_label = derive_progress_label(analyses, scan.get("progress_label", ""))

        lines = [
            f"## Scan {scan_id}",
            f"Status: {status}",
            f"Type: {scan.get('type', 'unknown')}",
            f"Progress: {progress}%" + (f" — {progress_label}" if progress_label else ""),
        ]
        # Portfolio discoveries land their candidate companies on the scan
        # record (set by the discovery worker). Surface them with their URLs so
        # the confirm flow has something to pass to confirm_portfolio_scan —
        # the write tools point clients here to "review the discovered
        # companies".
        portfolio_companies = scan.get("portfolio_companies", [])
        if portfolio_companies:
            lines.append(f"\n### Discovered Companies ({len(portfolio_companies)})")
            if scan.get("status") == "awaiting_confirmation":
                lines.append(
                    "Confirm the ones to analyze with "
                    "confirm_portfolio_scan(scan_id, [company URLs]):"
                )
            for company in portfolio_companies:
                name = company.get("name") or "?"
                url = company.get("url", "")
                lines.append(f"- {name} — {url}")
        if analyses:
            lines.append(f"\n### Analyses ({len(analyses)})")
            for analysis in analyses:
                score = analysis.get("overallRiskScore")
                score_text = f"{score}/10" if score is not None else "in progress"
                name = analysis.get("companyName") or "(pending)"
                lines.append(f"- {name} — Score: {score_text} — ID: {analysis.get('id', '')}")
        return "\n".join(lines)

    @mcp.tool()
    async def list_scans() -> str:  # noqa: NAMING001
        """List the scans in your organization.

        Returns each scan's ID, status, type (standalone/portfolio), and progress.
        Use get_scan with the ID for a scan's linked analyses.
        """
        user = get_authenticated_user()
        scans = scan_repo.find_recent_by_org(user.org_id, limit=None)
        if not scans:
            return f"No scans found. {NO_SCANS_GUIDANCE}"
        return _format_scans(scans)

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
        lines = [
            f"## Scan {scan_id}",
            f"Status: {scan.get('status', 'unknown')}",
            f"Type: {scan.get('type', 'unknown')}",
            f"Progress: {scan.get('progress', 0)}%",
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
        scan_companies = scan_repo.get_scan_companies(scan_id)
        if scan_companies:
            cids = [sc.get("company_id", "") for sc in scan_companies if sc.get("company_id")]
            if cids:
                cdata = company_repo.get_by_ids(cids)
                lines.append(f"\n### Analyses ({len(cdata)})")
                for c in cdata:
                    score = c.get("overall_risk_score", "N/A")
                    lines.append(
                        f"- {c.get('company_name', '?')} — Score: {score}/10 "
                        f"— ID: {c.get('id', '')}"
                    )
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

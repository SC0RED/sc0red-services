"""MCP write tools — start and confirm scans from an AI assistant.

These delegate to the same ``scan_core`` functions the HTTP handlers use, so a
scan started from Claude behaves identically to one started from the web UI.
Every tool follows the same order: validate inputs → ``write``-scope check →
org access (where a record is addressed) → rate limit → shared core →
Markdown result with next-step guidance. Rate limiting happens last so a
refused call never burns a scan slot on bad input.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.handlers.scan_core import ScanInputError, confirm_scan, start_scan
from src.mcp._tools_read_helpers import _verify_org_access
from src.mcp.auth_context import get_authenticated_user
from src.mcp.scan_rate_limiter import ScanRateLimitedError

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from src.mcp.auth_context import AuthenticatedUser
    from src.mcp.scan_rate_limiter import ScanRateLimiter
    from src.repositories.dynamodb.provider import DynamoDBStorageProvider

WRITE_SCOPE_REQUIRED_MESSAGE = (
    "This connection has read-only access — the `write` scope is required to "
    "start scans. Disconnect and reconnect this app, approving write access."
)


def _is_missing_write_scope(user: AuthenticatedUser) -> bool:  # noqa: NAMING001  is_ predicate; checker mis-flags leading-underscore
    return "write" not in user.scopes


def register_write_tools(
    mcp: FastMCP,
    storage: DynamoDBStorageProvider,
    *,
    sqs_client: Any,
    queue_url: str,
    rate_limiter: ScanRateLimiter,
) -> None:
    """Register the scan write tools on the server."""
    scan_repo = storage.create_scan_repository()

    @mcp.tool()
    async def start_company_scan(url: str) -> str:
        """Start an AI risk analysis for a single company.

        Kicks off the full analysis pipeline for the company website. Analysis
        takes several minutes — track progress with get_scan and read results
        with get_analysis once complete.

        Args:
            url: The company website URL (must start with http:// or https://).
        """
        if not url.startswith(("http://", "https://")):
            return "A company URL starting with http:// or https:// is required."
        user = get_authenticated_user()
        if _is_missing_write_scope(user):
            return WRITE_SCOPE_REQUIRED_MESSAGE
        try:
            rate_limiter.check_and_increment(user.org_id)
        except ScanRateLimitedError as error:
            return str(error)
        result = start_scan(
            scan_repo,
            url=url,
            scan_type="single",
            authentication=user,
            sqs=sqs_client,
            queue_url=queue_url,
        )
        return "\n".join(
            [
                "## Scan started",
                f"Scan ID: {result['scan_id']}",
                f"Analysis ID: {result['analysis_id']}",
                "Status: running",
                "",
                f'Analysis takes a few minutes. Poll get_scan("{result["scan_id"]}") '
                "for progress; when complete, read the results with "
                f'get_analysis("{result["analysis_id"]}").',
            ]
        )

    @mcp.tool()
    async def start_portfolio_scan(url: str) -> str:
        """Discover a PE firm's portfolio companies for analysis.

        Starts portfolio discovery on the firm's website. Once the scan reaches
        `awaiting_confirmation`, review the discovered companies via get_scan
        and confirm the ones to analyze with confirm_portfolio_scan.

        Args:
            url: The PE firm's website URL (must start with http:// or https://).
        """
        if not url.startswith(("http://", "https://")):
            return "A firm URL starting with http:// or https:// is required."
        user = get_authenticated_user()
        if _is_missing_write_scope(user):
            return WRITE_SCOPE_REQUIRED_MESSAGE
        try:
            rate_limiter.check_and_increment(user.org_id)
        except ScanRateLimitedError as error:
            return str(error)
        result = start_scan(
            scan_repo,
            url=url,
            scan_type="portfolio",
            authentication=user,
            sqs=sqs_client,
            queue_url=queue_url,
        )
        return "\n".join(
            [
                "## Portfolio discovery started",
                f"Scan ID: {result['scan_id']}",
                "Status: discovering",
                "",
                f'Poll get_scan("{result["scan_id"]}") until the status is '
                "awaiting_confirmation, review the discovered companies, then call "
                f'confirm_portfolio_scan("{result["scan_id"]}", [company URLs]) to analyze them.',
            ]
        )

    @mcp.tool()
    async def confirm_portfolio_scan(  # noqa: NAMING001  confirm is a verb (tool name is the client contract)
        scan_id: str, company_urls: list[str]
    ) -> str:
        """Confirm discovered portfolio companies for analysis.

        Use after start_portfolio_scan reaches `awaiting_confirmation`. Pass the
        URLs of the discovered companies you want analyzed (from get_scan's
        portfolio companies list).

        Args:
            scan_id: The portfolio scan to confirm.
            company_urls: Website URLs of the companies to analyze.
        """
        if not company_urls:
            return "At least one company URL is required."
        user = get_authenticated_user()
        if _is_missing_write_scope(user):
            return WRITE_SCOPE_REQUIRED_MESSAGE
        scan = scan_repo.get_by_id(scan_id)
        if error := _verify_org_access(scan, user, "Scan", scan_id):
            return error
        try:
            rate_limiter.check_and_increment(user.org_id)
        except ScanRateLimitedError as error:
            return str(error)
        # Resolve names from the discovery results so analysis cards render
        # with real company names, matching the web confirm flow.
        # scan is non-None here — _verify_org_access already returned for a
        # missing record.
        discovered_names = {
            company.get("url", ""): company.get("name", "")
            for company in scan.get("portfolio_companies", [])  # type: ignore[reportOptionalMemberAccess]
        }
        companies = [{"url": url, "name": discovered_names.get(url, "")} for url in company_urls]
        try:
            result = confirm_scan(
                scan_repo,
                scan_id=scan_id,
                companies=companies,
                authentication=user,
                sqs=sqs_client,
                queue_url=queue_url,
            )
        except ScanInputError as error:
            return str(error)
        queued = result["queued"]
        lines = [f"## {len(queued)} companies queued for analysis"]
        lines.extend(
            f"- {item['name'] or 'Unnamed company'} — analysis ID: {item['analysisId']}"
            for item in queued
        )
        lines.append("")
        lines.append(f'Poll get_scan("{scan_id}") for progress across the portfolio.')
        return "\n".join(lines)

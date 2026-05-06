"""MCP read tools — registered on the FastMCP server, reads DynamoDB directly."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from src.mcp.auth_context import get_authenticated_user

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from src.mcp.auth_context import AuthenticatedUser
    from src.repositories.dynamodb.provider import DynamoDBStorageProvider


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


def register_read_tools(mcp: FastMCP, storage: DynamoDBStorageProvider) -> None:
    """Register all read-only MCP tools on the server."""
    company_repo = storage.create_company_repository()
    assessment_repo = storage.create_assessment_repository()
    scan_repo = storage.create_scan_repository()
    user_repo = storage.create_user_repository()

    @mcp.tool()
    async def get_dashboard() -> str:
        """Get portfolio dashboard summary with stats and recent activity.

        Returns total analyses count, average risk score, critical risk count,
        scan count, and lists of recent analyses and scans.
        Use this when the user asks for an overview of their portfolio.
        """
        user = get_authenticated_user()
        companies, _ = company_repo.find_by_org(user.org_id)
        analyzed = [c for c in companies if c.get("overall_risk_score") is not None]

        total = len(analyzed)
        avg_score = (
            round(sum(float(c["overall_risk_score"]) for c in analyzed) / total, 1) if total else 0
        )
        critical = sum(1 for c in analyzed if c.get("risk_tier") == "critical")
        all_scans = scan_repo.find_recent_by_org(user.org_id, limit=None)

        lines = [
            "## Portfolio Dashboard",
            f"- Companies Analyzed: {total}",
            f"- Average Risk Score: {avg_score}/10",
            f"- Critical Risks: {critical}",
            f"- Total Scans: {len(all_scans)}",
        ]

        analyzed.sort(key=lambda c: c.get("analyzed_at", ""), reverse=True)
        if analyzed[:5]:
            lines.append("\n### Recent Analyses")
            for c in analyzed[:5]:
                score = c.get("overall_risk_score", "N/A")
                tier = c.get("risk_tier", "unknown")
                lines.append(
                    f"- {c.get('company_name', '?')} — "
                    f"Score: {score}/10 ({tier}) — ID: {c.get('id', '')}"
                )
        return "\n".join(lines)

    @mcp.tool()
    async def list_analyses() -> str:  # noqa: NAMING001
        """List all company risk analyses in your portfolio.

        Returns a summary of each analysis with company name, risk score,
        tier, and ID. Use get_analysis with the ID for full details.
        """
        user = get_authenticated_user()
        companies, _ = company_repo.find_by_org(user.org_id)
        analyzed = [c for c in companies if c.get("overall_risk_score") is not None]

        if not analyzed:
            return "No analyses found. Use start_company_scan to analyze a company."

        lines = [f"## {len(analyzed)} Analyses"]
        for c in analyzed:
            lines.append(_format_analysis_summary(c))
            lines.append(f"ID: {c.get('id', '')}")
            lines.append("")
        return "\n".join(lines)

    @mcp.tool()
    async def get_analysis(analysis_id: str) -> str:
        """Get full analysis details for a company.

        Includes risk score, risk dimensions, opportunities, EBITDA tree,
        and value chain. Use this when the user asks about a specific
        company's risk analysis or wants detailed risk/opportunity data.

        Args:
            analysis_id: The ID of the analysis to retrieve.
        """
        user = get_authenticated_user()
        company = company_repo.get_by_id(analysis_id)
        if error := _verify_org_access(company, user, "Analysis", analysis_id):
            return error

        data = _get_assessment_data(assessment_repo, analysis_id)
        risk_scores = data["risk_scores"]
        opportunities = data["opportunities"]
        ebitda_tree = data["ebitda_tree"]
        value_chain = data["value_chain"]
        documents = data["documents"]

        metadata_json = company.get("metadata_json", "")
        analysis_summary = ""
        top_actions: list[str] = []
        if metadata_json:
            meta = json.loads(metadata_json) if isinstance(metadata_json, str) else metadata_json
            analysis_summary = meta.get("analysis_summary", "")
            top_actions = meta.get("top_actions", [])

        lines = [
            f"## {company.get('company_name', 'Unknown')} — Analysis",
            f"URL: {company.get('company_url', 'N/A')}",
            f"Industry: {company.get('industry', 'N/A')}",
            f"Overall Risk Score: {company.get('overall_risk_score', 'N/A')}/10",
            f"Risk Tier: {company.get('risk_tier', 'N/A')}",
        ]
        if analysis_summary:
            lines.append(f"\n### Summary\n{analysis_summary}")
        if top_actions:
            lines.append("\n### Top Actions")
            lines.extend(f"- {a}" for a in top_actions)
        if risk_scores:
            lines.append("\n### Risk Dimensions")
            for r in risk_scores:
                name = r.get("name", r.get("category", "?"))
                lines.append(f"- **{name}**: {r.get('score', '?')}/10")
        if opportunities:
            lines.append(f"\n### Opportunities ({len(opportunities)})")
            for opp in opportunities[:10]:
                lever = opp.get("value_lever", "")
                impact = opp.get("impact_rating", "")
                lines.append(f"- [{lever}] {opp.get('title', '?')} (Impact: {impact})")
        if ebitda_tree:
            lines.append("\n### EBITDA Impact Model")
            if ebitda_tree.get("revenueEstimate"):
                lines.append(f"Revenue Estimate: {ebitda_tree['revenueEstimate']}")
            if ebitda_tree.get("ebitdaEstimate"):
                lines.append(f"EBITDA Estimate: {ebitda_tree['ebitdaEstimate']}")
        if value_chain and value_chain.get("steps"):
            lines.append(f"\n### Value Chain ({len(value_chain['steps'])} activities)")
            if value_chain.get("summary"):
                lines.append(value_chain["summary"])
        if documents:
            lines.append(f"\n### Documents ({len(documents)})")
            lines.extend(
                f"- {d.get('filename', '?')} ({d.get('fileType', '?')})" for d in documents
            )
        return "\n".join(lines)

    @mcp.tool()
    async def get_risk_breakdown(analysis_id: str) -> str:
        """Get risk scores by dimension for a specific analysis.

        Args:
            analysis_id: The ID of the analysis.
        """
        user = get_authenticated_user()
        company = company_repo.get_by_id(analysis_id)
        if error := _verify_org_access(company, user, "Analysis", analysis_id):
            return error
        data = _get_assessment_data(assessment_repo, analysis_id)
        if not data["risk_scores"]:
            return f"No risk scores found for analysis {analysis_id}."
        lines = [
            f"## Risk Breakdown — {company.get('company_name', 'Unknown')}",
            f"Overall: {company.get('overall_risk_score', 'N/A')}/10 "
            f"({company.get('risk_tier', 'N/A')})",
            "",
        ]
        for r in data["risk_scores"]:
            name = r.get("name", r.get("category", "?"))
            lines.append(f"- **{name}**: {r.get('score', '?')}/10")
        return "\n".join(lines)

    @mcp.tool()
    async def get_opportunities(analysis_id: str) -> str:
        """Get AI opportunities with value levers for a specific analysis.

        Args:
            analysis_id: The ID of the analysis.
        """
        user = get_authenticated_user()
        company = company_repo.get_by_id(analysis_id)
        if error := _verify_org_access(company, user, "Analysis", analysis_id):
            return error
        data = _get_assessment_data(assessment_repo, analysis_id)
        if not data["opportunities"]:
            return f"No opportunities found for analysis {analysis_id}."
        name = company.get("company_name", "Unknown")
        opps = data["opportunities"]
        lines = [f"## Opportunities — {name} ({len(opps)})"]
        for i, opp in enumerate(opps, 1):
            lines.append(f"\n### {i}. {opp.get('title', 'Untitled')}")
            lines.append(f"Value Lever: {opp.get('value_lever', 'N/A')}")
            lines.append(f"Impact: {opp.get('impact_rating', 'N/A')}")
            if opp.get("description"):
                lines.append(f"Description: {opp['description']}")
        return "\n".join(lines)

    @mcp.tool()
    async def get_ebitda_tree(analysis_id: str) -> str:
        """Get the EBITDA impact model for a specific analysis.

        Args:
            analysis_id: The ID of the analysis.
        """
        user = get_authenticated_user()
        company = company_repo.get_by_id(analysis_id)
        if error := _verify_org_access(company, user, "Analysis", analysis_id):
            return error
        data = _get_assessment_data(assessment_repo, analysis_id)
        if not data["ebitda_tree"]:
            return f"No EBITDA tree found for analysis {analysis_id}."
        tree = data["ebitda_tree"]
        lines = [
            f"## EBITDA Impact Model — {company.get('company_name', 'Unknown')}",
            f"Revenue Estimate: {tree.get('revenueEstimate', 'N/A')}",
            f"EBITDA Estimate: {tree.get('ebitdaEstimate', 'N/A')}",
        ]
        tree_data = tree.get("treeData", [])
        if tree_data:
            lines.append(f"\n### Tree Nodes ({len(tree_data)})")
            # Each node is `EbitdaNode.model_dump()` — snake_case keys. Reading
            # `value` (the legacy key) silently rendered blank for every node;
            # the correct field on the persisted shape is `value_range`.
            lines.extend(
                f"- {n.get('label', '?')}: {n.get('value_range', '')}" for n in tree_data
            )
        return "\n".join(lines)

    @mcp.tool()
    async def get_value_chain(analysis_id: str) -> str:
        """Get value chain analysis for a specific company.

        Args:
            analysis_id: The ID of the analysis.
        """
        user = get_authenticated_user()
        company = company_repo.get_by_id(analysis_id)
        if error := _verify_org_access(company, user, "Analysis", analysis_id):
            return error
        data = _get_assessment_data(assessment_repo, analysis_id)
        if not data["value_chain"]:
            return f"No value chain found for analysis {analysis_id}."
        chain = data["value_chain"]
        lines = [f"## Value Chain — {company.get('company_name', 'Unknown')}"]
        if chain.get("summary"):
            lines.append(chain["summary"])
        for step in chain.get("steps", []):
            lines.append(f"\n### {step.get('name', '?')} ({step.get('category', '')})")
            if step.get("description"):
                lines.append(step["description"])
        return "\n".join(lines)

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
    async def list_team_members() -> str:  # noqa: NAMING001
        """List team members and pending invitations in your organization."""
        user = get_authenticated_user()
        members = user_repo.find_by_org(user.org_id)
        inv_repo = storage.create_invitation_repository()
        invitations = inv_repo.find_by_org(user.org_id)
        lines = [f"## Team ({len(members)} members)"]
        lines.extend(
            f"- {m.get('name', m.get('email', '?'))} ({m.get('role', '?')})" for m in members
        )
        if invitations:
            lines.append(f"\n### Pending Invitations ({len(invitations)})")
            lines.extend(
                f"- {inv.get('email', '?')} (invited as {inv.get('role', '?')})"
                for inv in invitations
            )
        return "\n".join(lines)

    @mcp.tool()
    async def list_documents(analysis_id: str) -> str:  # noqa: NAMING001
        """List documents attached to a specific analysis.

        Args:
            analysis_id: The ID of the analysis.
        """
        user = get_authenticated_user()
        company = company_repo.get_by_id(analysis_id)
        if error := _verify_org_access(company, user, "Analysis", analysis_id):
            return error
        data = _get_assessment_data(assessment_repo, analysis_id)
        if not data["documents"]:
            return f"No documents attached to analysis {analysis_id}."
        name = company.get("company_name", "Unknown")
        docs = data["documents"]
        lines = [f"## Documents — {name} ({len(docs)})"]
        lines.extend(
            f"- {d.get('filename', '?')} ({d.get('fileType', '?')}, "
            f"{d.get('charCount', 0)} chars) — ID: {d.get('id', '')}"
            for d in docs
        )
        return "\n".join(lines)

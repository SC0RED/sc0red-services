"""MCP read tools — query existing Janus data.

All tools are registered on the FastMCP server instance.
Each tool calls the backend API via the internal API client.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from src.mcp.api_client import call_backend

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)


def _format_analysis_summary(analysis: dict[str, Any]) -> str:
    """Format a single analysis as concise text for LLM consumption."""
    lines = [
        f"**{analysis.get('companyName', 'Unknown')}**",
        f"URL: {analysis.get('companyUrl', 'N/A')}",
        f"Industry: {analysis.get('industry', 'N/A')}",
        f"Risk Score: {analysis.get('overallRiskScore', 'N/A')}/10",
        f"Risk Tier: {analysis.get('riskTier', 'N/A')}",
        f"Source: {analysis.get('scanType', 'N/A')}",
        f"Analyzed: {analysis.get('analyzedAt', 'N/A')}",
    ]
    return "\n".join(lines)


def _get_user_context() -> dict[str, str]:
    """Get user context for backend API calls.

    TODO: Wire this to actual OAuth token claims once MCP SDK
    provides access to the authenticated user in tool handlers.
    For now, uses environment-based defaults for development.
    """
    import os

    return {
        "user_id": os.environ.get("MCP_DEV_USER_ID", ""),
        "org_id": os.environ.get("MCP_DEV_ORG_ID", ""),
        "email": os.environ.get("MCP_DEV_EMAIL", ""),
        "role": os.environ.get("MCP_DEV_ROLE", "admin"),
    }


def register_read_tools(mcp: FastMCP) -> None:
    """Register all read-only MCP tools on the server."""

    @mcp.tool()
    async def get_dashboard() -> str:
        """Get portfolio dashboard summary with stats and recent activity.

        Returns total analyses count, average risk score, critical risk count,
        scan count, and lists of recent analyses and scans.
        Use this when the user asks for an overview of their portfolio.
        """
        data = await call_backend(
            method="GET",
            path="/api/dashboard",
            **_get_user_context(),
        )
        lines = [
            "## Portfolio Dashboard",
            f"- Companies Analyzed: {data.get('totalAnalyses', 0)}",
            f"- Average Risk Score: {data.get('avgRiskScore', 0):.1f}/10",
            f"- Critical Risks: {data.get('criticalCount', 0)}",
            f"- Total Scans: {data.get('scanCount', 0)}",
        ]

        recent = data.get("recentAnalyses", [])
        if recent:
            lines.append("\n### Recent Analyses")
            for analysis in recent[:5]:
                score = analysis.get("overallRiskScore", "N/A")
                tier = analysis.get("riskTier", "unknown")
                lines.append(
                    f"- {analysis.get('companyName', '?')} — "
                    f"Score: {score}/10 ({tier}) — ID: {analysis.get('id', '')}"
                )

        return "\n".join(lines)

    @mcp.tool()
    async def list_analyses() -> str:  # noqa: NAMING001
        """List all company risk analyses in your portfolio.

        Returns a summary of each analysis with company name, risk score,
        tier, and ID. Use get_analysis with the ID for full details.
        """
        data = await call_backend(
            method="GET",
            path="/api/analyses",
            **_get_user_context(),
        )
        analyses = data.get("analyses", [])
        if not analyses:
            return "No analyses found. Use start_company_scan to analyze a company."

        lines = [f"## {len(analyses)} Analyses"]
        for analysis in analyses:
            lines.append(_format_analysis_summary(analysis))
            lines.append(f"ID: {analysis.get('id', '')}")
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
        data = await call_backend(
            method="GET",
            path=f"/api/analysis/{analysis_id}",
            **_get_user_context(),
        )

        lines = [
            f"## {data.get('companyName', 'Unknown')} — Analysis",
            f"URL: {data.get('companyUrl', 'N/A')}",
            f"Industry: {data.get('industry', 'N/A')}",
            f"Overall Risk Score: {data.get('overallRiskScore', 'N/A')}/10",
            f"Risk Tier: {data.get('riskTier', 'N/A')}",
        ]

        if data.get("analysisSummary"):
            lines.append(f"\n### Summary\n{data['analysisSummary']}")

        if data.get("topActions"):
            lines.append("\n### Top Actions")
            for action in data["topActions"]:
                lines.append(f"- {action}")  # noqa: PERF401

        risk_scores = data.get("riskScores", [])
        if risk_scores:
            lines.append("\n### Risk Dimensions")
            for risk in risk_scores:
                risk_name = risk.get("name", risk.get("category", "?"))
                lines.append(f"- {risk_name}: {risk.get('score', '?')}/10")

        opportunities = data.get("opportunities", [])
        if opportunities:
            lines.append(f"\n### Opportunities ({len(opportunities)})")
            for opp in opportunities[:10]:
                lever = opp.get("value_lever", "")
                impact = opp.get("impact_rating", "")
                lines.append(f"- [{lever}] {opp.get('title', '?')} (Impact: {impact})")

        if data.get("ebitdaTree"):
            tree = data["ebitdaTree"]
            lines.append("\n### EBITDA Impact Model")
            if tree.get("revenueEstimate"):
                lines.append(f"Revenue Estimate: {tree['revenueEstimate']}")
            if tree.get("ebitdaEstimate"):
                lines.append(f"EBITDA Estimate: {tree['ebitdaEstimate']}")

        if data.get("valueChain"):
            chain = data["valueChain"]
            steps = chain.get("steps", [])
            lines.append(f"\n### Value Chain ({len(steps)} activities)")
            if chain.get("summary"):
                lines.append(chain["summary"])

        documents = data.get("documents", [])
        if documents:
            lines.append(f"\n### Documents ({len(documents)})")
            lines.extend(
                f"- {doc.get('filename', '?')} ({doc.get('fileType', '?')})" for doc in documents
            )

        return "\n".join(lines)

    @mcp.tool()
    async def get_risk_breakdown(analysis_id: str) -> str:
        """Get risk scores by dimension for a specific analysis.

        Shows each risk category (automation, workforce, data privacy, etc.)
        with its individual score. Use this for detailed risk dimension analysis.

        Args:
            analysis_id: The ID of the analysis.
        """
        data = await call_backend(
            method="GET",
            path=f"/api/analysis/{analysis_id}",
            **_get_user_context(),
        )
        risk_scores = data.get("riskScores", [])
        if not risk_scores:
            return f"No risk scores found for analysis {analysis_id}."

        lines = [
            f"## Risk Breakdown — {data.get('companyName', 'Unknown')}",
            f"Overall: {data.get('overallRiskScore', 'N/A')}/10 ({data.get('riskTier', 'N/A')})",
            "",
        ]
        for risk in risk_scores:
            name = risk.get("name", risk.get("category", "?"))
            score = risk.get("score", "?")
            lines.append(f"- **{name}**: {score}/10")

        return "\n".join(lines)

    @mcp.tool()
    async def get_opportunities(analysis_id: str) -> str:
        """Get AI opportunities with value levers for a specific analysis.

        Shows each opportunity with its value lever (automation, revenue growth,
        cost reduction, etc.), impact rating, and description.

        Args:
            analysis_id: The ID of the analysis.
        """
        data = await call_backend(
            method="GET",
            path=f"/api/analysis/{analysis_id}",
            **_get_user_context(),
        )
        opportunities = data.get("opportunities", [])
        if not opportunities:
            return f"No opportunities found for analysis {analysis_id}."

        lines = [f"## Opportunities — {data.get('companyName', 'Unknown')} ({len(opportunities)})"]
        for i, opp in enumerate(opportunities, 1):
            lines.append(f"\n### {i}. {opp.get('title', 'Untitled')}")
            lines.append(f"Value Lever: {opp.get('value_lever', 'N/A')}")
            lines.append(f"Impact: {opp.get('impact_rating', 'N/A')}")
            if opp.get("description"):
                lines.append(f"Description: {opp['description']}")

        return "\n".join(lines)

    @mcp.tool()
    async def get_ebitda_tree(analysis_id: str) -> str:
        """Get the EBITDA impact model for a specific analysis.

        Shows revenue and EBITDA estimates with the tree structure of
        financial impact nodes. Use this for financial analysis.

        Args:
            analysis_id: The ID of the analysis.
        """
        data = await call_backend(
            method="GET",
            path=f"/api/analysis/{analysis_id}",
            **_get_user_context(),
        )
        tree = data.get("ebitdaTree")
        if not tree:
            return f"No EBITDA tree found for analysis {analysis_id}."

        lines = [
            f"## EBITDA Impact Model — {data.get('companyName', 'Unknown')}",
            f"Revenue Estimate: {tree.get('revenueEstimate', 'N/A')}",
            f"EBITDA Estimate: {tree.get('ebitdaEstimate', 'N/A')}",
        ]

        tree_data = tree.get("treeData", [])
        if tree_data:
            lines.append(f"\n### Tree Nodes ({len(tree_data)})")
            for node in tree_data:
                label = node.get("label", "?")
                value = node.get("value", "")
                lines.append(f"- {label}: {value}")

        return "\n".join(lines)

    @mcp.tool()
    async def get_value_chain(analysis_id: str) -> str:
        """Get value chain analysis for a specific company.

        Shows the company's value chain activities (primary and support)
        with AI impact assessment for each step.

        Args:
            analysis_id: The ID of the analysis.
        """
        data = await call_backend(
            method="GET",
            path=f"/api/analysis/{analysis_id}",
            **_get_user_context(),
        )
        chain = data.get("valueChain")
        if not chain:
            return f"No value chain found for analysis {analysis_id}."

        lines = [f"## Value Chain — {data.get('companyName', 'Unknown')}"]
        if chain.get("summary"):
            lines.append(chain["summary"])

        steps = chain.get("steps", [])
        for step in steps:
            name = step.get("name", "?")
            category = step.get("category", "")
            lines.append(f"\n### {name} ({category})")
            if step.get("description"):
                lines.append(step["description"])
            if step.get("ai_impact"):
                lines.append(f"AI Impact: {step['ai_impact']}")

        return "\n".join(lines)

    @mcp.tool()
    async def get_scan(scan_id: str) -> str:
        """Get scan details including status and linked analyses.

        Shows scan progress, type, and all company analyses within the scan.

        Args:
            scan_id: The ID of the scan.
        """
        data = await call_backend(
            method="GET",
            path=f"/api/scan/{scan_id}",
            **_get_user_context(),
        )
        lines = [
            f"## Scan {scan_id}",
            f"Status: {data.get('status', 'unknown')}",
            f"Type: {data.get('type', 'unknown')}",
            f"Progress: {data.get('progress', 0)}%",
        ]

        analyses = data.get("analyses", [])
        if analyses:
            lines.append(f"\n### Analyses ({len(analyses)})")
            for analysis in analyses:
                name = analysis.get("companyName", "?")
                score = analysis.get("overallRiskScore", "N/A")
                lines.append(f"- {name} — Score: {score}/10 — ID: {analysis.get('id', '')}")

        return "\n".join(lines)

    @mcp.tool()
    async def list_team_members() -> str:  # noqa: NAMING001
        """List team members and pending invitations in your organization.

        Shows current members with their roles and any pending invitations.
        """
        data = await call_backend(
            method="GET",
            path="/api/org/members",
            **_get_user_context(),
        )
        members = data.get("members", [])
        invitations = data.get("pendingInvitations", [])

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
        data = await call_backend(
            method="GET",
            path=f"/api/analysis/{analysis_id}",
            **_get_user_context(),
        )
        documents = data.get("documents", [])
        if not documents:
            return f"No documents attached to analysis {analysis_id}."

        lines = [f"## Documents — {data.get('companyName', 'Unknown')} ({len(documents)})"]
        lines.extend(
            f"- {d.get('filename', '?')} ({d.get('fileType', '?')}, "
            f"{d.get('charCount', 0)} chars) — ID: {d.get('id', '')}"
            for d in documents
        )

        return "\n".join(lines)

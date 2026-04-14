"""MCP search and comparison tools.

Split from tools_read.py to stay under 400-line file limit.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from src.mcp.api_client import call_backend
from src.mcp.tools_read import _format_analysis_summary, _get_user_context

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)


def register_search_tools(mcp: FastMCP) -> None:
    """Register search and comparison MCP tools on the server."""

    @mcp.tool()
    async def search_analyses(query: str) -> str:
        """Search analyses by company name, URL, or industry.

        Performs a case-insensitive search across all analyses in your portfolio.
        Returns matching analyses with risk scores.

        Args:
            query: Search term — company name, URL fragment, or industry keyword.
        """
        data = await call_backend(
            method="GET",
            path="/api/analyses",
            **_get_user_context(),
        )
        analyses = data.get("analyses", [])
        query_lower = query.lower()

        matches = [
            a
            for a in analyses
            if query_lower in (a.get("companyName", "") or "").lower()
            or query_lower in (a.get("companyUrl", "") or "").lower()
            or query_lower in (a.get("industry", "") or "").lower()
        ]

        if not matches:
            return f'No analyses matching "{query}". Use list_analyses to see all.'

        lines = [f'## Search Results for "{query}" ({len(matches)} matches)']
        for analysis in matches:
            lines.append(_format_analysis_summary(analysis))
            lines.append(f"ID: {analysis.get('id', '')}")
            lines.append("")

        return "\n".join(lines)

    @mcp.tool()
    async def compare_analyses(analysis_ids: list[str]) -> str:  # noqa: NAMING001
        """Compare two or more analyses side by side.

        Shows risk scores, tiers, and key metrics for each company.
        Use this when the user wants to compare companies in their portfolio.

        Args:
            analysis_ids: List of 2+ analysis IDs to compare.
        """
        if len(analysis_ids) < 2:  # noqa: PLR2004
            return "Please provide at least 2 analysis IDs to compare."

        analyses = []
        for aid in analysis_ids:
            try:
                data = await call_backend(
                    method="GET",
                    path=f"/api/analysis/{aid}",
                    **_get_user_context(),
                )
                analyses.append(data)
            except Exception:
                analyses.append({"companyName": f"Error loading {aid}", "id": aid})

        lines = [f"## Comparison of {len(analyses)} Companies", ""]

        # Summary table
        lines.append("| Company | Risk Score | Tier | Industry | Opportunities |")
        lines.append("|---------|-----------|------|----------|---------------|")
        for a in analyses:
            name = a.get("companyName", "?")
            score = a.get("overallRiskScore", "N/A")
            tier = a.get("riskTier", "N/A")
            industry = a.get("industry", "N/A")
            opp_count = len(a.get("opportunities", []))
            lines.append(f"| {name} | {score}/10 | {tier} | {industry} | {opp_count} |")

        # Risk dimension comparison
        lines.append("\n### Risk Dimensions")
        all_categories: set[str] = set()
        for a in analyses:
            for risk in a.get("riskScores", []):
                all_categories.add(risk.get("name", risk.get("category", "?")))

        if all_categories:
            header = (
                "| Dimension | " + " | ".join(a.get("companyName", "?") for a in analyses) + " |"
            )
            separator = "|-----------|" + "|".join("---" for _ in analyses) + "|"
            lines.append(header)
            lines.append(separator)

            for category in sorted(all_categories):
                row = f"| {category} |"
                for a in analyses:
                    score = "N/A"
                    for risk in a.get("riskScores", []):
                        if risk.get("name", risk.get("category")) == category:
                            score = str(risk.get("score", "N/A"))
                    row += f" {score} |"
                lines.append(row)

        return "\n".join(lines)

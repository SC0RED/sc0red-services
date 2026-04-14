"""MCP search and comparison tools — reads DynamoDB directly."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.mcp.auth_context import get_authenticated_user
from src.mcp.tools_read import _format_analysis_summary, _get_assessment_data

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from src.repositories.dynamodb.provider import DynamoDBStorageProvider


def register_search_tools(mcp: FastMCP, storage: DynamoDBStorageProvider) -> None:
    """Register search and comparison MCP tools on the server."""
    company_repo = storage.create_company_repository()
    assessment_repo = storage.create_assessment_repository()

    @mcp.tool()
    async def search_analyses(query: str) -> str:
        """Search analyses by company name, URL, or industry.

        Performs a case-insensitive search across all analyses in your portfolio.

        Args:
            query: Search term — company name, URL fragment, or industry keyword.
        """
        user = get_authenticated_user()
        companies, _ = company_repo.find_by_org(user.org_id)
        analyzed = [c for c in companies if c.get("overall_risk_score") is not None]
        query_lower = query.lower()

        matches = [
            c
            for c in analyzed
            if query_lower in (c.get("company_name", "") or "").lower()
            or query_lower in (c.get("company_url", "") or "").lower()
            or query_lower in (c.get("industry", "") or "").lower()
        ]

        if not matches:
            return f'No analyses matching "{query}". Use list_analyses to see all.'

        lines = [f'## Search Results for "{query}" ({len(matches)} matches)']
        for c in matches:
            lines.append(_format_analysis_summary(c))
            lines.append(f"ID: {c.get('id', '')}")
            lines.append("")
        return "\n".join(lines)

    @mcp.tool()
    async def compare_analyses(analysis_ids: list[str]) -> str:  # noqa: NAMING001
        """Compare two or more analyses side by side.

        Shows risk scores, tiers, and key metrics for each company.

        Args:
            analysis_ids: List of 2+ analysis IDs to compare.
        """
        if len(analysis_ids) < 2:  # noqa: PLR2004
            return "Please provide at least 2 analysis IDs to compare."

        analyses: list[dict[str, Any]] = []
        for aid in analysis_ids:
            company = company_repo.get_by_id(aid)
            if not company:
                return f"Analysis {aid} not found."
            data = _get_assessment_data(assessment_repo, aid)
            analyses.append({**company, **data})

        lines = [f"## Comparison of {len(analyses)} Companies", ""]
        lines.append("| Company | Risk Score | Tier | Industry | Opportunities |")
        lines.append("|---------|-----------|------|----------|---------------|")
        for a in analyses:
            name = a.get("company_name", "?")
            score = a.get("overall_risk_score", "N/A")
            tier = a.get("risk_tier", "N/A")
            industry = a.get("industry", "N/A")
            opp_count = len(a.get("opportunities", []))
            lines.append(f"| {name} | {score}/10 | {tier} | {industry} | {opp_count} |")

        lines.append("\n### Risk Dimensions")
        all_categories: set[str] = set()
        for a in analyses:
            for r in a.get("risk_scores", []):
                all_categories.add(r.get("name", r.get("category", "?")))

        if all_categories:
            names = [a.get("company_name", "?") for a in analyses]
            lines.append("| Dimension | " + " | ".join(names) + " |")
            lines.append("|-----------|" + "|".join("---" for _ in analyses) + "|")
            for cat in sorted(all_categories):
                row = f"| {cat} |"
                for a in analyses:
                    score = "N/A"
                    for r in a.get("risk_scores", []):
                        if r.get("name", r.get("category")) == cat:
                            score = str(r.get("score", "N/A"))
                    row += f" {score} |"
                lines.append(row)

        return "\n".join(lines)

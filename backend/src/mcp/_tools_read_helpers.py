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


def _latest_assessment_id(assessment_repo: Any, company_id: str) -> str | None:
    """Return the most-recent assessment id for a company, or None if none exist."""
    assessments = assessment_repo.find_by_company(company_id)
    if not assessments:
        return None
    assessments.sort(key=lambda a: a.get("created_at", ""), reverse=True)
    return assessments[0]["id"]


def _get_assessment_data(assessment_repo: Any, company_id: str) -> dict[str, Any]:
    """Load latest assessment data for a company. Mirrors handle_get_analysis."""
    aid = _latest_assessment_id(assessment_repo, company_id)
    if aid is None:
        return {
            "risk_scores": [],
            "opportunities": [],
            "ebitda_tree": None,
            "value_chain": None,
            "documents": [],
        }

    return {
        "risk_scores": assessment_repo.get_risk_scores(aid),
        "opportunities": assessment_repo.get_opportunities(aid),
        "ebitda_tree": assessment_repo.get_ebitda_tree(aid),
        "value_chain": assessment_repo.get_value_chain(aid),
        "documents": assessment_repo.get_documents(aid),
    }


def _opportunity_titles(opportunities: list[dict[str, Any]], indices: list[int]) -> list[str]:
    """Resolve opportunity-array indices to their titles.

    The EBITDA tree (``linked_opportunity_indices``) and value-chain steps
    (``opportunity_indices``) reference opportunities by their position in the
    analysis's ``opportunities`` array. Resolving to titles makes the read-tool
    output paper-readable instead of leaking raw indices. The linkage is a soft
    data contract (the AI may not populate it, or may emit a stale index), so
    out-of-range indices are skipped rather than raising.
    """
    return [
        opportunities[index].get("title", f"opportunity #{index + 1}")
        for index in indices
        if 0 <= index < len(opportunities)
    ]


def _format_opportunities(company_name: str, opps: list[dict[str, Any]]) -> str:
    """Render the opportunities list as Markdown for an MCP client.

    Surfaces the full Opportunity contract: strategic category, timeline,
    investment (narrative range + numeric point estimate), ROI (narrative +
    numeric %), and implementation steps — not just title/lever/impact.
    """
    lines = [f"## Opportunities — {company_name} ({len(opps)})"]
    for index, opp in enumerate(opps, 1):
        lines.append(f"\n### {index}. {opp.get('title', 'Untitled')}")
        if opp.get("strategic_category"):
            lines.append(f"Category: {opp['strategic_category']}")
        lines.append(f"Value Lever: {opp.get('value_lever') or 'N/A'}")
        lines.append(f"Impact: {opp.get('impact_rating') or 'N/A'}")
        if opp.get("timeline"):
            lines.append(f"Timeline: {opp['timeline']}")
        # Investment / ROI carry both a narrative string range (per-card copy)
        # and a numeric point estimate (Quick Wins matrix axes); surface the
        # number alongside the prose when the AI could ground it.
        if opp.get("investment_range") or opp.get("investment_value_usd") is not None:
            investment = opp.get("investment_range") or "N/A"
            if opp.get("investment_value_usd") is not None:
                investment += f" (~${opp['investment_value_usd']:,})"
            lines.append(f"Investment: {investment}")
        if opp.get("roi_estimate") or opp.get("roi_estimate_pct") is not None:
            roi = opp.get("roi_estimate") or "N/A"
            if opp.get("roi_estimate_pct") is not None:
                roi += f" (~{opp['roi_estimate_pct']:g}%)"
            lines.append(f"ROI: {roi}")
        if opp.get("description"):
            lines.append(f"Description: {opp['description']}")
        if opp.get("implementation_steps"):
            lines.append("Implementation steps:")
            lines.extend(
                f"  {step_index}. {step}"
                for step_index, step in enumerate(opp["implementation_steps"], 1)
            )
    return "\n".join(lines)


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


def _format_value_chain(
    company_name: str, chain: dict[str, Any], opportunities: list[dict[str, Any]]
) -> str:
    """Render the value chain as Markdown for an MCP client."""
    heading = f"Value Chain — {company_name}"
    if placeholder := _ungrounded_message(
        chain,
        heading,
        "The business model could not be grounded in public information, "
        "so no operating model is shown.",
    ):
        return placeholder
    lines = [f"## {heading}"]
    if chain.get("summary"):
        lines.append(chain["summary"])
    # Container-level fields are camelCased by the repo (like
    # ``insufficientDataReason``); only the per-step dicts keep their
    # snake_case ``model_dump()`` keys.
    if chain.get("provenanceBasis"):
        lines.append(f"_Basis: {chain['provenanceBasis']}_")
    for step in chain.get("steps", []):
        # Steps are `ValueChainStep.model_dump()` — the activity name is `label`
        # (reading `name` rendered every step as "?").
        lines.append(f"\n### {step.get('label', '?')} ({step.get('category', '')})")
        if step.get("description"):
            lines.append(step["description"])
        if step.get("risk_categories"):
            lines.append(f"Risk areas: {', '.join(step['risk_categories'])}")
        linked = _opportunity_titles(opportunities, step.get("opportunity_indices", []))
        if linked:
            lines.append(f"Linked opportunities: {', '.join(linked)}")
        if step.get("confidence_basis"):
            confidence = step.get("confidence_level") or "?"
            lines.append(f"Confidence: {confidence} — {step['confidence_basis']}")
    return "\n".join(lines)


def _first_sentence(text: str) -> str:
    """First sentence of a definition, for compact BSC objective rendering."""
    stripped = text.strip()
    head, separator, _ = stripped.partition(". ")
    return head + "." if separator else stripped


def _format_objective(objective: dict[str, Any], opportunities: list[dict[str, Any]]) -> str:
    """Render one BSC objective: title — first-sentence definition — links."""
    line = f"- **{objective.get('title', '?')}**"
    if objective.get("confidence"):
        line += f" ({objective['confidence']})"
    if objective.get("definition"):
        line += f" — {_first_sentence(objective['definition'])}"
    linked = _opportunity_titles(opportunities, objective.get("linked_opportunity_indices", []))
    if linked:
        line += f" [opportunities: {', '.join(linked)}]"
    return line


def _format_strategy_map(
    strategy_map: dict[str, Any], company_name: str, opportunities: list[dict[str, Any]]
) -> str:
    """Render the Balanced Scorecard strategy map as sectioned Markdown.

    A sectioned layout (one heading per BSC perspective, one bullet per
    objective) reads better for an AI client than a cramped four-row table;
    each objective shows its title, the first sentence of its definition, and
    any linked opportunity titles. Top-level keys are camelCase
    (``model_dump(by_alias=True)`` at persist); nested objective fields keep
    their snake_case names.
    """
    vision = strategy_map.get("vision", {})
    mission = strategy_map.get("mission", {})
    value_proposition = strategy_map.get("valueProposition", {})
    lines = [f"## Strategy Map — {company_name}"]
    if vision.get("statement"):
        suffix = " (synthesised)" if vision.get("synthesised") else ""
        lines.append(f"**Vision:** {vision['statement']}{suffix}")
    if mission.get("statement"):
        suffix = " (synthesised)" if mission.get("synthesised") else ""
        lines.append(f"**Mission:** {mission['statement']}{suffix}")
    if value_proposition.get("primary"):
        discipline = value_proposition["primary"]
        if value_proposition.get("secondary"):
            discipline += f" + {value_proposition['secondary']}"
        lines.append(f"**Value Proposition:** {discipline}")

    priorities = strategy_map.get("strategicPriorities", [])
    if priorities:
        lines.append("\n### Strategic Priorities")
        lines.extend(f"- {p.get('name', '?')}: {p.get('result', '')}" for p in priorities)

    lines.append("\n### Financial")
    lines.extend(
        _format_objective(o, opportunities)
        for o in strategy_map.get("financial", {}).get("objectives", [])
    )
    lines.append("\n### Customer")
    lines.extend(
        _format_objective(o, opportunities)
        for o in strategy_map.get("customer", {}).get("objectives", [])
    )
    lines.append("\n### Internal Processes")
    for theme in strategy_map.get("internalProcesses", {}).get("themes", []):
        lines.append(f"**{theme.get('name', '?')}**")
        lines.extend(_format_objective(o, opportunities) for o in theme.get("objectives", []))
    lines.append("\n### Organizational Capacity")
    capacity = strategy_map.get("organizationalCapacity", {})
    for facet in ("people", "technology", "culture"):
        if capacity.get(facet):
            lines.append(f"_{facet.title()}_")
            lines.append(_format_objective(capacity[facet], opportunities))

    core_values = strategy_map.get("coreValues", {})
    if core_values.get("values"):
        suffix = " (inferred)" if core_values.get("synthesised") else ""
        lines.append(f"\n### Core Values{suffix}")
        lines.append(", ".join(core_values["values"]))
    return "\n".join(lines)


def _format_scans(scans: list[dict[str, Any]]) -> str:
    """Render the org's scans as Markdown for an MCP client."""
    lines = [f"## Scans ({len(scans)})"]
    for scan in scans:
        line = (
            f"- {scan['id']} — {scan.get('status', 'unknown')} "
            f"({scan.get('type', 'unknown')}, {scan.get('progress', 0)}%)"
        )
        if scan.get("created_at"):
            line += f" — {scan['created_at']}"
        lines.append(line)
    return "\n".join(lines)

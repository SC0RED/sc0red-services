"""Context construction + summarisation helpers for strategy-map generation.

Extracted from `generate_strategy_map.py` to keep that file under the
400-line limit. Responsible for:

- Building the shared context dict that every step's template
  consumes (`build_shared_context`).
- Summarising perspective outputs back into context fragments for
  later steps (`summarise_*`).
- Walking generated objectives for cross-cutting checks
  (`walk_objectives`).
- Heuristic go-to-market inference for the customer-perspective
  prompt (`infer_go_to_market`).

These helpers are pure functions over the company / perspective dict
shapes; no AI calls, no I/O.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterator

    from src.models.model_company import Company

# Cap on the size of pipeline-input fragments fed back into AI prompts.
# Strategy-map prompts include scraped text, opportunities, EBITDA
# tree, and value chain — but the LLM only needs enough context to
# reason. Truncating here keeps total prompt size bounded.
MAX_SCRAPED_TEXT_CHARS = 6_000
MAX_DOCUMENT_TEXT_CHARS = 6_000
MAX_JSON_FRAGMENT_CHARS = 4_000


def build_shared_context(company: Company) -> dict[str, Any]:
    """Build the variable-substitution dict used by every step's template.

    Pulls from the company's pipeline outputs: profile, risk
    assessment, opportunity result, EBITDA tree, value chain, and any
    user-uploaded document text. Computes summary fragments
    (truncated JSON, signal subsets) for the templates to slot in.
    """
    profile = company.profile
    opportunities = company.opportunity_result.opportunities if company.opportunity_result else []
    ebitda_tree = company.ebitda_tree
    value_chain = company.value_chain
    risk_scores = company.risk_assessment.risk_scores if company.risk_assessment else []

    customer_risk_categories = {"customer_behavior", "competitive_displacement"}
    customer_risk_signals = [
        {"category": rs.category, "score": rs.score, "rationale": rs.rationale}
        for rs in risk_scores
        if rs.category in customer_risk_categories
    ]

    operational_risk_categories = {
        "margin_compression",
        "supply_chain",
        "regulatory_compliance",
    }
    operational_risk_signals = [
        {"category": rs.category, "score": rs.score, "rationale": rs.rationale}
        for rs in risk_scores
        if rs.category in operational_risk_categories
    ]

    talent_risk = next(
        (rs for rs in risk_scores if rs.category == "talent_workforce"),
        None,
    )

    revenue_opportunities = [
        opp.model_dump() for opp in opportunities if opp.value_lever in ("Revenue Side", "Both")
    ]
    opportunity_categories = sorted(
        {opp.strategic_category for opp in opportunities if opp.strategic_category}
    )

    return {
        "company_name": company.company_name,
        "company_url": company.url,
        "industry": profile.industry if profile else "",
        "scraped_content": truncate(company.scraped_text, MAX_SCRAPED_TEXT_CHARS),
        "document_text": truncate(company.document_text or "", MAX_DOCUMENT_TEXT_CHARS),
        "opportunity_categories": ", ".join(opportunity_categories) or "(none)",
        "value_chain_summary": truncate(
            value_chain.summary if value_chain else "", MAX_JSON_FRAGMENT_CHARS
        ),
        "ebitda_tree": truncate(
            json.dumps(ebitda_tree.model_dump()) if ebitda_tree else "{}",
            MAX_JSON_FRAGMENT_CHARS,
        ),
        "revenue_estimate": ebitda_tree.revenue_estimate if ebitda_tree else "(unknown)",
        "ebitda_estimate": ebitda_tree.ebitda_estimate if ebitda_tree else "(unknown)",
        "top_opportunities": truncate(
            json.dumps([o.model_dump() for o in opportunities[:5]]),
            MAX_JSON_FRAGMENT_CHARS,
        ),
        "value_chain": truncate(
            json.dumps(value_chain.model_dump()) if value_chain else "{}",
            MAX_JSON_FRAGMENT_CHARS,
        ),
        "opportunities": truncate(
            json.dumps([o.model_dump() for o in opportunities]),
            MAX_JSON_FRAGMENT_CHARS,
        ),
        "customer_risk_signals": truncate(
            json.dumps(customer_risk_signals), MAX_JSON_FRAGMENT_CHARS
        ),
        "operational_risk_signals": truncate(
            json.dumps(operational_risk_signals), MAX_JSON_FRAGMENT_CHARS
        ),
        "revenue_opportunities": truncate(
            json.dumps(revenue_opportunities), MAX_JSON_FRAGMENT_CHARS
        ),
        "go_to_market_signal": infer_go_to_market(profile, opportunities),
        "talent_risk_score": talent_risk.score if talent_risk else "(unknown)",
        "talent_risk_rationale": talent_risk.rationale if talent_risk else "(no rationale)",
        "tech_signals": ", ".join(profile.tech_signals) if profile else "(unknown)",
        "tech_opportunities": truncate(
            json.dumps(
                [o.model_dump() for o in opportunities if "Technology" in o.strategic_category]
            ),
            MAX_JSON_FRAGMENT_CHARS,
        ),
        "published_values": "(none — synthesise from public materials)",
        "culture_signals": truncate(
            profile.description if profile else "", MAX_JSON_FRAGMENT_CHARS
        ),
    }


def summarise_value_proposition(value_proposition_data: dict[str, Any]) -> str:
    """One-line summary of the value-proposition classification for downstream prompts."""
    primary = value_proposition_data.get("primary", "(unspecified)")
    secondary = value_proposition_data.get("secondary")
    if primary == "hybrid" and secondary:
        return f"hybrid (primary blend: {secondary})"
    return str(primary)


def summarise_perspective(data: dict[str, Any]) -> str:
    """Truncated JSON dump of a perspective-step output for use as later-step context."""
    return truncate(json.dumps(data), MAX_JSON_FRAGMENT_CHARS)


def summarise_confidence(*perspectives: dict[str, Any]) -> str:
    """Brief tally of HIGH/MEDIUM/LOW confidence across all generated objectives."""
    counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for perspective in perspectives:
        for objective in walk_objectives(perspective):
            marker = objective.get("confidence")
            if marker in counts:
                counts[marker] += 1
    return f"HIGH={counts['HIGH']}, MEDIUM={counts['MEDIUM']}, LOW={counts['LOW']}"


def walk_objectives(perspective: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Yield every objective dict inside a perspective response, regardless of nesting."""
    objectives = perspective.get("objectives")
    if isinstance(objectives, list):
        yield from objectives
    themes = perspective.get("themes")
    if isinstance(themes, list):
        for theme in themes:
            if isinstance(theme, dict):
                theme_objectives = theme.get("objectives", [])
                if isinstance(theme_objectives, list):
                    yield from theme_objectives
    for key in ("people", "technology", "culture"):
        bucket = perspective.get(key)
        if isinstance(bucket, dict):
            yield bucket


def truncate(text: str, max_chars: int) -> str:
    """Hard-truncate a string to keep prompt sizes bounded."""
    if not text:
        return ""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n\n... [truncated for prompt size]"


def infer_go_to_market(profile: Any, _opportunities: list[Any]) -> str:
    """Best-effort inference of the company's go-to-market model.

    Used as a hint in the Customer-perspective prompt so the AI knows
    whether to add channel-relationship objectives. Heuristic, not
    authoritative — the resulting objective surfaces at MEDIUM
    confidence at best.

    `_opportunities` is currently unused but accepted to keep the
    signature stable; future heuristics can mine opportunity titles
    for channel signals (e.g. "dealer training", "marketplace
    partner programme").
    """
    if not profile:
        return "(unknown — synthesise from scraped content)"

    business_model = (profile.business_model or "").lower()
    description = (profile.description or "").lower()
    text = f"{business_model} {description}"

    if any(token in text for token in ("dealer", "distributor", "reseller", "franchise")):
        return (
            "channel-mediated (dealers / distributors / franchisees indicated in public materials)"
        )
    if any(token in text for token in ("marketplace", "two-sided", "platform")):
        return "marketplace / platform (two-sided)"
    if any(token in text for token in ("b2b", "enterprise", "saas")):
        return "direct B2B"
    if any(token in text for token in ("b2c", "consumer", "retail")):
        return "direct B2C"
    return "(unclear from public materials — flag for deep-dive)"


def unwrap_perspective(data: dict[str, Any], key: str) -> dict[str, Any]:
    """Normalise per-step responses that may or may not wrap under a top-level key.

    Some models return ``{"financial": {"objectives": [...]}}`` and
    others return ``{"objectives": [...]}`` directly. Tolerate both.
    """
    if key in data and isinstance(data[key], dict):
        return data[key]
    return data

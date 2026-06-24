"""Web-search portfolio recovery — shared by initial discovery and deepen.

When a firm's own site exposes no readable company list (client-side-rendered,
blocked, or genuinely sparse), web search is the recovery path. This module
owns the grounded-AI calls so both ``DiscoverPortfolio`` (single fallback pass)
and ``DeepenPortfolio`` (customer-triggered multi-pass) share one definition.

All calls are fail-soft: a search/AI failure or a schema-invalid response yields
no candidates rather than crashing the scan — only programming errors propagate.
Results are model-sourced CANDIDATES that the downstream validation step confirms.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import jsonschema
from signalfield_core.exceptions.base import EngineError
from signalfield_core.utilities.future_manager import FutureManagerError

from src.pipeline.pipeline_steps.ai_call import run_grounded_ai_call
from src.pipeline.pipeline_steps.portfolio_merge import normalize_url_key
from src.pipeline.prompts.loader import load_schema, load_system_prompt, load_template

if TYPE_CHECKING:
    from signalfield_core.services.ai_client_factory import AIClientFactory

logger = logging.getLogger(__name__)

# Distinct angles for the deepen multi-pass. Each pass is seeded with everything
# found so far so the model EXTENDS the list rather than repeating it; the angles
# push it toward holdings a single generic pass tends to miss.
_DEEP_PASS_ANGLES = [
    "Focus on the firm's most recent investments and newly announced deals.",
    "Focus on smaller, early-stage, or less widely-known holdings — not just the marquee names.",
    "Focus on holdings outside the firm's primary sector or in international markets.",
]


def _build_known_block(seed_names: list[str] | None) -> str:
    """Build the optional ``{known_companies}`` seed block for the prompt."""
    if not seed_names:
        return ""
    known = ", ".join(seed_names)
    return (
        "The firm's portfolio is known to include these companies "
        f"(found on its own site or an earlier pass): {known}.\n"
        "Return each of these companies' official website URL, and add "
        "any other current holdings you find."
    )


def run_web_search_discovery(
    ai_client_factory: AIClientFactory,
    firm_url: str,
    seed_names: list[str] | None = None,
    *,
    step_name: str = "DiscoverPortfolio",
    extra_instruction: str = "",
) -> list[dict[str, str]]:
    """Recover the firm's portfolio via a single grounded web-search pass.

    When ``seed_names`` is provided (e.g. logo-grid names), the prompt is seeded
    so the model resolves their official URLs rather than recalling from scratch.
    ``extra_instruction`` appends a pass-specific angle (used by the deepen
    multi-pass). Fail-soft — returns ``[]`` on any expected search/AI failure.
    """
    template = load_template("discover_portfolio_websearch")
    schema = load_schema("discover_portfolio_websearch")
    system_prompt = load_system_prompt("portfolio_validation")
    known_block = _build_known_block(seed_names)
    if extra_instruction:
        known_block = f"{known_block}\n{extra_instruction}".strip()
    prompt = template.format(firm_url=firm_url, known_companies=known_block)
    try:
        _label, content, _elapsed, _tokens, _sources = run_grounded_ai_call(
            ai_client_factory=ai_client_factory,
            user_prompt=prompt,
            schema=schema,
            system_prompt=system_prompt,
            label="portfolio_web_fallback",
            step_name=step_name,
        )
    except (
        EngineError,
        FutureManagerError,
        jsonschema.ValidationError,
        ValueError,
        RuntimeError,
        KeyError,
        TypeError,
    ):
        # Fail-soft: a search failure or a malformed (schema-invalid) AI response
        # yields no extra candidates — the scan continues on existing results.
        logger.exception(
            "[%s] web-search pass failed for %s; continuing without extra candidates",
            step_name,
            firm_url,
        )
        return []
    companies = content["companies"]
    logger.info(
        "[%s] web-search pass recovered %d candidate(s) for %s",
        step_name,
        len(companies),
        firm_url,
    )
    return companies


def run_deep_web_search_discovery(
    ai_client_factory: AIClientFactory,
    firm_url: str,
    seed_names: list[str],
    *,
    step_name: str = "DeepenPortfolio",
) -> list[dict[str, str]]:
    """Multi-pass deepen: several angled, seeded web-search passes, deduped.

    Each pass is seeded with the running union of known names so later passes
    extend rather than repeat. Sequential (not parallel) so each pass can be
    seeded with the previous passes' finds. Returns the union of NEW candidates
    keyed by normalized URL, excluding the seed companies already known.
    """
    known_names = list(seed_names)
    seen_keys: set[str] = set()
    recovered: list[dict[str, str]] = []
    for index, angle in enumerate(_DEEP_PASS_ANGLES):
        results = run_web_search_discovery(
            ai_client_factory,
            firm_url,
            known_names,
            step_name=step_name,
            extra_instruction=angle,
        )
        for company in results:
            key = normalize_url_key(company["url"])
            if not key or key in seen_keys:
                continue
            seen_keys.add(key)
            recovered.append(company)
            known_names.append(company["name"])
        logger.info(
            "[%s] deepen pass %d/%d: %d unique candidate(s) so far for %s",
            step_name,
            index + 1,
            len(_DEEP_PASS_ANGLES),
            len(recovered),
            firm_url,
        )
    return recovered

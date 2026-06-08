"""Decomposed financial-research orchestrator (the question DAG).

Replaces the deterministic industry templates: instead of keyword-matching a
company to a hardcoded P&L, we ask the model a set of small, sharply-scoped
questions and assemble the answers. Independent questions run in parallel within
a round (via ``FutureManager``); dependent questions run in the next round. Two
questions (disclosed figures, revenue range) enable the provider's native web
search to ground quantitative facts; the rest rely on the model's knowledge.

This module owns ONLY the research (the ``FinancialResearchFacts`` it returns);
the EBITDA-tree / value-chain assembly over those facts lives in the assembler
modules. See the ``decomposed-financial-research`` + ``web-search-grounding``
capabilities. All AI calls go through ``run_structured_ai_call`` /
``run_grounded_ai_call``; parallelism uses ``FutureManager`` (never raw threads).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from signalfield_core.utilities.future_manager import FutureManager

from src.pipeline.pipeline_steps.ai_call import run_grounded_ai_call, run_structured_ai_call
from src.pipeline.prompts.loader import load_schema, load_system_prompt, load_template

if TYPE_CHECKING:
    from signalfield_core.models.ai_response import WebSearchSource
    from signalfield_core.services.ai_client_factory import AIClientFactory

STEP_NAME = "FinancialResearch"
_MAX_SCRAPED_TEXT_CHARS = 12000
_MAX_WORKERS = 10


@dataclass
class FinancialResearchFacts:
    """Structured output of the research DAG — consumed by the assemblers.

    Each ``*`` field is the validated content dict of the corresponding question
    (keys match that question's schema). ``citations`` maps a question label to
    the ``web_sources`` returned for it (only the searched questions populate it).
    ``revenue_model_plausible`` is the adversarial verification verdict.
    """

    company_type: str
    revenue_model: dict[str, Any]
    disclosed_figures: dict[str, Any]
    scale_signals: dict[str, Any]
    revenue_mix: dict[str, Any]
    margins: dict[str, Any]
    revenue_range: dict[str, Any]
    cost_drivers: dict[str, Any]
    operating_steps: dict[str, Any]
    revenue_model_plausible: bool
    citations: dict[str, list[WebSearchSource]] = field(default_factory=dict)


def run_financial_research(
    ai_client_factory: AIClientFactory,
    *,
    company_name: str,
    url: str,
    industry: str,
    scraped_text: str,
    document_text: str = "",
) -> FinancialResearchFacts:
    """Run the two-round research DAG and return the assembled facts.

    Round 1 (parallel, independent): company_type, revenue_model,
    disclosed_figures (web search), scale_signals.
    Round 2 (parallel, depends on R1): revenue_mix, margin_band, revenue_range
    (web search), cost_drivers, operating_steps, and the revenue-model
    plausibility verification.
    """
    system_prompt = load_system_prompt("financial_research")
    scraped = scraped_text[:_MAX_SCRAPED_TEXT_CHARS]
    if document_text:
        scraped = (
            f"{scraped}\n\n--- ATTACHED DOCUMENTS ---\n{document_text[:_MAX_SCRAPED_TEXT_CHARS]}"
        )
    base_vars: dict[str, Any] = {
        "company_name": company_name,
        "url": url,
        "industry": industry,
        "scraped_text": scraped,
    }

    # ── Round 1 ────────────────────────────────────────────────────────────
    round1 = _run_round(
        ai_client_factory,
        system_prompt,
        [
            _Q("company_type", base_vars, grounded=False),
            _Q("revenue_model", base_vars, grounded=False),
            _Q("disclosed_figures", base_vars, grounded=True),
            _Q("scale_signals", base_vars, grounded=False),
        ],
    )
    revenue_model = round1["revenue_model"].content

    # ── Round 2 (depends on R1) ──────────────────────────────────────────────
    r2_vars = {
        **base_vars,
        "company_type": round1["company_type"].content["company_type"],
        "revenue_model": revenue_model["revenue_model"],
        "fee_structure": revenue_model["fee_structure"],
        "scale_signals": _summarise(round1["scale_signals"].content),
        "disclosed_figures": _summarise(round1["disclosed_figures"].content),
    }
    round2 = _run_round(
        ai_client_factory,
        system_prompt,
        [
            _Q("revenue_mix", r2_vars, grounded=False),
            _Q("margin_band", r2_vars, grounded=False),
            _Q("revenue_range", r2_vars, grounded=True),
            _Q("cost_drivers", r2_vars, grounded=False),
            _Q("operating_steps", r2_vars, grounded=False),
            _Q("verify_revenue_model", r2_vars, grounded=False),
        ],
    )

    citations: dict[str, list[WebSearchSource]] = {}
    all_answers = {**round1, **round2}
    for label in ("disclosed_figures", "revenue_range"):
        answer = all_answers.get(label)
        if answer and answer.web_sources:
            citations[label] = answer.web_sources

    return FinancialResearchFacts(
        company_type=round1["company_type"].content["company_type"],
        revenue_model=revenue_model,
        disclosed_figures=round1["disclosed_figures"].content,
        scale_signals=round1["scale_signals"].content,
        revenue_mix=round2["revenue_mix"].content,
        margins=round2["margin_band"].content,
        revenue_range=round2["revenue_range"].content,
        cost_drivers=round2["cost_drivers"].content,
        operating_steps=round2["operating_steps"].content,
        revenue_model_plausible=bool(round2["verify_revenue_model"].content["plausible"]),
        citations=citations,
    )


# ---------------------------------------------------------------------------
# Round execution
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Q:
    """A single research question to execute in a round."""

    name: str
    render_vars: dict[str, Any]
    grounded: bool


@dataclass
class _Answer:
    """A question's validated content plus any web-search sources."""

    content: dict[str, Any]
    web_sources: list[WebSearchSource]


def _run_round(
    ai_client_factory: AIClientFactory,
    system_prompt: str,
    questions: list[_Q],
) -> dict[str, _Answer]:
    """Execute a round of questions in parallel; return answers keyed by name."""
    results: list[tuple[str, _Answer]] = []
    with FutureManager(name=f"{STEP_NAME}Round", max_workers=_MAX_WORKERS) as manager:
        for question in questions:
            manager.submit_task(_execute_question, ai_client_factory, system_prompt, question)
        results = manager.wait_for_all_and_collect_results()
    return dict(results)


def _execute_question(
    ai_client_factory: AIClientFactory,
    system_prompt: str,
    question: _Q,
) -> tuple[str, _Answer]:
    """Render + execute one question via the shared AI-call path."""
    user_prompt = _render(question.name, question.render_vars)
    schema = load_schema(f"financial/{question.name}")
    if question.grounded:
        _, content, _elapsed, _tokens, web_sources = run_grounded_ai_call(
            ai_client_factory=ai_client_factory,
            user_prompt=user_prompt,
            schema=schema,
            system_prompt=system_prompt,
            label=question.name,
            step_name=STEP_NAME,
        )
        return question.name, _Answer(content=content, web_sources=web_sources)
    _, content, _elapsed, _tokens = run_structured_ai_call(
        ai_client_factory=ai_client_factory,
        user_prompt=user_prompt,
        schema=schema,
        system_prompt=system_prompt,
        label=question.name,
        step_name=STEP_NAME,
    )
    return question.name, _Answer(content=content, web_sources=[])


def _render(name: str, render_vars: dict[str, Any]) -> str:
    """Render a financial-research template with the given variables.

    Uses ``str.format`` with a superset of keys (unused keys are ignored).
    Scraped/disclosed values are inserted verbatim — only the static template
    string is parsed, so braces inside the content are harmless.
    """
    return load_template(f"financial/{name}").format(**render_vars)


def _summarise(content: dict[str, Any]) -> str:
    """Compact a Round-1 answer dict into a short string for a Round-2 prompt."""
    parts = [f"{key}: {value}" for key, value in content.items() if key != "basis"]
    return "; ".join(parts) if parts else "(none)"

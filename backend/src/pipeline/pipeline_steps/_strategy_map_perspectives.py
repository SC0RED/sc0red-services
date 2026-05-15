"""Decomposed perspective generation for the strategy-map step.

  Round 1 — title lists (4 calls in parallel, one per perspective):
    - financial:  {titles: [t1, t2, t3]}
    - customer:   {titles: [t1, t2, t3, t4]}
    - internal:   {themes: [{name, supports_financial_objectives}]}
    - capacity:   {people: t, technology: t, culture: t}

  Round 2 — details + internal-theme titles + core values (parallel,
    ~13 calls). See ``_strategy_map_perspective_rounds.py`` for the
    implementation.

  Round 3 — internal-processes per-objective details (parallel, ~9
    calls). Same helper module.

Each call goes through ``run_structured_ai_call``, parallel blocks use
``FutureManager``, and per-call elapsed times are recorded on the
shared ``StepTimer`` (matching the pattern other AI-heavy pipeline
steps already use).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from signalfield_core.utilities.future_manager import FutureManager

from src.pipeline.pipeline_steps._strategy_map_assembly import (
    build_capacity_objectives,
    build_customer_objectives,
    build_financial_objectives,
    build_internal_themes,
)
from src.pipeline.pipeline_steps._strategy_map_corpus import (
    load_decomposed_template,
    load_per_call_schema,
)
from src.pipeline.pipeline_steps._strategy_map_perspective_rounds import (
    run_round2_details_and_internal_titles,
    run_round3_internal_details,
)

if TYPE_CHECKING:
    from src.pipeline.pipeline_steps.ai_call import TokenCounts
    from src.pipeline.pipeline_steps.generate_strategy_map import GenerateStrategyMap
    from src.pipeline.step_timer import StepTimer

# Optional 0-100 percent / label callable invoked at three intra-step
# phase boundaries (after Round 1, after Round 2, after Round 3). The
# inline scan pipeline currently passes ``None`` — the scan's own
# ``mark_question_complete`` flow is granular enough at the step level.
# The hook is retained so a future caller (e.g. a debug-CLI driver) can
# re-enable phase-boundary visibility without touching this module.
ProgressEmitter = Callable[[int, str], None]

# Cap on parallelism within Round 1. Round 2 / Round 3 caps live with
# their implementations in ``_strategy_map_perspective_rounds.py``.
_ROUND1_MAX_WORKERS = 4

_SCHEMA_CACHE: dict[str, dict[str, Any]] = {}
_PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


def _schema(name: str) -> dict[str, Any]:
    """Memoised per-call schema lookup."""
    if name not in _SCHEMA_CACHE:
        _SCHEMA_CACHE[name] = load_per_call_schema(name)
    return _SCHEMA_CACHE[name]


def _render(name: str, context: dict[str, Any]) -> str:
    """Render a decomposed template with `{key}` placeholder substitution.

    Single-token placeholders only; JSON braces with whitespace or
    nested content are left untouched so example JSON in the template
    body doesn't collide with the placeholder syntax.
    """
    template = load_decomposed_template(name)

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key in context:
            return str(context[key])
        return "(unknown)"

    return _PLACEHOLDER_RE.sub(replace, template)


def generate_perspectives_decomposed(
    step: GenerateStrategyMap,
    *,
    system_prompt: str,
    context: dict[str, Any],
    timer: StepTimer,
    progress_emitter: ProgressEmitter | None = None,
) -> tuple[
    dict[str, Any],  # financial perspective ({"objectives": [...]})
    dict[str, Any],  # customer perspective ({"objectives": [...]})
    dict[str, Any],  # internal-processes perspective ({"themes": [...]})
    dict[str, Any],  # organizational-capacity ({"people", "technology", "culture"})
    dict[str, Any],  # core values ({"values", "synthesised", "rationale"})
]:
    """Run the decomposed perspective generation chain.

    Returns the four perspectives in the same shape ``assemble_strategy_map``
    expects — the calling site in ``generate_strategy_map.py`` cannot tell
    whether the decomposed or the legacy single-call path produced them.

    The ``step`` argument is the GenerateStrategyMap instance whose
    ``_run_ai_call`` method we delegate to; this keeps all AI invocation
    funneled through one place (per CLAUDE.md mandatory pattern).

    ``progress_emitter`` is an optional 0-100 percent / label callable
    invoked at three phase boundaries so the frontend can replace its
    static spinner with a moving progress bar. ``None`` disables
    emission (used by tests + any caller that doesn't care).
    """

    def _emit(progress: int, label: str) -> None:
        if progress_emitter is not None:
            progress_emitter(progress, label)

    # ── Round 1: 4 parallel title-list calls (one per perspective). ──
    round1_results = _run_round1_titles(
        step, system_prompt=system_prompt, context=context, timer=timer
    )
    financial_titles: list[str] = round1_results["financial"]["titles"]
    customer_titles: list[str] = round1_results["customer"]["titles"]
    internal_themes_meta: list[dict[str, Any]] = round1_results["internal"]["themes"]
    capacity_titles: dict[str, str] = round1_results["capacity"]

    _emit(30, "Elaborating perspective objectives…")

    # Sibling-text for Round 2's capacity detail prompts. Capacity is
    # bucket-keyed (3 fixed buckets), so each detail call sees ALL three
    # bucket titles as sibling context — the prompt template warns the
    # AI not to confuse buckets, not to differentiate from itself.
    # Financial / customer sibling lists are built per-call inside the
    # round runner (one without each call's own title) so the prompt
    # never contains the title being elaborated as a "sibling".
    capacity_titles_text = _format_capacity_titles(capacity_titles)

    # ── Round 2: details + per-theme internal titles + core values. ──
    round2_results = run_round2_details_and_internal_titles(
        step,
        render=_render,
        schema_lookup=_schema,
        system_prompt=system_prompt,
        context=context,
        timer=timer,
        financial_titles=financial_titles,
        customer_titles=customer_titles,
        capacity_titles=capacity_titles,
        internal_themes_meta=internal_themes_meta,
        capacity_titles_text=capacity_titles_text,
    )

    financial_details = round2_results["financial_details"]
    customer_details = round2_results["customer_details"]
    capacity_details = round2_results["capacity_details"]
    titles_per_theme = round2_results["titles_per_theme"]
    core_values = round2_results["core_values"]

    _emit(60, "Mapping internal processes…")

    # ── Round 3: internal-processes per-objective details. ──
    details_per_theme = run_round3_internal_details(
        step,
        render=_render,
        schema_lookup=_schema,
        system_prompt=system_prompt,
        context=context,
        timer=timer,
        themes_meta=internal_themes_meta,
        titles_per_theme=titles_per_theme,
    )

    _emit(80, "Synthesising strategic priorities…")

    # Assemble per-perspective dicts in the shape ``assemble_strategy_map`` expects.
    financial = {"objectives": build_financial_objectives(financial_titles, financial_details)}
    customer = {"objectives": build_customer_objectives(customer_titles, customer_details)}
    internal = {
        "themes": build_internal_themes(internal_themes_meta, titles_per_theme, details_per_theme)
    }
    capacity = build_capacity_objectives(capacity_titles, capacity_details)

    return financial, customer, internal, capacity, core_values


def _run_round1_titles(
    step: GenerateStrategyMap,
    *,
    system_prompt: str,
    context: dict[str, Any],
    timer: StepTimer,
) -> dict[str, Any]:
    """Run all four perspective title-list calls in parallel."""
    tasks = [
        ("titles_financial", "round1_titles_financial", _schema("financial_titles")),
        ("titles_customer", "round1_titles_customer", _schema("customer_titles")),
        ("themes_internal", "round1_themes_internal", _schema("internal_themes")),
        ("titles_capacity", "round1_titles_capacity", _schema("capacity_titles")),
    ]

    collected: list[tuple[str, dict[str, Any], float, TokenCounts]] = []
    with FutureManager(name="GenerateStrategyMap.R1", max_workers=_ROUND1_MAX_WORKERS) as manager:
        for label, template_name, schema in tasks:
            manager.submit_task(
                step._run_ai_call,
                _render(template_name, context),
                schema,
                system_prompt,
                label,
            )
        collected = manager.wait_for_all_and_collect_results()

    for label, _data, elapsed, tokens in collected:
        timer.record(f"ai_call_{label}", elapsed)
        timer.record_tokens(f"ai_call_{label}", tokens)

    by_label: dict[str, dict[str, Any]] = {label: data for label, data, _e, _t in collected}
    return {
        "financial": by_label["titles_financial"],
        "customer": by_label["titles_customer"],
        "internal": by_label["themes_internal"],
        "capacity": by_label["titles_capacity"],
    }


# ── Sibling-text formatters ──────────────────────────────────────────────


def _format_capacity_titles(titles: dict[str, str]) -> str:
    """Format the capacity bucket→title mapping for sibling-context display."""
    return "\n".join(f"- {bucket.capitalize()}: {title}" for bucket, title in titles.items())

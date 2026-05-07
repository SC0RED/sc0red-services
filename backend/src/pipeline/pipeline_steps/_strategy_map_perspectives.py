"""Decomposed perspective generation for the strategy-map step.

Implements `optimize-strategy-map-latency` Phase 1 — replaces the four
sequential single-call-per-perspective AI rounds (~30s combined) with a
two-phase / three-phase pattern that parallelises elaboration:

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
steps already use). See the optimize-strategy-map-latency design.md
Decisions §1, §2, §3, §4 for the full rationale.

This module is invoked from ``generate_strategy_map.py`` ONLY when the
``GENERATE_STRATEGY_MAP_DECOMPOSED=1`` env var is set. Otherwise the
existing single-call-per-perspective path runs unchanged.
"""

from __future__ import annotations

import re
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
    from src.pipeline.pipeline_steps.generate_strategy_map import GenerateStrategyMap
    from src.pipeline.step_timer import StepTimer

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

    Mirrors the regex behaviour in ``_strategy_map_corpus.render_template``
    (single-token placeholders only, JSON braces ignored). Decomposed
    templates live under ``templates/decomposed/`` rather than
    ``templates/``, so the existing renderer cannot be re-used directly —
    this adapter loads from the decomposed loader instead.
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
    """
    # ── Round 1: 4 parallel title-list calls (one per perspective). ──
    round1_results = _run_round1_titles(
        step, system_prompt=system_prompt, context=context, timer=timer
    )
    financial_titles: list[str] = round1_results["financial"]["titles"]
    customer_titles: list[str] = round1_results["customer"]["titles"]
    internal_themes_meta: list[dict[str, Any]] = round1_results["internal"]["themes"]
    capacity_titles: dict[str, str] = round1_results["capacity"]

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

    collected: list[tuple[str, dict[str, Any], float]] = []
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

    for label, _data, elapsed in collected:
        timer.record(f"ai_call_{label}", elapsed)

    by_label: dict[str, dict[str, Any]] = {label: data for label, data, _e in collected}
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

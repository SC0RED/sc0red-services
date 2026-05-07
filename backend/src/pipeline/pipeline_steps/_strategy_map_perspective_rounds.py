"""Round 2 + Round 3 implementations for the decomposed perspectives flow.

Extracted from ``_strategy_map_perspectives.py`` to keep that module
under the 400-line frontend file-size limit. The public entry point
``generate_perspectives_decomposed`` lives in the parent module and
delegates here for the two heaviest parallel blocks:

  - Round 2: financial / customer / capacity details + internal-theme
    title lists + core values (parallel, ~13 calls).
  - Round 3: internal-processes per-objective details (parallel, ~9 calls).

Both rounds use the parent module's ``_render`` / ``_schema`` helpers
so all template-loading and schema-resolution stays in one place.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from signalfield_core.utilities.future_manager import FutureManager

if TYPE_CHECKING:
    from src.pipeline.pipeline_steps.generate_strategy_map import GenerateStrategyMap
    from src.pipeline.step_timer import StepTimer

# Cap on parallelism per round. Match the values in the parent module.
_ROUND2_MAX_WORKERS = 20
_ROUND3_MAX_WORKERS = 9

# Type aliases for the renderer + schema-lookup callables passed in from
# the parent module. Defined here (not imported) to avoid a circular
# import — the parent module imports the round runners from this module.
_RenderCallable = Callable[[str, dict[str, Any]], str]
_SchemaLookupCallable = Callable[[str], dict[str, Any]]


def _format_siblings(titles: list[str], current_index: int) -> str:
    """Bullet-list every title EXCEPT the one at ``current_index``.

    Each Round 2 / Round 3 detail call elaborates ONE objective; the
    sibling list provided in its prompt must omit that objective so the
    AI is asked to differentiate from peers, not from itself. Falling
    back to ``"(none)"`` when there are no siblings keeps the prompt
    template's placeholder substitution sane.
    """
    siblings = [title for index, title in enumerate(titles) if index != current_index]
    if not siblings:
        return "(none)"
    return "\n".join(f"- {sibling}" for sibling in siblings)


def run_round2_details_and_internal_titles(
    step: GenerateStrategyMap,
    *,
    render: _RenderCallable,
    schema_lookup: _SchemaLookupCallable,
    system_prompt: str,
    context: dict[str, Any],
    timer: StepTimer,
    financial_titles: list[str],
    customer_titles: list[str],
    capacity_titles: dict[str, str],
    internal_themes_meta: list[dict[str, Any]],
    capacity_titles_text: str,
) -> dict[str, Any]:
    """Run all Round 2 calls in parallel and split out by category.

    Returns a dict with keys:
      - ``financial_details``: list aligned with financial_titles
      - ``customer_details``:  list aligned with customer_titles
      - ``capacity_details``:  dict keyed by bucket
      - ``titles_per_theme``:  list of title-lists (aligned with themes_meta)
      - ``core_values``:       full {values, synthesised, rationale} dict
    """
    collected: list[tuple[str, dict[str, Any], float]] = []
    with FutureManager(name="GenerateStrategyMap.R2", max_workers=_ROUND2_MAX_WORKERS) as manager:
        # Financial details (one per title). Sibling text is computed
        # PER CALL so each call's prompt sees the OTHER titles only,
        # never its own — otherwise the "do NOT elaborate these" rule
        # in the prompt is self-contradictory.
        for index, title in enumerate(financial_titles):
            sub_context = {
                **context,
                "objective_title": title,
                "sibling_titles": _format_siblings(financial_titles, index),
            }
            manager.submit_task(
                step._run_ai_call,
                render("round2_detail_financial", sub_context),
                schema_lookup("financial_objective_detail"),
                system_prompt,
                f"detail_financial_F{index + 1}",
            )

        # Customer details — same per-call sibling-list pattern.
        for index, title in enumerate(customer_titles):
            sub_context = {
                **context,
                "objective_title": title,
                "sibling_titles": _format_siblings(customer_titles, index),
            }
            manager.submit_task(
                step._run_ai_call,
                render("round2_detail_customer", sub_context),
                schema_lookup("customer_objective_detail"),
                system_prompt,
                f"detail_customer_C{index + 1}",
            )

        # Capacity details (one per fixed bucket: people, technology, culture)
        for bucket in ("people", "technology", "culture"):
            sub_context = {
                **context,
                "bucket": bucket,
                "objective_title": capacity_titles[bucket],
                "sibling_titles": capacity_titles_text,
            }
            manager.submit_task(
                step._run_ai_call,
                render("round2_detail_capacity", sub_context),
                schema_lookup("capacity_objective_detail"),
                system_prompt,
                f"detail_capacity_{bucket}",
            )

        # Internal — per-theme objective title lists (Round 2 for internal)
        for theme_index, theme in enumerate(internal_themes_meta):
            siblings = (
                ", ".join(t["name"] for j, t in enumerate(internal_themes_meta) if j != theme_index)
                or "(none)"
            )
            sub_context = {
                **context,
                "theme_name": theme["name"],
                "supports_financial_objectives": ", ".join(theme["supports_financial_objectives"]),
                "sibling_theme_names": siblings,
            }
            manager.submit_task(
                step._run_ai_call,
                render("round2_titles_internal_per_theme", sub_context),
                schema_lookup("internal_titles_per_theme"),
                system_prompt,
                f"titles_internal_T{theme_index + 1}",
            )

        # Core values — runs in parallel with the detail block. Both
        # vision_statement and mission_statement are written to context
        # by Step 1 in `generate_strategy_map.execute()` BEFORE this
        # function is called. Hard-key access here (not `.get(...)` with
        # a silent default) so a future refactor that drops the Step 1
        # write surfaces as a KeyError rather than producing an empty
        # vision/mission for the AI to hallucinate around.
        manager.submit_task(
            step._run_ai_call,
            render(
                "round1_core_values",
                {
                    **context,
                    "vision_statement": context["vision_statement"],
                    "mission_statement": context["mission_statement"],
                },
            ),
            schema_lookup("core_values"),
            system_prompt,
            "core_values",
        )

        collected = manager.wait_for_all_and_collect_results()

    for label, _data, elapsed in collected:
        timer.record(f"ai_call_{label}", elapsed)

    by_label: dict[str, dict[str, Any]] = {label: data for label, data, _e in collected}

    financial_details = [
        by_label[f"detail_financial_F{index + 1}"] for index in range(len(financial_titles))
    ]
    customer_details = [
        by_label[f"detail_customer_C{index + 1}"] for index in range(len(customer_titles))
    ]
    capacity_details = {
        bucket: by_label[f"detail_capacity_{bucket}"]
        for bucket in ("people", "technology", "culture")
    }
    titles_per_theme = [
        by_label[f"titles_internal_T{theme_index + 1}"]["titles"]
        for theme_index in range(len(internal_themes_meta))
    ]
    core_values = by_label["core_values"]

    return {
        "financial_details": financial_details,
        "customer_details": customer_details,
        "capacity_details": capacity_details,
        "titles_per_theme": titles_per_theme,
        "core_values": core_values,
    }


def run_round3_internal_details(
    step: GenerateStrategyMap,
    *,
    render: _RenderCallable,
    schema_lookup: _SchemaLookupCallable,
    system_prompt: str,
    context: dict[str, Any],
    timer: StepTimer,
    themes_meta: list[dict[str, Any]],
    titles_per_theme: list[list[str]],
) -> list[list[dict[str, Any]]]:
    """Run one detail call per (theme, objective) pair, flattened in parallel.

    Returns a list of detail-lists aligned with ``titles_per_theme``.
    """
    collected: list[tuple[str, dict[str, Any], float]] = []
    with FutureManager(name="GenerateStrategyMap.R3", max_workers=_ROUND3_MAX_WORKERS) as manager:
        for theme_index, (theme, titles) in enumerate(
            zip(themes_meta, titles_per_theme, strict=True)
        ):
            for obj_index, title in enumerate(titles):
                siblings = ", ".join(t for j, t in enumerate(titles) if j != obj_index) or "(none)"
                sub_context = {
                    **context,
                    "theme_name": theme["name"],
                    "supports_financial_objectives": ", ".join(
                        theme["supports_financial_objectives"]
                    ),
                    "objective_title": title,
                    "sibling_titles": siblings,
                }
                manager.submit_task(
                    step._run_ai_call,
                    render("round3_detail_internal", sub_context),
                    schema_lookup("internal_objective_detail"),
                    system_prompt,
                    f"detail_internal_T{theme_index + 1}_O{obj_index + 1}",
                )
        collected = manager.wait_for_all_and_collect_results()

    for label, _data, elapsed in collected:
        timer.record(f"ai_call_{label}", elapsed)

    by_label: dict[str, dict[str, Any]] = {label: data for label, data, _e in collected}

    details_per_theme: list[list[dict[str, Any]]] = []
    for theme_index, titles in enumerate(titles_per_theme):
        theme_details = [
            by_label[f"detail_internal_T{theme_index + 1}_O{obj_index + 1}"]
            for obj_index in range(len(titles))
        ]
        details_per_theme.append(theme_details)

    return details_per_theme

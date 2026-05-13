"""Decomposed vision/mission and value-proposition generation for the strategy-map step.

  Vision/Mission bank (4 calls in parallel):
    - vision_text       → vision prose only
    - mission_text      → mission prose only
    - vision_synth      → synthesised flag + rationale for the vision
    - mission_synth     → synthesised flag + rationale for the mission

  Value Proposition bank (4 calls in parallel):
    - vp_primary        → primary classifier (operational_excellence | …)
    - vp_secondary      → secondary classifier (only used when primary == hybrid)
    - vp_exemplar       → exemplar company prose
    - vp_rationale      → rationale prose

Each call goes through ``run_structured_ai_call``, parallel blocks use
``FutureManager``, and per-call elapsed times are recorded on the
shared ``StepTimer``.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from signalfield_core.utilities.future_manager import FutureManager

from src.pipeline.pipeline_steps._strategy_map_corpus import (
    load_decomposed_template,
    load_per_call_schema,
)

if TYPE_CHECKING:
    from src.pipeline.pipeline_steps.generate_strategy_map import GenerateStrategyMap
    from src.pipeline.step_timer import StepTimer

# Cap on parallelism within each bank. Sized to the bank's own call
# count — never larger, so we don't starve unrelated work.
_VISION_MISSION_MAX_WORKERS = 4
_VALUE_PROPOSITION_MAX_WORKERS = 4

_SCHEMA_CACHE: dict[str, dict[str, Any]] = {}
_PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


def _schema(name: str) -> dict[str, Any]:
    """Memoised per-call schema lookup.

    Identical to the helper in ``_strategy_map_perspectives.py`` — kept
    module-local so each decomposed module owns its cache and module
    initialisation order doesn't matter.
    """
    if name not in _SCHEMA_CACHE:
        _SCHEMA_CACHE[name] = load_per_call_schema(name)
    return _SCHEMA_CACHE[name]


def _render(name: str, context: dict[str, Any]) -> str:
    """Render a decomposed template with ``{key}`` placeholder substitution.

    Mirrors ``_strategy_map_perspectives._render`` — single-token
    placeholders only, JSON braces ignored, missing keys substituted
    with ``(unknown)``.
    """
    template = load_decomposed_template(name)

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key in context:
            return str(context[key])
        return "(unknown)"

    return _PLACEHOLDER_RE.sub(replace, template)


def run_decomposed_vision_mission(
    step: GenerateStrategyMap,
    *,
    system_prompt: str,
    context: dict[str, Any],
    timer: StepTimer,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Run the 4-call vision/mission decomposition and assemble.

    Returns ``(vision_dict, mission_dict)`` matching the shape Step 1's
    single call produces today — the calling site cannot tell whether
    the decomposed or monolithic path produced the result.

    Both sub-banks (vision_text + vision_synth and mission_text +
    mission_synth) run in a single ``FutureManager`` block at
    ``max_workers=4`` so all four calls overlap. Assembly merges the
    text and the synth fields into the assembled dicts.
    """
    tasks: list[tuple[str, str, dict[str, Any]]] = [
        ("vision_text", "vision_text", _schema("vision_text")),
        ("mission_text", "mission_text", _schema("mission_text")),
        ("vision_synth", "vision_synth", _schema("synth_yesno")),
        ("mission_synth", "mission_synth", _schema("synth_yesno")),
    ]

    collected: list[tuple[str, dict[str, Any], float]] = []
    with FutureManager(
        name="GenerateStrategyMap.synthesis_vm",
        max_workers=_VISION_MISSION_MAX_WORKERS,
    ) as manager:
        for label, template_name, schema in tasks:
            manager.submit_task(
                step._run_ai_call,
                _render(template_name, context),
                schema,
                system_prompt,
                label,
            )
        collected = manager.wait_for_all_and_collect_results()

    # Record per-call elapsed before returning. CloudWatch sees
    # ``ai_call_vision_text``, ``ai_call_mission_text``,
    # ``ai_call_vision_synth``, ``ai_call_mission_synth``.
    for label, _data, elapsed in collected:
        timer.record(f"ai_call_{label}", elapsed)

    by_label: dict[str, dict[str, Any]] = {label: data for label, data, _e in collected}

    vision = {
        "statement": by_label["vision_text"]["statement"],
        "synthesised": by_label["vision_synth"]["synthesised"],
        "rationale": by_label["vision_synth"]["rationale"],
    }
    mission = {
        "statement": by_label["mission_text"]["statement"],
        "synthesised": by_label["mission_synth"]["synthesised"],
        "rationale": by_label["mission_synth"]["rationale"],
    }
    return vision, mission


def run_decomposed_value_proposition(
    step: GenerateStrategyMap,
    *,
    system_prompt: str,
    context: dict[str, Any],
    timer: StepTimer,
) -> dict[str, Any]:
    """Run the 4-call value-proposition decomposition and assemble.

    Returns a dict shaped like the existing Step 2 output — keys
    ``primary``, ``secondary``, ``rationale``, ``exemplar_company``.

    All four calls run in parallel. ``vp_secondary`` always runs but
    its result is only honoured in the assembled output when
    ``primary == "hybrid"`` (per design Decision §2). The discarded
    secondary call costs a few extra tokens; the tradeoff is a tighter
    latency envelope vs sequential conditional logic.
    """
    tasks: list[tuple[str, str, dict[str, Any]]] = [
        ("vp_primary", "vp_primary", _schema("vp_primary")),
        ("vp_secondary", "vp_secondary", _schema("vp_secondary")),
        ("vp_exemplar", "vp_exemplar", _schema("vp_exemplar")),
        ("vp_rationale", "vp_rationale", _schema("vp_rationale")),
    ]

    collected: list[tuple[str, dict[str, Any], float]] = []
    with FutureManager(
        name="GenerateStrategyMap.synthesis_vp",
        max_workers=_VALUE_PROPOSITION_MAX_WORKERS,
    ) as manager:
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

    primary = by_label["vp_primary"]["primary"]
    # Hybrid is the only case that uses the secondary classifier output.
    secondary = by_label["vp_secondary"]["secondary"] if primary == "hybrid" else None

    return {
        "primary": primary,
        "secondary": secondary,
        "rationale": by_label["vp_rationale"]["rationale"],
        "exemplar_company": by_label["vp_exemplar"]["exemplar_company"],
    }

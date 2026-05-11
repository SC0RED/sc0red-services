"""Legacy (monolithic) step runners for the strategy-map step.

Houses the four pre-decomposition step implementations: Step 1 (vision +
mission), Step 2 (value proposition), Steps 3-6 (per-perspective
parallel block), Step 7 (arrows + priorities + gaps).

These remain in active use when neither feature flag is set
(``GENERATE_STRATEGY_MAP_DECOMPOSED`` / ``GENERATE_STRATEGY_MAP_DECOMPOSED_SYNTHESIS``).
Phase 1's decomposed perspectives replace Steps 3-6; Phase 2's
decomposed synthesis replaces Steps 1, 2, and 7. With both flags off,
all four legacy runners execute through ``GenerateStrategyMap.execute()``.

Extracted from ``generate_strategy_map.py`` to keep that file under the
400-line audit limit (CLAUDE.md mandatory). Each runner takes the
``GenerateStrategyMap`` instance as ``step`` and delegates AI calls
through ``step._run_ai_call`` — same pattern Phase 1's
``_strategy_map_perspectives.py`` and Phase 2's
``_strategy_map_synthesis.py`` already use.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from signalfield_core.utilities.future_manager import FutureManager

from src.pipeline.pipeline_steps._strategy_map_corpus import load_schema, render_template

if TYPE_CHECKING:
    from src.pipeline.pipeline_steps.generate_strategy_map import GenerateStrategyMap
    from src.pipeline.step_timer import StepTimer

# Same schema used by every legacy call — different steps populate
# different parts of the structure. Final Pydantic validation happens
# in ``assemble_strategy_map()``.
_SCHEMA = load_schema()

# Cap on concurrent AI calls during the Steps 3-6 parallel block.
# Matches ``PARALLEL_MAX_WORKERS`` from the parent module's historical
# value; kept duplicated here to make this module self-contained.
_PARALLEL_MAX_WORKERS = 4

# CloudWatch metric prefix; mirrors ``STEP_NAME`` in the parent module.
_STEP_NAME = "GenerateStrategyMap"


def run_step_1_vision_mission(
    step: GenerateStrategyMap,
    system_prompt: str,
    context: dict[str, Any],
    timer: StepTimer,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Run Step 1 and split the response into vision + mission halves."""
    prompt = render_template("01_vision_mission", context)
    _label, content, elapsed = step._run_ai_call(prompt, _SCHEMA, system_prompt, "vision_mission")
    timer.record("ai_call_vision_mission", elapsed)
    if "vision" not in content or "mission" not in content:
        message = (
            f"[{_STEP_NAME}] Step 1 response missing vision or mission keys: "
            f"got keys={list(content.keys())}"
        )
        raise ValueError(message)
    return content["vision"], content["mission"]


def run_step_2_value_proposition(
    step: GenerateStrategyMap,
    system_prompt: str,
    context: dict[str, Any],
    timer: StepTimer,
) -> dict[str, Any]:
    """Run Step 2 and return the classification dict."""
    prompt = render_template("02_value_proposition_classify", context)
    _label, content, elapsed = step._run_ai_call(
        prompt, _SCHEMA, system_prompt, "value_proposition"
    )
    timer.record("ai_call_value_proposition", elapsed)
    # Some models wrap the answer under `valueProposition`; tolerate both.
    if "primary" in content:
        return content
    if "valueProposition" in content:
        return content["valueProposition"]
    message = (
        f"[{_STEP_NAME}] Step 2 response missing 'primary' classification: "
        f"got keys={list(content.keys())}"
    )
    raise ValueError(message)


def run_steps_3_through_6_in_parallel(
    step: GenerateStrategyMap,
    system_prompt: str,
    context: dict[str, Any],
    timer: StepTimer,
) -> dict[str, dict[str, Any]]:
    """Run the four perspective generations concurrently, collected by label."""
    # Initialise outside the `with` so pyright sees `collected` as
    # always-bound when we read it afterwards. The FutureManager's
    # ``wait_for_all_and_collect_results`` returns synchronously before
    # the context exits, but the static analyser doesn't know that.
    collected: list[tuple[str, dict[str, Any], float]] = []
    with FutureManager(name=_STEP_NAME, max_workers=_PARALLEL_MAX_WORKERS) as manager:
        for label, template_name in (
            ("financial", "03_financial_perspective"),
            ("customer", "04_customer_perspective"),
            ("internal_processes", "05_internal_processes"),
            ("organizational_capacity", "06_organizational_capacity"),
        ):
            manager.submit_task(
                step._run_ai_call,
                render_template(template_name, context),
                _SCHEMA,
                system_prompt,
                label,
            )
        collected = manager.wait_for_all_and_collect_results()

    # Record per-call elapsed before returning. Each label is the
    # perspective name; ``StepTimer`` keys land in CloudWatch as
    # ``ai_call_{perspective}``.
    for label, _data, elapsed in collected:
        timer.record(f"ai_call_{label}", elapsed)

    return {label: data for label, data, _elapsed in collected}


def run_step_7_arrows_and_gaps(
    step: GenerateStrategyMap,
    system_prompt: str,
    context: dict[str, Any],
    timer: StepTimer,
) -> dict[str, Any]:
    """Run Step 7 and return the finale dict (priorities + arrows + gaps)."""
    prompt = render_template("07_arrows_and_gaps", context)
    _label, content, elapsed = step._run_ai_call(prompt, _SCHEMA, system_prompt, "arrows_and_gaps")
    timer.record("ai_call_arrows_and_gaps", elapsed)
    for required in ("strategicPriorities", "arrows", "whatsMissing"):
        if required not in content:
            message = (
                f"[{_STEP_NAME}] Step 7 response missing '{required}': "
                f"got keys={list(content.keys())}"
            )
            raise ValueError(message)
    return content

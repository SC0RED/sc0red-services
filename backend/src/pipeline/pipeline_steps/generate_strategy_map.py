r"""Pipeline step: generate the AI-augmented Balanced Scorecard strategy map.

Inserted between `ComputeValueChain` and `PersistResults` in the
single-company analysis pipeline. Consumes existing pipeline output
(scraped content, profile, risk assessment, opportunities, EBITDA
tree, value chain) plus any user-uploaded document text, and produces
a `StrategyMap` artifact persisted on the assessment record.

Generation runs as a 7-step chain:
  Step 1 — Vision and Mission synthesis        (single AI call)
  Step 2 — Customer Value Proposition classify (single AI call)
  Step 3 — Financial perspective objectives    \
  Step 4 — Customer perspective objectives     -- 4 calls in parallel
  Step 5 — Internal Processes (themed)         -- via FutureManager
  Step 6 — Organizational Capacity (P/T/C)     /
  Step 7 — Arrows + Strategic Priorities       (single AI call)

The corpus that grounds generation lives at `prompts/strategy_map/`
and is loaded via `_strategy_map_corpus.py`. Context construction
and summarisation helpers live in `_strategy_map_context.py`. Output
assembly + validation lives in `_strategy_map_assembly.py`.

Per CLAUDE.md mandatory patterns:
  - Subclass `RequestStep`.
  - Every AI call goes through `run_structured_ai_call`.
  - Parallel block uses `FutureManager` (not raw thread pools).
  - Prompts loaded from external files (no inline AI prompt strings).
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any, cast

from signalfield_core.pipeline.step import RequestStep

from src.pipeline.pipeline_steps._strategy_map_assembly import (
    assemble_strategy_map,
    extract_core_values,
)
from src.pipeline.pipeline_steps._strategy_map_context import (
    build_shared_context,
    summarise_confidence,
    summarise_perspective,
    summarise_value_proposition,
    unwrap_perspective,
)
from src.pipeline.pipeline_steps._strategy_map_corpus import compose_system_prompt
from src.pipeline.pipeline_steps._strategy_map_legacy_steps import (
    run_step_1_vision_mission,
    run_step_2_value_proposition,
    run_step_7_arrows_and_gaps,
    run_steps_3_through_6_in_parallel,
)
from src.pipeline.pipeline_steps.ai_call import run_structured_ai_call
from src.pipeline.step_timer import StepTimer

if TYPE_CHECKING:
    from signalfield_core.services.ai_client_factory import AIClientFactory

    from src.facades.company_accessor import CompanyAccessor

logger = logging.getLogger(__name__)

STEP_NAME = "GenerateStrategyMap"
"""CloudWatch log filter prefix and metric label."""

DECOMPOSED_FLAG_ENV_VAR = "GENERATE_STRATEGY_MAP_DECOMPOSED"
"""Env var that gates the decomposed (Phase 1) call shape.

When set to ``"1"`` on the strategy-map worker Lambda, Steps 3-6
delegate to ``_strategy_map_perspectives.generate_perspectives_decomposed``,
which fans the four perspectives out into ~25 small parallel AI calls
instead of the legacy 4-call-per-perspective pattern. Default OFF —
the legacy single-call path runs unchanged. See
``optimize-strategy-map-latency`` design Decision §0a for which
Lambda receives this env var.
"""

DECOMPOSED_SYNTHESIS_FLAG_ENV_VAR = "GENERATE_STRATEGY_MAP_DECOMPOSED_SYNTHESIS"
"""Env var that gates the decomposed (Phase 2) synthesis call shape.

When set to ``"1"`` ON TOP OF ``GENERATE_STRATEGY_MAP_DECOMPOSED=1``:
- Step 1 (Vision/Mission) delegates to
  ``_strategy_map_synthesis.run_decomposed_vision_mission`` (4 parallel
  sub-calls).
- Step 2 (Value Proposition) delegates to
  ``_strategy_map_synthesis.run_decomposed_value_proposition`` (4 parallel
  sub-calls).
- Step 7 (Arrows + Priorities) delegates to
  ``_strategy_map_arrows.run_decomposed_arrows_and_priorities`` (~15-25
  parallel per-pair yes/no calls + 1 holistic priorities call). The
  legacy "What's Missing" / gaps section was removed by the
  ``redesign-strategy-map`` Phase 2 change.

This flag MUST NOT be set without ``GENERATE_STRATEGY_MAP_DECOMPOSED=1``
— ``execute()`` raises a ``ValueError`` before any AI call is made if
synthesis decomposition is requested while Phase 1 is off. The arrows
module reuses the Phase 1 decomposed perspective output for candidate
pair enumeration; without Phase 1's per-objective IDs the arrows
fan-out would be ill-defined.

Default OFF — Phase 1 alone (or fully monolithic) runs unchanged.
"""


def _decomposed_path_enabled() -> bool:
    """Whether the decomposed Phase 1 call shape should run.

    Reads the env var at call time (not import time) so test fixtures
    can flip it via ``monkeypatch.setenv``.
    """
    return os.environ.get(DECOMPOSED_FLAG_ENV_VAR, "0") == "1"


def _decomposed_synthesis_enabled() -> bool:
    """Whether the decomposed Phase 2 synthesis call shape should run.

    Reads the env var at call time. Callers MUST also verify
    ``_decomposed_path_enabled()`` — the synthesis path requires the
    Phase 1 perspective output to enumerate arrow candidate pairs.
    """
    return os.environ.get(DECOMPOSED_SYNTHESIS_FLAG_ENV_VAR, "0") == "1"


class GenerateStrategyMap(RequestStep):
    """Generate the Balanced Scorecard strategy map for the company."""

    def __init__(self, ai_client_factory: AIClientFactory) -> None:
        """Initialise with an AI client factory shared across the pipeline."""
        super().__init__()
        self._ai_client_factory = ai_client_factory

    def execute(self) -> None:
        """Run the 7-step generation chain and persist the assembled map.

        Wall-clock timings for every AI call are recorded via ``StepTimer`` and
        emitted as ``GenerateStrategyMap.timings`` on the request_executor's
        details payload — same pattern other AI-heavy steps follow
        (``ParallelProfileRiskAndIdeation``, ``DetailOpportunities``).
        """
        accessor = cast("CompanyAccessor", self.entity_accessor)
        company = accessor.company

        # Sanity gate: we need the prerequisite analysis output. If
        # any is missing, the upstream pipeline failed and we should
        # not silently produce a half-baked strategy map.
        if not company.profile:
            message = "Cannot generate strategy map: company profile missing"
            raise ValueError(message)
        if not company.risk_assessment:
            message = "Cannot generate strategy map: risk assessment missing"
            raise ValueError(message)
        if not company.opportunity_result:
            message = "Cannot generate strategy map: opportunity result missing"
            raise ValueError(message)

        # The system prompt is the same for every AI call in the
        # chain — load + concatenate the corpus once.
        system_prompt = compose_system_prompt()

        # Build the shared context dict; later steps mutate it to add
        # their outputs as substitution variables for downstream
        # prompts.
        context = build_shared_context(company)

        # Feature-flag validation. Phase 2 (synthesis decomposition)
        # MUST run on top of Phase 1 (perspective decomposition). The
        # arrows module reuses Phase 1's per-objective IDs (F1..F3,
        # C1..C4, I*.*, O.P/O.T/O.C) to enumerate candidate pairs —
        # without Phase 1 these IDs may not have stable shapes.
        synthesis_decomposed = _decomposed_synthesis_enabled()
        phase1_decomposed = _decomposed_path_enabled()
        if synthesis_decomposed and not phase1_decomposed:
            message = (
                "Cannot enable GENERATE_STRATEGY_MAP_DECOMPOSED_SYNTHESIS=1 "
                "without GENERATE_STRATEGY_MAP_DECOMPOSED=1. The synthesis "
                "decomposition reuses Phase 1's perspective output."
            )
            raise ValueError(message)

        # ``StepTimer`` collects per-AI-call elapsed times; we always emit the
        # collected timings to ``request_executor`` even on the failure path so
        # CloudWatch shows which calls completed before the exception.
        timer = StepTimer(STEP_NAME)
        try:
            # Step 1 — Vision and Mission. Two paths:
            # - Decomposed (Phase 2): 4 parallel sub-calls in
            #   ``_strategy_map_synthesis.run_decomposed_vision_mission``.
            # - Monolithic: today's single AI call.
            if synthesis_decomposed:
                from src.pipeline.pipeline_steps._strategy_map_synthesis import (
                    run_decomposed_vision_mission,
                )

                vision_data, mission_data = run_decomposed_vision_mission(
                    self,
                    system_prompt=system_prompt,
                    context=context,
                    timer=timer,
                )
            else:
                vision_data, mission_data = run_step_1_vision_mission(
                    self, system_prompt, context, timer
                )
            context["vision_statement"] = vision_data["statement"]
            context["mission_statement"] = mission_data["statement"]

            # Step 2 — Customer Value Proposition classification. Two paths:
            # - Decomposed (Phase 2): 4 parallel sub-calls.
            # - Monolithic: today's single AI call.
            if synthesis_decomposed:
                from src.pipeline.pipeline_steps._strategy_map_synthesis import (
                    run_decomposed_value_proposition,
                )

                value_proposition_data = run_decomposed_value_proposition(
                    self,
                    system_prompt=system_prompt,
                    context=context,
                    timer=timer,
                )
            else:
                value_proposition_data = run_step_2_value_proposition(
                    self, system_prompt, context, timer
                )
            context["value_proposition"] = summarise_value_proposition(value_proposition_data)

            # Steps 3-6 — perspective generation. Two paths:
            # - Legacy: 4 single-call-per-perspective rounds in parallel.
            # - Decomposed (Phase 1, feature-flagged): ~25 small calls
            #   across Round 1 / 2 / 3 with positional-ID assignment in
            #   the assembly layer. See `_strategy_map_perspectives.py`.
            if _decomposed_path_enabled():
                # Imported here (not at module top) so the import + its
                # transitive schema-loading don't run on the legacy path.
                # Keeps the legacy path's startup cost unchanged when the
                # flag is OFF — matters because strategy_map_handler
                # cold-start is on the user's first-click critical path.
                from src.pipeline.appsync_notifier import notify_strategy_map_progress
                from src.pipeline.pipeline_steps._strategy_map_perspectives import (
                    generate_perspectives_decomposed,
                )

                # Phase-boundary progress emission. The executor is
                # created with request_id=analysis_id and scan_id=scan_id
                # by the strategy-map worker (see
                # ``strategy_map_handler._generate_and_persist``); both
                # are required to route AppSync events to the right
                # subscribed frontend.
                analysis_id = self.request_executor.request_id
                scan_id = self.request_executor.scan_id

                def _emit_progress(progress: int, label: str) -> None:
                    notify_strategy_map_progress(
                        scan_id=scan_id,
                        analysis_id=analysis_id,
                        progress=progress,
                        label=label,
                    )

                _emit_progress(15, "Generating perspective titles…")

                (
                    financial_data,
                    customer_data,
                    internal_data,
                    capacity_data,
                    core_values_data,
                ) = generate_perspectives_decomposed(
                    self,
                    system_prompt=system_prompt,
                    context=context,
                    timer=timer,
                    progress_emitter=_emit_progress,
                )
            else:
                results = run_steps_3_through_6_in_parallel(self, system_prompt, context, timer)

                # Some models wrap output under a top-level key; tolerate both.
                financial_data = unwrap_perspective(results["financial"], "financial")
                customer_data = unwrap_perspective(results["customer"], "customer")
                internal_data = unwrap_perspective(
                    results["internal_processes"], "internalProcesses"
                )
                capacity_data = unwrap_perspective(
                    results["organizational_capacity"], "organizationalCapacity"
                )
                core_values_data = extract_core_values(results["organizational_capacity"])

            # Update context for Step 7's prompt.
            context["financial_objectives"] = summarise_perspective(financial_data)
            context["customer_objectives"] = summarise_perspective(customer_data)
            context["internal_processes"] = summarise_perspective(internal_data)
            context["organizational_capacity"] = summarise_perspective(capacity_data)
            context["confidence_summary"] = summarise_confidence(
                financial_data, customer_data, internal_data, capacity_data
            )

            # Step 7 — Arrows + Strategic Priorities. Two paths:
            # - Decomposed (Phase 2): per-pair yes/no arrows bank +
            #   holistic priorities, run in parallel.
            # - Monolithic: today's single AI call (still produces a
            #   ``whatsMissing`` block; the assembly drops it).
            # The What's Missing / gaps section is removed end-to-end
            # under the ``redesign-strategy-map`` Phase 2 change.
            if synthesis_decomposed:
                from src.pipeline.pipeline_steps._strategy_map_arrows import (
                    run_decomposed_arrows_and_priorities,
                )

                finale_data = run_decomposed_arrows_and_priorities(
                    self,
                    system_prompt=system_prompt,
                    context=context,
                    timer=timer,
                    financial=financial_data,
                    customer=customer_data,
                    internal_processes=internal_data,
                    organizational_capacity=capacity_data,
                )
            else:
                finale_data = run_step_7_arrows_and_gaps(self, system_prompt, context, timer)

            # Assemble + validate the full StrategyMap.
            strategy_map = assemble_strategy_map(
                vision=vision_data,
                mission=mission_data,
                value_proposition=value_proposition_data,
                financial=financial_data,
                customer=customer_data,
                internal_processes=internal_data,
                organizational_capacity=capacity_data,
                core_values=core_values_data,
                finale=finale_data,
            )

            accessor.set_strategy_map(strategy_map)
        finally:
            # Always emit timings, even on failure, so partial-call latencies
            # are visible in CloudWatch for diagnostics.
            self.request_executor.add_details(timer.to_details())

        self.request_executor.mark_question_complete("generate_strategy_map")

    # ── AI plumbing ─────────────────────────────────────────────────────────

    def _run_ai_call(
        self,
        user_prompt: str,
        schema: dict[str, Any],
        system_prompt: str,
        label: str,
    ) -> tuple[str, dict[str, Any], float]:
        """Execute a single AI call via the shared `run_structured_ai_call`."""
        return run_structured_ai_call(
            ai_client_factory=self._ai_client_factory,
            user_prompt=user_prompt,
            schema=schema,
            system_prompt=system_prompt,
            label=label,
            step_name=STEP_NAME,
        )

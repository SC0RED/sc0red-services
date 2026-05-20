r"""Pipeline step: generate the AI-augmented Balanced Scorecard strategy map.

Inserted between `ComputeValueChain` and `PersistResults` in the
single-company analysis pipeline. Consumes existing pipeline output
(scraped content, profile, risk assessment, opportunities, EBITDA
tree, value chain) plus any user-uploaded document text, and produces
a `StrategyMap` artifact persisted on the assessment record.

Generation runs as a fully decomposed chain (~25 small AI calls fanned
out under ``FutureManager``). Modules:
  - ``_strategy_map_synthesis``  — Vision/Mission and Value Proposition
                                   (Phase 2: 4 + 4 parallel sub-calls).
  - ``_strategy_map_perspectives`` — Financial / Customer /
                                     Internal-Processes / Organizational
                                     Capacity (Phase 1: Rounds 1/2/3).
  - ``_strategy_map_arrows``     — Strategic Priorities + per-pair
                                   arrow yes/no calls (Phase 2).
  - ``_strategy_map_assembly``   — Final Pydantic validation.

The corpus that grounds generation lives at `prompts/strategy_map/`
and is loaded via `_strategy_map_corpus.py`. Context construction
and summarisation helpers live in `_strategy_map_context.py`.

The earlier monolithic (single-call-per-step) path was removed end-to-end
under ``redesign-strategy-map`` Phase 3 — the decomposed chain is the
only path, no feature flags.

Per CLAUDE.md mandatory patterns:
  - Subclass `RequestStep`.
  - Every AI call goes through `run_structured_ai_call`.
  - Parallel block uses `FutureManager` (not raw thread pools).
  - Prompts loaded from external files (no inline AI prompt strings).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, cast

from signalfield_core.exceptions.base import EngineError
from signalfield_core.pipeline.step import RequestStep
from signalfield_core.utilities.future_manager import FutureManagerError

from src.pipeline.pipeline_steps._strategy_map_arrows import (
    run_decomposed_arrows_and_priorities,
)
from src.pipeline.pipeline_steps._strategy_map_assembly import assemble_strategy_map
from src.pipeline.pipeline_steps._strategy_map_context import (
    build_shared_context,
    summarise_confidence,
    summarise_perspective,
    summarise_value_proposition,
)
from src.pipeline.pipeline_steps._strategy_map_corpus import compose_system_prompt
from src.pipeline.pipeline_steps._strategy_map_perspectives import (
    generate_perspectives_decomposed,
)
from src.pipeline.pipeline_steps._strategy_map_synthesis import (
    run_decomposed_value_proposition,
    run_decomposed_vision_mission,
)
from src.pipeline.pipeline_steps.ai_call import run_structured_ai_call
from src.pipeline.step_timer import StepTimer

if TYPE_CHECKING:
    from signalfield_core.services.ai_client_factory import AIClientFactory

    from src.facades.company_accessor import CompanyAccessor
    from src.pipeline.pipeline_steps.ai_call import TokenCounts

logger = logging.getLogger(__name__)

STEP_NAME = "GenerateStrategyMap"
"""CloudWatch log filter prefix and metric label."""


class GenerateStrategyMap(RequestStep):
    """Generate the Balanced Scorecard strategy map for the company."""

    def __init__(self, ai_client_factory: AIClientFactory) -> None:
        """Initialise with an AI client factory shared across the pipeline."""
        super().__init__()
        self._ai_client_factory = ai_client_factory

    def execute(self) -> None:
        """Run the decomposed generation chain and persist the assembled map.

        Wall-clock timings for every AI call are recorded via ``StepTimer`` and
        emitted as ``GenerateStrategyMap.timings`` on the request_executor's
        details payload — same pattern other AI-heavy steps follow
        (``ParallelProfileRiskAndIdeation``, ``DetailOpportunities``).

        **Soft-fail semantics for AI domain errors.** A strategy map is an
        additive analysis output; the user's primary value lives in the
        risk scores, opportunities, EBITDA tree, and value chain produced
        by upstream steps. When the AI chain fails — rate limit, schema
        validation, ``FutureManager`` aggregation, malformed AI output
        that's missing an expected key or has the wrong type — this step
        logs the failure, leaves ``company.strategy_map`` as ``None``,
        and returns normally so ``PersistResults`` saves the rest of the
        analysis intact. The user lands on the analysis page with all
        data except the map. Re-analyse regenerates everything
        including the map.

        ``KeyError`` and ``TypeError`` are included in the catch list
        because the synthesis / arrows / assembly modules access AI
        response dicts directly (``vision_data["statement"]``,
        ``content["primary"]``); a missing key or wrong-typed value
        from the AI surfaces as one of these. Genuine programming
        bugs in our own code tend to surface as ``AttributeError``
        against ``self`` / module imports — those are NOT caught and
        will propagate so SQS retries and CloudWatch shows the stack
        trace.

        The prerequisite gates also raise ``ValueError`` if upstream
        pipeline output is missing — those are caught here for the
        same reason (upstream already failed; producing a degraded
        analysis without a map is the right outcome).

        Net effect: this preserves the failure-isolation property the
        dedicated on-demand worker provided in the pre-Phase-4 design.
        """
        accessor = cast("CompanyAccessor", self.entity_accessor)
        company = accessor.company

        # ``StepTimer`` collects per-AI-call elapsed times; we always emit the
        # collected timings to ``request_executor`` even on the failure path so
        # CloudWatch shows which calls completed before the exception.
        timer = StepTimer(STEP_NAME)
        try:
            self._generate_and_set(accessor, company, timer)
        except (
            EngineError,
            FutureManagerError,
            ValueError,
            RuntimeError,
            KeyError,
            TypeError,
        ):
            # Domain failure — degrade gracefully so ``PersistResults``
            # can save the rest of the analysis. The stack trace surfaces
            # in CloudWatch via ``logger.exception``; the company record
            # ends up with no strategy map and the frontend slot renders
            # nothing for it.
            logger.exception(
                "[%s] Strategy-map generation failed; analysis will persist without a map",
                STEP_NAME,
            )
            accessor.set_strategy_map(None)
        finally:
            # Always emit timings, even on failure, so partial-call latencies
            # are visible in CloudWatch for diagnostics.
            self.request_executor.add_details(timer.to_details())

        self.request_executor.mark_question_complete("generate_strategy_map")

    def _generate_and_set(
        self,
        accessor: CompanyAccessor,
        company: Any,
        timer: StepTimer,
    ) -> None:
        """Run the full generation chain and set the result on the accessor."""
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
        # their outputs as substitution variables for downstream prompts.
        context = build_shared_context(company)

        # Step 1 — Vision and Mission (4 parallel sub-calls).
        vision_data, mission_data = run_decomposed_vision_mission(
            self,
            system_prompt=system_prompt,
            context=context,
            timer=timer,
        )
        context["vision_statement"] = vision_data["statement"]
        context["mission_statement"] = mission_data["statement"]

        # Step 2 — Customer Value Proposition (4 parallel sub-calls).
        value_proposition_data = run_decomposed_value_proposition(
            self,
            system_prompt=system_prompt,
            context=context,
            timer=timer,
        )
        context["value_proposition"] = summarise_value_proposition(value_proposition_data)

        # Steps 3-6 — perspective generation (~25 small parallel
        # calls across Round 1 / Round 2 / Round 3, with positional-ID
        # assignment in the assembly layer).
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
            progress_emitter=None,
        )

        # Update context for Step 7's prompt.
        context["financial_objectives"] = summarise_perspective(financial_data)
        context["customer_objectives"] = summarise_perspective(customer_data)
        context["internal_processes"] = summarise_perspective(internal_data)
        context["organizational_capacity"] = summarise_perspective(capacity_data)
        context["confidence_summary"] = summarise_confidence(
            financial_data, customer_data, internal_data, capacity_data
        )

        # Step 7 — Arrows + Strategic Priorities. Per-pair yes/no
        # arrow bank fanned out in parallel + one holistic priorities
        # call. The What's Missing / gaps section was removed end-to-end
        # under ``redesign-strategy-map`` Phase 2.
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

        # Assemble + validate the full StrategyMap. The opportunity_count
        # threads through so the assembly layer can clip any
        # ``linked_opportunity_indices`` value the AI emitted outside
        # ``[0, opportunity_count)`` — defends the dot strip on the
        # frontend against AI drift and against context truncation if
        # the opportunities JSON were ever cut short before the AI saw it.
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
            opportunity_count=len(company.opportunity_result.opportunities),
        )

        accessor.set_strategy_map(strategy_map)

    # ── AI plumbing ─────────────────────────────────────────────────────────

    def _run_ai_call(
        self,
        user_prompt: str,
        schema: dict[str, Any],
        system_prompt: str,
        label: str,
    ) -> tuple[str, dict[str, Any], float, TokenCounts]:
        """Execute a single AI call via the shared `run_structured_ai_call`.

        Returns ``(label, content, elapsed, token_counts)``. Strategy-map
        sub-modules destructure all four and pair ``timer.record_tokens(...)``
        with the existing ``timer.record(...)`` call so each per-call entry in
        the CloudWatch payload carries elapsed-time + token-count keys.
        """
        return run_structured_ai_call(
            ai_client_factory=self._ai_client_factory,
            user_prompt=user_prompt,
            schema=schema,
            system_prompt=system_prompt,
            label=label,
            step_name=STEP_NAME,
        )

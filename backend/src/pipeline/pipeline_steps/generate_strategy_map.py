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
                + "What's Missing?" gaps

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
from typing import TYPE_CHECKING, Any, cast

from signalfield_core.pipeline.step import RequestStep
from signalfield_core.utilities.future_manager import FutureManager

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
from src.pipeline.pipeline_steps._strategy_map_corpus import (
    compose_system_prompt,
    load_schema,
    render_template,
)
from src.pipeline.pipeline_steps.ai_call import run_structured_ai_call

if TYPE_CHECKING:
    from signalfield_core.services.ai_client_factory import AIClientFactory

    from src.facades.company_accessor import CompanyAccessor

logger = logging.getLogger(__name__)

STEP_NAME = "GenerateStrategyMap"
"""CloudWatch log filter prefix and metric label."""

PARALLEL_MAX_WORKERS = 4
"""Cap on concurrent AI calls during the Steps 3-6 parallel block."""

# Loaded once at module import. The same schema is passed to every
# AI call — different steps populate different parts of the structure.
# Final assembly + Pydantic validation in `assemble_strategy_map()`
# is the gating check.
_SCHEMA = load_schema()


class GenerateStrategyMap(RequestStep):
    """Generate the Balanced Scorecard strategy map for the company."""

    def __init__(self, ai_client_factory: AIClientFactory) -> None:
        """Initialise with an AI client factory shared across the pipeline."""
        super().__init__()
        self._ai_client_factory = ai_client_factory

    def execute(self) -> None:
        """Run the 7-step generation chain and persist the assembled map."""
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

        # Step 1 — Vision and Mission
        vision_data, mission_data = self._step_1_vision_mission(system_prompt, context)
        context["vision_statement"] = vision_data["statement"]
        context["mission_statement"] = mission_data["statement"]

        # Step 2 — Customer Value Proposition classification
        value_proposition_data = self._step_2_value_proposition(system_prompt, context)
        context["value_proposition"] = summarise_value_proposition(value_proposition_data)

        # Steps 3-6 — perspective generation in parallel via
        # FutureManager (per CLAUDE.md mandatory pattern).
        results = self._steps_3_through_6_in_parallel(system_prompt, context)

        # Some models wrap output under a top-level key; tolerate both.
        financial_data = unwrap_perspective(results["financial"], "financial")
        customer_data = unwrap_perspective(results["customer"], "customer")
        internal_data = unwrap_perspective(results["internal_processes"], "internalProcesses")
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

        # Step 7 — Arrows + Strategic Priorities + What's Missing
        finale_data = self._step_7_arrows_and_gaps(system_prompt, context)

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
        self.request_executor.mark_question_complete("generate_strategy_map")

    # ── Step runners ────────────────────────────────────────────────────────

    def _step_1_vision_mission(
        self,
        system_prompt: str,
        context: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Run Step 1 and split the response into vision + mission halves."""
        prompt = render_template("01_vision_mission", context)
        _label, content, _elapsed = self._run_ai_call(
            prompt, _SCHEMA, system_prompt, "vision_mission"
        )
        if "vision" not in content or "mission" not in content:
            message = (
                f"[{STEP_NAME}] Step 1 response missing vision or mission keys: "
                f"got keys={list(content.keys())}"
            )
            raise ValueError(message)
        return content["vision"], content["mission"]

    def _step_2_value_proposition(
        self,
        system_prompt: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Run Step 2 and return the classification dict."""
        prompt = render_template("02_value_proposition_classify", context)
        _label, content, _elapsed = self._run_ai_call(
            prompt, _SCHEMA, system_prompt, "value_proposition"
        )
        # Some models wrap the answer under `valueProposition`; tolerate both.
        if "primary" in content:
            return content
        if "valueProposition" in content:
            return content["valueProposition"]
        message = (
            f"[{STEP_NAME}] Step 2 response missing 'primary' classification: "
            f"got keys={list(content.keys())}"
        )
        raise ValueError(message)

    def _steps_3_through_6_in_parallel(
        self,
        system_prompt: str,
        context: dict[str, Any],
    ) -> dict[str, dict[str, Any]]:
        """Run the four perspective generations concurrently, collected by label."""
        # Initialise outside the `with` so pyright sees `collected` as
        # always-bound when we read it afterwards. The FutureManager's
        # `wait_for_all_and_collect_results` returns synchronously
        # before the context exits, but the static analyser doesn't
        # know that.
        collected: list[tuple[str, dict[str, Any], float]] = []
        with FutureManager(name=STEP_NAME, max_workers=PARALLEL_MAX_WORKERS) as manager:
            for label, template_name in (
                ("financial", "03_financial_perspective"),
                ("customer", "04_customer_perspective"),
                ("internal_processes", "05_internal_processes"),
                ("organizational_capacity", "06_organizational_capacity"),
            ):
                manager.submit_task(
                    self._run_ai_call,
                    render_template(template_name, context),
                    _SCHEMA,
                    system_prompt,
                    label,
                )
            collected = manager.wait_for_all_and_collect_results()

        return {label: data for label, data, _elapsed in collected}

    def _step_7_arrows_and_gaps(
        self,
        system_prompt: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Run Step 7 and return the finale dict (priorities + arrows + gaps)."""
        prompt = render_template("07_arrows_and_gaps", context)
        _label, content, _elapsed = self._run_ai_call(
            prompt, _SCHEMA, system_prompt, "arrows_and_gaps"
        )
        for required in ("strategicPriorities", "arrows", "whatsMissing"):
            if required not in content:
                message = (
                    f"[{STEP_NAME}] Step 7 response missing '{required}': "
                    f"got keys={list(content.keys())}"
                )
                raise ValueError(message)
        return content

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

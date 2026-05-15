"""JanusRequestExecutor — simplified PipelineExecutor implementation.

Satisfies the signalfield_core PipelineExecutor protocol (10 members).
Simplified from Engine's RequestExecutor (600+ lines) to ~150 lines.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from signalfield_core.domain.entity import EntityAccessor
    from signalfield_core.pipeline.step import RequestStep

    from src.repositories.dynamodb.company_repository import DynamoDBCompanyRepository

logger = logging.getLogger(__name__)


# Sub-step entries whose keys begin with one of these prefixes carry token
# counts (integers), not elapsed-time durations. The post-pipeline summary
# log uses this to render counts as ``N tokens`` instead of the elapsed
# ``N.NNs`` format. Introduced 2026-05-15 with the strategy-map token
# telemetry — every other ``{step}.timings`` entry is still a float of
# wall-clock seconds.
_TOKEN_KEY_PREFIXES: tuple[str, ...] = ("tokens_in_", "tokens_out_", "cached_tokens_")


def _format_timing_value(sub_name: str, value: Any) -> str:
    """Render a ``{step}.timings`` entry for the human-readable summary log.

    Token-count keys (prefixed with ``tokens_in_`` / ``tokens_out_`` /
    ``cached_tokens_``) render as ``N tokens``. Everything else is
    treated as elapsed seconds and rendered with two decimals + ``s``.
    """
    if sub_name.startswith(_TOKEN_KEY_PREFIXES):
        return f"{int(value)} tokens"
    return f"{value:.2f}s"


# Maps pipeline question keys → (progress percentage, user-visible label)
_PROGRESS_MAP: dict[str, tuple[int, str]] = {
    "scrape_and_resolve": (15, "Scraping website content..."),
    "extract_profile": (30, "Extracting company profile..."),
    "assess_risk": (45, "Running AI risk assessment..."),
    "ideate_opportunities": (55, "Generating opportunity ideas..."),
    "generate_opportunities": (65, "Gathering implementation details..."),
    "generate_ebitda_tree": (70, "Building EBITDA analysis..."),
    "compute_value_chain": (75, "Mapping value chain..."),
    # The strategy-map step adds ~35 s on top of the ~30 s analysis
    # body, so the bar sits at 80 % for the largest single chunk of
    # wall-clock time. The label changes ("Generating strategy map…")
    # so the user sees progress is alive even though the percentage
    # holds. Re-introduced into the auto-pipeline by the
    # ``redesign-strategy-map`` Phase 4 change, which deleted the
    # on-demand SQS worker.
    "generate_strategy_map": (80, "Generating strategy map..."),
    "persist_results": (95, "Saving results..."),
    # Portfolio discovery pipeline (async via SQS worker)
    "discover_portfolio": (10, "Finding portfolio companies..."),
    "validate_portfolio": (18, "Validating portfolio companies..."),
}


class JanusRequestExecutor:
    """Pipeline executor for Janus assessments.

    Implements the PipelineExecutor protocol: tracks question completion,
    step timing, exceptions, and supports dynamic step insertion.
    """

    def __init__(
        self,
        tenant_id: str | None = None,
        request_id: str = "",
        pipeline: list[RequestStep] | None = None,
        company_repo: DynamoDBCompanyRepository | None = None,
        scan_id: str = "",
    ) -> None:
        self.tenant_id = tenant_id
        self.request_id = request_id
        self.scan_id = scan_id
        self.exceptions: list[Exception] = []
        self._completed_questions: set[str] = set()
        self._details: dict[str, Any] = {}
        self._pipeline: list[RequestStep] = list(pipeline) if pipeline else []
        self._step_timings: dict[str, float] = {}
        self._entity_accessor: EntityAccessor | None = None
        self._company_repo = company_repo

    # ── PipelineExecutor protocol ────────────────────────────────────

    def mark_question_complete(self, question_key: str) -> None:
        """Mark a single question as complete and update scan progress in DynamoDB."""
        self._completed_questions.add(question_key)
        logger.info("Question complete: %s", question_key)
        self._report_progress(question_key)

    def mark_multiple_questions_complete(self, question_keys: list[str]) -> None:
        """Mark multiple questions as complete."""
        for key in question_keys:
            self.mark_question_complete(key)

    def is_question_complete(self, question_key: str) -> bool:
        """Return True if the given question key has been marked complete."""
        return question_key in self._completed_questions

    def add_details(self, details: dict[str, Any]) -> None:
        """Merge additional key-value details into the executor's detail store."""
        self._details.update(details)

    def propagate_entity_accessor(self, entity_accessor: EntityAccessor) -> None:
        """Set the entity accessor on the executor and all pipeline steps."""
        self._entity_accessor = entity_accessor
        for step in self._pipeline:
            step.entity_accessor = entity_accessor

    def add_step_after(self, step_name: str, new_step: RequestStep) -> None:
        """Insert a new step immediately after the named step in the pipeline."""
        for i, step in enumerate(self._pipeline):
            if step.step_name() == step_name:
                new_step.request_executor = self
                if self._entity_accessor is not None:
                    new_step.entity_accessor = self._entity_accessor
                self._pipeline.insert(i + 1, new_step)
                return
        message = f"Step '{step_name}' not found in pipeline"
        raise ValueError(message)

    def add_step_before(self, step_name: str, new_step: RequestStep) -> None:
        """Insert a new step immediately before the named step in the pipeline."""
        for i, step in enumerate(self._pipeline):
            if step.step_name() == step_name:
                new_step.request_executor = self
                if self._entity_accessor is not None:
                    new_step.entity_accessor = self._entity_accessor
                self._pipeline.insert(i, new_step)
                return
        message = f"Step '{step_name}' not found in pipeline"
        raise ValueError(message)

    def has_step(self, step_name: str) -> bool:
        """Return True if a step with the given name exists in the pipeline."""
        return any(s.step_name() == step_name for s in self._pipeline)

    # ── Execution ────────────────────────────────────────────────────

    @property
    def details(self) -> dict[str, Any]:
        """Return a copy of the accumulated execution details."""
        return dict(self._details)

    @property
    def step_timings(self) -> dict[str, float]:
        """Return a copy of the step timing measurements."""
        return dict(self._step_timings)

    def execute_all(self) -> None:
        """Execute all pipeline steps in order."""
        pipeline_start = time.monotonic()
        logger.info(
            "[pipeline] starting request_id=%s, steps=%s",
            self.request_id,
            [s.step_name() for s in self._pipeline],
        )
        for step in self._pipeline:
            step_name = step.step_name()
            logger.info("[pipeline] executing step=%s request_id=%s", step_name, self.request_id)
            start = time.monotonic()
            try:
                step.execute()
            except Exception as exc:
                self.exceptions.append(exc)
                logger.exception(
                    "[pipeline] step=%s FAILED request_id=%s",
                    step_name,
                    self.request_id,
                )
                raise
            finally:
                elapsed = time.monotonic() - start
                self._step_timings[step_name] = elapsed
                logger.info(
                    "[pipeline] step=%s completed in %.2fs request_id=%s",
                    step_name,
                    elapsed,
                    self.request_id,
                )

        total_elapsed = time.monotonic() - pipeline_start
        self._step_timings["_total"] = total_elapsed

        # Log performance summary with sub-step details
        timing_lines = [
            f"  {name}: {duration:.2f}s" for name, duration in self._step_timings.items()
        ]
        substep_lines = []
        for key, value in self._details.items():
            if key.endswith(".timings") and isinstance(value, dict):
                step_label = key.removesuffix(".timings")
                for sub_name, sub_value in value.items():
                    substep_lines.append(
                        f"    {step_label}.{sub_name}: {_format_timing_value(sub_name, sub_value)}"
                    )

        summary = "\n".join(timing_lines)
        if substep_lines:
            summary += "\n  Sub-step breakdown:\n" + "\n".join(substep_lines)

        logger.info(
            "[pipeline] completed request_id=%s in %.2fs\n%s",
            self.request_id,
            total_elapsed,
            summary,
        )

    # ── Progress reporting ───────────────────────────────────────────

    def _report_progress(self, question_key: str) -> None:
        """Write pipeline progress to DynamoDB and push to AppSync.

        Writes to:
        1. The company record (pipeline_progress + pipeline_label) — always, if company_repo
           is configured. This enables per-company progress for portfolio scans.
        2. AppSync (fire-and-forget) — enables real-time UI updates without polling.
        3. The scan record (progress + progress_label) — only for standalone scans where
           a single company's progress IS the scan progress. For portfolio scans, the
           scan-level progress is computed from company completion counts in sqs_handler.

        Silently skips if repos are not configured (i.e. running in tests).
        """
        from src.pipeline.appsync_notifier import notify_progress

        progress_entry = _PROGRESS_MAP.get(question_key)
        if not progress_entry:
            return

        progress, label = progress_entry

        # Always write to company record (per-company progress)
        if self._company_repo and self.request_id:
            try:
                self._company_repo.update(
                    self.request_id,
                    {"pipeline_progress": progress, "pipeline_label": label},
                )
            except Exception:
                logger.warning(
                    "Failed to update company progress for %s (step=%s)",
                    self.request_id,
                    question_key,
                    exc_info=True,
                )

        # Push real-time update to AppSync (fire-and-forget)
        if self.scan_id:
            notify_progress(
                scan_id=self.scan_id,
                progress=progress,
                label=label,
                company_id=self.request_id,
            )

        # NOTE: scan-level progress is NOT written here. For standalone scans,
        # the handler computes it from the single company's pipeline_progress.
        # For portfolio scans, sqs_handler._update_scan_progress handles it
        # based on company completion counts. Writing step progress to the
        # scan record from workers would cause conflicts in portfolio mode.

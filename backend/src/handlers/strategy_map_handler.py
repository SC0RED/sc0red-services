"""SQS worker for on-demand strategy-map generation.

Consumes messages from ``janus-strategy-map-queue`` (a dedicated queue per the
strategy-map-on-demand spec, decision §2). Each message triggers a single
``GenerateStrategyMap`` run against the persisted analysis data, persists the
result, and pushes an AppSync completion event.

The pipeline-step variant of ``GenerateStrategyMap`` runs as part of the
end-to-end analysis pipeline; this worker runs the *same* step in isolation
against pre-persisted data. Hydration (DB rows → ``Company`` Pydantic) lives
in ``_strategy_map_hydration``.

Failure handling per CLAUDE.md fail-fast:

- Domain errors (``EngineError``, ``ValueError``, ``RuntimeError``,
  ``StrategyMapHydrationError``) → log + push ``strategy_map_failed`` event
  + return success so SQS does NOT retry. The user-visible recovery is the
  CTA returning with a "try again" message.
- Programming errors (``KeyError``, ``TypeError``, ``AttributeError``) →
  propagate to SQS retry. After ``maxReceiveCount`` retries the message
  lands in the DLQ and a CloudWatch alarm fires for ops.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from signalfield_core.exceptions.base import EngineError

from src.facades.company_accessor import CompanyAccessor
from src.handlers._strategy_map_hydration import (
    StrategyMapHydrationError,
    hydrate_company_for_strategy_map,
)
from src.pipeline.appsync_notifier import (
    notify_strategy_map_complete,
    notify_strategy_map_failed,
)
from src.pipeline.pipeline_steps.generate_strategy_map import GenerateStrategyMap
from src.pipeline.request_executor import JanusRequestExecutor

if TYPE_CHECKING:
    from signalfield_core.services.ai_client_factory import AIClientFactory

    from src.repositories.dynamodb.assessment_repository import (
        DynamoDBAssessmentRepository,
    )
    from src.repositories.dynamodb.company_repository import (
        DynamoDBCompanyRepository,
    )
    from src.repositories.dynamodb.provider import DynamoDBStorageProvider

logger = logging.getLogger(__name__)


class StrategyMapSQSHandler:
    """Consumes ``janus-strategy-map-queue`` messages and runs on-demand generation."""

    def __init__(
        self,
        storage: DynamoDBStorageProvider,
        ai_client_factory: AIClientFactory,
    ) -> None:
        self._storage = storage
        self._ai_client_factory = ai_client_factory

    # MUST match the SQS queue's ``max_receive_count`` configured at
    # ``infrastructure/stacks/strategy_map_construct.py``'s ``StrategyMapQueue``
    # ``DeadLetterQueue(max_receive_count=...)`` argument. The two values
    # live in separate runtime contexts (Python Lambda vs CDK synthesis)
    # and there is no automated drift guard — if you change one, change
    # the other. The fail-safe cleanup below uses this constant to detect
    # the final retry attempt before SQS routes to the DLQ.
    _MAX_RECEIVE_COUNT = 3

    def handle(self, event: dict[str, Any]) -> dict[str, Any]:
        """Process all SQS records in the event.

        Returns the standard ``{"batchItemFailures": [...]}`` shape so SQS
        retries only the records that hit programming errors. Domain errors
        are translated to AppSync ``strategy_map_failed`` events and the
        record is consumed (success).

        On the FINAL retry attempt (receive count == max_receive_count),
        a programming error triggers a fail-safe cleanup: the company's
        ``strategy_map_generation_state`` is cleared and a
        ``strategy_map_failed`` AppSync event is pushed so the frontend
        UI returns to the CTA state. Without this, the message would
        land in the DLQ with the company record's "generating" marker
        still set, leaving the user permanently stuck on the spinner.
        Lambda timeouts are NOT covered by this path (the process is
        killed mid-execution); the queue's visibility timeout + the
        Lambda timeout sizing in ``strategy_map_construct.py`` are
        what protect against that mode.
        """
        records = event.get("Records", [])
        batch_item_failures: list[dict[str, str]] = []

        for record in records:
            message_id = record.get("messageId", "")
            try:
                body = json.loads(record["body"])
                self._process_message(body)
            except Exception:
                # Programming error — surface to SQS so the message retries.
                # CloudWatch captures the full traceback for diagnosis.
                logger.exception(
                    "Strategy-map worker failed on programming error for %s", message_id
                )
                receive_count_string = record.get("attributes", {}).get(
                    "ApproximateReceiveCount", "1"
                )
                try:
                    receive_count = int(receive_count_string)
                except ValueError:
                    receive_count = 1
                if receive_count >= self._MAX_RECEIVE_COUNT:
                    # Last attempt — message will go to DLQ after this. Run
                    # the fail-safe cleanup so the user isn't permanently
                    # stuck on "Generating your strategy map…".
                    self._fail_safe_cleanup_for_message(record)
                if message_id:
                    batch_item_failures.append({"itemIdentifier": message_id})

        return {"batchItemFailures": batch_item_failures}

    def _fail_safe_cleanup_for_message(self, record: dict[str, Any]) -> None:
        """Clear stuck ``generating`` state on the final SQS retry.

        Runs only when ``ApproximateReceiveCount`` has hit the queue's
        ``max_receive_count`` — at that point SQS will route the message
        to the DLQ regardless of what we return, so this is our last
        chance to free the company record from the "generating" marker.

        Body parsing + field extraction happen OUTSIDE the inner try so
        a malformed body fails loudly (and gets caught by the outer
        ``handle()`` except, which already logged the original error).
        Only the DDB + AppSync calls are wrapped — those are the IO
        operations whose transient failure (throttle, network) we
        explicitly want to swallow rather than mask the original
        programming error already in CloudWatch.
        """
        body = json.loads(record["body"])
        analysis_id = body.get("analysis_id")
        scan_id = body.get("scan_id", "")
        if not analysis_id:
            logger.warning("Fail-safe cleanup skipped: message body missing analysis_id")
            return

        try:
            company_repo = self._storage.create_company_repository()
            company_repo.clear_strategy_map_generation_state(analysis_id)
            notify_strategy_map_failed(
                scan_id=scan_id,
                analysis_id=analysis_id,
                error_message=(
                    "Strategy-map generation hit the retry limit. "
                    "Please try again — the analysis is ready to retry."
                ),
            )
            logger.info(
                "Fail-safe cleanup completed for analysis=%s scan=%s",
                analysis_id,
                scan_id,
            )
        except Exception:
            logger.exception("Fail-safe cleanup itself failed; manual DLQ inspection required")

    def _process_message(self, message: dict[str, Any]) -> None:
        """Run a single strategy-map generation job."""
        if message.get("type") != "strategy_map_generation":
            # Defensive: the dedicated queue should only receive this type, but
            # if the dispatcher ever wires it onto a multiplexed queue, fail
            # loudly rather than silently no-op.
            error_message = (
                f"Unexpected message type on strategy-map queue: {message.get('type')!r}"
            )
            raise ValueError(error_message)

        analysis_id = message["analysis_id"]
        scan_id = message.get("scan_id", "")

        company_repo = self._storage.create_company_repository()
        assessment_repo = self._storage.create_assessment_repository()

        try:
            self._generate_and_persist(
                analysis_id=analysis_id,
                scan_id=scan_id,
                company_repo=company_repo,
                assessment_repo=assessment_repo,
            )
        except (EngineError, ValueError, RuntimeError, StrategyMapHydrationError) as error:
            # Domain failure path — the user clicked Generate but something
            # the AI / hydration / validation layer couldn't recover from
            # happened. Translate into an AppSync failure event so the
            # frontend can show "We couldn't generate your strategy map."
            logger.exception(
                "Strategy-map generation failed for analysis=%s scan=%s",
                analysis_id,
                scan_id,
            )
            self._clear_generation_state(company_repo, analysis_id)
            notify_strategy_map_failed(
                scan_id=scan_id, analysis_id=analysis_id, error_message=str(error)
            )
            return

        # Success path — the generation step set the result on the accessor;
        # persistence happened inside _generate_and_persist; AppSync push
        # now signals the frontend to re-fetch.
        notify_strategy_map_complete(scan_id=scan_id, analysis_id=analysis_id)

    def _generate_and_persist(
        self,
        *,
        analysis_id: str,
        scan_id: str,
        company_repo: DynamoDBCompanyRepository,
        assessment_repo: DynamoDBAssessmentRepository,
    ) -> None:
        """Hydrate, generate, persist. Wrapped in a single try-block by the caller."""
        # Hydrate the in-memory Company shape that GenerateStrategyMap expects.
        company = hydrate_company_for_strategy_map(self._storage, analysis_id)
        accessor = CompanyAccessor(company)

        # Build a request executor with a single-step pipeline so
        # GenerateStrategyMap can call its existing
        # `self.request_executor.add_details(...)` and
        # `mark_question_complete(...)` hooks unchanged. Wiring mirrors the
        # `CompanyAnalysisFactory.build_executor` pattern: instantiate the
        # step + executor, then bind them to each other and the accessor
        # directly. We avoid `propagate_entity_accessor` because that goes
        # through a stricter protocol surface than `RequestStep` exposes.
        step = GenerateStrategyMap(ai_client_factory=self._ai_client_factory)
        executor = JanusRequestExecutor(
            tenant_id=None,
            request_id=analysis_id,
            pipeline=[step],
            company_repo=company_repo,
            scan_id=scan_id,
        )
        step.request_executor = executor
        step.entity_accessor = accessor

        # Run generation via ``executor.execute_all()`` so the executor's
        # post-step ``logger.info("[pipeline] completed …")`` summary fires
        # — that's where the ``GenerateStrategyMap.timings`` block lands
        # in CloudWatch (matching the analysis worker's logging contract).
        # Calling ``step.execute()`` directly would bypass the summary.
        # The step's execute() validates prerequisites and raises
        # ValueError on missing data; ``execute_all()`` re-raises after
        # recording the elapsed time and the outer try/except in
        # ``_process_message`` translates that to AppSync failure.
        executor.execute_all()

        # The step set the strategy map on the accessor; the in-pipeline
        # variant relies on PersistResults to actually write to DynamoDB,
        # but the worker is running in isolation so we persist directly.
        if accessor.company.strategy_map is None:
            error_message = (
                f"GenerateStrategyMap completed without setting a strategy map "
                f"on the accessor for analysis={analysis_id}"
            )
            raise RuntimeError(error_message)

        # ``model_dump(by_alias=True)`` mirrors what PersistResults does for the
        # pipeline-step path so the on-disk shape is identical between the two
        # call paths.
        strategy_map_payload = accessor.company.strategy_map.model_dump(by_alias=True)

        # Look up the latest assessment id (hydration already used it but
        # didn't surface it).
        assessments = assessment_repo.find_by_company(analysis_id)
        if not assessments:
            error_message = f"Cannot persist strategy map: analysis {analysis_id} has no assessment"
            raise RuntimeError(error_message)
        assessments.sort(key=lambda a: a.get("created_at", ""), reverse=True)
        assessment_id = assessments[0]["id"]

        assessment_repo.save_strategy_map(assessment_id, strategy_map_payload)

        # Clear in-flight state so the next GET response shows the persisted
        # map without the generating placeholder.
        self._clear_generation_state(company_repo, analysis_id)

    @staticmethod
    def _clear_generation_state(company_repo: DynamoDBCompanyRepository, analysis_id: str) -> None:
        """Clear ``strategy_map_generation_state`` from the company record.

        Delegates to the repo's ``clear_strategy_map_generation_state`` which
        issues a DynamoDB REMOVE (not SET-to-None) so the field is genuinely
        absent from subsequent reads.
        """
        company_repo.clear_strategy_map_generation_state(analysis_id)

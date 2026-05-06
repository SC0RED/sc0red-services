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

    def handle(self, event: dict[str, Any]) -> dict[str, Any]:
        """Process all SQS records in the event.

        Returns the standard ``{"batchItemFailures": [...]}`` shape so SQS
        retries only the records that hit programming errors. Domain errors
        are translated to AppSync ``strategy_map_failed`` events and the
        record is consumed (success).
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
                if message_id:
                    batch_item_failures.append({"itemIdentifier": message_id})

        return {"batchItemFailures": batch_item_failures}

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

        # Run generation. The step's execute() validates prerequisites and
        # raises ValueError on missing data — we catch that in the outer try.
        step.execute()

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

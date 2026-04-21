"""SQS handler for async company analysis.

Processes messages from the portfolio analysis queue — each message
triggers a single company analysis pipeline.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from signalfield_core.exceptions.base import EngineError

from src.handlers.factory_manager import FactoryManager
from src.pipeline.appsync_notifier import notify_progress
from src.repositories.dynamodb.provider import DynamoDBStorageProvider

logger = logging.getLogger(__name__)


class SQSHandler:
    """Processes SQS messages for async company analysis."""

    def __init__(self, storage: DynamoDBStorageProvider | None = None) -> None:
        self._storage = storage or DynamoDBStorageProvider()
        self._factory_manager = FactoryManager(self._storage)

    def handle(self, event: dict[str, Any]) -> dict[str, Any]:
        """Process all SQS records in the event and return batch failure info."""
        records = event.get("Records", [])
        batch_item_failures: list[dict[str, str]] = []

        for record in records:
            message_id = record.get("messageId", "")
            try:
                body = json.loads(record["body"])
                self._process_message(body)
            except Exception:
                logger.exception("SQS message processing failed for %s", message_id)
                if message_id:
                    batch_item_failures.append({"itemIdentifier": message_id})

        return {"batchItemFailures": batch_item_failures}

    def _process_message(self, message: dict[str, Any]) -> None:
        """Dispatch an SQS message to the correct pipeline.

        Message discriminators (checked in order):
        - ``type == "portfolio_discovery"`` → portfolio-scan pipeline
        - ``reanalyze == True`` → company re-analysis
        - default → new company analysis
        """
        if message.get("type") == "portfolio_discovery":
            self._process_portfolio_discovery(message)
        elif message.get("reanalyze"):
            self._process_reanalysis(message)
        else:
            self._process_new_analysis(message)

    def _process_new_analysis(self, message: dict[str, Any]) -> None:
        """Run the company analysis pipeline for a new scan."""
        url = message["url"]
        org_id = message["org_id"]
        user_id = message["user_id"]
        scan_id = message["scan_id"]
        company_name = message.get("company_name", "")
        request_id = message["request_id"]

        logger.info("Processing async analysis for %s (%s)", company_name or url, scan_id)

        # Persist company identity BEFORE the pipeline runs. On failure,
        # this ensures the record has a name and URL for display + retry.
        # PersistResults overwrites with pipeline-resolved values on success.
        company_repo = self._storage.create_company_repository()
        company_repo.update(
            request_id,
            {
                "id": request_id,
                "company_name": company_name,
                "company_url": url,
                "scan_id": scan_id,
                "org_id": org_id,
            },
        )

        try:
            self._factory_manager.run_company_analysis(
                url=url,
                org_id=org_id,
                user_id=user_id,
                scan_id=scan_id,
                company_name=company_name,
                request_id=request_id,
            )
        except (EngineError, ValueError, RuntimeError) as error:
            logger.exception(
                "Pipeline failed for %s (scan=%s, request=%s)",
                company_name or url,
                scan_id,
                request_id,
            )
            self._record_failure(scan_id, request_id, str(error))
            return
        except Exception as error:
            # Catch-all for programming errors (AttributeError, KeyError, etc.).
            # Record the failure and consume the message instead of retrying via
            # SQS — a consistently-crashing message would retry max_receive_count
            # times, each consuming Lambda capacity and starving other messages.
            # The full traceback is logged to CloudWatch for debugging.
            logger.exception(
                "Unexpected error for %s (scan=%s, request=%s)",
                company_name or url,
                scan_id,
                request_id,
            )
            self._record_failure(scan_id, request_id, str(error))
            return

        # Per-company completion event — the realtime hook uses this to detect
        # the first completed company and navigate to the portfolio page early.
        notify_progress(
            scan_id=scan_id,
            progress=100,
            label="Analysis complete",
            status="complete",
            company_id=request_id,
        )

        self._update_scan_progress(scan_id)

    def _process_reanalysis(self, message: dict[str, Any]) -> None:
        """Re-run the pipeline with supplementary document text.

        Ordering: fetch doc text → run pipeline → delete old results.
        Old results are kept until the pipeline succeeds so that a failure
        does not leave the user with no analysis data.
        """
        analysis_id = message["analysis_id"]
        url = message["url"]
        org_id = message["org_id"]
        user_id = message["user_id"]
        # scan_id is always present but may be "" for standalone (non-portfolio) re-analyses
        scan_id = message["scan_id"]

        logger.info("Re-analyzing %s with documents", analysis_id)

        # Fetch combined document text from DynamoDB
        assessment_repo = self._storage.create_assessment_repository()
        assessments = assessment_repo.find_by_company(analysis_id)
        document_text = ""
        old_assessment_id = ""
        if assessments:
            old_assessment_id = assessments[0]["id"]
            document_text = assessment_repo.get_combined_document_text(old_assessment_id)

        try:
            self._factory_manager.run_company_analysis(
                url=url,
                org_id=org_id,
                user_id=user_id,
                scan_id=scan_id,
                request_id=analysis_id,
                document_text=document_text or None,
            )
        except (EngineError, ValueError, RuntimeError) as error:
            logger.exception("Re-analysis pipeline failed for %s", analysis_id)
            company_repo = self._storage.create_company_repository()
            company_repo.update(analysis_id, {"error": str(error)})
            if scan_id:
                self._update_scan_progress(scan_id)
            return
        except Exception as error:
            logger.exception("Unexpected error during re-analysis for %s", analysis_id)
            company_repo = self._storage.create_company_repository()
            company_repo.update(analysis_id, {"error": str(error)})
            if scan_id:
                self._update_scan_progress(scan_id)
            return

        # Delete old results only after pipeline succeeds — preserves data on failure
        if old_assessment_id:
            assessment_repo.delete_analysis_results(old_assessment_id)

        if scan_id:
            self._update_scan_progress(scan_id)

    def _process_portfolio_discovery(self, message: dict[str, Any]) -> None:
        """Run the portfolio discovery + validation pipeline for a scan.

        Flow: mark scan ``discovering`` → run pipeline → write results +
        transition to ``awaiting_confirmation`` (success) or ``failed``
        (domain error). Programming errors propagate to trigger SQS retry.
        """
        url = message["url"]
        org_id = message["org_id"]
        user_id = message["user_id"]
        scan_id = message["scan_id"]

        logger.info("Starting portfolio discovery for %s (scan=%s)", url, scan_id)

        scan_repo = self._storage.create_scan_repository()
        scan_repo.update(scan_id, {"status": "discovering", "progress": 5})
        notify_progress(
            scan_id=scan_id,
            progress=5,
            label="Starting portfolio discovery…",
            status="discovering",
        )

        try:
            result = self._factory_manager.run_portfolio_discovery(
                url=url,
                org_id=org_id,
                user_id=user_id,
                scan_id=scan_id,
            )
        except (EngineError, ValueError, RuntimeError) as error:
            logger.exception("Portfolio discovery failed for scan=%s", scan_id)
            scan_repo.update(scan_id, {"status": "failed", "error": str(error)})
            notify_progress(
                scan_id=scan_id,
                progress=0,
                label=f"Discovery failed: {error}",
                status="failed",
            )
            return
        # Programming errors (AttributeError, KeyError, TypeError) propagate
        # to the outer SQS handler, triggering retry via batchItemFailures.

        # Bare key access — if the pipeline succeeds but omits this key it
        # is a programming error (schema drift), not a user-visible state.
        # Let KeyError propagate so SQS retries and CloudWatch captures it
        # rather than silently stranding the user on an empty confirmation.
        companies = result["details"]["portfolio_companies"]
        scan_repo.update(
            scan_id,
            {
                "status": "awaiting_confirmation",
                "progress": 20,
                "portfolio_companies": companies,
            },
        )
        notify_progress(
            scan_id=scan_id,
            progress=20,
            label="Ready for confirmation",
            status="awaiting_confirmation",
        )
        logger.info(
            "Portfolio discovery complete for scan=%s (companies=%d)",
            scan_id,
            len(companies),
        )

    def _record_failure(self, scan_id: str, request_id: str, error_message: str) -> None:
        """Record a pipeline failure on the company and update scan progress.

        Uses update() (attribute-level patch) instead of save() to avoid
        overwriting any fields already persisted by earlier pipeline steps.
        If the record does not yet exist, update_item creates a minimal item.
        """
        company_repo = self._storage.create_company_repository()
        company_repo.update(request_id, {"id": request_id, "error": error_message})

        # Per-company failure event — lets the frontend show the FAILED badge
        # instantly via realtime instead of waiting for the next poll cycle.
        notify_progress(
            scan_id=scan_id,
            progress=0,
            label=f"Analysis failed: {error_message}",
            status="failed",
            company_id=request_id,
        )

        self._update_scan_progress(scan_id)

    def _update_scan_progress(self, scan_id: str) -> None:
        """Recalculate and persist scan progress based on resolved companies."""
        scan_repo = self._storage.create_scan_repository()
        scan = scan_repo.get_by_id(scan_id)
        if scan is None:
            raise RuntimeError(
                f"Scan {scan_id} not found after analysis — possible consistency error"
            )

        total_companies = scan.get("total_companies", 0)
        company_repo = self._storage.create_company_repository()
        linked = scan_repo.get_scan_companies(scan_id)
        resolved = sum(
            1
            for link in linked
            if (record := company_repo.get_by_id(link["company_id"]))
            and (record.get("overall_risk_score") is not None or record.get("error"))
        )

        if total_companies and resolved >= total_companies:
            scan_repo.update(
                scan_id,
                {"status": "complete", "progress": 100, "completed_count": resolved},
            )
            notify_progress(
                scan_id=scan_id,
                progress=100,
                label="Analysis complete!",
                status="complete",
            )
        else:
            progress = (
                min(10 + round((resolved / total_companies) * 85), 95) if total_companies else 50
            )
            scan_repo.update(scan_id, {"progress": progress, "completed_count": resolved})

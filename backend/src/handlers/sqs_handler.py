"""SQS handler for async company analysis.

Processes messages from the portfolio analysis queue — each message
triggers a single company analysis pipeline.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from src.handlers.factory_manager import FactoryManager
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
        """Process a single SQS message and run the company analysis pipeline."""
        url = message["url"]
        org_id = message["org_id"]
        user_id = message["user_id"]
        scan_id = message["scan_id"]
        company_name = message.get("company_name", "")

        logger.info("Processing async analysis for %s (%s)", company_name or url, scan_id)

        self._factory_manager.run_company_analysis(
            url=url,
            org_id=org_id,
            user_id=user_id,
            scan_id=scan_id,
            company_name=company_name,
        )

        # Update scan progress
        scan_repo = self._storage.create_scan_repository()
        scan = scan_repo.get_by_id(scan_id)
        if scan:
            current_progress = scan.get("progress", 0)
            new_progress = min(current_progress + 10, 95)
            scan_repo.update(scan_id, {"progress": new_progress})

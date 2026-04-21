"""Step Function handlers for portfolio batch coordination.

Three handlers invoked by the Step Functions state machine:
- send_wave: dispatches a wave of company analyses via direct Lambda invoke
- check_wave: polls DynamoDB to see if the wave is complete
- mark_complete: updates the scan to status=complete after all waves finish
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import boto3

from src.pipeline.appsync_notifier import notify_progress
from src.repositories.dynamodb.provider import DynamoDBStorageProvider

logger = logging.getLogger(__name__)

_WORKER_FUNCTION_NAME = os.environ.get("WORKER_FUNCTION_NAME", "")


def handle_send_wave(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    """Send the next wave of company analyses by invoking the Worker Lambda directly.

    Input:
        companies: list of {name, url, analysis_id} remaining to process
        wave_size: number of companies per wave
        scan_id, org_id, user_id: scan context

    Output:
        remaining_companies: companies not yet dispatched
        wave_company_ids: analysis_ids of the dispatched wave
        scan_id, org_id, user_id: passthrough for subsequent states
    """
    companies = event["companies"]
    wave_size = event["wave_size"]
    scan_id = event["scan_id"]
    org_id = event["org_id"]
    user_id = event["user_id"]

    if not _WORKER_FUNCTION_NAME:
        message = "WORKER_FUNCTION_NAME not set — cannot dispatch wave"
        raise RuntimeError(message)

    wave = companies[:wave_size]
    remaining = companies[wave_size:]

    lambda_client = boto3.client("lambda")
    wave_company_ids = []

    for company in wave:
        payload = {
            "source": "step_functions",
            "url": company["url"],
            "company_name": company.get("name", ""),
            "org_id": org_id,
            "user_id": user_id,
            "scan_id": scan_id,
            "request_id": company["analysis_id"],
        }
        lambda_client.invoke(
            FunctionName=_WORKER_FUNCTION_NAME,
            InvocationType="Event",
            Payload=json.dumps(payload),
        )
        wave_company_ids.append(company["analysis_id"])

    logger.info(
        "Dispatched wave of %d companies for scan=%s (%d remaining)",
        len(wave),
        scan_id,
        len(remaining),
    )

    return {
        "companies": remaining,
        "remaining_count": len(remaining),
        "wave_company_ids": wave_company_ids,
        "scan_id": scan_id,
        "org_id": org_id,
        "user_id": user_id,
        "wave_size": wave_size,
    }


def handle_check_wave(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    """Check if all companies in the current wave have completed.

    Queries DynamoDB for each company record and checks for analyzedAt or error.

    Output includes wave_done=True/False; all other fields are passthrough.
    """
    wave_company_ids = event["wave_company_ids"]
    scan_id = event["scan_id"]

    storage = DynamoDBStorageProvider()
    company_repo = storage.create_company_repository()

    records = company_repo.get_by_ids(wave_company_ids)
    resolved = sum(1 for record in records if record.get("analyzed_at") or record.get("error"))

    wave_done = resolved >= len(wave_company_ids)

    logger.info(
        "Wave check for scan=%s: %d/%d resolved (done=%s)",
        scan_id,
        resolved,
        len(wave_company_ids),
        wave_done,
    )

    return {
        **event,
        "wave_done": wave_done,
    }


def handle_mark_complete(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    """Mark the scan as complete after all waves finish.

    Updates the scan record and emits an AppSync notification.
    """
    scan_id = event["scan_id"]

    storage = DynamoDBStorageProvider()
    scan_repo = storage.create_scan_repository()

    scan_repo.update(scan_id, {"status": "complete", "progress": 100})

    notify_progress(
        scan_id=scan_id,
        progress=100,
        label="Analysis complete!",
        status="complete",
    )

    logger.info("Portfolio scan complete: scan=%s", scan_id)

    return {"scan_id": scan_id, "status": "complete"}

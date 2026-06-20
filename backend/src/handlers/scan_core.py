"""Shared scan-start/confirm core — one code path for HTTP and MCP.

``handle_scan_start`` / ``handle_scan_confirm`` (HTTP) and the MCP write tools
(``start_company_scan`` etc.) both delegate here, so scans behave identically
regardless of entry point. Functions return plain dicts; callers own their
envelopes (HTTP responses vs Markdown tool output). Caller-controlled input
problems raise ``ScanInputError`` — the one expected domain error callers map
to a 400 / tool message. Anything else propagating is a bug and must surface.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Protocol

import boto3

from src.handlers.sqs_messages import (
    build_analysis_message,
    build_portfolio_deepen_message,
    build_portfolio_discovery_message,
)

if TYPE_CHECKING:
    from src.repositories.dynamodb.scan_repository import DynamoDBScanRepository

logger = logging.getLogger(__name__)


class ScanActor(Protocol):
    """Whoever is starting the scan.

    Satisfied structurally by the HTTP ``AuthContext`` and the MCP
    ``AuthenticatedUser`` alike (read-only properties, so frozen dataclasses
    qualify).
    """

    @property
    def user_id(self) -> str:
        """Internal id of the user starting the scan."""
        ...

    @property
    def org_id(self) -> str:
        """Organization the scan belongs to."""
        ...


class ScanInputError(ValueError):
    """Caller-visible validation failure (HTTP 400 / MCP tool message)."""


def start_scan(
    scan_repo: DynamoDBScanRepository,
    *,
    url: str,
    scan_type: str,
    authentication: ScanActor,
    sqs: Any,
    queue_url: str,
) -> dict[str, Any]:
    """Create a scan record and dispatch the work; return snake_case result.

    Returns ``{"scan_id", "status"}`` for portfolio scans and additionally
    ``"analysis_id"`` for single scans. Presence validation of ``url`` /
    ``scan_type`` is the caller's job (each entry point phrases it natively).
    """
    scan_id = _create_scan_record(scan_repo, url, scan_type, authentication)
    if scan_type == "portfolio":
        return _start_portfolio_scan(scan_id, url, authentication, sqs, queue_url)
    return _start_single_scan(scan_repo, scan_id, url, authentication, sqs, queue_url)


def _create_scan_record(
    scan_repo: DynamoDBScanRepository,
    url: str,
    scan_type: str,
    authentication: ScanActor,
) -> str:
    scan_id = str(uuid.uuid4())
    # Portfolio scans are created in "discovering" so the DB record matches
    # the API response the client receives. The worker is idempotent — it
    # re-asserts "discovering" on entry, then transitions to
    # "awaiting_confirmation" (success) or "failed" (domain error). Single
    # scans are "running" since they dispatch per-company work to SQS.
    initial_status = "discovering" if scan_type == "portfolio" else "running"
    scan_repo.create(
        {
            "id": scan_id,
            "org_id": authentication.org_id,
            "created_by": authentication.user_id,
            "type": scan_type,
            "source_url": url,
            "status": initial_status,
            "progress": 0,
            "created_at": datetime.now(UTC).isoformat(),
        }
    )
    return scan_id


def _start_portfolio_scan(
    scan_id: str,
    url: str,
    authentication: ScanActor,
    sqs: Any,
    queue_url: str,
) -> dict[str, Any]:
    """Dispatch portfolio discovery to the SQS worker and return immediately.

    The worker runs ``DiscoverPortfolio`` → ``ValidatePortfolioCompanies`` and
    writes results to the scan record. Clients poll the scan to observe the
    status transition through ``discovering`` to ``awaiting_confirmation``
    (or ``failed``).
    """
    sqs.send_message(
        QueueUrl=queue_url,
        MessageBody=build_portfolio_discovery_message(
            url=url,
            org_id=authentication.org_id,
            user_id=authentication.user_id,
            scan_id=scan_id,
        ),
    )
    return {"scan_id": scan_id, "status": "discovering"}


def _start_single_scan(
    scan_repo: DynamoDBScanRepository,
    scan_id: str,
    url: str,
    authentication: ScanActor,
    sqs: Any,
    queue_url: str,
) -> dict[str, Any]:
    analysis_id = str(uuid.uuid4())
    scan_repo.update(scan_id, {"status": "running", "progress": 10, "total_companies": 1})
    scan_repo.link_company(scan_id, analysis_id, "")

    sqs.send_message(
        QueueUrl=queue_url,
        MessageBody=build_analysis_message(
            url=url,
            org_id=authentication.org_id,
            user_id=authentication.user_id,
            scan_id=scan_id,
            request_id=analysis_id,
        ),
    )

    return {"scan_id": scan_id, "status": "running", "analysis_id": analysis_id}


def deepen_scan(  # noqa: NAMING001  deepen is a verb; not in the checker's heuristic list
    scan_repo: DynamoDBScanRepository,
    *,
    scan_id: str,
    source_url: str,
    authentication: ScanActor,
    sqs: Any,
    queue_url: str,
) -> dict[str, Any]:
    """Dispatch a customer-triggered deepen of an awaiting-confirmation scan.

    Marks the scan ``discovering`` (so clients re-enter the polling/realtime
    loop immediately) and dispatches a deepen message; the worker seeds from the
    scan's current companies, runs the deeper search, and merges results back.
    Returns ``{"scan_id", "status"}``. Scan existence/org/status validation is
    the caller's job.
    """
    scan_repo.update(scan_id, {"status": "discovering", "progress": 5})
    sqs.send_message(
        QueueUrl=queue_url,
        MessageBody=build_portfolio_deepen_message(
            url=source_url,
            org_id=authentication.org_id,
            user_id=authentication.user_id,
            scan_id=scan_id,
        ),
    )
    return {"scan_id": scan_id, "status": "discovering"}


def confirm_scan(  # noqa: NAMING001  confirm is a verb; not in the checker's heuristic list
    scan_repo: DynamoDBScanRepository,
    *,
    scan_id: str,
    companies: list[dict[str, Any]],
    authentication: ScanActor,
    sqs: Any,
    queue_url: str,
) -> dict[str, Any]:
    """Confirm discovered companies and dispatch their analyses.

    Returns ``{"queued": [{"name", "analysisId"}, …]}`` (item keys match the
    long-standing HTTP response shape verbatim). Scan existence + org access
    are the caller's job; this core only enforces company validity.

    Raises:
        ScanInputError: If no company has an http(s) url.
    """
    valid_companies = [c for c in companies if c.get("url", "").startswith(("http://", "https://"))]
    if not valid_companies:
        raise ScanInputError("At least one company with a url is required")

    scan_repo.update(
        scan_id,
        {"status": "running", "progress": 10, "total_companies": len(valid_companies)},
    )

    # Create scan→company links and build the company list for dispatch.
    # The link record persists company_url + order_index so the portfolio
    # view can render every card from t=0 in submission order, even
    # before a worker has picked up the SQS message.
    queued: list[dict[str, str]] = []
    company_payloads: list[dict[str, str]] = []
    for index, company in enumerate(valid_companies):
        company_name = company.get("name", "")
        company_url = company["url"]
        analysis_id = str(uuid.uuid4())
        scan_repo.link_company(
            scan_id,
            analysis_id,
            company_name,
            company_url=company_url,
            order_index=index,
        )
        queued.append({"name": company_name, "analysisId": analysis_id})
        company_payloads.append(
            {
                "name": company_name,
                "url": company_url,
                "analysis_id": analysis_id,
            }
        )

    if len(valid_companies) == 1:
        # Single company — send directly to SQS (fast path, no orchestration).
        sqs.send_message(
            QueueUrl=queue_url,
            MessageBody=build_analysis_message(
                url=valid_companies[0]["url"],
                org_id=authentication.org_id,
                user_id=authentication.user_id,
                scan_id=scan_id,
                request_id=queued[0]["analysisId"],
                company_name=valid_companies[0].get("name", ""),
            ),
        )
    else:
        # Multiple companies — dispatch via Step Functions in waves.
        # Fail-fast: missing ARN in a deployed environment is a config bug.
        state_machine_arn = os.environ["PORTFOLIO_STATE_MACHINE_ARN"]
        wave_size = int(os.environ.get("WAVE_SIZE", "4"))
        sfn_client = boto3.client("stepfunctions")  # type: ignore[reportUnknownMemberType]
        sfn_client.start_execution(
            stateMachineArn=state_machine_arn,
            input=json.dumps(
                {
                    "companies": company_payloads,
                    "wave_size": wave_size,
                    "scan_id": scan_id,
                    "org_id": authentication.org_id,
                    "user_id": authentication.user_id,
                }
            ),
        )

    return {"queued": queued}

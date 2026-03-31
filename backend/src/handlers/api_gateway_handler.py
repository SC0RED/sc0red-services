"""API Gateway REST handler — routes HTTP requests to business logic.

Replaces the Next.js API routes with equivalent Python handlers.
Request/response shapes are identical to minimize frontend changes.
"""

from __future__ import annotations

import json
import logging
import os
from decimal import Decimal
from typing import Any

import boto3

from src.handlers.auth_middleware import require_authentication
from src.handlers.factory_manager import FactoryManager
from src.handlers.router import Router
from src.repositories.dynamodb.provider import DynamoDBStorageProvider

logger = logging.getLogger(__name__)

LambdaResponse = dict[str, Any]


def serialize_decimal(value: object) -> float | int | str:
    """Convert Decimal to numeric types so JSON output stays numeric, not stringified."""
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    return str(value)


def build_json_response(body: dict[str, Any], status: int = 200) -> LambdaResponse:
    """Build an API Gateway JSON response with CORS headers."""
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
            "Access-Control-Allow-Methods": "GET,POST,DELETE,OPTIONS",
        },
        "body": json.dumps(body, default=serialize_decimal),
    }


def build_error(message: str, status: int = 400) -> LambdaResponse:
    """Build an error JSON response with the given message and status code."""
    return build_json_response({"error": message}, status)


def build_company_summary(company: dict[str, Any]) -> dict[str, Any]:
    """Build a camelCase summary dict from a company DynamoDB record."""
    # Uses .get() because during pipeline execution, the company record is
    # a partial item (only pipeline_progress + pipeline_label) created by
    # _report_progress. Full fields are only present after persist_results.
    return {
        "id": company.get("id", ""),
        "companyName": company.get("company_name", ""),
        "companyUrl": company.get("company_url", ""),
        "industry": company.get("industry", ""),
        "overallRiskScore": company.get("overall_risk_score"),
        "riskTier": company.get("risk_tier"),
        "error": company.get("error"),
        "analyzedAt": company.get("analyzed_at"),
        "pipelineProgress": company.get("pipeline_progress", 0),
        "pipelineLabel": company.get("pipeline_label", ""),
    }


class APIGatewayHandler:
    """Handles all API Gateway HTTP requests."""

    def __init__(self, storage: DynamoDBStorageProvider | None = None) -> None:
        self._storage = storage or DynamoDBStorageProvider()
        self._factory_manager = FactoryManager(self._storage)
        self._queue_url = os.environ["ANALYSIS_QUEUE_URL"]
        self._sqs = boto3.client("sqs")
        self._documents_bucket = os.environ.get("DOCUMENTS_BUCKET", "")
        if not self._documents_bucket:
            logger.warning(
                "DOCUMENTS_BUCKET not set — S3 document upload disabled, falling back to base64"
            )
        self._s3 = boto3.client("s3") if self._documents_bucket else None
        self._router = self._build_router()

    def _build_router(self) -> Router:
        from src.handlers.analysis_handlers import (
            handle_dashboard,
            handle_delete_analysis,
            handle_get_analysis,
            handle_list_analyses,
            handle_reanalyze,
        )
        from src.handlers.auth_handlers import handle_login, handle_register
        from src.handlers.document_handlers import (
            handle_create_document,
            handle_delete_document,
            handle_upload_url,
        )
        from src.handlers.invitation_handlers import (
            handle_invite_member,
            handle_list_members,
            handle_remove_member,
            handle_resend_invite,
            handle_revoke_invite,
        )
        from src.handlers.scan_handlers import (
            handle_delete_scan,
            handle_scan_confirm,
            handle_scan_start,
            handle_scan_status,
        )

        router = Router()

        router.protected(
            "GET",
            "/api/config",
            lambda _event, _authentication: build_json_response(
                {
                    "appsyncEndpoint": os.environ.get("APPSYNC_ENDPOINT", ""),
                    "appsyncApiKey": os.environ.get("APPSYNC_API_KEY", ""),
                }
            ),
        )

        router.public(
            "POST",
            "/api/auth/register",
            lambda event: handle_register(event, self._storage),
        )
        router.public(
            "POST",
            "/api/auth/login",
            lambda event: handle_login(event, self._storage),
        )

        # Org member management
        router.protected(
            "POST",
            "/api/org/invite",
            lambda event, authentication: handle_invite_member(
                event, authentication, self._storage
            ),
        )
        router.protected(
            "POST",
            "/api/org/invite/resend",
            lambda event, authentication: handle_resend_invite(
                event, authentication, self._storage
            ),
        )
        router.protected(
            "DELETE",
            "/api/org/invite/{invite_id}",
            lambda event, authentication, invite_id: handle_revoke_invite(
                event, authentication, self._storage, invite_id
            ),
        )
        router.protected(
            "GET",
            "/api/org/members",
            lambda event, authentication: handle_list_members(event, authentication, self._storage),
        )
        router.protected(
            "DELETE",
            "/api/org/members/{user_id}",
            lambda event, authentication, user_id: handle_remove_member(
                event, authentication, self._storage, user_id
            ),
        )

        router.protected(
            "POST",
            "/api/scan/start",
            lambda event, authentication: handle_scan_start(
                event,
                authentication,
                self._storage,
                self._factory_manager,
                self._sqs,
                self._queue_url,
            ),
        )
        router.protected(
            "GET",
            "/api/scan/{scan_id}",
            lambda event, authentication, scan_id: handle_scan_status(
                event, authentication, self._storage, scan_id
            ),
        )
        router.protected(
            "POST",
            "/api/scan/{scan_id}/confirm",
            lambda event, authentication, scan_id: handle_scan_confirm(
                event, authentication, self._storage, self._sqs, self._queue_url, scan_id
            ),
        )
        router.protected(
            "DELETE",
            "/api/scan/{scan_id}",
            lambda event, authentication, scan_id: handle_delete_scan(
                event, authentication, self._storage, scan_id
            ),
        )

        router.protected(
            "GET",
            "/api/analysis/{analysis_id}",
            lambda event, authentication, analysis_id: handle_get_analysis(
                event, authentication, self._storage, analysis_id
            ),
        )
        router.protected(
            "DELETE",
            "/api/analysis/{analysis_id}",
            lambda event, authentication, analysis_id: handle_delete_analysis(
                event, authentication, self._storage, analysis_id
            ),
        )
        router.protected(
            "GET",
            "/api/analyses",
            lambda event, authentication: handle_list_analyses(
                event, authentication, self._storage
            ),
        )
        router.protected(
            "GET",
            "/api/dashboard",
            lambda event, authentication: handle_dashboard(event, authentication, self._storage),
        )
        router.protected(
            "POST",
            "/api/analysis/{analysis_id}/reanalyze",
            lambda event, authentication, analysis_id: handle_reanalyze(
                event, authentication, self._storage, self._sqs, self._queue_url, analysis_id
            ),
        )

        router.protected(
            "POST",
            "/api/analysis/{analysis_id}/upload-url",
            lambda event, authentication, analysis_id: handle_upload_url(
                event, authentication, self._storage, self._s3, self._documents_bucket, analysis_id
            ),
        )
        router.protected(
            "POST",
            "/api/analysis/{analysis_id}/documents",
            lambda event, authentication, analysis_id: handle_create_document(
                event, authentication, self._storage, self._s3, self._documents_bucket, analysis_id
            ),
        )
        router.protected(
            "DELETE",
            "/api/analysis/{analysis_id}/documents/{document_id}",
            lambda event, authentication, analysis_id, document_id: handle_delete_document(
                event, authentication, self._storage, analysis_id, document_id
            ),
        )

        return router

    def handle(self, event: dict[str, Any]) -> LambdaResponse:
        """Route an API Gateway event to the appropriate handler."""
        method = event.get("httpMethod", "GET")
        path = event.get("path", "")
        headers = event.get("headers") or {}

        if method == "OPTIONS":
            return build_json_response({}, 200)

        result = self._router.dispatch(method, path)
        if result is None:
            return build_error("Not found", 404)

        handler, path_params, authenticated = result
        if not authenticated:
            return handler(event, **path_params)

        try:
            authentication = require_authentication(headers)
        except ValueError as e:
            return build_error(str(e), 401)

        return handler(event, authentication, **path_params)

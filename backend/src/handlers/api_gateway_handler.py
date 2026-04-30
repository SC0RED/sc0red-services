"""API Gateway REST handler — routes HTTP requests to business logic.

Replaces the Next.js API routes with equivalent Python handlers.
Request/response shapes are identical to minimize frontend changes.
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from decimal import Decimal
from typing import Any

import boto3

from src.handlers.api_response_logger import finalize_response
from src.handlers.auth_middleware import require_authentication
from src.handlers.factory_manager import FactoryManager
from src.handlers.router import Router
from src.repositories.dynamodb.provider import DynamoDBStorageProvider

logger = logging.getLogger(__name__)

LambdaResponse = dict[str, Any]

# ── Error codes ────────────────────────────────────────────────────────────
# Included in error responses as {"error": "...", "code": "..."}
# so the frontend can handle errors programmatically.

VALIDATION_ERROR = "VALIDATION_ERROR"
NOT_FOUND = "NOT_FOUND"
UNAUTHORIZED = "UNAUTHORIZED"
FORBIDDEN = "FORBIDDEN"
CONFLICT = "CONFLICT"
NOT_CONFIGURED = "NOT_CONFIGURED"
ROUTE_NOT_FOUND = "ROUTE_NOT_FOUND"


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


def build_error(message: str, status: int = 400, code: str = "") -> LambdaResponse:
    """Build an error JSON response with the given message, status code, and error code."""
    body: dict[str, Any] = {"error": message}
    if code:
        body["code"] = code
    return build_json_response(body, status)


def check_org_access(
    resource: dict[str, Any] | None,
    authentication: Any,
) -> LambdaResponse | None:
    """Check if a resource belongs to the authenticated user's org.

    Returns a 404 error response if the resource is missing or belongs to
    a different org. Returns None if access is allowed.
    """
    if not resource or resource.get("org_id") != authentication.org_id:
        return build_error("Not found", 404, NOT_FOUND)
    return None


# `build_company_summary` and `compute_company_state` live in
# `src.utilities.scan_summary` to keep utilities independent of
# handlers (utilities ← handlers, never the reverse). Import from
# `src.utilities.scan_summary` directly.


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
        from src.handlers.activity_handlers import handle_get_activity
        from src.handlers.admin_handlers import register_routes as register_admin_routes
        from src.handlers.analysis_handlers import (
            handle_bulk_delete_analyses,
            handle_dashboard,
            handle_delete_analysis,
            handle_get_analysis,
            handle_list_analyses,
            handle_reanalyze,
        )
        from src.handlers.analytics_handlers import handle_post_event as handle_post_analytics_event
        from src.handlers.auth_handlers import handle_register
        from src.handlers.document_handlers import (
            handle_create_document,
            handle_delete_document,
            handle_upload_url,
        )
        from src.handlers.internal_handlers import register_routes as register_internal_routes
        from src.handlers.invitation_handlers import (
            handle_invite_member,
            handle_list_members,
            handle_remove_member,
            handle_resend_invite,
            handle_revoke_invite,
        )
        from src.handlers.oauth_handlers import handle_oauth_approve
        from src.handlers.pdf_render_handlers import register_routes as register_pdf_render_routes
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
        # Bulk delete: race-immune cascade. See `handle_bulk_delete_analyses`
        # for why parallel `DELETE /api/analysis/{id}` calls leave orphan
        # scans, which this endpoint fixes by collapsing N deletes into
        # one handler run.
        router.protected(
            "POST",
            "/api/analyses/bulk-delete",
            lambda event, authentication: handle_bulk_delete_analyses(
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

        # ── OAuth ────────────────────────────────────────────────────────────
        router.protected(
            "POST",
            "/api/oauth/approve",
            lambda event, authentication: handle_oauth_approve(
                event, authentication, self._storage
            ),
        )

        # ── Analytics ────────────────────────────────────────────────────────
        router.protected(
            "POST",
            "/api/analytics/events",
            handle_post_analytics_event,
        )

        # ── Activity feed ────────────────────────────────────────────────────
        router.protected(
            "GET",
            "/api/activity",
            lambda event, authentication: handle_get_activity(event, authentication, self._storage),
        )

        # Admin-only surface for browsing + restoring tombstoned records.
        # Route wiring lives in `admin_handlers.register_routes` so future
        # admin endpoints don't require a gateway edit.
        register_admin_routes(router, self._storage)

        # Internal-key endpoints for the headless PDF render flow.
        register_internal_routes(router, self._storage)

        # PDF render proxy — Cognito-auth, boto3-invokes the Node.js Lambda.
        register_pdf_render_routes(router)

        return router

    def handle(self, event: dict[str, Any]) -> LambdaResponse:
        """Route an API Gateway event to the appropriate handler."""
        start_time = time.monotonic()
        method = event.get("httpMethod", "GET")
        path = event.get("path", "")
        headers = event.get("headers") or {}

        # Extract correlation ID from API Gateway context or generate one
        request_context = event.get("requestContext") or {}
        request_id = request_context.get("requestId") or str(uuid.uuid4())

        if method == "OPTIONS":
            return build_json_response({}, 200)

        finalize_args = {
            "method": method,
            "path": path,
            "request_id": request_id,
            "start_time": start_time,
        }

        result = self._router.dispatch(method, path)
        if result is None:
            return finalize_response(
                build_error("Not found", 404, ROUTE_NOT_FOUND), **finalize_args
            )

        handler, path_params, authenticated = result
        if not authenticated:
            response = handler(event, **path_params)
            return finalize_response(response, **finalize_args)

        try:
            # Pass the user repo so the middleware resolves
            # `authentication.user_id` to the internal user id via the
            # cognito_sub / email fallback chain. See
            # `openspec/changes/fix-actor-attribution/`.
            authentication = require_authentication(
                headers, user_repo=self._storage.create_user_repository()
            )
        except ValueError as e:
            return finalize_response(build_error(str(e), 401, UNAUTHORIZED), **finalize_args)

        response = handler(event, authentication, **path_params)
        return finalize_response(response, **finalize_args)

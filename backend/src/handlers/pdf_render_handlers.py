"""PDF render proxy handler.

The Next.js `/api/export/pdf/{id}` route POSTs to
`/api/admin/render-pdf` (Cognito-authenticated). This handler boto3-
invokes the Node.js PDF render Lambda (see `backend/lambdas/pdf-render/`)
and returns the binary PDF response.

Why proxy through Python instead of mounting the Node.js Lambda directly
on API Gateway: the existing API Gateway uses `LambdaRestApi` (single-
Lambda proxy), and the Python API Lambda is the canonical Cognito-
authenticated entry point. Forwarding via boto3 keeps the auth boundary
single-sourced. Per design.md D2 / task 3.2.
"""

from __future__ import annotations

import json
import logging
import os
from typing import TYPE_CHECKING, Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from src.handlers.api_gateway_handler import (
    NOT_CONFIGURED,
    VALIDATION_ERROR,
    build_error,
    build_json_response,
)

if TYPE_CHECKING:
    from src.handlers.api_gateway_handler import LambdaResponse
    from src.handlers.auth_middleware import AuthContext
    from src.handlers.router import Router

logger = logging.getLogger(__name__)

PDF_RENDER_LAMBDA_ARN_ENVIRONMENT_NAME = "PDF_RENDER_LAMBDA_ARN"


def register_routes(router: Router) -> None:
    """Wire the PDF render proxy into the API Gateway router.

    Cognito-protected — the `Router.protected` middleware forwards a
    validated `AuthContext` to `handle_render_pdf`.
    """
    router.protected("POST", "/api/admin/render-pdf", handle_render_pdf)


# Module-level boto3 client survives Lambda container reuse, avoiding
# the ~50ms per-invoke client init.
_lambda_client = None


def _get_lambda_client() -> Any:
    """Cached boto3 Lambda client. Module-level cache survives container reuse."""
    global _lambda_client
    if _lambda_client is None:
        _lambda_client = boto3.client("lambda")
    return _lambda_client


def _read_body(event: dict[str, Any]) -> dict[str, Any] | None:
    raw = event.get("body")
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None


def handle_render_pdf(
    event: dict[str, Any],
    authentication: AuthContext,
) -> LambdaResponse:
    """POST /api/admin/render-pdf.

    Forwards the request to the Node.js PDF render Lambda. The request
    body is `{analysisId, token, frontendBaseUrl, companyName}` — the
    same shape the Node.js Lambda's `handler` expects.

    The Cognito JWT has already been validated by middleware before we
    arrive here, so we just need to forward + return.
    """
    render_arn = os.environ.get(PDF_RENDER_LAMBDA_ARN_ENVIRONMENT_NAME, "")
    if not render_arn:
        logger.error("handle_render_pdf: %s not set", PDF_RENDER_LAMBDA_ARN_ENVIRONMENT_NAME)
        return build_error("PDF render not configured", 500, NOT_CONFIGURED)

    body = _read_body(event)
    if body is None:
        return build_error("Request body must be JSON", 400, VALIDATION_ERROR)

    required = ("analysisId", "token", "frontendBaseUrl", "companyName")
    for field in required:
        if not isinstance(body.get(field), str) or not body[field]:
            return build_error(f"Field '{field}' is required", 400, VALIDATION_ERROR)

    # Pass through only the fields the Node.js Lambda expects — never
    # forward the full event (Cognito claims, request context, etc).
    payload = {field: body[field] for field in required}

    # Audit log: who minted this render? Useful for tracing weird PDFs
    # back to the org/user that requested them.
    logger.info(
        "render_pdf_invoke",
        extra={
            "user_id": authentication.user_id,
            "org_id": authentication.org_id,
            "analysis_id": payload["analysisId"],
        },
    )

    try:
        response = _get_lambda_client().invoke(
            FunctionName=render_arn,
            InvocationType="RequestResponse",
            Payload=json.dumps({"body": json.dumps(payload)}).encode("utf-8"),
        )
    except (BotoCoreError, ClientError) as error:
        logger.exception("render_pdf_invoke_failed")
        return build_error(f"PDF render invoke failed: {error}", 502)

    raw_payload = response.get("Payload")
    if raw_payload is None:
        return build_error("PDF render returned no payload", 502)

    try:
        result = json.loads(raw_payload.read().decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as error:
        logger.exception("render_pdf_payload_decode_failed")
        return build_error(f"PDF render returned invalid payload: {error}", 502)

    status = int(result.get("statusCode", 500))
    success_status = 200
    if status != success_status:
        # Surface the error back to the caller verbatim — the frontend
        # button shows a generic Toast, but logs preserve the reason.
        try:
            body_payload = json.loads(result.get("body", "{}"))
            return build_json_response(body_payload, status)
        except (TypeError, ValueError):
            return build_error("PDF render failed", status)

    # Happy path: the Node.js Lambda returned `{statusCode: 200, body: <base64>,
    # isBase64Encoded: true, headers: {...}}`. Re-emit it as our own API
    # Gateway proxy response so binary streams correctly via the
    # `application/pdf` binary media-type configured at the gateway.
    if "body" not in result:
        # Contract violation — the Node.js handler always sets `body` on
        # the success path. A 200 with no body would silently render an
        # empty PDF in the browser; surface as 502 instead.
        logger.error("render_pdf_missing_body")
        return build_error("PDF render returned 200 with no body", 502)

    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/pdf",
            "Cache-Control": "no-store",
            "Access-Control-Allow-Origin": "*",
        },
        "body": result["body"],
        "isBase64Encoded": bool(result.get("isBase64Encoded")),
    }

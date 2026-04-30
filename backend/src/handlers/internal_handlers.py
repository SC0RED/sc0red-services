"""Internal-key authenticated handlers.

These endpoints sit behind a per-environment shared-secret API key
(`INTERNAL_API_KEY`, Secrets Manager-managed) instead of a Cognito JWT.
They exist for service-to-service calls within our own AWS account that
don't have a user session — specifically the headless PDF render path,
where the Next.js `/print/{analysisId}` server component needs to load
analysis data on behalf of a render job whose only authorisation is a
short-lived HMAC URL token (the URL token's claims are forwarded as
`X-Org-Id`).

Auth model:
- `X-Internal-Api-Key` MUST match `INTERNAL_API_KEY` env var (constant-time)
- `X-Org-Id` MUST be present and is used to scope the lookup
- The handler is registered as `Router.public` so the standard JWT
  middleware doesn't run; this module enforces its own auth boundary

Anything more sensitive than read-only analysis data should NOT be
exposed via this path without explicit review.
"""

from __future__ import annotations

import hmac
import logging
import os
from typing import TYPE_CHECKING, Any

from src.handlers.analysis_payload import build_analysis_payload
from src.handlers.api_gateway_handler import (
    NOT_CONFIGURED,
    NOT_FOUND,
    UNAUTHORIZED,
    VALIDATION_ERROR,
    build_error,
    build_json_response,
)

if TYPE_CHECKING:
    from src.handlers.api_gateway_handler import LambdaResponse
    from src.handlers.router import Router
    from src.repositories.dynamodb.provider import DynamoDBStorageProvider

logger = logging.getLogger(__name__)

INTERNAL_API_KEY_ENVIRONMENT_NAME = "INTERNAL_API_KEY"


def register_routes(router: Router, storage: DynamoDBStorageProvider) -> None:
    """Wire the internal-key endpoints into the API Gateway router.

    Keeps route registration adjacent to the handler module — same
    pattern as `admin_handlers.register_routes`. Routes are `public`
    because this module enforces its own auth (constant-time API key +
    X-Org-Id), bypassing the Cognito middleware.
    """
    router.public(
        "GET",
        "/api/internal/analysis/{analysis_id}",
        lambda event, analysis_id: handle_internal_get_analysis(event, storage, analysis_id),
    )


class InternalKeyNotConfiguredError(RuntimeError):
    """Raised when the `INTERNAL_API_KEY` env var is not set.

    The handler catches this and returns a 500 — surfaces the misconfig
    to ops without a misleading 401 (which would imply a client problem).
    """


def _read_internal_key() -> str:
    """Resolve the shared secret.

    Raises `InternalKeyNotConfiguredError` when the env var is unset —
    matches the fail-fast pattern used in the TypeScript
    `readSigningSecret()`.
    """
    secret = os.environ.get(INTERNAL_API_KEY_ENVIRONMENT_NAME, "")
    if not secret:
        raise InternalKeyNotConfiguredError(
            f"{INTERNAL_API_KEY_ENVIRONMENT_NAME} is not set on the API Lambda runtime",
        )
    return secret


def _get_header(headers: dict[str, str], name: str) -> str:
    """Case-insensitive header lookup. API Gateway sometimes lowercases."""
    return headers.get(name) or headers.get(name.lower(), "")


def handle_internal_get_analysis(
    event: dict[str, Any],
    storage: DynamoDBStorageProvider,
    analysis_id: str,
) -> LambdaResponse:
    """Handle GET /api/internal/analysis/{analysis_id}.

    Verifies the internal API key (constant-time) and the org-id header,
    then loads the analysis payload scoped to that org. 404 on miss
    (mirrors the user-facing endpoint's behaviour to avoid leaking the
    existence of cross-org resources).
    """
    try:
        expected_key = _read_internal_key()
    except InternalKeyNotConfiguredError:
        # The env var is not set in this environment. Surface as 500 so
        # ops sees the misconfiguration; do NOT 401 (a 401 would imply a
        # client-fixable problem, which it isn't).
        logger.exception("internal_get_analysis: misconfigured")
        return build_error("Internal endpoint not configured", 500, NOT_CONFIGURED)

    headers = event.get("headers") or {}
    provided_key = _get_header(headers, "X-Internal-Api-Key")
    if not provided_key or not hmac.compare_digest(provided_key, expected_key):
        return build_error("Unauthorized", 401, UNAUTHORIZED)

    org_id = _get_header(headers, "X-Org-Id")
    if not org_id:
        return build_error("X-Org-Id header is required", 400, VALIDATION_ERROR)

    company_repo = storage.create_company_repository()
    company = company_repo.get_by_id(analysis_id)
    if not company or company.get("org_id") != org_id:
        return build_error("Not found", 404, NOT_FOUND)

    return build_json_response(build_analysis_payload(storage, company, analysis_id))

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
- `X-Internal-Api-Key` MUST match the secret resolved from
  `INTERNAL_API_KEY_ARN` at runtime (constant-time compare)
- `X-Org-Id` MUST be present and is used to scope the lookup
- The handler is registered as `Router.public` so the standard JWT
  middleware doesn't run; this module enforces its own auth boundary

Why ARN-based runtime resolution:
- `lambda:GetFunctionConfiguration` is granted to debug/observability
  IAM roles in many orgs. Baking the cleartext secret into
  `Environment.Variables` would expose it via that path. Resolving from
  Secrets Manager at request time (with a module-level cache) keeps the
  exposure narrowed to `secretsmanager:GetSecretValue` on the specific
  secret ARN, which only the API Lambda role holds.

Anything more sensitive than read-only analysis data should NOT be
exposed via this path without explicit review.
"""

from __future__ import annotations

import hmac
import logging
import os
from typing import TYPE_CHECKING, Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

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

INTERNAL_API_KEY_ARN_ENVIRONMENT_NAME = "INTERNAL_API_KEY_ARN"


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
    """Raised when the internal-key secret can't be resolved.

    Triggers when `INTERNAL_API_KEY_ARN` is unset, when the Secrets
    Manager fetch fails, or when the secret value comes back empty.
    The handler maps this to a 500 — surfaces the misconfig to ops
    without a misleading 401.
    """


# Module-level cache of the resolved secret. Survives Lambda container
# reuse so we only pay the Secrets Manager round-trip on the first
# request after a cold start (~30ms). Rotation requires a new container
# (or explicit invalidation, which we don't need today) — documented in
# the secret-rotation runbook.
_internal_api_key_cache: str | None = None
_secrets_client = None


def _get_secrets_client() -> Any:
    """Cached boto3 Secrets Manager client.

    Module-level cache survives container reuse, avoiding ~50ms
    per-invoke client init.
    """
    global _secrets_client
    if _secrets_client is None:
        _secrets_client = boto3.client("secretsmanager")
    return _secrets_client


def _read_internal_key() -> str:
    """Resolve the shared secret from Secrets Manager (cached).

    Reads `INTERNAL_API_KEY_ARN` from env, fetches the secret value via
    `secretsmanager:GetSecretValue` on first use, caches at the module
    level for the lifetime of the Lambda container.
    """
    global _internal_api_key_cache
    if _internal_api_key_cache is not None:
        return _internal_api_key_cache

    arn = os.environ.get(INTERNAL_API_KEY_ARN_ENVIRONMENT_NAME, "")
    if not arn:
        raise InternalKeyNotConfiguredError(
            f"{INTERNAL_API_KEY_ARN_ENVIRONMENT_NAME} is not set on the API Lambda runtime",
        )

    try:
        response = _get_secrets_client().get_secret_value(SecretId=arn)
    except (BotoCoreError, ClientError) as error:
        message = (
            f"Failed to resolve {INTERNAL_API_KEY_ARN_ENVIRONMENT_NAME} "
            f"({arn}): {type(error).__name__}"
        )
        raise InternalKeyNotConfiguredError(message) from error

    secret = response.get("SecretString", "")
    if not secret:
        raise InternalKeyNotConfiguredError(
            f"Secrets Manager returned empty value for {arn}",
        )

    _internal_api_key_cache = secret
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

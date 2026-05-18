"""Cached resolver for the PDF token signing secret.

The async PDF export endpoint signs short-lived URL tokens with an HMAC
secret stored in Secrets Manager. Each token-sign needs the secret
value, but we don't want to hit Secrets Manager on every invocation —
a Lambda container that stays warm for many minutes should round-trip
once.

This module owns:
- The ``PDF_TOKEN_SECRET_ARN`` env var name + the cached boto3 client.
- The runtime fetch + module-level cache of the secret string.

Extracted from ``pdf_export_handlers.py`` so that handler stays under
the 400-line backend file limit (see ``CLAUDE.md`` + ``scripts/audit.sh``).
"""

from __future__ import annotations

import logging
import os
from typing import Any

import boto3

logger = logging.getLogger(__name__)

PDF_TOKEN_SECRET_ARN_ENVIRONMENT_NAME = "PDF_TOKEN_SECRET_ARN"  # noqa: S105  # nosec B105  env var name, not a secret value


# Module-level caches survive Lambda warm-restart, avoiding ~30 ms
# Secrets Manager round-trips per invocation. The client cache also
# avoids the ~50 ms boto3 client init.
_secrets_client: Any = None
_pdf_token_secret_cache: str | None = None


def _get_secrets_client() -> Any:
    """Cached boto3 Secrets Manager client."""
    global _secrets_client
    if _secrets_client is None:
        _secrets_client = boto3.client("secretsmanager")
    return _secrets_client


def read_pdf_token_secret() -> str:
    """Fetch the PDF token signing secret (cached for the container lifetime).

    The secret value is stored in Secrets Manager and injected via the
    ``PDF_TOKEN_SECRET_ARN`` env var. We resolve at runtime (not via
    Lambda env) so the cleartext is never visible via
    ``lambda:GetFunctionConfiguration``.

    Raises ``RuntimeError`` if the env var is unset (configuration bug
    that no fallback can paper over). Raises ``botocore.exceptions.ClientError``
    on Secrets Manager failure (throttling, missing permissions, wrong
    ARN); callers catch + return 500.
    """
    global _pdf_token_secret_cache
    if _pdf_token_secret_cache is not None:
        return _pdf_token_secret_cache
    secret_arn = os.environ.get(PDF_TOKEN_SECRET_ARN_ENVIRONMENT_NAME, "")
    if not secret_arn:
        message = (
            f"{PDF_TOKEN_SECRET_ARN_ENVIRONMENT_NAME} not set — "
            "the API Lambda needs the PDF token secret ARN to mint async-render tokens."
        )
        raise RuntimeError(message)
    response = _get_secrets_client().get_secret_value(SecretId=secret_arn)
    _pdf_token_secret_cache = response["SecretString"]
    return _pdf_token_secret_cache


def _reset_caches_for_tests() -> None:
    """Reset module-level caches between tests. Call from test fixtures only."""
    global _secrets_client, _pdf_token_secret_cache
    _secrets_client = None
    _pdf_token_secret_cache = None

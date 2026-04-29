"""Authentication middleware — Cognito RS256 JWT validation.

Validates JWTs issued by the Cognito User Pool against its JWKS public keys.
Supports COGNITO_JWKS_URL override for testing with mock JWKS endpoints.

User-id resolution (`fix-actor-attribution` boundary fix):
After validating the JWT we resolve `AuthContext.user_id` to the
internal `user["id"]` so handlers can store / read actor attribution
without per-call-site translation. Resolution priority:

  1. `custom:legacy_user_id` claim (preferred when Cognito emits it)
  2. `find_by_cognito_sub(token.sub)` via GSI5
  3. `find_by_email(token.email)` via GSI4 (legacy / unbackfilled
     records)

If all three fail we raise `ValueError` with the same
"Token missing user identifier" semantics that the JWT-only path
used previously — better to fail loudly than to surface a stranger's
id downstream.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import jwt
from jwt import PyJWKClient

if TYPE_CHECKING:
    from src.repositories.dynamodb.user_repository import DynamoDBUserRepository

logger = logging.getLogger(__name__)

# Module-level JWKS client — survives Lambda container reuse, avoids
# re-fetching the JWKS on every request.
_jwks_client: PyJWKClient | None = None


def _get_jwks_client() -> PyJWKClient:
    """Return a cached PyJWKClient for the Cognito User Pool."""
    global _jwks_client
    if _jwks_client is not None:
        return _jwks_client

    # Allow explicit JWKS URL override (for E2E testing with mock JWKS)
    jwks_url = os.environ.get("COGNITO_JWKS_URL", "")
    if not jwks_url:
        region = os.environ.get("COGNITO_REGION", "")
        pool_id = os.environ.get("COGNITO_USER_POOL_ID", "")
        if not region or not pool_id:
            message = "COGNITO_REGION and COGNITO_USER_POOL_ID must be configured"
            raise ValueError(message)
        jwks_url = f"https://cognito-idp.{region}.amazonaws.com/{pool_id}/.well-known/jwks.json"

    _jwks_client = PyJWKClient(jwks_url, cache_keys=True, lifespan=3600)
    return _jwks_client


@dataclass
class AuthContext:
    """Authenticated user context extracted from JWT."""

    user_id: str
    org_id: str
    email: str
    role: str
    name: str = ""


def validate_token(
    authorization: str,
    user_repo: DynamoDBUserRepository | None = None,
) -> AuthContext:
    """Validate an RS256 Bearer token and return the auth context.

    Pass ``user_repo`` to enable the cognito_sub / email fallback chain
    for resolving ``AuthContext.user_id`` to the internal
    ``user["id"]``. When omitted (older callers, tests that don't need
    the lookup), the function falls back to the JWT-only resolution
    that returns whatever the token carries — the legacy behaviour.
    Production callers MUST pass a repo so the actor-id stored on
    records is always the internal id, never the Cognito sub. See
    `openspec/changes/fix-actor-attribution/`.

    Raises:
        ValueError: If the token is missing, invalid, expired, or no
            user can be resolved (when ``user_repo`` is provided and
            all three resolution paths fail).
    """
    if not authorization or not authorization.startswith("Bearer "):
        message = "Missing or invalid Authorization header"
        raise ValueError(message)

    token = authorization[7:]

    try:
        payload = _decode_rs256_token(token)
    except jwt.ExpiredSignatureError:
        message = "Token expired"
        raise ValueError(message) from None
    except (jwt.PyJWKClientError, jwt.InvalidTokenError) as error:
        message = f"Invalid token: {error}"
        raise ValueError(message) from None

    # Extract claims — support both Cognito custom attributes and plain claims
    org_id = payload.get("custom:org_id") or payload.get("orgId", "")
    if not org_id:
        message = "Token missing required org_id claim"
        raise ValueError(message)

    user_id = _resolve_user_id(payload, user_repo)
    if not user_id:
        message = "Token missing user identifier"
        raise ValueError(message)

    return AuthContext(
        user_id=user_id,
        org_id=org_id,
        email=payload.get("email", ""),
        role=payload.get("custom:role") or payload.get("role", "analyst"),
        name=payload.get("name", ""),
    )


def _resolve_user_id(
    payload: dict[str, Any],
    user_repo: DynamoDBUserRepository | None,
) -> str:
    """Resolve `AuthContext.user_id` to the internal user id.

    Resolution chain:
    1. ``custom:legacy_user_id`` claim — preferred when Cognito emits it.
    2. ``user_repo.find_by_cognito_sub(token.sub)`` — primary fallback,
       single-item GSI5 query. Returns None for records that haven't
       been backfilled yet (the user-cognito-keys backfill populates
       `cognito_sub` + `GSI5PK` post-deploy).
    3. ``user_repo.find_by_email(token.email)`` — secondary fallback,
       covers the GSI5-still-CREATING window and any record whose
       `cognito_sub` was never written. Existing GSI4 has every
       user record indexed by email since day 0.

    Returns the empty string if no resolution succeeds AND no
    `user_repo` is provided AND the token has no `sub` (legacy
    behaviour). Production callers should treat empty string as a
    failure and raise `ValueError` upstream.
    """
    legacy_id = payload.get("custom:legacy_user_id", "")
    if legacy_id:
        return legacy_id

    sub = payload.get("sub", "") or payload.get("id", "")
    email = payload.get("email", "")

    # No repo passed (older callers / tests) — fall back to whatever
    # the token carries. Matches the pre-`fix-actor-attribution`
    # behaviour exactly.
    if user_repo is None:
        return sub

    if sub:
        user = user_repo.find_by_cognito_sub(sub)
        if user and user.get("id"):
            return user["id"]

    if email:
        user = user_repo.find_by_email(email)
        if user and user.get("id"):
            return user["id"]

    # No resolution path succeeded. Caller raises `ValueError` —
    # better to fail loudly than to surface a stranger's id (or a
    # raw Cognito sub) on stored actor fields downstream.
    return ""


def _decode_rs256_token(token: str) -> dict[str, Any]:
    """Decode and verify an RS256 JWT against the JWKS endpoint."""
    client_id = os.environ.get("COGNITO_CLIENT_ID", "")

    # Build issuer for verification (skip if using custom JWKS URL)
    issuer = None
    region = os.environ.get("COGNITO_REGION", "")
    pool_id = os.environ.get("COGNITO_USER_POOL_ID", "")
    if region and pool_id:
        issuer = f"https://cognito-idp.{region}.amazonaws.com/{pool_id}"

    # When using custom JWKS URL (E2E), skip audience/issuer verification.
    # In production (no COGNITO_JWKS_URL), all three must be configured.
    using_custom_jwks = bool(os.environ.get("COGNITO_JWKS_URL"))

    decode_options: dict[str, Any] = {"verify_exp": True}
    decode_kwargs: dict[str, Any] = {"algorithms": ["RS256"]}

    if using_custom_jwks:
        decode_options["verify_aud"] = False
        decode_options["verify_iss"] = False
    else:
        if not client_id:
            message = "COGNITO_CLIENT_ID must be configured"
            raise ValueError(message)
        decode_kwargs["audience"] = client_id
        decode_kwargs["issuer"] = issuer

    jwks_client = _get_jwks_client()
    signing_key = jwks_client.get_signing_key_from_jwt(token)

    return jwt.decode(
        token,
        signing_key.key,
        options=decode_options,
        **decode_kwargs,
    )


def require_authentication(
    headers: dict[str, str],
    user_repo: DynamoDBUserRepository | None = None,
) -> AuthContext:
    """Extract and validate authentication from request headers.

    Production callers SHOULD pass ``user_repo`` so `AuthContext.user_id`
    is resolved to the internal user id (see `validate_token` docstring
    + `openspec/changes/fix-actor-attribution/`). When omitted, the
    function falls back to the JWT-only behaviour that returns whatever
    the token carries — preserved for legacy/test callers that don't
    need translation.
    """
    authentication_header = headers.get("Authorization") or headers.get("authorization", "")
    return validate_token(authentication_header, user_repo=user_repo)

"""Authentication middleware — dual Cognito RS256 / legacy HS256 validation.

Validates JWTs from either:
1. Cognito User Pool (RS256, verified against JWKS public keys)
2. Legacy NextAuth bridge tokens (HS256, verified with shared NEXTAUTH_SECRET)

During the migration window, both token types are accepted. After full
migration to Cognito (Phase 5), the HS256 fallback will be removed.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

import jwt
from jwt import PyJWKClient

logger = logging.getLogger(__name__)

# Module-level JWKS client — survives Lambda container reuse, avoids
# re-fetching the JWKS on every request.
_jwks_client: PyJWKClient | None = None


def _get_jwks_client() -> PyJWKClient | None:
    """Return a cached PyJWKClient for the Cognito User Pool, or None if not configured."""
    global _jwks_client
    if _jwks_client is not None:
        return _jwks_client

    region = os.environ.get("COGNITO_REGION", "")
    pool_id = os.environ.get("COGNITO_USER_POOL_ID", "")
    if not region or not pool_id:
        return None

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


def validate_token(authorization: str) -> AuthContext:
    """Validate a Bearer token and return the auth context.

    Tries Cognito RS256 validation first. If the token is not a Cognito token
    (wrong issuer, missing kid, etc.), falls back to legacy HS256 validation.

    Raises:
        ValueError: If the token is missing, invalid, or expired.
    """
    if not authorization or not authorization.startswith("Bearer "):
        message = "Missing or invalid Authorization header"
        raise ValueError(message)

    token = authorization[7:]

    # Try Cognito RS256 first
    cognito_result = _try_cognito_validation(token)
    if cognito_result is not None:
        return cognito_result

    # Fall back to legacy HS256
    return _validate_legacy_token(token)


def _try_cognito_validation(token: str) -> AuthContext | None:
    """Attempt to validate token as a Cognito RS256 JWT.

    Returns AuthContext if valid, None if the token is not a Cognito token
    (so the caller can try legacy validation). Raises ValueError only for
    tokens that ARE Cognito tokens but are expired or malformed.
    """
    jwks_client = _get_jwks_client()
    if jwks_client is None:
        return None  # Cognito not configured — skip

    client_id = os.environ.get("COGNITO_CLIENT_ID", "")
    region = os.environ.get("COGNITO_REGION", "")
    pool_id = os.environ.get("COGNITO_USER_POOL_ID", "")
    issuer = f"https://cognito-idp.{region}.amazonaws.com/{pool_id}"

    try:
        # Check if this is a Cognito token by inspecting the header
        unverified_header = jwt.get_unverified_header(token)
        if unverified_header.get("alg") != "RS256":
            return None  # Not an RS256 token — try legacy

        signing_key = jwks_client.get_signing_key_from_jwt(token)

        payload: dict[str, Any] = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=client_id,
            issuer=issuer,
            options={"verify_exp": True},
        )
    except jwt.ExpiredSignatureError:
        message = "Token expired"
        raise ValueError(message) from None
    except (jwt.PyJWKClientError, jwt.InvalidTokenError):
        # Not a Cognito token or JWKS fetch failed — fall through to legacy
        return None

    # Extract claims from Cognito ID token
    org_id = payload.get("custom:org_id", "")
    if not org_id:
        message = "Cognito token missing required custom:org_id claim"
        raise ValueError(message)

    user_id = payload.get("custom:legacy_user_id") or payload.get("sub", "")
    if not user_id:
        message = "Cognito token missing user identifier"
        raise ValueError(message)

    logger.info("Cognito RS256 token validated: user=%s org=%s", user_id, org_id)

    return AuthContext(
        user_id=user_id,
        org_id=org_id,
        email=payload.get("email", ""),
        role=payload.get("custom:role", "analyst"),
        name=payload.get("name", ""),
    )


def _validate_legacy_token(token: str) -> AuthContext:
    """Validate a legacy HS256 JWT using NEXTAUTH_SECRET.

    This path will be removed after full Cognito migration (Phase 5).
    """
    secret = os.environ.get("NEXTAUTH_SECRET", "")
    if not secret:
        message = "NEXTAUTH_SECRET not configured and token is not a valid Cognito JWT"
        raise ValueError(message)

    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            options={"verify_exp": True},
        )
    except jwt.ExpiredSignatureError:
        message = "Token expired"
        raise ValueError(message) from None
    except jwt.InvalidTokenError as error:
        message = f"Invalid token: {error}"
        raise ValueError(message) from None

    user_id = payload.get("id") or payload.get("sub")
    org_id = payload.get("orgId")
    if not user_id or not org_id:
        message = "Token missing required claims: user identifier (id/sub) and orgId"
        raise ValueError(message)

    logger.info("Legacy HS256 token validated: user=%s org=%s", user_id, org_id)

    return AuthContext(
        user_id=user_id,
        org_id=org_id,
        email=payload.get("email", ""),
        role=payload.get("role", "analyst"),
        name=payload.get("name", ""),
    )


def require_authentication(headers: dict[str, str]) -> AuthContext:
    """Extract and validate authentication from request headers."""
    authentication_header = headers.get("Authorization") or headers.get("authorization", "")
    return validate_token(authentication_header)

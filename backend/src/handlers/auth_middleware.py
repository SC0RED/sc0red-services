"""Authentication middleware — Cognito RS256 JWT validation.

Validates JWTs issued by the Cognito User Pool against its JWKS public keys.
Supports COGNITO_JWKS_URL override for testing with mock JWKS endpoints.
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


def validate_token(authorization: str) -> AuthContext:
    """Validate an RS256 Bearer token and return the auth context.

    Raises:
        ValueError: If the token is missing, invalid, or expired.
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
    except Exception as error:
        logger.warning("Token validation failed: %s", error)
        message = f"Invalid token: {error}"
        raise ValueError(message) from None

    # Extract claims — support both Cognito custom attributes and plain claims
    org_id = payload.get("custom:org_id") or payload.get("orgId", "")
    if not org_id:
        message = "Token missing required org_id claim"
        raise ValueError(message)

    user_id = payload.get("custom:legacy_user_id") or payload.get("sub") or payload.get("id", "")
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


def _decode_rs256_token(token: str) -> dict[str, Any]:
    """Decode and verify an RS256 JWT against the JWKS endpoint."""
    client_id = os.environ.get("COGNITO_CLIENT_ID", "")

    # Build issuer for verification (skip if using custom JWKS URL)
    issuer = None
    region = os.environ.get("COGNITO_REGION", "")
    pool_id = os.environ.get("COGNITO_USER_POOL_ID", "")
    if region and pool_id:
        issuer = f"https://cognito-idp.{region}.amazonaws.com/{pool_id}"

    # Decode options — verify audience and issuer only if configured
    decode_options: dict[str, Any] = {"verify_exp": True}
    decode_kwargs: dict[str, Any] = {"algorithms": ["RS256"]}
    if client_id:
        decode_kwargs["audience"] = client_id
    else:
        decode_options["verify_aud"] = False
    if issuer:
        decode_kwargs["issuer"] = issuer
    else:
        decode_options["verify_iss"] = False

    jwks_client = _get_jwks_client()
    signing_key = jwks_client.get_signing_key_from_jwt(token)

    return jwt.decode(
        token,
        signing_key.key,
        options=decode_options,
        **decode_kwargs,
    )


def require_authentication(headers: dict[str, str]) -> AuthContext:
    """Extract and validate authentication from request headers."""
    authentication_header = headers.get("Authorization") or headers.get("authorization", "")
    return validate_token(authentication_header)

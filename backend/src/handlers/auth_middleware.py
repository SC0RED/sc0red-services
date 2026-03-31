"""Authentication middleware — Cognito RS256 JWT validation.

Validates JWTs issued by the Cognito User Pool against its JWKS public keys.
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
    """Validate a Cognito RS256 Bearer token and return the auth context.

    Raises:
        ValueError: If the token is missing, invalid, or expired.
    """
    if not authorization or not authorization.startswith("Bearer "):
        message = "Missing or invalid Authorization header"
        raise ValueError(message)

    token = authorization[7:]

    client_id = os.environ.get("COGNITO_CLIENT_ID", "")
    region = os.environ.get("COGNITO_REGION", "")
    pool_id = os.environ.get("COGNITO_USER_POOL_ID", "")
    issuer = f"https://cognito-idp.{region}.amazonaws.com/{pool_id}"

    try:
        jwks_client = _get_jwks_client()
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
    except (jwt.PyJWKClientError, jwt.InvalidTokenError) as error:
        message = f"Invalid token: {error}"
        raise ValueError(message) from None

    # Extract claims from Cognito ID token
    org_id = payload.get("custom:org_id", "")
    if not org_id:
        message = "Token missing required custom:org_id claim"
        raise ValueError(message)

    user_id = payload.get("custom:legacy_user_id") or payload.get("sub", "")
    if not user_id:
        message = "Token missing user identifier"
        raise ValueError(message)

    return AuthContext(
        user_id=user_id,
        org_id=org_id,
        email=payload.get("email", ""),
        role=payload.get("custom:role", "analyst"),
        name=payload.get("name", ""),
    )


def require_authentication(headers: dict[str, str]) -> AuthContext:
    """Extract and validate authentication from request headers."""
    authentication_header = headers.get("Authorization") or headers.get("authorization", "")
    return validate_token(authentication_header)

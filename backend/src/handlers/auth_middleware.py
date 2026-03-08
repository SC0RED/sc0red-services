"""NextAuth JWT validation middleware.

Validates JWTs issued by NextAuth using the shared NEXTAUTH_SECRET.
NextAuth uses a symmetric encryption scheme (JWE with A256GCM) by default,
but when configured with JWT strategy it also supports standard JWS.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import jwt


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

    Args:
        authorization: The Authorization header value (e.g., "Bearer <token>").

    Raises:
        ValueError: If the token is missing, invalid, or expired.
    """
    if not authorization or not authorization.startswith("Bearer "):
        message = "Missing or invalid Authorization header"
        raise ValueError(message)

    token = authorization[7:]
    secret = os.environ.get("NEXTAUTH_SECRET", "")
    if not secret:
        message = "NEXTAUTH_SECRET not configured"
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
    except jwt.InvalidTokenError as e:
        message = f"Invalid token: {e}"
        raise ValueError(message) from None

    user_id = payload.get("id") or payload.get("sub")
    org_id = payload.get("orgId")
    if not user_id or not org_id:
        message = "Token missing required claims: user identifier (id/sub) and orgId"
        raise ValueError(message)

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

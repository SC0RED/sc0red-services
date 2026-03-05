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
        msg = "Missing or invalid Authorization header"
        raise ValueError(msg)

    token = authorization[7:]
    secret = os.environ.get("NEXTAUTH_SECRET", "")
    if not secret:
        msg = "NEXTAUTH_SECRET not configured"
        raise ValueError(msg)

    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            options={"verify_exp": True},
        )
    except jwt.ExpiredSignatureError:
        msg = "Token expired"
        raise ValueError(msg) from None
    except jwt.InvalidTokenError as e:
        msg = f"Invalid token: {e}"
        raise ValueError(msg) from None

    return AuthContext(
        user_id=payload.get("id", payload.get("sub", "")),
        org_id=payload.get("orgId", ""),
        email=payload.get("email", ""),
        role=payload.get("role", "analyst"),
        name=payload.get("name", ""),
    )


def require_auth(headers: dict[str, str]) -> AuthContext:
    """Extract and validate auth from request headers."""
    auth_header = headers.get("Authorization") or headers.get("authorization", "")
    return validate_token(auth_header)

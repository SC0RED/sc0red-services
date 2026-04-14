"""Authenticated user context for MCP tool handlers.

Uses contextvars to propagate user identity from OAuth token validation
(in oauth_provider.load_access_token) into tool handler functions.

Usage in tools:
    from src.mcp.auth_context import get_authenticated_user
    user = get_authenticated_user()  # raises if not authenticated
"""

from __future__ import annotations

import contextvars
from dataclasses import dataclass


@dataclass(frozen=True)
class AuthenticatedUser:
    """User identity extracted from a validated OAuth access token."""

    user_id: str
    org_id: str
    email: str
    role: str
    client_id: str
    scopes: list[str]


_current_user: contextvars.ContextVar[AuthenticatedUser | None] = contextvars.ContextVar(
    "mcp_authenticated_user", default=None
)


def set_authenticated_user(user: AuthenticatedUser) -> None:
    """Store the authenticated user for the current request context."""
    _current_user.set(user)


def get_authenticated_user() -> AuthenticatedUser:
    """Get the authenticated user from the current request context.

    Raises:
        RuntimeError: If no authenticated user is set (tool called outside auth context).
    """
    user = _current_user.get()
    if user is None:
        message = "No authenticated user in context — tool called outside OAuth auth flow"
        raise RuntimeError(message)
    return user


def clear_authenticated_user() -> None:
    """Clear the authenticated user (end of request)."""
    _current_user.set(None)

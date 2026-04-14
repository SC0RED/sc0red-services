"""Internal API client for MCP tools to call the Janus backend.

All MCP tool handlers use this client to forward requests to the existing
backend API endpoints. Authentication bridging (MCP OAuth → backend auth)
will be implemented via contextvars when user identity propagation is wired.

Currently uses a development-only HS256 token for local testing.
Production deployment requires the contextvars auth bridge (tracked).
"""

from __future__ import annotations

import os
from typing import Any

import httpx
import jwt as pyjwt

API_URL = os.environ.get("API_URL", "http://localhost:8001")
INTERNAL_SIGNING_KEY = os.environ.get("INTERNAL_SIGNING_KEY", "")


async def call_backend(  # noqa: NAMING001
    *,
    method: str,
    path: str,
    user_id: str,
    org_id: str,
    email: str,
    role: str,
    body: dict[str, Any] | None = None,
    params: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Call the Janus backend API on behalf of an MCP user.

    Args:
        method: HTTP method (GET, POST, DELETE).
        path: API path (e.g., /api/dashboard).
        user_id: The authenticated user's ID.
        org_id: The user's organization ID.
        email: The user's email.
        role: The user's role.
        body: Optional JSON body for POST requests.
        params: Optional query parameters.

    Returns:
        Parsed JSON response from the backend.

    Raises:
        httpx.HTTPStatusError: If the backend returns a non-2xx status.
        RuntimeError: If INTERNAL_SIGNING_KEY is not configured.
    """
    if not INTERNAL_SIGNING_KEY:
        message = (
            "INTERNAL_SIGNING_KEY not set. "
            "MCP→backend auth bridge requires this env var for development. "
            "Production auth will use contextvars-based token forwarding."
        )
        raise RuntimeError(message)

    if not user_id or not org_id:
        message = "user_id and org_id are required for backend API calls"
        raise ValueError(message)

    internal_token = pyjwt.encode(
        {
            "sub": user_id,
            "email": email,
            "custom:org_id": org_id,
            "custom:role": role,
            "name": email.split("@", maxsplit=1)[0],
        },
        INTERNAL_SIGNING_KEY,
        algorithm="HS256",
    )

    headers = {
        "Authorization": f"Bearer {internal_token}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(base_url=API_URL, timeout=30.0) as client:
        response = await client.request(
            method=method,
            url=path,
            headers=headers,
            json=body,
            params=params,
        )
        response.raise_for_status()
        return response.json()  # type: ignore[no-any-return]

"""Internal API client for MCP tools to call the Janus backend.

All MCP tool handlers use this client to forward requests to the existing
backend API endpoints. The client adds authentication headers derived from
the OAuth token's user identity.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

API_URL = os.environ.get("API_URL", "http://localhost:8001")


async def call_backend(
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

    Creates a minimal JWT-like auth header the backend accepts for
    internal service calls. In production, this will use a service token
    or internal auth mechanism.

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
    """
    import jwt as pyjwt

    # Create a minimal internal token for backend auth
    # The backend validates JWT structure and extracts claims
    signing_key = os.environ.get("INTERNAL_SIGNING_KEY", "internal-dev-key")
    internal_token = pyjwt.encode(
        {
            "sub": user_id,
            "email": email,
            "custom:org_id": org_id,
            "custom:role": role,
            "name": email.split("@", maxsplit=1)[0],
        },
        signing_key,
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

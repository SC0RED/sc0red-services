"""CORS for browser-based MCP clients (e.g. MCP Inspector).

Browser MCP clients run the OAuth flow and then connect to the authenticated
Streamable HTTP transport at ``/mcp`` with an ``Authorization: Bearer`` header.
Sending that header makes the browser fire a CORS preflight (``OPTIONS``).

The MCP SDK attaches a CORS layer only to the OAuth routes (``/token``,
``/register``, …) with ``allow_headers=["mcp-protocol-version"]`` — it never
adds CORS to the ``/mcp`` transport route, whose ``RequireAuthMiddleware``
rejects the *unauthenticated* preflight with a ``401`` that carries no
``Access-Control-Allow-Origin``. The browser then blocks the request and the
client surfaces ``TypeError: Failed to fetch`` — the connection can never
complete. (Verified against the staging Function URL: ``OPTIONS /mcp`` → 401
with no ACAO; ``OPTIONS /token`` → 200 with ACAO.)

Wrapping the whole app with an OUTERMOST ``CORSMiddleware`` fixes this:

* Starlette's ``CORSMiddleware`` short-circuits a valid preflight with a ``200``
  *before* the request reaches the router, so ``RequireAuthMiddleware`` never
  sees the unauthenticated ``OPTIONS`` — no spurious 401.
* ``Authorization`` (plus the transport's ``mcp-*`` headers) is in the allow
  list, so the real authenticated request passes its preflight.
* The actual-request path adds ``Access-Control-Allow-Origin`` to every
  response — including the SDK's 401s — so the browser can read them.

``allow_origins=["*"]`` matches the SDK's own posture for the OAuth routes: the
transport is protected by the bearer token, not by request origin, and no
cookies/credentials are involved (so ``*`` is valid and safe here).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.middleware.cors import CORSMiddleware

if TYPE_CHECKING:
    from starlette.applications import Starlette

# Request headers a browser MCP client sends that are not CORS-safelisted:
#   authorization        — the OAuth bearer token on every authed request
#   mcp-protocol-version — protocol negotiation (also allowed by the SDK)
#   mcp-session-id       — Streamable HTTP session correlation
#   last-event-id        — SSE stream resumption cursor
# content-type is included explicitly because non-form JSON bodies are not
# safelisted and therefore trigger a preflight.
MCP_ALLOWED_HEADERS: list[str] = [
    "authorization",
    "content-type",
    "mcp-protocol-version",
    "mcp-session-id",
    "last-event-id",
]

# Response headers browser JS must be able to read off the transport responses.
MCP_EXPOSED_HEADERS: list[str] = ["mcp-session-id", "mcp-protocol-version"]

# Methods the Streamable HTTP transport uses: POST (messages), GET (SSE stream),
# DELETE (session teardown). OPTIONS is the preflight itself.
MCP_ALLOWED_METHODS: list[str] = ["GET", "POST", "DELETE", "OPTIONS"]

# Preflight cache lifetime (seconds) — mirrors the SDK/Function-URL default.
MCP_CORS_MAX_AGE: int = 600


def add_cors_middleware(app: Starlette) -> None:
    """Add the outermost CORS layer so browser MCP clients can reach ``/mcp``.

    Must be called after ``streamable_http_app()`` builds the app but before it
    serves its first request. ``add_middleware`` inserts at the top of the
    stack, so this CORS layer wraps the SDK's auth middleware and handles the
    preflight before authentication can reject it.
    """
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=MCP_ALLOWED_METHODS,
        allow_headers=MCP_ALLOWED_HEADERS,
        expose_headers=MCP_EXPOSED_HEADERS,
        max_age=MCP_CORS_MAX_AGE,
    )

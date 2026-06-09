"""Tests for the MCP browser-CORS layer (``src/mcp/cors.py``).

These reproduce the failure mode that broke MCP Inspector: a ``/mcp`` route
whose endpoint requires auth (401s without it) and carries no CORS headers of
its own. ``add_cors_middleware`` must make the preflight succeed and make even
the 401 readable by the browser.
"""

from __future__ import annotations

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from src.mcp.cors import (
    MCP_ALLOWED_HEADERS,
    MCP_ALLOWED_METHODS,
    MCP_CORS_MAX_AGE,
    MCP_EXPOSED_HEADERS,
    add_cors_middleware,
)

INSPECTOR_ORIGIN = "http://localhost:6274"


async def _authentication_required(_request: object) -> JSONResponse:
    """Stand-in for the SDK's RequireAuthMiddleware-wrapped /mcp endpoint:
    rejects everything that reaches it with a bare 401 (no CORS headers)."""
    return JSONResponse({"error": "Authentication required"}, status_code=401)


def _build_client() -> TestClient:
    app = Starlette(
        routes=[Route("/mcp", _authentication_required, methods=["GET", "POST", "DELETE"])]
    )
    add_cors_middleware(app)
    return TestClient(app)


def test_preflight_answered_before_authentication() -> None:
    # The browser preflights the authed POST with an Authorization header. CORS
    # must short-circuit it with a 200 — never reaching the 401 endpoint.
    response = _build_client().options(
        "/mcp",
        headers={
            "Origin": INSPECTOR_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type,mcp-protocol-version",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "*"
    allowed = response.headers["access-control-allow-headers"].lower()
    assert "authorization" in allowed
    assert "mcp-protocol-version" in allowed
    # The transport's methods must be advertised and the preflight cached for
    # the configured max-age (exercises MCP_ALLOWED_METHODS / MCP_CORS_MAX_AGE
    # by effect, not by tautology).
    allowed_methods = response.headers["access-control-allow-methods"].upper()
    for method in MCP_ALLOWED_METHODS:
        assert method in allowed_methods
    assert response.headers["access-control-max-age"] == str(MCP_CORS_MAX_AGE)


def test_actual_request_401_still_carries_cors_headers() -> None:
    # Even the endpoint's 401 must include ACAO, or the browser blocks the
    # response and the client reports "Failed to fetch" instead of the 401.
    response = _build_client().get("/mcp", headers={"Origin": INSPECTOR_ORIGIN})
    assert response.status_code == 401
    assert response.headers["access-control-allow-origin"] == "*"


def test_session_id_is_exposed_to_the_browser() -> None:
    # The transport returns mcp-session-id; browser JS can only read it if it is
    # in Access-Control-Expose-Headers.
    response = _build_client().post("/mcp", headers={"Origin": INSPECTOR_ORIGIN})
    exposed = response.headers["access-control-expose-headers"].lower()
    for header in MCP_EXPOSED_HEADERS:
        assert header in exposed


def test_authorization_is_in_the_allow_list() -> None:
    # Guard against the regression that caused this bug — the SDK's default
    # allow-list omitted Authorization.
    assert "authorization" in MCP_ALLOWED_HEADERS

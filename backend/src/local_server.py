"""FastAPI wrapper around the Lambda handler for local development.

Run with: uvicorn src.local_server:app --port 8001 --reload
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from src.handlers.api_handler_entry import handle_api_event

app = FastAPI(title="sc0red Services Backend (Local Dev)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def _lambda_proxy(request: Request, method: str) -> Response:
    """Convert a FastAPI request into a Lambda API Gateway event."""
    body = None
    if method in ("POST", "PUT", "PATCH"):
        raw = await request.body()
        body = raw.decode("utf-8") if raw else None

    # Build API Gateway v1 event
    event: dict[str, Any] = {
        "httpMethod": method,
        "path": request.url.path,
        "headers": dict(request.headers),
        "queryStringParameters": dict(request.query_params) or None,
        "body": body,
        "requestContext": {"stage": "local"},
    }

    result = handle_api_event(event, None)

    return Response(
        content=result.get("body", ""),
        status_code=result.get("statusCode", 200),
        headers=result.get("headers", {}),
        media_type="application/json",
    )


@app.get("/api/health")
async def get_health() -> dict[str, str]:
    """Return a simple health check response."""
    return {"status": "ok"}


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
async def handle_catch_all(request: Request) -> Response:
    """Route all HTTP methods to the Lambda handler proxy."""
    return await _lambda_proxy(request, request.method)

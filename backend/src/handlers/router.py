"""Lightweight regex-based HTTP router for API Gateway Lambda handlers."""
from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any, NamedTuple

LambdaResponse = dict[str, Any]
RouteHandler = Callable[..., LambdaResponse]


def _compile_route(template: str) -> re.Pattern[str]:
    pattern = re.sub(r"\{(\w+)\}", r"(?P<\1>[^/]+)", template)
    return re.compile(f"^{pattern}$")


class Route(NamedTuple):
    """A single registered route entry."""

    method: str
    pattern: re.Pattern[str]
    handler: RouteHandler
    authenticated: bool


class Router:
    """Route registry for API Gateway Lambda handlers.

    Example:
        router = Router()
        router.public("POST", "/api/auth/login", handler_fn)
        router.protected("GET", "/api/scan/{scan_id}", handler_fn)

        result = router.dispatch("GET", "/api/scan/abc-123")
        # → (handler_fn, {"scan_id": "abc-123"}, True)
    """

    def __init__(self) -> None:
        self._routes: list[Route] = []

    def public(self, method: str, path: str, handler: RouteHandler) -> None:
        """Register a route that requires no authentication."""
        self._routes.append(Route(method, _compile_route(path), handler, authenticated=False))

    def protected(self, method: str, path: str, handler: RouteHandler) -> None:
        """Register a route that requires a valid auth token."""
        self._routes.append(Route(method, _compile_route(path), handler, authenticated=True))

    def dispatch(
        self, method: str, path: str
    ) -> tuple[RouteHandler, dict[str, str], bool] | None:
        """Match method+path against registered routes. Returns None if no match."""
        for route in self._routes:
            if route.method == method and (match := route.pattern.match(path)):
                return route.handler, match.groupdict(), route.authenticated
        return None

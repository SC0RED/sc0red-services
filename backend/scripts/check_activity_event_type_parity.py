#!/usr/bin/env python3
"""Activity event type-parity checker (backend ↔ frontend).

Compares the string-literal values declared in ``EventType`` (backend
``backend/src/handlers/activity_handlers.py``) against
``ActivityEventType`` (frontend ``frontend/src/lib/types/api.ts``).
Fails the build if they drift.

Why this exists: same reason as ``check_analytics_type_parity.py`` —
two source-of-truth declarations on either side of an HTTP boundary,
with only a comment enforcing parity. If the backend adds a new
event type without the frontend, the row renders without a link and
no error surfaces. The previous review of PR #197 caught this
specific failure-class risk; this check moves it from "noticed
eventually" to "rejected on every PR".

Pattern intentionally mirrors ``check_analytics_type_parity.py`` so
future engineers can copy-paste a third instance in 5 minutes when a
new event-typed boundary appears.

Usage:
    python backend/scripts/check_activity_event_type_parity.py

Exits 0 on parity, 1 with a readable diff on drift.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_BACKEND_HANDLER = _REPO_ROOT / "backend" / "src" / "handlers" / "activity_handlers.py"
_FRONTEND_TYPES = _REPO_ROOT / "frontend" / "src" / "lib" / "types" / "api.ts"

# Single alias to check today; the script is structured to make adding a
# second alias on this surface a one-line change.
_BACKEND_ALIAS = "EventType"
_FRONTEND_ALIAS = "ActivityEventType"


# --------------------------------------------------------------------------- #
# Backend (Python) extraction                                                 #
# --------------------------------------------------------------------------- #


def extract_backend_values(source: str) -> set[str]:
    """Return the literal values declared in ``EventType = Literal[...]``."""
    tree = ast.parse(source)
    for node in ast.iter_child_nodes(tree):
        if not isinstance(node, ast.Assign):
            continue
        if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            continue
        if node.targets[0].id != _BACKEND_ALIAS:
            continue
        return _extract_literal_values(node.value)
    raise SystemExit(
        f"Missing backend Literal alias `{_BACKEND_ALIAS}` (in {_BACKEND_HANDLER})"
    )


def _extract_literal_values(expr: ast.expr) -> set[str]:
    """Extract string values from a ``Literal[...]`` subscript expression."""
    if not isinstance(expr, ast.Subscript):
        raise SystemExit(f"{_BACKEND_ALIAS}: expected `Literal[...]` assignment")

    slice_node = expr.slice
    items: list[ast.expr] = (
        list(slice_node.elts) if isinstance(slice_node, ast.Tuple) else [slice_node]
    )

    values: set[str] = set()
    for item in items:
        if isinstance(item, ast.Constant) and isinstance(item.value, str):
            values.add(item.value)
        else:
            raise SystemExit(
                f"{_BACKEND_ALIAS}: only string-literal members supported "
                f"(got {ast.dump(item)})"
            )
    return values


# --------------------------------------------------------------------------- #
# Frontend (TypeScript) extraction                                            #
# --------------------------------------------------------------------------- #


# Quote-style agnostic — Prettier may rewrite single → double on entries
# containing apostrophes, like our help-content.ts had to learn the hard
# way (see check-help-content.mjs).
_TS_STRING_LITERAL_RE = re.compile(r"['\"]([^'\"]+)['\"]")

# Any top-level declaration keyword terminates the current type body.
_TS_BODY_BOUNDARY_RE = re.compile(
    r"\n(?:export|interface|declare|const|class|function|type)\s"
)


def extract_frontend_values(source: str) -> set[str]:
    """Return the literal values declared in ``export type ActivityEventType``."""
    anchor = re.search(rf"export\s+type\s+{re.escape(_FRONTEND_ALIAS)}\s*=", source)
    if not anchor:
        raise SystemExit(
            f"Missing frontend type alias `{_FRONTEND_ALIAS}` (in {_FRONTEND_TYPES})"
        )

    body_start = anchor.end()
    boundary = _TS_BODY_BOUNDARY_RE.search(source[body_start:])
    body_end = body_start + boundary.start() if boundary else len(source)
    body = source[body_start:body_end]

    literals = set(_TS_STRING_LITERAL_RE.findall(body))
    if not literals:
        raise SystemExit(
            f"{_FRONTEND_ALIAS}: no string literals found (in {_FRONTEND_TYPES})"
        )
    return literals


# --------------------------------------------------------------------------- #
# Comparison + reporting                                                      #
# --------------------------------------------------------------------------- #


def compare(backend_values: set[str], frontend_values: set[str]) -> str | None:
    """Return a human-readable mismatch description, or None on parity."""
    if backend_values == frontend_values:
        return None
    only_backend = sorted(backend_values - frontend_values) or ["(none)"]
    only_frontend = sorted(frontend_values - backend_values) or ["(none)"]
    return (
        f"Activity event type mismatch:\n"
        f"      only in backend ({_BACKEND_ALIAS}):  {only_backend}\n"
        f"      only in frontend ({_FRONTEND_ALIAS}): {only_frontend}"
    )


def main() -> int:
    """Run the parity check. Exit 0 on success, 1 on drift."""
    if not _BACKEND_HANDLER.exists():
        print(f"error: {_BACKEND_HANDLER} not found", file=sys.stderr)
        return 1
    if not _FRONTEND_TYPES.exists():
        print(f"error: {_FRONTEND_TYPES} not found", file=sys.stderr)
        return 1

    backend = extract_backend_values(_BACKEND_HANDLER.read_text(encoding="utf-8"))
    frontend = extract_frontend_values(_FRONTEND_TYPES.read_text(encoding="utf-8"))

    mismatch = compare(backend, frontend)
    if mismatch:
        print("Activity event type-parity check FAILED:\n", file=sys.stderr)
        print(f"  - {mismatch}", file=sys.stderr)
        print(
            f"\nThese files must stay in sync:"
            f"\n    {_BACKEND_HANDLER.relative_to(_REPO_ROOT)}"
            f"\n    {_FRONTEND_TYPES.relative_to(_REPO_ROOT)}",
            file=sys.stderr,
        )
        return 1

    print(f"Activity event type-parity: OK ({len(backend)} types)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

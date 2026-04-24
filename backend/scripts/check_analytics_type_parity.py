#!/usr/bin/env python3
"""Analytics envelope type-parity checker (backend ↔ frontend).

Compares the string-literal values declared in the Python Pydantic model
(``backend/src/models/analytics_events.py``) against the TypeScript union
types (``frontend/src/lib/types/analytics.ts``). Fails the build if they
drift.

Why this exists: the two files declare the same envelope literals
independently — only a comment ("must stay in sync") enforces parity.
Adding a new event on one side without the other silently 400s every
emit from that surface and the regression stays invisible until the
funnel dashboard looks wrong three weeks later. This script moves that
failure from "runtime, noticed eventually" to "CI, every PR".

Checked invariants:

1. ``AnalyticsEventType`` — set of allowed event names.
2. ``AnalyticsSource`` — set of allowed source tags.
3. ``ActiveLeverFilter`` — set of allowed lever values.
4. ``ANALYTICS_VERSION`` — the single string constant.

Usage:
    python backend/scripts/check_analytics_type_parity.py

Exits 0 on parity, 1 with a readable diff on drift.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_BACKEND_MODEL = _REPO_ROOT / "backend" / "src" / "models" / "analytics_events.py"
_FRONTEND_TYPES = _REPO_ROOT / "frontend" / "src" / "lib" / "types" / "analytics.ts"

# Named aliases that must exist on both sides with identical value sets.
_UNION_ALIASES: tuple[str, ...] = (
    "AnalyticsEventType",
    "AnalyticsSource",
    "ActiveLeverFilter",
)

_VERSION_NAME = "ANALYTICS_VERSION"


# --------------------------------------------------------------------------- #
# Backend (Python) extraction                                                 #
# --------------------------------------------------------------------------- #


def extract_backend_values(source: str) -> tuple[dict[str, set[str]], str]:
    """Return ({alias: {values}}, version) from the Pydantic model file.

    Raises SystemExit if any expected name is missing or malformed —
    malformed declarations are themselves a drift risk.
    """
    tree = ast.parse(source)
    union_values: dict[str, set[str]] = {}
    version: str | None = None

    for node in ast.iter_child_nodes(tree):
        if not isinstance(node, ast.Assign):
            continue
        if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            continue
        name = node.targets[0].id

        if name == _VERSION_NAME:
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                version = node.value.value
        elif name in _UNION_ALIASES:
            union_values[name] = _extract_literal_values(node.value, name)

    missing = [alias for alias in _UNION_ALIASES if alias not in union_values]
    if missing:
        raise SystemExit(f"Missing backend Literal aliases: {missing} (in {_BACKEND_MODEL})")
    if version is None:
        raise SystemExit(f"Missing backend constant {_VERSION_NAME} (in {_BACKEND_MODEL})")

    return union_values, version


def _extract_literal_values(expr: ast.expr, alias: str) -> set[str]:
    """Extract string values from a ``Literal[...]`` subscript expression."""
    if not isinstance(expr, ast.Subscript):
        raise SystemExit(f"{alias}: expected `Literal[...]` assignment")

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
                f"{alias}: only string-literal members supported (got {ast.dump(item)})"
            )
    return values


# --------------------------------------------------------------------------- #
# Frontend (TypeScript) extraction                                            #
# --------------------------------------------------------------------------- #


# Accept either quote style — Prettier configs vary between repos, and
# the checker should care about literal values, not their delimiters.
_TS_STRING_LITERAL_RE = re.compile(r"['\"]([^'\"]+)['\"]")

# Any top-level declaration keyword terminates the current type body.
# Keeping this set tight avoids bleeding string literals from an
# adjacent declaration (e.g. ``WebAnalyticsEventType = Exclude<...,
# '...'>``) — but it must cover every form someone might add between
# aliases, or we silently read past the intended end of the body.
_TS_BODY_BOUNDARY_RE = re.compile(
    r"\n(?:export|interface|declare|const|class|function|type)\s"
)


def extract_frontend_values(source: str) -> tuple[dict[str, set[str]], str]:
    """Return ({alias: {values}}, version) from the TS types file.

    The TS file uses multi-line unions (``export type X =\\n    | 'a'\\n    | 'b'``),
    so we anchor on ``export type <Alias> =`` and read until the next
    top-level declaration keyword. That boundary is tight enough to
    avoid bleeding string literals in from adjacent types.
    """
    union_values: dict[str, set[str]] = {}
    for alias in _UNION_ALIASES:
        anchor = re.search(rf"export\s+type\s+{re.escape(alias)}\s*=", source)
        if not anchor:
            raise SystemExit(f"Missing frontend type alias `{alias}` (in {_FRONTEND_TYPES})")

        body_start = anchor.end()
        boundary = _TS_BODY_BOUNDARY_RE.search(source[body_start:])
        body_end = body_start + boundary.start() if boundary else len(source)
        body = source[body_start:body_end]

        literals = set(_TS_STRING_LITERAL_RE.findall(body))
        if not literals:
            raise SystemExit(f"{alias}: no string literals found (in {_FRONTEND_TYPES})")
        union_values[alias] = literals

    version_match = re.search(
        rf"export\s+const\s+{_VERSION_NAME}\s*=\s*['\"]([^'\"]+)['\"]",
        source,
    )
    if not version_match:
        raise SystemExit(f"Missing frontend constant {_VERSION_NAME} (in {_FRONTEND_TYPES})")

    return union_values, version_match.group(1)


# --------------------------------------------------------------------------- #
# Comparison + reporting                                                      #
# --------------------------------------------------------------------------- #


def compare(
    backend: tuple[dict[str, set[str]], str],
    frontend: tuple[dict[str, set[str]], str],
) -> list[str]:
    """Return a list of human-readable mismatch descriptions (empty = parity)."""
    backend_unions, backend_version = backend
    frontend_unions, frontend_version = frontend
    mismatches: list[str] = []

    if backend_version != frontend_version:
        mismatches.append(
            f"{_VERSION_NAME} mismatch: "
            f"backend={backend_version!r} vs frontend={frontend_version!r}"
        )

    for alias in _UNION_ALIASES:
        backend_set = backend_unions[alias]
        frontend_set = frontend_unions[alias]
        if backend_set != frontend_set:
            only_backend = sorted(backend_set - frontend_set) or ["(none)"]
            only_frontend = sorted(frontend_set - backend_set) or ["(none)"]
            mismatches.append(
                f"{alias} mismatch:\n"
                f"      only in backend:  {only_backend}\n"
                f"      only in frontend: {only_frontend}"
            )

    return mismatches


def main() -> int:
    """Run the parity check. Exit 0 on success, 1 on drift."""
    if not _BACKEND_MODEL.exists():
        print(f"error: {_BACKEND_MODEL} not found", file=sys.stderr)
        return 1
    if not _FRONTEND_TYPES.exists():
        print(f"error: {_FRONTEND_TYPES} not found", file=sys.stderr)
        return 1

    backend = extract_backend_values(_BACKEND_MODEL.read_text(encoding="utf-8"))
    frontend = extract_frontend_values(_FRONTEND_TYPES.read_text(encoding="utf-8"))

    mismatches = compare(backend, frontend)
    if mismatches:
        print("Analytics envelope type-parity check FAILED:\n", file=sys.stderr)
        for message in mismatches:
            print(f"  - {message}", file=sys.stderr)
        print(
            f"\nThese files must stay in sync:"
            f"\n    {_BACKEND_MODEL.relative_to(_REPO_ROOT)}"
            f"\n    {_FRONTEND_TYPES.relative_to(_REPO_ROOT)}",
            file=sys.stderr,
        )
        return 1

    print("Analytics envelope type-parity: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())

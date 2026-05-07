"""Corpus loaders for the strategy-map generation step.

The shared `prompts/loader.py` resolves files at `prompts/system/`,
`prompts/guides/`, `prompts/templates/`, and `prompts/schemas/`. The
strategy-map corpus is nested one level deeper at
`prompts/strategy_map/system/`, `prompts/strategy_map/guides/`, etc.
This module provides the matching loaders for that nested layout.

Files are read on first access and cached at module level — the same
performance pattern the parent loader uses.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_PROMPTS_ROOT = Path(__file__).parent.parent / "prompts" / "strategy_map"
_cache: dict[str, str] = {}


def _read(relative_path: str) -> str:
    """Read a file under the strategy_map prompts root with module-level caching."""
    if relative_path not in _cache:
        path = _PROMPTS_ROOT / relative_path
        _cache[relative_path] = path.read_text(encoding="utf-8").strip()
    return _cache[relative_path]


def load_system_prompt() -> str:
    """Load the strategy-map system prompt."""
    return _read("system/strategy_map_generator.md")


def load_guide(name: str) -> str:
    """Load a named guide from `guides/`. `name` does not include the .md suffix."""
    return _read(f"guides/{name}.md")


def load_exemplar(name: str) -> str:
    """Load a named exemplar from `exemplars/`. `name` does not include the .md suffix."""
    return _read(f"exemplars/{name}.md")


def load_template(name: str) -> str:
    """Load a named template from `templates/`. `name` does not include the .md suffix."""
    return _read(f"templates/{name}.md")


def load_decomposed_template(name: str) -> str:
    """Load a per-call template from `templates/decomposed/`.

    Used by the optimize-strategy-map-latency Phase 1 path. Decomposed
    templates correspond to ONE round of one perspective (e.g.
    `round1_titles_financial`, `round2_detail_customer`,
    `round3_detail_internal`). The `name` does not include the .md
    suffix.
    """
    return _read(f"templates/decomposed/{name}.md")


def load_schema() -> dict[str, Any]:
    """Load and parse the JSON schema for the strategy-map output."""
    raw = _read("schemas/strategy_map_output.json")
    return json.loads(raw)


def load_per_call_schema(name: str) -> dict[str, Any]:
    """Load and parse a per-call JSON schema from `schemas/per_call/`.

    Used by the optimize-strategy-map-latency Phase 1 path. Per-call
    schemas are sliced subsets of the full strategy-map schema, one
    per decomposed call shape (e.g. `financial_titles`,
    `customer_objective_detail`). They omit the `id` field per
    Decision §2 of the design — the assembly layer assigns positional
    IDs from title-list order.
    """
    raw = _read(f"schemas/per_call/{name}.json")
    return json.loads(raw)


def compose_system_prompt() -> str:
    """Assemble the full system prompt by concatenating the corpus.

    Order is deliberate: role first, then framework theory, then
    house style (which builds on theory), then anti-patterns (which
    the AI must avoid), then exemplars (few-shot grounding).
    """
    return "\n\n---\n\n".join(
        [
            load_system_prompt(),
            load_guide("kaplan_norton_framework"),
            load_guide("vector_style_guide"),
            load_guide("anti_patterns"),
            "## Exemplar 1 — Mobil 2000 (HBR canonical, hybrid value-prop case)\n\n"
            + load_exemplar("mobil_2000"),
            "## Exemplar 2 — Wawa 2011 (Vector house-style example)\n\n"
            + load_exemplar("wawa_2011"),
        ]
    )


_PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")
"""Pattern matching a `{key}` placeholder. Only single-token names
qualify — JSON braces (`{ "field": …}` with whitespace inside) are
ignored, which lets us paste JSON examples directly into templates."""


def render_template(name: str, context: dict[str, Any]) -> str:
    """Load a per-step template and substitute context values.

    Templates contain `{key_name}` placeholders that get replaced
    with `context[key_name]`. Missing keys are replaced with the
    literal string ``(unknown)`` rather than raising — early-stage
    steps don't have every context variable populated yet (e.g.
    Step 1 doesn't have a value_proposition).

    Note: we use a regex-based substitution rather than
    `str.format_map` so JSON examples in the template (which contain
    literal `{` and `}`) don't collide with the placeholder syntax.
    Only `{single_token_name}` patterns are recognised; JSON braces
    with whitespace or nested content are left untouched.
    """
    template = load_template(name)

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key in context:
            return str(context[key])
        return "(unknown)"

    return _PLACEHOLDER_RE.sub(replace, template)

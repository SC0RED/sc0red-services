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


def load_decomposed_template(name: str) -> str:
    """Load a per-call template from `templates/decomposed/`.

    Strategy-map generation is fully decomposed; each template
    corresponds to ONE round of one perspective (e.g.
    `round1_titles_financial`, `round2_detail_customer`,
    `round3_detail_internal`) or one synthesis sub-call. The `name`
    does not include the .md suffix.
    """
    return _read(f"templates/decomposed/{name}.md")


def load_schema() -> dict[str, Any]:
    """Load and parse the JSON schema for the assembled strategy-map output.

    The assembled-output schema documents the full ``StrategyMap``
    shape and is the source for strict-mode invariant tests
    (``test_strategy_map_schema_strict_mode.py``). The per-call schemas
    used by individual AI calls live under ``schemas/per_call/`` and
    are loaded via ``load_per_call_schema``.
    """
    raw = _read("schemas/strategy_map_output.json")
    return json.loads(raw)


def load_per_call_schema(name: str) -> dict[str, Any]:
    """Load and parse a per-call JSON schema from `schemas/per_call/`.

    Per-call schemas are sliced subsets of the full strategy-map
    schema, one per decomposed call shape (e.g. `financial_titles`,
    `customer_objective_detail`). They omit the `id` field —
    the assembly layer assigns positional IDs from title-list order.
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
            load_guide("sc0red_advisory_style_guide"),
            load_guide("anti_patterns"),
            "## Exemplar 1 — Mobil 2000 (HBR canonical, hybrid value-prop case)\n\n"
            + load_exemplar("mobil_2000"),
            "## Exemplar 2 — Wawa 2011 (sc0red Advisory house-style example)\n\n"
            + load_exemplar("wawa_2011"),
        ]
    )

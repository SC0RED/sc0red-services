"""Prompt and template loader — reads from prompts/ directory with caching."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_PROMPTS_DIR = Path(__file__).parent
_cache: dict[str, str] = {}


def _load_file(relative_path: str) -> str:
    if relative_path not in _cache:
        file_path = _PROMPTS_DIR / relative_path
        _cache[relative_path] = file_path.read_text(encoding="utf-8").strip()
    return _cache[relative_path]


def load_system_prompt(name: str) -> str:
    """Load a system prompt from the system/ directory."""
    return _load_file(f"system/{name}.md")


def load_guide(name: str) -> str:
    """Load a guide from the guides/ directory."""
    return _load_file(f"guides/{name}.md")


def load_template(name: str) -> str:
    """Load a user prompt template from the templates/ directory."""
    return _load_file(f"templates/{name}.md")


def load_schema(name: str) -> dict[str, Any]:
    """Load a JSON schema from the schemas/ directory."""
    content = _load_file(f"schemas/{name}.json")
    return json.loads(content)

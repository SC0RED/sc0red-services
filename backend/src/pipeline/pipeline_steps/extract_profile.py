"""Profile extraction constants — system prompt, schema, and prompt template.

Used by ParallelProfileRiskAndIdeation to build the profile extraction AI call.
"""

from __future__ import annotations

from typing import Any

from src.pipeline.prompts.loader import load_schema, load_system_prompt, load_template

PROFILE_SYSTEM_PROMPT = load_system_prompt("profile_extraction")

PROFILE_PROMPT_TEMPLATE = load_template("profile")

PROFILE_SCHEMA: dict[str, Any] = load_schema("profile")

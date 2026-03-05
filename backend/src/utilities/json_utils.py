"""Shared JSON parsing utilities."""

from __future__ import annotations

import json
from typing import Any


def parse_json_response(text: str) -> dict[str, Any]:
    """Parse JSON with fallback for markdown-wrapped responses.

    First tries direct JSON parse. If that fails, extracts the first
    JSON object from the text (handles ```json...``` wrapping).
    """
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1:
            msg = "No JSON object found in response"
            raise ValueError(msg) from None
        return json.loads(text[start : end + 1])

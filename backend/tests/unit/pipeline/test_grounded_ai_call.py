"""Tests for ``run_grounded_ai_call`` (web-search-grounding capability).

Pins: the grounded variant enables the provider ``web_search`` tool, returns the
``web_sources`` as a 5th element, and shares the validate/telemetry core with
``run_structured_ai_call`` (whose 4-tuple contract is unchanged).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from src.pipeline.pipeline_steps.ai_call import (
    TokenCounts,
    run_grounded_ai_call,
    run_structured_ai_call,
)

_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"answer": {"type": "string"}},
    "required": ["answer"],
    "additionalProperties": False,
}


def _factory(content: dict[str, Any], *, web_sources: list[Any] | None = None) -> MagicMock:
    factory = MagicMock()
    client = factory.get_client.return_value
    client.model = "gpt-test"
    response = MagicMock()
    response.content = content
    response.metadata = {}
    response.input_tokens = 10
    response.output_tokens = 5
    response.cached_input_tokens = 0
    # Real SDK responses always carry a list; default to [] for the plain case.
    response.web_sources = web_sources if web_sources is not None else []
    client.query_structured.return_value = response
    return factory


def test_grounded_call_enables_web_search_tool():
    factory = _factory({"answer": "ok"})
    run_grounded_ai_call(
        ai_client_factory=factory,
        user_prompt="p",
        schema=_SCHEMA,
        system_prompt="s",
        label="revenue_range",
        step_name="FinancialResearch",
    )
    _, kwargs = factory.get_client.call_args
    assert kwargs["tools"] == [{"type": "web_search"}]


def test_grounded_call_returns_web_sources():
    src = MagicMock()
    factory = _factory({"answer": "$90M"}, web_sources=[src])
    label, content, _elapsed, tokens, web_sources = run_grounded_ai_call(
        ai_client_factory=factory,
        user_prompt="p",
        schema=_SCHEMA,
        system_prompt="s",
        label="revenue_range",
        step_name="FinancialResearch",
    )
    assert label == "revenue_range"
    assert content == {"answer": "$90M"}
    assert isinstance(tokens, TokenCounts)
    assert web_sources == [src]


def test_grounded_call_passes_allowed_domains():
    factory = _factory({"answer": "ok"})
    run_grounded_ai_call(
        ai_client_factory=factory,
        user_prompt="p",
        schema=_SCHEMA,
        system_prompt="s",
        label="disclosed_figures",
        step_name="FinancialResearch",
        allowed_domains=["sec.gov"],
    )
    _, kwargs = factory.get_client.call_args
    assert kwargs["allowed_domains"] == ["sec.gov"]


def test_plain_call_unchanged_and_does_not_enable_tools():
    factory = _factory({"answer": "ok"})
    result = run_structured_ai_call(
        ai_client_factory=factory,
        user_prompt="p",
        schema=_SCHEMA,
        system_prompt="s",
        label="company_type",
        step_name="FinancialResearch",
    )
    # 4-tuple contract preserved.
    assert len(result) == 4
    _, kwargs = factory.get_client.call_args
    assert "tools" not in kwargs

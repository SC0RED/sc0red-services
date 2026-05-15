"""Shared AI call execution — used by all pipeline steps that make AI requests.

Centralises the get_client → query_structured → log pattern so changes
to retry logic, verbosity, or instrumentation happen in one place.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import jsonschema
from signalfield_core.models.enums import Precision, ReasoningEffort, Verbosity

if TYPE_CHECKING:
    from signalfield_core.services.ai_client_factory import AIClientFactory

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TokenCounts:
    """Per-call token consumption read from the SDK response.

    ``cached_input_tokens`` is a SUBSET of ``input_tokens`` — the portion served
    from the provider's prompt cache at a discounted price. When the provider
    doesn't expose cache information (older OpenAI surfaces, today's Anthropic),
    ``cached_input_tokens`` is ``0`` and consumers should treat the cache hit
    rate as unknown rather than zero.

    Pipeline steps emit these counts to ``StepTimer.record_tokens(label, counts)``
    so each per-call entry in the CloudWatch payload has its own three keys
    alongside the existing ``ai_call_{label}`` elapsed entry.
    """

    input_tokens: int
    output_tokens: int
    cached_input_tokens: int


def run_structured_ai_call(
    *,
    ai_client_factory: AIClientFactory,
    user_prompt: str,
    schema: dict[str, Any],
    system_prompt: str,
    label: str,
    step_name: str,
) -> tuple[str, dict[str, Any], float, TokenCounts]:
    """Execute a single structured AI call.

    Returns ``(label, content, elapsed_seconds, token_counts)``. All pipeline
    steps delegate to this function so AI client configuration, logging format,
    error handling, schema validation, and per-call telemetry are consistent
    across the pipeline.

    Two defensive gates run after the SDK call:

    1. **Schema validation** (``jsonschema.validate(response.content, schema)``):
       OpenAI's structured-output mode already enforces the schema, so this is
       a defensive fast-fail check — a malformed response trips at the exact
       call site with its ``label`` instead of propagating into downstream
       assembly and surfacing as a Pydantic error several steps later. Overhead
       is ~100-500 μs per call (negligible vs. the 500-2000 ms OpenAI latency
       dominating each call). See
       ``prompts/strategy_map/schemas/per_call/README.md`` for the pipeline's
       validation contract.

    2. **Token-count extraction**: reads ``input_tokens`` / ``output_tokens`` /
       ``cached_input_tokens`` from the SDK response and returns them as a
       ``TokenCounts`` so callers can record per-call telemetry via
       ``StepTimer.record_tokens(label, counts)``. Available since
       signalfield-core v0.2.0.
    """
    client = ai_client_factory.get_client(
        verbosity=Verbosity.MEDIUM,
        reasoning_effort=ReasoningEffort.LOW,
        precision=Precision.STANDARD,
        instructions=system_prompt,
    )
    logger.info(
        "[%s:%s] sending AI request: prompt_len=%d, model=%s",
        step_name,
        label,
        len(user_prompt),
        getattr(client, "model", "unknown"),
    )
    start = time.monotonic()
    try:
        response = client.query_structured(input_text=user_prompt, json_schema=schema)
    except Exception:
        logger.exception("[%s:%s] AI request failed", step_name, label)
        raise
    elapsed = time.monotonic() - start
    logger.info(
        "[%s:%s] AI response received in %.2fs: metadata=%s",
        step_name,
        label,
        elapsed,
        response.metadata,
    )
    try:
        jsonschema.validate(instance=response.content, schema=schema)
    except jsonschema.ValidationError:
        logger.exception(
            "[%s:%s] AI response failed per-call schema validation",
            step_name,
            label,
        )
        raise
    token_counts = TokenCounts(
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        cached_input_tokens=response.cached_input_tokens,
    )
    return label, response.content, elapsed, token_counts

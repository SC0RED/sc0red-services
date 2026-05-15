"""Shared AI call execution — used by all pipeline steps that make AI requests.

Centralises the get_client → query_structured → log pattern so changes
to retry logic, verbosity, or instrumentation happen in one place.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

import jsonschema
from signalfield_core.models.enums import Precision, ReasoningEffort, Verbosity

if TYPE_CHECKING:
    from signalfield_core.services.ai_client_factory import AIClientFactory

logger = logging.getLogger(__name__)


def run_structured_ai_call(
    *,
    ai_client_factory: AIClientFactory,
    user_prompt: str,
    schema: dict[str, Any],
    system_prompt: str,
    label: str,
    step_name: str,
) -> tuple[str, dict[str, Any], float]:
    """Execute a single structured AI call and return (label, content, elapsed_seconds).

    All pipeline steps delegate to this function so that AI client configuration,
    logging format, and error handling are consistent across the pipeline.

    A boundary-validation pass runs ``jsonschema.validate(response, schema)`` on
    every response before returning. OpenAI's structured-output mode already
    enforces the schema, so this is a defensive fast-fail check — a malformed
    response trips at the exact call site with its ``label`` instead of
    propagating into downstream assembly and surfacing as a Pydantic error
    several steps later. Overhead is ~100-500 μs per call (negligible vs. the
    500-2000 ms OpenAI latency dominating each call). See
    ``prompts/strategy_map/schemas/per_call/README.md`` for the pipeline's
    validation contract.
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
    return label, response.content, elapsed

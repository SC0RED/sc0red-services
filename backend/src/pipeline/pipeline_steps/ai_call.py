"""Shared AI call execution — used by all pipeline steps that make AI requests.

Centralises the get_client → query_structured → log pattern so changes
to retry logic, verbosity, or instrumentation happen in one place.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

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
    return label, response.content, elapsed

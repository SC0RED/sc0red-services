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
    from signalfield_core.models.ai_response import WebSearchSource
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
    precision: Precision = Precision.STANDARD,
) -> tuple[str, dict[str, Any], float, TokenCounts]:
    """Execute a single structured AI call.

    Returns ``(label, content, elapsed_seconds, token_counts)``. All pipeline
    steps delegate to this function so AI client configuration, logging format,
    error handling, schema validation, and per-call telemetry are consistent
    across the pipeline.

    ``precision`` chooses which model the SDK routes to:

    - ``Precision.STANDARD`` (default) → ``gpt-5.4-mini`` as of
      signalfield-core v0.3.0. Bulk-parallel / short-output tier — much
      lower latency and tighter tail than ``gpt-5.1``.
    - ``Precision.ADVANCED`` → ``gpt-5.1``. Escape hatch for call sites
      where output specificity (PE-grade ROI estimates, accurate
      categorical classification) matters more than latency.

    The sc0red Services 2026-05-15 benchmark (``backend/scripts/benchmark/results/``)
    cleared mini for all strategy-map calls + risk batches + ideation +
    portfolio discovery/validation. Two call sites flagged 🔴 and use
    ``Precision.ADVANCED``: ``ParallelProfileRiskAndIdeation``'s
    ``extract_profile`` task and ``DetailOpportunities``.

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
        precision=precision,
        instructions=system_prompt,
    )
    logger.info(
        "[%s:%s] sending AI request: prompt_len=%d, model=%s",
        step_name,
        label,
        len(user_prompt),
        getattr(client, "model", "unknown"),
    )
    content, elapsed, token_counts, _web_sources = _execute_structured(
        client, user_prompt=user_prompt, schema=schema, label=label, step_name=step_name
    )
    return label, content, elapsed, token_counts


# ---------------------------------------------------------------------------
# Web-search-grounded variant + shared core
# ---------------------------------------------------------------------------

# Provider-native web-search tool config (OpenAI Responses ``web_search``).
# Attached at client construction; the SDK extracts the resulting sources.
_WEB_SEARCH_TOOL: list[dict[str, str]] = [{"type": "web_search"}]


def run_grounded_ai_call(
    *,
    ai_client_factory: AIClientFactory,
    user_prompt: str,
    schema: dict[str, Any],
    system_prompt: str,
    label: str,
    step_name: str,
    precision: Precision = Precision.STANDARD,
    allowed_domains: list[str] | None = None,
) -> tuple[str, dict[str, Any], float, TokenCounts, list[WebSearchSource]]:
    """Structured AI call with the provider's native ``web_search`` tool enabled.

    Identical to ``run_structured_ai_call`` except it (a) attaches the
    ``web_search`` tool so the model can ground quantitative facts against the
    live web and (b) returns the resulting ``web_sources`` (url/title/snippet)
    as a fifth element, so callers can attach citations and set ``DISCLOSED``
    provenance. ``allowed_domains`` optionally restricts search to an allow-list.

    Used by the financial-research steps for the few questions whose answer
    lives in the world rather than the model's training knowledge (see the
    web-search-grounding capability). Existing callers that don't need grounding
    keep using ``run_structured_ai_call`` and its unchanged 4-tuple — both route
    through the same ``_execute_structured`` core.
    """
    client = ai_client_factory.get_client(
        verbosity=Verbosity.MEDIUM,
        reasoning_effort=ReasoningEffort.LOW,
        precision=precision,
        instructions=system_prompt,
        tools=_WEB_SEARCH_TOOL,
        allowed_domains=allowed_domains,
    )
    logger.info(
        "[%s:%s] sending grounded AI request (web_search): prompt_len=%d, model=%s",
        step_name,
        label,
        len(user_prompt),
        getattr(client, "model", "unknown"),
    )
    content, elapsed, token_counts, web_sources = _execute_structured(
        client, user_prompt=user_prompt, schema=schema, label=label, step_name=step_name
    )
    logger.info(
        "[%s:%s] grounded call returned %d web source(s)", step_name, label, len(web_sources)
    )
    return label, content, elapsed, token_counts, web_sources


def _execute_structured(
    client: Any,
    *,
    user_prompt: str,
    schema: dict[str, Any],
    label: str,
    step_name: str,
) -> tuple[dict[str, Any], float, TokenCounts, list[WebSearchSource]]:
    """Shared core: query the client, log, validate, extract tokens + web sources.

    Both ``run_structured_ai_call`` and ``run_grounded_ai_call`` route through
    here so the query / schema-validation / telemetry contract stays
    single-sourced; they differ only in whether the client carries the
    ``web_search`` tool and whether the caller is handed the ``web_sources``.
    """
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
    # Defensive: only a genuine list counts (real SDK responses always carry a
    # ``web_sources`` list; test doubles / older responses may not).
    raw_sources = getattr(response, "web_sources", None)
    web_sources = list(raw_sources) if isinstance(raw_sources, list) else []
    return response.content, elapsed, token_counts, web_sources

"""Lightweight sub-step timing for pipeline performance instrumentation.

Usage inside a pipeline step's execute():

    timer = StepTimer("GenerateStrategyMap")
    label, content, elapsed, tokens = run_structured_ai_call(...)
    timer.record(label, elapsed)
    timer.record_tokens(label, tokens)
    self.request_executor.add_details(timer.to_details())

Produces details like:
    {"GenerateStrategyMap.timings": {
        "ai_call_vision_text": 1.2,
        "tokens_in_vision_text": 1450,
        "tokens_out_vision_text": 220,
        "cached_tokens_vision_text": 1320,
        "ai_call_mission_text": 1.1,
        "tokens_in_mission_text": 1450,
        ...
        "total": 28.4
    }}

Token-count entries are integers. Elapsed entries (including ``total``)
are floats. Both share the same per-call ``label`` so CloudWatch Insights
queries can group them by call.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Generator

    from src.pipeline.pipeline_steps.ai_call import TokenCounts


class StepTimer:
    """Collects sub-step wall-clock timings and per-call token counts for a pipeline step.

    Timings (floats, seconds) and token counts (ints) are kept in separate
    internal dicts so callers always pass typed values, and merged into a
    single flat payload at ``to_details()`` time. The merged shape mirrors
    the historical ``elapsed-only`` payload so existing CloudWatch
    dashboards and queries continue to work; consumers that want the new
    keys query for ``tokens_in_*`` / ``tokens_out_*`` / ``cached_tokens_*``
    additively.
    """

    def __init__(self, step_name: str) -> None:
        self._step_name = step_name
        self._timings: dict[str, float] = {}
        self._token_counts: dict[str, int] = {}
        self._start = time.monotonic()

    @contextmanager
    def measure(self, label: str) -> Generator[None, None, None]:
        """Time a block and record it under *label*.

        Records elapsed time even if the block raises, so failure-path
        timings are preserved for diagnostics.
        """
        start = time.monotonic()
        try:
            yield
        finally:
            self._timings[label] = time.monotonic() - start

    def record(self, label: str, elapsed: float) -> None:
        """Manually record a timing (useful for values returned from threads)."""
        self._timings[label] = elapsed

    def record_tokens(self, label: str, counts: TokenCounts) -> None:
        """Record per-call token counts under three keys keyed by *label*.

        Writes ``tokens_in_{label}``, ``tokens_out_{label}``, and
        ``cached_tokens_{label}``. Pair with ``record(label, elapsed)`` at
        each AI call site to emit a complete observability record per call.

        Counts come from the SDK's ``StructuredResponse`` (signalfield-core
        v0.2.0+) — ``cached_input_tokens`` is the subset of ``input_tokens``
        served from the provider's prompt cache (0 when the provider doesn't
        expose cache information).
        """
        self._token_counts[f"tokens_in_{label}"] = counts.input_tokens
        self._token_counts[f"tokens_out_{label}"] = counts.output_tokens
        self._token_counts[f"cached_tokens_{label}"] = counts.cached_input_tokens

    def to_details(self) -> dict[str, dict[str, float | int]]:
        """Return a dict suitable for ``request_executor.add_details()``.

        Merges timings and token counts into a single flat dict under a single
        ``{step_name}.timings`` key. Elapsed entries are floats; token-count
        entries are ints. CloudWatch Insights stores both as numeric values
        and treats them identically at query time.
        """
        result: dict[str, float | int] = dict(self._timings)
        result.update(self._token_counts)
        result["total"] = time.monotonic() - self._start
        return {f"{self._step_name}.timings": result}

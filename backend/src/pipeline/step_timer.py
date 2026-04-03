"""Lightweight sub-step timing for pipeline performance instrumentation.

Usage inside a pipeline step's execute():

    timer = StepTimer("GenerateOpportunities")
    with timer.measure("ai_call_high_priority"):
        result_a = client.query_structured(...)
    with timer.measure("ai_call_strategic"):
        result_b = client.query_structured(...)
    self.request_executor.add_details(timer.to_details())

Produces details like:
    {"GenerateOpportunities.timings": {
        "ai_call_high_priority": 52.3,
        "ai_call_strategic": 48.1,
        "total": 100.4
    }}
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Generator


class StepTimer:
    """Collects sub-step wall-clock timings for a pipeline step."""

    def __init__(self, step_name: str) -> None:
        self._step_name = step_name
        self._timings: dict[str, float] = {}
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

    def to_details(self) -> dict[str, dict[str, float]]:
        """Return a dict suitable for ``request_executor.add_details()``."""
        result = dict(self._timings)
        result["total"] = time.monotonic() - self._start
        return {f"{self._step_name}.timings": result}

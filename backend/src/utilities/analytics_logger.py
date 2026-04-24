"""CloudWatch Logs sink for sc0red CTA analytics events.

Writes `EnrichedAnalyticsEvent` instances as structured JSON log lines to a
dedicated log group. Downstream, operators query the log group via
CloudWatch Logs Insights to compute funnel metrics (expand → click) and
per-org breakdowns.

Design decisions (see
``openspec/changes/opportunities-cta-analytics/design.md``):

- **Dedicated log group** (not the API Lambda's own log group) so Logs
  Insights queries never have to filter operational noise from analytics.
- **One log stream per Lambda execution context**. AWS Lambda provides
  ``AWS_LAMBDA_LOG_STREAM_NAME`` which is stable for the life of the
  container. Reusing it avoids the per-event ``CreateLogStream`` round
  trip after the first call. Outside Lambda (tests, local server) we fall
  back to a module-lifetime UUID-suffixed stream.
- **Fail-fast on missing ``ANALYTICS_LOG_GROUP`` in non-development
  environments**. A silently-dropped event is worse than a visible error,
  because the first signal that analytics is broken would be "the funnel
  dashboard is empty" three weeks later.
- **No retry, no queue**. CTA volume is low; if a ``put_log_events`` call
  fails we log and re-raise. The handler above converts the exception
  into a 500 — callers (the frontend emit helper) already swallow errors
  so the user never sees it.
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from threading import Lock
from typing import TYPE_CHECKING

import boto3
from botocore.exceptions import ClientError

if TYPE_CHECKING:
    from src.models.analytics_events import EnrichedAnalyticsEvent

logger = logging.getLogger(__name__)

_ANALYTICS_LOG_GROUP_ENV = "ANALYTICS_LOG_GROUP"
_STAGE_ENV = "STAGE"
_LAMBDA_STREAM_ENV = "AWS_LAMBDA_LOG_STREAM_NAME"


class AnalyticsLoggerNotConfiguredError(RuntimeError):
    """Raised when ``ANALYTICS_LOG_GROUP`` is unset in a non-development stage.

    Separate exception type so handler code can distinguish configuration
    drift ("ops forgot to set the env var") from transport errors ("the
    CloudWatch API is down").
    """


class _CloudWatchAnalyticsSink:
    """Singleton wrapper around ``boto3.client("logs")``.

    Creates the log stream lazily on first write. Subsequent writes reuse
    the stream.

    Not thread-safe for stream creation (a lock guards the
    ``CreateLogStream`` call), but ``put_log_events`` itself is safe to
    call concurrently on the same stream — CloudWatch accepts unordered
    events as of Nov 2023.
    """

    def __init__(self, log_group_name: str, log_stream_name: str) -> None:
        self._log_group_name = log_group_name
        self._log_stream_name = log_stream_name
        self._client = boto3.client("logs")
        self._stream_ready = False
        self._stream_lock = Lock()

    def _ensure_stream(self) -> None:
        if self._stream_ready:
            return
        with self._stream_lock:
            if self._stream_ready:
                return
            try:
                self._client.create_log_stream(
                    logGroupName=self._log_group_name,
                    logStreamName=self._log_stream_name,
                )
            except ClientError as error:
                code = error.response.get("Error", {}).get("Code", "")
                if code != "ResourceAlreadyExistsException":
                    raise
                # Stream pre-existed — fine, another container created it.
            self._stream_ready = True

    def put(self, message: str) -> None:
        """Write a single JSON log line to the analytics log stream."""
        self._ensure_stream()
        self._client.put_log_events(
            logGroupName=self._log_group_name,
            logStreamName=self._log_stream_name,
            logEvents=[
                {
                    "timestamp": int(time.time() * 1000),
                    "message": message,
                }
            ],
        )


_sink: _CloudWatchAnalyticsSink | None = None
_sink_lock = Lock()


def _resolve_stream_name() -> str:
    """Return a stable stream name for the current execution context.

    In Lambda, ``AWS_LAMBDA_LOG_STREAM_NAME`` is set per container and
    stable across warm invocations. Outside Lambda we generate a
    module-lifetime UUID — tests and local dev won't collide with each
    other because each process gets its own.
    """
    lambda_stream = os.environ.get(_LAMBDA_STREAM_ENV)
    if lambda_stream:
        return lambda_stream
    return f"local-{uuid.uuid4()}"


def _is_development() -> bool:
    """Return True when running in the development stage (LocalStack, tests, local dev)."""
    return os.environ.get(_STAGE_ENV, "development") == "development"


def _get_sink() -> _CloudWatchAnalyticsSink | None:
    """Return the shared sink, creating it on first call.

    Returns ``None`` when ``ANALYTICS_LOG_GROUP`` is unset *and* we are in
    development — dev environments without a log group configured are
    expected to no-op. In any other stage, a missing log group raises.
    """
    global _sink
    if _sink is not None:
        return _sink

    log_group = os.environ.get(_ANALYTICS_LOG_GROUP_ENV, "")
    if not log_group:
        if _is_development():
            logger.warning(
                "%s is unset — analytics events will be dropped (development stage only)",
                _ANALYTICS_LOG_GROUP_ENV,
            )
            return None
        raise AnalyticsLoggerNotConfiguredError(
            f"{_ANALYTICS_LOG_GROUP_ENV} is required outside the development stage"
        )

    with _sink_lock:
        if _sink is None:
            _sink = _CloudWatchAnalyticsSink(
                log_group_name=log_group,
                log_stream_name=_resolve_stream_name(),
            )
    return _sink


def log_event(enriched_event: EnrichedAnalyticsEvent) -> None:
    """Write an enriched analytics event to the dedicated CloudWatch log group.

    The event is serialized as a single-line JSON object — Logs Insights
    auto-discovers the fields so queries like
    ``stats count() by event_type`` work out of the box.

    Raises:
        AnalyticsLoggerNotConfiguredError: ``ANALYTICS_LOG_GROUP`` is
            unset and we are not in the development stage.
        ClientError: the CloudWatch Logs API call failed (network,
            throttling, IAM). The caller decides whether to surface or
            swallow — the handler currently surfaces, the frontend
            swallows.
    """
    sink = _get_sink()
    if sink is None:
        return
    sink.put(json.dumps(enriched_event.model_dump(), separators=(",", ":")))


def reset_for_testing() -> None:
    """Reset the module-level sink so unit tests can re-exercise init logic.

    Production code never calls this. Tests that manipulate
    ``ANALYTICS_LOG_GROUP`` / ``STAGE`` between cases must call it to
    avoid the first-test sink leaking into the next case.
    """
    global _sink
    with _sink_lock:
        _sink = None

"""Tests for the CloudWatch analytics logger sink."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from src.models.analytics_events import AnalyticsEvent, EnrichedAnalyticsEvent
from src.utilities import analytics_logger
from src.utilities.analytics_logger import (
    AnalyticsLoggerNotConfiguredError,
    emit_event,
    reset_for_testing,
)

if TYPE_CHECKING:
    from pytest import MonkeyPatch


def _sample_enriched_event() -> EnrichedAnalyticsEvent:
    client = AnalyticsEvent(
        event_id="uuid-1",
        event_type="sc0red_cta_rendered_strategy_map",
        timestamp="2026-04-24T12:00:00.000Z",
        analytics_version="1",
        source="web",
        analysis_id="assess-1",
        opportunity_count=3,
        active_lever_filter=None,
    )
    return EnrichedAnalyticsEvent.from_client_event(client, user_id="user-1", org_id="org-1")


@pytest.fixture(autouse=True)
def _isolate_sink() -> None:
    """Reset the module-level sink between tests — env var flips would otherwise leak."""
    reset_for_testing()
    yield
    reset_for_testing()


class TestLogEventInDevelopment:
    """Development stage: no log group configured is expected; emit_event no-ops."""

    def test_no_log_group_in_development_is_noop(self, monkeypatch: MonkeyPatch) -> None:
        monkeypatch.delenv("ANALYTICS_LOG_GROUP", raising=False)
        monkeypatch.setenv("STAGE", "development")

        with patch.object(analytics_logger, "boto3") as mock_boto:
            emit_event(_sample_enriched_event())

        mock_boto.client.assert_not_called()

    def test_default_stage_is_development(self, monkeypatch: MonkeyPatch) -> None:
        """STAGE unset is treated as development (matches sc0red_services_stack default)."""
        monkeypatch.delenv("ANALYTICS_LOG_GROUP", raising=False)
        monkeypatch.delenv("STAGE", raising=False)

        # No raise means "treated as development".
        emit_event(_sample_enriched_event())


class TestLogEventFailsFastOutsideDevelopment:
    @pytest.mark.parametrize("stage", ["staging", "testing", "production"])
    def test_missing_log_group_raises(self, monkeypatch: MonkeyPatch, stage: str) -> None:
        monkeypatch.delenv("ANALYTICS_LOG_GROUP", raising=False)
        monkeypatch.setenv("STAGE", stage)

        with pytest.raises(AnalyticsLoggerNotConfiguredError):
            emit_event(_sample_enriched_event())


class TestLogEventSuccess:
    def test_writes_event_as_single_json_line(self, monkeypatch: MonkeyPatch) -> None:
        monkeypatch.setenv("ANALYTICS_LOG_GROUP", "/sc0red-services/staging/analytics-events")
        monkeypatch.setenv("STAGE", "staging")
        monkeypatch.setenv("AWS_LAMBDA_LOG_STREAM_NAME", "2026/04/24/[$LATEST]deadbeef")

        mock_client = MagicMock()
        with patch.object(analytics_logger, "boto3") as mock_boto:
            mock_boto.client.return_value = mock_client
            emit_event(_sample_enriched_event())

        mock_boto.client.assert_called_once_with("logs")
        mock_client.create_log_stream.assert_called_once_with(
            logGroupName="/sc0red-services/staging/analytics-events",
            logStreamName="2026/04/24/[$LATEST]deadbeef",
        )
        mock_client.put_log_events.assert_called_once()
        call_kwargs = mock_client.put_log_events.call_args.kwargs
        assert call_kwargs["logGroupName"] == "/sc0red-services/staging/analytics-events"
        assert call_kwargs["logStreamName"] == "2026/04/24/[$LATEST]deadbeef"
        assert len(call_kwargs["logEvents"]) == 1
        entry = call_kwargs["logEvents"][0]
        assert isinstance(entry["timestamp"], int)
        assert entry["timestamp"] > 0
        payload = json.loads(entry["message"])
        assert payload["event_type"] == "sc0red_cta_rendered_strategy_map"
        assert payload["user_id"] == "user-1"
        assert payload["org_id"] == "org-1"
        # Strategy-map CTA events MUST carry a null lever filter — the
        # surface has no lever-filter concept and non-null would corrupt
        # cross-surface funnel queries that join on ``event_type``.
        assert payload["active_lever_filter"] is None

    def test_stream_is_created_only_once_per_process(self, monkeypatch: MonkeyPatch) -> None:
        monkeypatch.setenv("ANALYTICS_LOG_GROUP", "/sc0red-services/staging/analytics-events")
        monkeypatch.setenv("STAGE", "staging")
        monkeypatch.setenv("AWS_LAMBDA_LOG_STREAM_NAME", "warm-container-stream")

        mock_client = MagicMock()
        with patch.object(analytics_logger, "boto3") as mock_boto:
            mock_boto.client.return_value = mock_client
            emit_event(_sample_enriched_event())
            emit_event(_sample_enriched_event())
            emit_event(_sample_enriched_event())

        assert mock_client.create_log_stream.call_count == 1
        assert mock_client.put_log_events.call_count == 3

    def test_falls_back_to_generated_stream_outside_lambda(self, monkeypatch: MonkeyPatch) -> None:
        """Without AWS_LAMBDA_LOG_STREAM_NAME we still produce a non-empty stream name."""
        monkeypatch.setenv("ANALYTICS_LOG_GROUP", "/sc0red-services/staging/analytics-events")
        monkeypatch.setenv("STAGE", "staging")
        monkeypatch.delenv("AWS_LAMBDA_LOG_STREAM_NAME", raising=False)

        mock_client = MagicMock()
        with patch.object(analytics_logger, "boto3") as mock_boto:
            mock_boto.client.return_value = mock_client
            emit_event(_sample_enriched_event())

        stream_name = mock_client.create_log_stream.call_args.kwargs["logStreamName"]
        assert stream_name.startswith("local-")
        assert len(stream_name) > len("local-")

    def test_existing_stream_is_not_an_error(self, monkeypatch: MonkeyPatch) -> None:
        """ResourceAlreadyExistsException is an expected race, not a failure."""
        monkeypatch.setenv("ANALYTICS_LOG_GROUP", "/sc0red-services/staging/analytics-events")
        monkeypatch.setenv("STAGE", "staging")

        mock_client = MagicMock()
        mock_client.create_log_stream.side_effect = ClientError(
            {"Error": {"Code": "ResourceAlreadyExistsException", "Message": "exists"}},
            "CreateLogStream",
        )
        with patch.object(analytics_logger, "boto3") as mock_boto:
            mock_boto.client.return_value = mock_client
            emit_event(_sample_enriched_event())

        mock_client.put_log_events.assert_called_once()


class TestLogEventErrorPropagation:
    def test_create_log_stream_error_propagates(self, monkeypatch: MonkeyPatch) -> None:
        """Non-AlreadyExists CloudWatch errors propagate — they are real failures."""
        monkeypatch.setenv("ANALYTICS_LOG_GROUP", "/sc0red-services/staging/analytics-events")
        monkeypatch.setenv("STAGE", "staging")

        mock_client = MagicMock()
        mock_client.create_log_stream.side_effect = ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "no perms"}},
            "CreateLogStream",
        )
        with patch.object(analytics_logger, "boto3") as mock_boto:
            mock_boto.client.return_value = mock_client
            with pytest.raises(ClientError):
                emit_event(_sample_enriched_event())

        mock_client.put_log_events.assert_not_called()

    def test_put_log_events_error_propagates(self, monkeypatch: MonkeyPatch) -> None:
        monkeypatch.setenv("ANALYTICS_LOG_GROUP", "/sc0red-services/staging/analytics-events")
        monkeypatch.setenv("STAGE", "staging")

        mock_client = MagicMock()
        mock_client.put_log_events.side_effect = ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "slow down"}},
            "PutLogEvents",
        )
        with patch.object(analytics_logger, "boto3") as mock_boto:
            mock_boto.client.return_value = mock_client
            with pytest.raises(ClientError):
                emit_event(_sample_enriched_event())

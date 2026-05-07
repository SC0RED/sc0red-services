"""Tests for AppSync progress notifier."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.pipeline.appsync_notifier import (
    notify_progress,
    notify_strategy_map_complete,
    notify_strategy_map_failed,
    notify_strategy_map_progress,
)


class TestNotifyProgress:
    def test_skips_when_endpoint_not_configured(self):
        """When APPSYNC_ENDPOINT is empty, notify_progress is a no-op."""
        with patch("src.pipeline.appsync_notifier._APPSYNC_ENDPOINT", ""):
            # Should not raise or make any HTTP calls
            notify_progress(scan_id="scan-1", progress=50, label="Testing...")

    def test_skips_when_api_key_not_configured(self):
        """When APPSYNC_API_KEY is empty, notify_progress is a no-op."""
        with patch("src.pipeline.appsync_notifier._APPSYNC_ENDPOINT", "https://example.com"):
            with patch("src.pipeline.appsync_notifier._APPSYNC_API_KEY", ""):
                notify_progress(scan_id="scan-1", progress=50, label="Testing...")

    @patch("src.pipeline.appsync_notifier.urlopen")
    def test_sends_mutation_when_configured(self, mock_urlopen: MagicMock):
        """When both endpoint and key are set, sends a GraphQL mutation."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        with (
            patch("src.pipeline.appsync_notifier._APPSYNC_ENDPOINT", "https://appsync.example.com/graphql"),
            patch("src.pipeline.appsync_notifier._APPSYNC_API_KEY", "da2-fakekey123"),
        ):
            notify_progress(
                scan_id="scan-1",
                progress=45,
                label="Assessing risks...",
                company_id="company-1",
            )

        mock_urlopen.assert_called_once()
        request = mock_urlopen.call_args[0][0]
        assert request.full_url == "https://appsync.example.com/graphql"
        assert request.get_header("X-api-key") == "da2-fakekey123"
        assert request.get_header("Content-type") == "application/json"

    @patch("src.pipeline.appsync_notifier.urlopen")
    def test_handles_network_error_gracefully(self, mock_urlopen: MagicMock):
        """Network errors are logged but do not propagate."""
        from urllib.error import URLError

        mock_urlopen.side_effect = URLError("Connection refused")

        with (
            patch("src.pipeline.appsync_notifier._APPSYNC_ENDPOINT", "https://appsync.example.com/graphql"),
            patch("src.pipeline.appsync_notifier._APPSYNC_API_KEY", "da2-fakekey123"),
        ):
            # Should not raise
            notify_progress(scan_id="scan-1", progress=50, label="Testing...")

    @patch("src.pipeline.appsync_notifier.urlopen")
    def test_handles_non_200_response(self, mock_urlopen: MagicMock):
        """Non-200 responses are logged but do not propagate."""
        mock_response = MagicMock()
        mock_response.status = 500
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        with (
            patch("src.pipeline.appsync_notifier._APPSYNC_ENDPOINT", "https://appsync.example.com/graphql"),
            patch("src.pipeline.appsync_notifier._APPSYNC_API_KEY", "da2-fakekey123"),
        ):
            # Should not raise
            notify_progress(scan_id="scan-1", progress=50, label="Testing...")

    @patch("src.pipeline.appsync_notifier.urlopen")
    def test_default_status_is_running(self, mock_urlopen: MagicMock):
        """When status is not specified, defaults to 'running'."""
        import json

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        with (
            patch("src.pipeline.appsync_notifier._APPSYNC_ENDPOINT", "https://appsync.example.com/graphql"),
            patch("src.pipeline.appsync_notifier._APPSYNC_API_KEY", "da2-fakekey123"),
        ):
            notify_progress(scan_id="scan-1", progress=50, label="Testing...")

        request = mock_urlopen.call_args[0][0]
        body = json.loads(request.data)
        assert body["variables"]["input"]["status"] == "running"
        assert body["variables"]["input"]["companyId"] == ""


class TestNotifyStrategyMapComplete:
    """Per the strategy-map-on-demand spec, the worker pushes a
    `strategy_map_complete` event by reusing `publishProgress` with a
    distinguished `status` value. Frontend filters by status to route the
    event into the strategy-map subscription path."""

    @patch("src.pipeline.appsync_notifier.urlopen")
    def test_emits_publishProgress_with_strategy_map_complete_status(
        self, mock_urlopen: MagicMock
    ):
        import json

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        with (
            patch(
                "src.pipeline.appsync_notifier._APPSYNC_ENDPOINT",
                "https://appsync.example.com/graphql",
            ),
            patch("src.pipeline.appsync_notifier._APPSYNC_API_KEY", "da2-fakekey123"),
        ):
            notify_strategy_map_complete(scan_id="scan-9", analysis_id="analysis-7")

        request = mock_urlopen.call_args[0][0]
        body = json.loads(request.data)
        # analysis_id maps to the existing companyId field on the progress
        # channel — the frontend already subscribes by companyId.
        assert body["variables"]["input"]["companyId"] == "analysis-7"
        assert body["variables"]["input"]["scanId"] == "scan-9"
        assert body["variables"]["input"]["status"] == "strategy_map_complete"
        assert body["variables"]["input"]["progress"] == 100

    def test_skips_when_endpoint_not_configured(self):
        """No AppSync endpoint → no-op (consistent with notify_progress)."""
        with patch("src.pipeline.appsync_notifier._APPSYNC_ENDPOINT", ""):
            notify_strategy_map_complete(scan_id="scan-1", analysis_id="a-1")


class TestNotifyStrategyMapFailed:
    """Worker error path: push `strategy_map_failed` event so the frontend
    transitions the slot back to CTA state with a "try again" message."""

    @patch("src.pipeline.appsync_notifier.urlopen")
    def test_emits_publishProgress_with_strategy_map_failed_status(
        self, mock_urlopen: MagicMock
    ):
        import json

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        with (
            patch(
                "src.pipeline.appsync_notifier._APPSYNC_ENDPOINT",
                "https://appsync.example.com/graphql",
            ),
            patch("src.pipeline.appsync_notifier._APPSYNC_API_KEY", "da2-fakekey123"),
        ):
            notify_strategy_map_failed(
                scan_id="scan-x",
                analysis_id="analysis-y",
                error_message="OpenAI rate limit",
            )

        request = mock_urlopen.call_args[0][0]
        body = json.loads(request.data)
        assert body["variables"]["input"]["companyId"] == "analysis-y"
        assert body["variables"]["input"]["status"] == "strategy_map_failed"
        # Generic user-visible label — implementation details (rate-limit etc.)
        # stay in CloudWatch via the warning log, not in the AppSync payload.
        assert "fail" in body["variables"]["input"]["progressLabel"].lower()
        # Sensitive details from `error_message` MUST NOT leak into the payload.
        assert "rate limit" not in body["variables"]["input"]["progressLabel"].lower()


class TestNotifyStrategyMapProgress:
    """In-flight progress events emitted at phase boundaries inside the
    strategy-map worker (per the strategy-map-on-demand observability
    follow-up). Frontend filters by `status="strategy_map_progress"` and
    routes to its `onProgress` callback so the generating placeholder
    can render a moving bar instead of a static spinner."""

    @patch("src.pipeline.appsync_notifier.urlopen")
    def test_emits_publishProgress_with_strategy_map_progress_status(
        self, mock_urlopen: MagicMock
    ):
        import json

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        with (
            patch(
                "src.pipeline.appsync_notifier._APPSYNC_ENDPOINT",
                "https://appsync.example.com/graphql",
            ),
            patch("src.pipeline.appsync_notifier._APPSYNC_API_KEY", "da2-fakekey123"),
        ):
            notify_strategy_map_progress(
                scan_id="scan-1",
                analysis_id="analysis-1",
                progress=30,
                label="Elaborating perspective objectives…",
            )

        request = mock_urlopen.call_args[0][0]
        body = json.loads(request.data)
        assert body["variables"]["input"]["scanId"] == "scan-1"
        assert body["variables"]["input"]["companyId"] == "analysis-1"
        assert body["variables"]["input"]["status"] == "strategy_map_progress"
        assert body["variables"]["input"]["progress"] == 30
        assert body["variables"]["input"]["progressLabel"] == "Elaborating perspective objectives…"

    def test_skips_when_endpoint_not_configured(self):
        """No AppSync endpoint → no-op (consistent with notify_progress)."""
        with patch("src.pipeline.appsync_notifier._APPSYNC_ENDPOINT", ""):
            notify_strategy_map_progress(
                scan_id="scan-1",
                analysis_id="a-1",
                progress=50,
                label="Halfway",
            )

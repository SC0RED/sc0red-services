"""Tests for the analytics event handler + dispatch integration."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from src.handlers.analytics_handlers import handle_post_event
from src.handlers.auth_middleware import AuthContext


def _auth(user_id: str = "user-1", org_id: str = "org-1") -> AuthContext:
    return AuthContext(user_id=user_id, org_id=org_id, email="a@b.com", role="analyst")


def _body(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "event_id": "uuid-1",
        "event_type": "sc0red_cta_banner_expanded",
        "timestamp": "2026-04-24T12:00:00.000Z",
        "analytics_version": "1",
        "source": "web",
        "analysis_id": "assess-1",
        "opportunity_count": 3,
        "active_lever_filter": "Revenue Side",
    }
    base.update(overrides)
    return base


def _event(body: dict[str, object] | None = None, raw: str | None = None) -> dict[str, object]:
    if raw is not None:
        return {"body": raw}
    return {"body": json.dumps(body if body is not None else _body())}


class TestHandlePostEventHappyPath:
    def test_returns_202_on_valid_envelope(self) -> None:
        with patch("src.handlers.analytics_handlers.log_event") as mock_log:
            result = handle_post_event(_event(), _auth())
        assert result["statusCode"] == 202
        body = json.loads(result["body"])
        assert body == {"accepted": True}
        mock_log.assert_called_once()

    def test_enriches_with_jwt_identity(self) -> None:
        with patch("src.handlers.analytics_handlers.log_event") as mock_log:
            handle_post_event(_event(), _auth(user_id="user-42", org_id="org-99"))

        enriched = mock_log.call_args.args[0]
        assert enriched.user_id == "user-42"
        assert enriched.org_id == "org-99"
        assert enriched.event_type == "sc0red_cta_banner_expanded"

    def test_spoofed_org_id_in_body_is_ignored(self) -> None:
        """Anti-spoofing: body-side user_id / org_id are rejected by the envelope,
        but even the happy path above proves JWT values override anything the
        client might send. Here we explicitly confirm the JWT wins."""
        with patch("src.handlers.analytics_handlers.log_event") as mock_log:
            handle_post_event(
                _event(_body()),  # clean body
                _auth(user_id="real-user", org_id="real-org"),
            )

        enriched = mock_log.call_args.args[0]
        assert enriched.user_id == "real-user"
        assert enriched.org_id == "real-org"


class TestHandlePostEventValidation:
    def test_invalid_json_returns_400(self) -> None:
        with patch("src.handlers.analytics_handlers.log_event") as mock_log:
            result = handle_post_event(_event(raw="{not json"), _auth())
        assert result["statusCode"] == 400
        mock_log.assert_not_called()

    def test_missing_event_type_returns_400(self) -> None:
        body = _body()
        del body["event_type"]
        with patch("src.handlers.analytics_handlers.log_event") as mock_log:
            result = handle_post_event(_event(body), _auth())
        assert result["statusCode"] == 400
        mock_log.assert_not_called()

    def test_unknown_event_type_returns_400(self) -> None:
        with patch("src.handlers.analytics_handlers.log_event") as mock_log:
            result = handle_post_event(
                _event(_body(event_type="sc0red_cta_unicorn")),
                _auth(),
            )
        assert result["statusCode"] == 400
        mock_log.assert_not_called()

    def test_spoofed_user_id_in_body_is_rejected(self) -> None:
        """`extra="forbid"` on AnalyticsEvent rejects body-level identity fields."""
        with patch("src.handlers.analytics_handlers.log_event") as mock_log:
            result = handle_post_event(
                _event(_body(user_id="spoofed")),
                _auth(),
            )
        assert result["statusCode"] == 400
        mock_log.assert_not_called()

    def test_spoofed_org_id_in_body_is_rejected(self) -> None:
        with patch("src.handlers.analytics_handlers.log_event") as mock_log:
            result = handle_post_event(
                _event(_body(org_id="spoofed-org")),
                _auth(),
            )
        assert result["statusCode"] == 400
        mock_log.assert_not_called()

    def test_pdf_event_with_web_source_returns_400(self) -> None:
        body = _body(
            event_type="sc0red_cta_rendered_in_pdf",
            source="web",
            active_lever_filter=None,
        )
        with patch("src.handlers.analytics_handlers.log_event") as mock_log:
            result = handle_post_event(_event(body), _auth())
        assert result["statusCode"] == 400
        mock_log.assert_not_called()

    def test_empty_body_returns_400(self) -> None:
        with patch("src.handlers.analytics_handlers.log_event") as mock_log:
            result = handle_post_event({"body": None}, _auth())
        assert result["statusCode"] == 400
        mock_log.assert_not_called()


class TestHandlePostEventErrorPropagation:
    def test_sink_error_propagates(self) -> None:
        """If the CloudWatch sink fails, the exception bubbles up — the API
        Gateway handler converts it to 500. We do NOT swallow logger errors."""
        with (
            patch(
                "src.handlers.analytics_handlers.log_event",
                side_effect=RuntimeError("CloudWatch unavailable"),
            ),
            pytest.raises(RuntimeError, match="CloudWatch unavailable"),
        ):
            handle_post_event(_event(), _auth())


class TestDispatchIntegration:
    """Confirm the route is registered on the API Gateway router."""

    def test_route_is_registered(self) -> None:
        from unittest.mock import MagicMock

        from src.handlers.api_gateway_handler import APIGatewayHandler

        with patch("src.handlers.api_gateway_handler.boto3") as mock_boto:
            mock_boto.client.return_value = MagicMock()
            import os as os_module

            original_queue = os_module.environ.get("ANALYSIS_QUEUE_URL")
            os_module.environ["ANALYSIS_QUEUE_URL"] = "http://queue"
            try:
                storage = MagicMock()
                handler = APIGatewayHandler(storage)
            finally:
                if original_queue is None:
                    del os_module.environ["ANALYSIS_QUEUE_URL"]
                else:
                    os_module.environ["ANALYSIS_QUEUE_URL"] = original_queue

        result = handler._router.dispatch("POST", "/api/analytics/events")
        assert result is not None
        _handler_fn, path_params, authenticated = result
        assert path_params == {}
        assert authenticated is True

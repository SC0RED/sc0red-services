"""Tests for Cognito CustomMessage Lambda trigger — branded invitation emails."""

from unittest.mock import patch

from src.handlers.cognito_custom_message import handle_custom_message


def _make_event(trigger_source: str, email: str = "test@example.com", code: str = "Abc123!x") -> dict:
    return {
        "triggerSource": trigger_source,
        "request": {
            "usernameParameter": email,
            "codeParameter": code,
        },
        "response": {},
    }


class TestCustomMessageAdminCreateUser:
    def test_sets_branded_email_subject(self):
        event = _make_event("CustomMessage_AdminCreateUser")
        with patch.dict("os.environ", {"FRONTEND_DOMAIN": "https://app.janus.ai"}):
            result = handle_custom_message(event, None)

        assert result["response"]["emailSubject"] == "You've been invited to sc0red Services"

    def test_email_contains_accept_link(self):
        event = _make_event("CustomMessage_AdminCreateUser", email="analyst@firm.com")
        with patch.dict("os.environ", {"FRONTEND_DOMAIN": "https://app.janus.ai"}):
            result = handle_custom_message(event, None)

        body = result["response"]["emailMessage"]
        assert "https://app.janus.ai/accept-invite?email=analyst@firm.com" in body

    def test_email_contains_temporary_password(self):
        event = _make_event("CustomMessage_AdminCreateUser", code="TempPass1!")
        with patch.dict("os.environ", {"FRONTEND_DOMAIN": "https://app.janus.ai"}):
            result = handle_custom_message(event, None)

        body = result["response"]["emailMessage"]
        assert "TempPass1!" in body

    def test_email_contains_branding(self):
        event = _make_event("CustomMessage_AdminCreateUser")
        with patch.dict("os.environ", {"FRONTEND_DOMAIN": "https://app.janus.ai"}):
            result = handle_custom_message(event, None)

        body = result["response"]["emailMessage"]
        assert "sc0red Services" in body
        assert "AI Risk &amp; Strategic Intelligence" in body
        assert "Accept Invitation" in body

    def test_email_is_html(self):
        event = _make_event("CustomMessage_AdminCreateUser")
        with patch.dict("os.environ", {"FRONTEND_DOMAIN": "https://app.janus.ai"}):
            result = handle_custom_message(event, None)

        body = result["response"]["emailMessage"]
        assert "<!DOCTYPE html>" in body


class TestOtherTriggerSources:
    def test_verification_returns_unchanged(self):
        event = _make_event("CustomMessage_SignUp")
        result = handle_custom_message(event, None)

        assert "emailMessage" not in result["response"]

    def test_forgot_password_returns_unchanged(self):
        event = _make_event("CustomMessage_ForgotPassword")
        result = handle_custom_message(event, None)

        assert "emailMessage" not in result["response"]

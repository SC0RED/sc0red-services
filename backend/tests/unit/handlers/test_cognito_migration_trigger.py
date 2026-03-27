"""Tests for Cognito User Migration Lambda trigger."""

from unittest.mock import MagicMock

import bcrypt
import pytest

from src.handlers.cognito_migration_trigger import (
    InvalidCredentialsError,
    UserNotFoundError,
    handle_migration,
)


def _make_user(
    email: str = "test@example.com",
    password: str = "Test1234",
    name: str = "Test User",
    org_id: str = "org-123",
    user_id: str = "user-456",
    role: str = "admin",
) -> dict:
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt(10)).decode()
    return {
        "id": user_id,
        "email": email,
        "name": name,
        "org_id": org_id,
        "role": role,
        "password_hash": password_hash,
    }


def _make_auth_event(email: str = "test@example.com", password: str = "Test1234") -> dict:
    return {
        "triggerSource": "UserMigration_Authentication",
        "userName": email,
        "request": {"password": password},
        "response": {},
    }


def _make_forgot_event(email: str = "test@example.com") -> dict:
    return {
        "triggerSource": "UserMigration_ForgotPassword",
        "userName": email,
        "request": {},
        "response": {},
    }


class TestMigrationAuthentication:
    def test_successful_migration(self):
        user = _make_user()
        user_repo = MagicMock()
        user_repo.find_by_email.return_value = user

        event = _make_auth_event()
        result = handle_migration(event, user_repo)

        attrs = result["response"]["userAttributes"]
        assert attrs["email"] == "test@example.com"
        assert attrs["email_verified"] == "true"
        assert attrs["name"] == "Test User"
        assert attrs["custom:org_id"] == "org-123"
        assert attrs["custom:role"] == "admin"
        assert attrs["custom:legacy_user_id"] == "user-456"
        assert result["response"]["finalUserStatus"] == "CONFIRMED"
        assert result["response"]["messageAction"] == "SUPPRESS"

    def test_wrong_password_raises(self):
        user = _make_user(password="CorrectPassword1")
        user_repo = MagicMock()
        user_repo.find_by_email.return_value = user

        event = _make_auth_event(password="WrongPassword1")

        with pytest.raises(InvalidCredentialsError):
            handle_migration(event, user_repo)

    def test_user_not_found_raises(self):
        user_repo = MagicMock()
        user_repo.find_by_email.return_value = None

        event = _make_auth_event(email="unknown@example.com")

        with pytest.raises(UserNotFoundError, match="unknown@example.com"):
            handle_migration(event, user_repo)

    def test_missing_password_hash_raises(self):
        user = _make_user()
        del user["password_hash"]
        user_repo = MagicMock()
        user_repo.find_by_email.return_value = user

        event = _make_auth_event()

        with pytest.raises(InvalidCredentialsError):
            handle_migration(event, user_repo)

    def test_analyst_role_migrated(self):
        user = _make_user(role="analyst")
        user_repo = MagicMock()
        user_repo.find_by_email.return_value = user

        event = _make_auth_event()
        result = handle_migration(event, user_repo)

        assert result["response"]["userAttributes"]["custom:role"] == "analyst"


class TestMigrationForgotPassword:
    def test_successful_forgot_password(self):
        user = _make_user()
        user_repo = MagicMock()
        user_repo.find_by_email.return_value = user

        event = _make_forgot_event()
        result = handle_migration(event, user_repo)

        attrs = result["response"]["userAttributes"]
        assert attrs["email"] == "test@example.com"
        assert attrs["email_verified"] == "true"
        assert attrs["custom:org_id"] == "org-123"
        assert attrs["custom:legacy_user_id"] == "user-456"
        assert result["response"]["messageAction"] == "SUPPRESS"
        # Should NOT have finalUserStatus for forgot-password
        assert "finalUserStatus" not in result["response"]

    def test_unknown_user_forgot_password_raises(self):
        user_repo = MagicMock()
        user_repo.find_by_email.return_value = None

        event = _make_forgot_event(email="unknown@example.com")

        with pytest.raises(UserNotFoundError):
            handle_migration(event, user_repo)


class TestUnsupportedTrigger:
    def test_unsupported_trigger_raises(self):
        user_repo = MagicMock()
        user_repo.find_by_email.return_value = _make_user()

        event = {
            "triggerSource": "SomeOtherTrigger",
            "userName": "test@example.com",
            "request": {},
            "response": {},
        }

        with pytest.raises(ValueError, match="Unsupported trigger source"):
            handle_migration(event, user_repo)

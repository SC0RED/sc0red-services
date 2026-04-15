"""Tests for MCP auth context (contextvars-based user identity)."""

import pytest

from src.mcp.auth_context import (
    AuthenticatedUser,
    clear_authenticated_user,
    get_authenticated_user,
    set_authenticated_user,
)


def _make_user(**overrides):
    defaults = {
        "user_id": "u1",
        "org_id": "o1",
        "email": "test@test.com",
        "role": "admin",
        "client_id": "c1",
        "scopes": ["read", "write"],
    }
    defaults.update(overrides)
    return AuthenticatedUser(**defaults)


class TestSetAndGetAuthenticatedUser:
    def test_set_and_get(self):
        user = _make_user()
        set_authenticated_user(user)
        result = get_authenticated_user()
        assert result.user_id == "u1"
        assert result.org_id == "o1"
        assert result.email == "test@test.com"
        assert result.role == "admin"

    def test_raises_when_not_set(self):
        clear_authenticated_user()
        with pytest.raises(RuntimeError, match="No authenticated user"):
            get_authenticated_user()

    def test_clear_resets(self):
        set_authenticated_user(_make_user())
        clear_authenticated_user()
        with pytest.raises(RuntimeError):
            get_authenticated_user()

    def test_overwrite(self):
        set_authenticated_user(_make_user(user_id="first"))
        set_authenticated_user(_make_user(user_id="second"))
        assert get_authenticated_user().user_id == "second"


class TestAuthenticatedUserImmutable:
    def test_frozen(self):
        user = _make_user()
        with pytest.raises(AttributeError):
            user.user_id = "changed"

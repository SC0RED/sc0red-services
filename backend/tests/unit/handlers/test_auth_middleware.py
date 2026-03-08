"""Tests for authentication middleware."""

import os
import time
from unittest.mock import patch

import jwt
import pytest

from src.handlers.auth_middleware import AuthContext, require_authentication, validate_token


class TestValidateToken:
    @patch.dict(os.environ, {"NEXTAUTH_SECRET": "test-secret-key"})
    def test_valid_token(self):
        payload = {
            "id": "user-1",
            "orgId": "org-1",
            "email": "test@example.com",
            "role": "admin",
            "name": "Test User",
        }
        token = jwt.encode(payload, "test-secret-key", algorithm="HS256")

        context = validate_token(f"Bearer {token}")

        assert isinstance(context, AuthContext)
        assert context.user_id == "user-1"
        assert context.org_id == "org-1"
        assert context.email == "test@example.com"
        assert context.role == "admin"
        assert context.name == "Test User"

    @patch.dict(os.environ, {"NEXTAUTH_SECRET": "test-secret-key"})
    def test_token_with_sub_field(self):
        payload = {"sub": "user-2", "orgId": "org-2"}
        token = jwt.encode(payload, "test-secret-key", algorithm="HS256")

        context = validate_token(f"Bearer {token}")
        assert context.user_id == "user-2"

    @patch.dict(os.environ, {"NEXTAUTH_SECRET": "test-secret-key"})
    def test_token_missing_org_id_raises(self):
        payload = {"id": "user-1"}  # no orgId
        token = jwt.encode(payload, "test-secret-key", algorithm="HS256")

        with pytest.raises(ValueError, match="missing required claims"):
            validate_token(f"Bearer {token}")

    @patch.dict(os.environ, {"NEXTAUTH_SECRET": "test-secret-key"})
    def test_token_missing_user_id_raises(self):
        payload = {"orgId": "org-1"}  # no id or sub
        token = jwt.encode(payload, "test-secret-key", algorithm="HS256")

        with pytest.raises(ValueError, match="missing required claims"):
            validate_token(f"Bearer {token}")

    def test_missing_bearer_prefix(self):
        with pytest.raises(ValueError, match="Missing"):
            validate_token("just-a-token")

    def test_empty_authorization(self):
        with pytest.raises(ValueError, match="Missing"):
            validate_token("")

    @patch.dict(os.environ, {"NEXTAUTH_SECRET": "test-secret-key"})
    def test_invalid_token(self):
        with pytest.raises(ValueError, match="Invalid"):
            validate_token("Bearer invalid.token.here")

    @patch.dict(os.environ, {"NEXTAUTH_SECRET": "correct-key"})
    def test_wrong_secret(self):
        token = jwt.encode({"id": "user-1"}, "wrong-key", algorithm="HS256")
        with pytest.raises(ValueError, match="Invalid"):
            validate_token(f"Bearer {token}")


class TestRequireAuth:
    @patch.dict(os.environ, {"NEXTAUTH_SECRET": "test-key"})
    def test_extracts_from_headers(self):
        payload = {"id": "user-1", "orgId": "org-1"}
        token = jwt.encode(payload, "test-key", algorithm="HS256")

        context = require_authentication({"Authorization": f"Bearer {token}"})
        assert context.user_id == "user-1"

    @patch.dict(os.environ, {"NEXTAUTH_SECRET": "test-key"})
    def test_case_insensitive_header(self):
        payload = {"id": "user-1", "orgId": "org-1"}
        token = jwt.encode(payload, "test-key", algorithm="HS256")

        context = require_authentication({"authorization": f"Bearer {token}"})
        assert context.user_id == "user-1"

    def test_missing_authentication_header(self):
        with pytest.raises(ValueError, match="Missing"):
            require_authentication({})

    @patch.dict(os.environ, {}, clear=True)
    def test_no_secret_configured(self):
        with pytest.raises(ValueError, match="NEXTAUTH_SECRET"):
            validate_token("Bearer some.token.here")

    @patch.dict(os.environ, {"NEXTAUTH_SECRET": "test-secret-key-long-enough"})
    def test_expired_token(self):
        payload = {"id": "user-1", "exp": int(time.time()) - 3600}
        token = jwt.encode(payload, "test-secret-key-long-enough", algorithm="HS256")
        with pytest.raises(ValueError, match="expired"):
            validate_token(f"Bearer {token}")

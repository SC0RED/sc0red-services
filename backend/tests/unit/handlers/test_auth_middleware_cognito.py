"""Tests for dual Cognito RS256 / legacy HS256 auth middleware."""

from unittest.mock import MagicMock, patch

import jwt as pyjwt
import pytest

from src.handlers.auth_middleware import AuthContext, validate_token


class TestLegacyHS256Validation:
    """HS256 path — existing behavior, must not regress."""

    def test_valid_legacy_token(self):
        secret = "test-secret-minimum-32-characters"
        token = pyjwt.encode(
            {"id": "user-1", "orgId": "org-1", "email": "a@b.com", "role": "admin"},
            secret,
            algorithm="HS256",
        )
        with patch.dict("os.environ", {"NEXTAUTH_SECRET": secret, "COGNITO_USER_POOL_ID": ""}):
            result = validate_token(f"Bearer {token}")

        assert result.user_id == "user-1"
        assert result.org_id == "org-1"
        assert result.email == "a@b.com"
        assert result.role == "admin"

    def test_missing_bearer_prefix_raises(self):
        with pytest.raises(ValueError, match="Missing or invalid"):
            validate_token("not-a-bearer-token")

    def test_empty_authorization_raises(self):
        with pytest.raises(ValueError, match="Missing or invalid"):
            validate_token("")

    def test_expired_legacy_token_raises(self):
        import time

        secret = "test-secret-minimum-32-characters"
        token = pyjwt.encode(
            {"id": "u", "orgId": "o", "exp": int(time.time()) - 100},
            secret,
            algorithm="HS256",
        )
        with patch.dict("os.environ", {"NEXTAUTH_SECRET": secret, "COGNITO_USER_POOL_ID": ""}):
            with pytest.raises(ValueError, match="Token expired"):
                validate_token(f"Bearer {token}")

    def test_missing_org_id_raises(self):
        secret = "test-secret-minimum-32-characters"
        token = pyjwt.encode({"id": "user-1"}, secret, algorithm="HS256")
        with patch.dict("os.environ", {"NEXTAUTH_SECRET": secret, "COGNITO_USER_POOL_ID": ""}):
            with pytest.raises(ValueError, match="missing required claims"):
                validate_token(f"Bearer {token}")

    def test_sub_claim_used_when_id_missing(self):
        secret = "test-secret-minimum-32-characters"
        token = pyjwt.encode(
            {"sub": "user-sub", "orgId": "org-1"},
            secret,
            algorithm="HS256",
        )
        with patch.dict("os.environ", {"NEXTAUTH_SECRET": secret, "COGNITO_USER_POOL_ID": ""}):
            result = validate_token(f"Bearer {token}")
        assert result.user_id == "user-sub"


class TestCognitoRS256Validation:
    """RS256 path — Cognito tokens."""

    def test_rs256_token_skipped_when_cognito_not_configured(self):
        """When COGNITO_USER_POOL_ID is empty, RS256 path is skipped entirely."""
        secret = "test-secret-minimum-32-characters"
        token = pyjwt.encode(
            {"id": "user-1", "orgId": "org-1"},
            secret,
            algorithm="HS256",
        )
        with patch.dict(
            "os.environ",
            {"NEXTAUTH_SECRET": secret, "COGNITO_USER_POOL_ID": "", "COGNITO_REGION": ""},
        ):
            # Reset cached JWKS client
            import src.handlers.auth_middleware as mod

            mod._jwks_client = None

            result = validate_token(f"Bearer {token}")
            assert result.user_id == "user-1"

    def test_hs256_token_falls_through_when_cognito_configured(self):
        """HS256 tokens should still work when Cognito is configured but token is not RS256."""
        secret = "test-secret-minimum-32-characters"
        token = pyjwt.encode(
            {"id": "user-1", "orgId": "org-1", "email": "a@b.com"},
            secret,
            algorithm="HS256",
        )
        with patch.dict(
            "os.environ",
            {
                "NEXTAUTH_SECRET": secret,
                "COGNITO_USER_POOL_ID": "us-east-1_FAKE",
                "COGNITO_REGION": "us-east-1",
                "COGNITO_CLIENT_ID": "fakeclientid",
            },
        ):
            import src.handlers.auth_middleware as mod

            mod._jwks_client = None

            # Mock the JWKS client to avoid real HTTP call
            mock_jwks = MagicMock()
            with patch.object(mod, "_get_jwks_client", return_value=mock_jwks):
                result = validate_token(f"Bearer {token}")

            assert result.user_id == "user-1"
            assert result.org_id == "org-1"

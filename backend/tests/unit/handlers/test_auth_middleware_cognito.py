"""Tests for Cognito RS256 auth middleware (Phase 5 — HS256 removed)."""

from unittest.mock import MagicMock, patch

import jwt as pyjwt
import pytest

from src.handlers.auth_middleware import validate_token


class TestValidateToken:
    def test_missing_bearer_prefix_raises(self):
        with pytest.raises(ValueError, match="Missing or invalid"):
            validate_token("not-a-bearer-token")

    def test_empty_authorization_raises(self):
        with pytest.raises(ValueError, match="Missing or invalid"):
            validate_token("")

    def test_cognito_not_configured_raises(self):
        """Without Cognito env vars, validation fails — no HS256 fallback."""
        import src.handlers.auth_middleware as module

        module._jwks_client = None

        token = pyjwt.encode({"sub": "user-1"}, "secret", algorithm="HS256")
        with patch.dict("os.environ", {"COGNITO_USER_POOL_ID": "", "COGNITO_REGION": ""}):
            with pytest.raises(ValueError, match="COGNITO_REGION and COGNITO_USER_POOL_ID"):
                validate_token(f"Bearer {token}")

    def test_hs256_token_rejected_when_cognito_configured(self):
        """HS256 tokens are no longer accepted — only RS256."""
        import src.handlers.auth_middleware as module

        module._jwks_client = None

        token = pyjwt.encode(
            {"id": "user-1", "orgId": "org-1"},
            "secret",
            algorithm="HS256",
        )
        with patch.dict(
            "os.environ",
            {
                "COGNITO_USER_POOL_ID": "us-east-1_FAKE",
                "COGNITO_REGION": "us-east-1",
                "COGNITO_CLIENT_ID": "fakeclientid",
            },
        ):
            mock_jwks = MagicMock()
            mock_jwks.get_signing_key_from_jwt.side_effect = pyjwt.InvalidTokenError("bad")
            with patch.object(module, "_get_jwks_client", return_value=mock_jwks):
                with pytest.raises(ValueError, match="Invalid token"):
                    validate_token(f"Bearer {token}")


class TestRequireAuthentication:
    def test_extracts_from_headers(self):
        from src.handlers.auth_middleware import require_authentication

        with pytest.raises(ValueError, match="Missing or invalid"):
            require_authentication({})

    def test_case_insensitive_header(self):
        from src.handlers.auth_middleware import require_authentication

        with pytest.raises(ValueError):
            require_authentication({"authorization": "Bearer bad-token"})

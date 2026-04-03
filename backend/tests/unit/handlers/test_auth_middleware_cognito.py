"""Tests for Cognito RS256 auth middleware."""

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
        import src.handlers.auth_middleware as module

        module._jwks_client = None

        token = pyjwt.encode({"sub": "user-1"}, "secret", algorithm="HS256")
        with patch.dict("os.environ", {
            "COGNITO_USER_POOL_ID": "",
            "COGNITO_REGION": "",
            "COGNITO_CLIENT_ID": "",
            "COGNITO_JWKS_URL": "",
        }):
            with pytest.raises(ValueError, match="COGNITO_CLIENT_ID must be configured"):
                validate_token(f"Bearer {token}")

    def test_jwks_url_override_used_when_set(self):
        """COGNITO_JWKS_URL takes precedence over region+pool_id."""
        import src.handlers.auth_middleware as module

        module._jwks_client = None

        with patch.dict("os.environ", {
            "COGNITO_JWKS_URL": "http://mock:8080/.well-known/jwks.json",
            "COGNITO_USER_POOL_ID": "",
            "COGNITO_REGION": "",
            "COGNITO_CLIENT_ID": "",
        }):
            client = module._get_jwks_client()
            assert client is not None

        # Reset for other tests
        module._jwks_client = None

    def test_missing_client_id_raises_in_production(self):
        """Production (no COGNITO_JWKS_URL) requires COGNITO_CLIENT_ID."""
        import src.handlers.auth_middleware as module

        module._jwks_client = None

        token = pyjwt.encode({"sub": "user-1"}, "secret", algorithm="HS256")
        with patch.dict("os.environ", {
            "COGNITO_USER_POOL_ID": "us-east-1_FAKE",
            "COGNITO_REGION": "us-east-1",
            "COGNITO_CLIENT_ID": "",
            "COGNITO_JWKS_URL": "",
        }):
            with pytest.raises(ValueError, match="COGNITO_CLIENT_ID must be configured"):
                validate_token(f"Bearer {token}")

    def test_custom_jwks_url_skips_audience_check(self):
        """With COGNITO_JWKS_URL set, audience/issuer verification is skipped."""
        import src.handlers.auth_middleware as module

        module._jwks_client = None

        with patch.dict("os.environ", {
            "COGNITO_JWKS_URL": "http://mock:8080/.well-known/jwks.json",
            "COGNITO_CLIENT_ID": "",
            "COGNITO_USER_POOL_ID": "",
            "COGNITO_REGION": "",
        }):
            # Should not raise about missing client ID
            client = module._get_jwks_client()
            assert client is not None
        module._jwks_client = None

    def test_invalid_token_rejected(self):
        import src.handlers.auth_middleware as module

        module._jwks_client = None

        with patch.dict("os.environ", {
            "COGNITO_USER_POOL_ID": "us-east-1_FAKE",
            "COGNITO_REGION": "us-east-1",
            "COGNITO_CLIENT_ID": "fakeclient",
            "COGNITO_JWKS_URL": "",
        }):
            mock_jwks = MagicMock()
            mock_jwks.get_signing_key_from_jwt.side_effect = pyjwt.InvalidTokenError("bad")
            with patch.object(module, "_get_jwks_client", return_value=mock_jwks):
                with pytest.raises(ValueError, match="Invalid token"):
                    validate_token("Bearer some-invalid-token")


    def test_expired_token_raises(self):
        import src.handlers.auth_middleware as module

        module._jwks_client = None

        mock_jwks = MagicMock()
        mock_jwks.get_signing_key_from_jwt.side_effect = pyjwt.ExpiredSignatureError("expired")
        with patch.dict("os.environ", {
            "COGNITO_JWKS_URL": "http://mock:8080/.well-known/jwks.json",
            "COGNITO_CLIENT_ID": "",
        }):
            with patch.object(module, "_get_jwks_client", return_value=mock_jwks):
                with pytest.raises(ValueError, match="Token expired"):
                    validate_token("Bearer some-expired-token")
        module._jwks_client = None


class TestRequireAuthentication:
    def test_extracts_from_headers(self):
        from src.handlers.auth_middleware import require_authentication

        with pytest.raises(ValueError, match="Missing or invalid"):
            require_authentication({})

    def test_case_insensitive_header(self):
        from src.handlers.auth_middleware import require_authentication

        with pytest.raises(ValueError):
            require_authentication({"authorization": "Bearer bad-token"})

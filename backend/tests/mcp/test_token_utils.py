"""Tests for MCP OAuth token utilities."""

import time

import jwt
import pytest

from src.mcp.token_utils import (
    generate_authorization_code,
    generate_refresh_token,
    generate_rsa_key_pair,
    hash_token,
    create_signed_access_token,
    is_valid_pkce,
    verify_access_token,
)


@pytest.fixture()
def rsa_keys():
    private_pem, public_pem = generate_rsa_key_pair()
    return private_pem, public_pem


class TestGenerateRSAKeyPair:
    def test_returns_pem_strings(self):
        private_pem, public_pem = generate_rsa_key_pair()
        assert private_pem.startswith("-----BEGIN PRIVATE KEY-----")
        assert public_pem.startswith("-----BEGIN PUBLIC KEY-----")

    def test_keys_are_different_each_call(self):
        pair_a = generate_rsa_key_pair()
        pair_b = generate_rsa_key_pair()
        assert pair_a[0] != pair_b[0]


class TestSignAndVerifyAccessToken:
    def test_sign_and_verify_roundtrip(self, rsa_keys):
        private_pem, public_pem = rsa_keys
        token = create_signed_access_token(
            private_key_pem=private_pem,
            user_id="user-123",
            email="test@example.com",
            org_id="org-456",
            role="admin",
            client_id="client-789",
            scopes=["read", "write"],
            issuer="https://mcp.example.com",
        )
        payload = verify_access_token(token, public_key_pem=public_pem, issuer="https://mcp.example.com")
        assert payload["sub"] == "user-123"
        assert payload["email"] == "test@example.com"
        assert payload["org_id"] == "org-456"
        assert payload["role"] == "admin"
        assert payload["client_id"] == "client-789"
        assert payload["scope"] == "read write"

    def test_expired_token_raises(self, rsa_keys):
        private_pem, public_pem = rsa_keys
        token = create_signed_access_token(
            private_key_pem=private_pem,
            user_id="user-123",
            email="test@example.com",
            org_id="org-456",
            role="admin",
            client_id="client-789",
            scopes=["read"],
            issuer="https://mcp.example.com",
            expires_in_seconds=-10,
        )
        with pytest.raises(jwt.ExpiredSignatureError):
            verify_access_token(token, public_key_pem=public_pem, issuer="https://mcp.example.com")

    def test_wrong_issuer_raises(self, rsa_keys):
        private_pem, public_pem = rsa_keys
        token = create_signed_access_token(
            private_key_pem=private_pem,
            user_id="user-123",
            email="test@example.com",
            org_id="org-456",
            role="admin",
            client_id="client-789",
            scopes=["read"],
            issuer="https://mcp.example.com",
        )
        with pytest.raises(jwt.InvalidIssuerError):
            verify_access_token(token, public_key_pem=public_pem, issuer="https://wrong.com")

    def test_wrong_key_raises(self, rsa_keys):
        private_pem, _ = rsa_keys
        _, other_public = generate_rsa_key_pair()
        token = create_signed_access_token(
            private_key_pem=private_pem,
            user_id="user-123",
            email="test@example.com",
            org_id="org-456",
            role="admin",
            client_id="client-789",
            scopes=["read"],
            issuer="https://mcp.example.com",
        )
        with pytest.raises(jwt.InvalidSignatureError):
            verify_access_token(token, public_key_pem=other_public, issuer="https://mcp.example.com")

    def test_custom_expiry(self, rsa_keys):
        private_pem, public_pem = rsa_keys
        token = create_signed_access_token(
            private_key_pem=private_pem,
            user_id="u1",
            email="t@t.com",
            org_id="o1",
            role="admin",
            client_id="c1",
            scopes=["read"],
            issuer="https://mcp.example.com",
            expires_in_seconds=7200,
        )
        payload = verify_access_token(token, public_key_pem=public_pem, issuer="https://mcp.example.com")
        assert payload["exp"] - payload["iat"] == 7200


class TestGenerateAuthorizationCode:
    def test_returns_string(self):
        code = generate_authorization_code()
        assert isinstance(code, str)
        assert len(code) > 20

    def test_unique_each_call(self):
        codes = {generate_authorization_code() for _ in range(100)}
        assert len(codes) == 100


class TestGenerateRefreshToken:
    def test_returns_string(self):
        token = generate_refresh_token()
        assert isinstance(token, str)
        assert len(token) > 30

    def test_unique_each_call(self):
        tokens = {generate_refresh_token() for _ in range(100)}
        assert len(tokens) == 100


class TestValidatePKCE:
    def test_valid_challenge(self):
        import hashlib
        from base64 import urlsafe_b64encode

        verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        challenge = urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
        assert is_valid_pkce(verifier, challenge) is True

    def test_invalid_challenge(self):
        assert is_valid_pkce("correct-verifier", "wrong-challenge") is False

    def test_empty_strings(self):
        assert is_valid_pkce("", "") is False


class TestHashToken:
    def test_deterministic(self):
        assert hash_token("abc123") == hash_token("abc123")

    def test_different_inputs_different_hashes(self):
        assert hash_token("abc") != hash_token("def")

    def test_returns_64_chars(self):
        assert len(hash_token("test")) == 64

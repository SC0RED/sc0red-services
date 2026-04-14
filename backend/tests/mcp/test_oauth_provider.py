"""Tests for MCP OAuth provider."""

import os

import boto3
import pytest
from moto import mock_aws

from src.mcp.oauth_provider import (
    JanusOAuthProvider,
    StoredAuthorizationCode,
    StoredRefreshToken,
)
from src.mcp.oauth_repository import OAuthRepository
from src.mcp.token_utils import generate_rsa_key_pair

from mcp.server.auth.provider import AuthorizationParams
from mcp.shared.auth import OAuthClientInformationFull


@pytest.fixture(autouse=True)
def _aws_credentials():
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"  # noqa: S105
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"


@pytest.fixture
def rsa_keys():
    return generate_rsa_key_pair()


@pytest.fixture
def provider(rsa_keys):
    private_pem, public_pem = rsa_keys
    with mock_aws():
        client = boto3.client("dynamodb", region_name="us-east-1")
        client.create_table(
            TableName="janus-test",
            KeySchema=[
                {"AttributeName": "pk", "KeyType": "HASH"},
                {"AttributeName": "sk", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "pk", "AttributeType": "S"},
                {"AttributeName": "sk", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        repo = OAuthRepository("janus-test")
        yield JanusOAuthProvider(
            repository=repo,
            private_key_pem=private_pem,
            public_key_pem=public_pem,
            issuer_url="https://mcp.test.janus.sc0red.com",
            consent_base_url="https://test.janus.sc0red.com",
        )


def _make_client_info(client_id="test-client"):
    return OAuthClientInformationFull(
        client_id=client_id,
        client_name="Test App",
        redirect_uris=["http://localhost:12345/callback"],
        grant_types=["authorization_code", "refresh_token"],
        response_types=["code"],
        token_endpoint_auth_method="none",
    )


class TestGetClient:
    @pytest.mark.asyncio
    async def test_returns_none_for_unknown(self, provider):
        result = await provider.get_client("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_registered_client(self, provider):
        client_info = _make_client_info("my-client")
        await provider.register_client(client_info)
        result = await provider.get_client("my-client")
        assert result is not None
        assert result.client_name == "Test App"


class TestRegisterClient:
    @pytest.mark.asyncio
    async def test_generates_client_id_if_missing(self, provider):
        info = OAuthClientInformationFull(
            client_name="New App",
            redirect_uris=["http://localhost:1234"],
            grant_types=["authorization_code"],
            response_types=["code"],
            token_endpoint_auth_method="none",
        )
        await provider.register_client(info)
        assert info.client_id is not None
        assert info.client_id.startswith("dyn_")

    @pytest.mark.asyncio
    async def test_preserves_provided_client_id(self, provider):
        info = _make_client_info("explicit-id")
        await provider.register_client(info)
        result = await provider.get_client("explicit-id")
        assert result is not None


class TestAuthorize:
    @pytest.mark.asyncio
    async def test_returns_consent_url(self, provider):
        client = _make_client_info()
        params = AuthorizationParams(
            state="random-state",
            scopes=["read", "write"],
            code_challenge="test-challenge",
            redirect_uri="http://localhost:12345/callback",
            redirect_uri_provided_explicitly=True,
        )
        url = await provider.authorize(client, params)
        assert url.startswith("https://test.janus.sc0red.com/oauth/authorize?")
        assert "client_id=test-client" in url
        assert "state=random-state" in url
        assert "code_challenge=test-challenge" in url


class TestExchangeAuthorizationCode:
    @pytest.mark.asyncio
    async def test_issues_tokens(self, provider):
        client = _make_client_info()
        code = StoredAuthorizationCode(
            code="test-code",
            client_id="test-client",
            user_id="user-123",
            org_id="org-456",
            email="test@test.com",
            role="admin",
            code_challenge="challenge",
            redirect_uri="http://localhost:12345/callback",
            redirect_uri_provided_explicitly=True,
            scopes=["read", "write"],
        )
        # Save the code first so delete doesn't fail
        provider._repository.save_authorization_code(
            "test-code", client_id="test-client", user_id="user-123",
            org_id="org-456", email="test@test.com", role="admin",
            code_challenge="challenge", redirect_uri="http://localhost:12345/callback",
            scopes=["read", "write"],
        )
        token = await provider.exchange_authorization_code(client, code)
        assert token.access_token
        assert token.refresh_token
        assert token.token_type == "Bearer"
        assert token.expires_in == 3600

    @pytest.mark.asyncio
    async def test_deletes_code_after_exchange(self, provider):
        client = _make_client_info()
        provider._repository.save_authorization_code(
            "one-time-code", client_id="test-client", user_id="u1",
            org_id="o1", email="t@t.com", role="admin",
            code_challenge="ch", redirect_uri="http://localhost",
            scopes=["read"],
        )
        code = StoredAuthorizationCode(
            code="one-time-code", client_id="test-client", user_id="u1",
            org_id="o1", email="t@t.com", role="admin",
            code_challenge="ch", redirect_uri="http://localhost",
            redirect_uri_provided_explicitly=True,
            scopes=["read"],
        )
        await provider.exchange_authorization_code(client, code)
        assert provider._repository.get_authorization_code("one-time-code") is None


class TestLoadAndExchangeRefreshToken:
    @pytest.mark.asyncio
    async def test_load_refresh_token(self, provider):
        from src.mcp.token_utils import hash_token
        provider._repository.save_refresh_token(
            hash_token("refresh-abc"), user_id="u1", org_id="o1",
            email="t@t.com", role="admin", client_id="test-client",
            scopes=["read"],
        )
        client = _make_client_info()
        result = await provider.load_refresh_token(client, "refresh-abc")
        assert result is not None
        assert result.user_id == "u1"

    @pytest.mark.asyncio
    async def test_exchange_refresh_rotates_tokens(self, provider):
        from src.mcp.token_utils import hash_token
        provider._repository.save_refresh_token(
            hash_token("old-refresh"), user_id="u1", org_id="o1",
            email="t@t.com", role="admin", client_id="test-client",
            scopes=["read", "write"],
        )
        stored = StoredRefreshToken(
            token_hash=hash_token("old-refresh"), user_id="u1", org_id="o1",
            email="t@t.com", role="admin", client_id="test-client",
            scopes=["read", "write"],
        )
        client = _make_client_info()
        token = await provider.exchange_refresh_token(client, stored, [])
        assert token.access_token
        assert token.refresh_token
        # Old refresh token should be deleted
        assert provider._repository.get_refresh_token(hash_token("old-refresh")) is None


class TestLoadAuthorizationCode:
    @pytest.mark.asyncio
    async def test_returns_none_for_wrong_client(self, provider):
        provider._repository.save_authorization_code(
            "code-for-other", client_id="other-client", user_id="u1",
            org_id="o1", email="t@t.com", role="admin",
            code_challenge="ch", redirect_uri="http://localhost",
            scopes=["read"],
        )
        client = _make_client_info("test-client")
        result = await provider.load_authorization_code(client, "code-for-other")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_for_unknown_code(self, provider):
        client = _make_client_info()
        result = await provider.load_authorization_code(client, "nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_code_for_matching_client(self, provider):
        provider._repository.save_authorization_code(
            "valid-code", client_id="test-client", user_id="u1",
            org_id="o1", email="t@t.com", role="admin",
            code_challenge="ch", redirect_uri="http://localhost",
            scopes=["read"],
        )
        client = _make_client_info("test-client")
        result = await provider.load_authorization_code(client, "valid-code")
        assert result is not None
        assert result.user_id == "u1"


class TestExchangeRefreshTokenScopes:
    @pytest.mark.asyncio
    async def test_uses_provided_scopes_when_given(self, provider):
        from src.mcp.token_utils import hash_token
        provider._repository.save_refresh_token(
            hash_token("scoped-ref"), user_id="u1", org_id="o1",
            email="t@t.com", role="admin", client_id="test-client",
            scopes=["read", "write"],
        )
        stored = StoredRefreshToken(
            token_hash=hash_token("scoped-ref"), user_id="u1", org_id="o1",
            email="t@t.com", role="admin", client_id="test-client",
            scopes=["read", "write"],
        )
        client = _make_client_info()
        token = await provider.exchange_refresh_token(client, stored, ["read"])
        assert token.scope == "read"


class TestLoadAccessToken:
    @pytest.mark.asyncio
    async def test_valid_token(self, provider):
        from src.mcp.token_utils import hash_token, sign_access_token
        access_token = sign_access_token(
            private_key_pem=provider._private_key_pem,
            user_id="u1", email="t@t.com", org_id="o1", role="admin",
            client_id="c1", scopes=["read"], issuer="https://mcp.test.janus.sc0red.com",
        )
        provider._repository.save_access_token(
            hash_token(access_token), user_id="u1", org_id="o1",
            client_id="c1", scopes=["read"],
        )
        result = await provider.load_access_token(access_token)
        assert result is not None
        assert result.user_id == "u1"
        assert result.org_id == "o1"

    @pytest.mark.asyncio
    async def test_invalid_token_returns_none(self, provider):
        result = await provider.load_access_token("invalid-garbage-token")
        assert result is None

    @pytest.mark.asyncio
    async def test_valid_jwt_but_not_in_db_returns_none(self, provider):
        from src.mcp.token_utils import sign_access_token
        access_token = sign_access_token(
            private_key_pem=provider._private_key_pem,
            user_id="u1", email="t@t.com", org_id="o1", role="admin",
            client_id="c1", scopes=["read"], issuer="https://mcp.test.janus.sc0red.com",
        )
        # JWT is valid but no record in DynamoDB
        result = await provider.load_access_token(access_token)
        assert result is None


class TestRevokeToken:
    @pytest.mark.asyncio
    async def test_revoke_access_token(self, provider):
        from src.mcp.oauth_provider import StoredAccessToken
        from src.mcp.token_utils import hash_token
        provider._repository.save_access_token(
            "hash-to-revoke", user_id="u1", org_id="o1", client_id="c1", scopes=["read"],
        )
        token = StoredAccessToken(
            token_hash="hash-to-revoke", user_id="u1", org_id="o1",
            client_id="c1", scopes=["read"],
        )
        await provider.revoke_token(token)
        assert provider._repository.get_access_token("hash-to-revoke") is None

    @pytest.mark.asyncio
    async def test_revoke_refresh_token(self, provider):
        provider._repository.save_refresh_token(
            "ref-to-revoke", user_id="u1", org_id="o1", email="t@t.com",
            role="admin", client_id="c1", scopes=["read"],
        )
        token = StoredRefreshToken(
            token_hash="ref-to-revoke", user_id="u1", org_id="o1",
            email="t@t.com", role="admin", client_id="c1", scopes=["read"],
        )
        await provider.revoke_token(token)
        assert provider._repository.get_refresh_token("ref-to-revoke") is None

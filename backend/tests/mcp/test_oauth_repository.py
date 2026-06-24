"""Tests for MCP OAuth DynamoDB repository."""

import os
from unittest.mock import patch

import boto3
import pytest
from moto import mock_aws

from src.mcp.oauth_repository import OAuthRepository


@pytest.fixture(autouse=True)
def _aws_credentials():
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"


@pytest.fixture
def repository():
    with mock_aws():
        client = boto3.client("dynamodb", region_name="us-east-1")
        client.create_table(
            TableName="sc0red-services-test",
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
        yield OAuthRepository("sc0red-services-test")


class TestClientCRUD:
    def test_save_and_get_client(self, repository):
        repository.save_client(
            "client-1", {"client_name": "Test App", "redirect_uris": ["http://localhost"]}
        )
        result = repository.get_client("client-1")
        assert result is not None
        assert result["client_name"] == "Test App"
        assert result["redirect_uris"] == ["http://localhost"]

    def test_get_nonexistent_client(self, repository):
        assert repository.get_client("nonexistent") is None


class TestAuthorizationCodeCRUD:
    def test_save_and_get_code(self, repository):
        repository.save_authorization_code(
            "code-123",
            client_id="client-1",
            user_id="user-1",
            org_id="org-1",
            email="test@test.com",
            role="admin",
            code_challenge="challenge",
            redirect_uri="http://localhost",
            scopes=["read", "write"],
        )
        result = repository.get_authorization_code("code-123")
        assert result is not None
        assert result["user_id"] == "user-1"
        assert result["code_challenge"] == "challenge"

    def test_get_nonexistent_code(self, repository):
        assert repository.get_authorization_code("nonexistent") is None

    def test_expired_code_returns_none(self, repository):
        repository.save_authorization_code(
            "expired-code",
            client_id="c1",
            user_id="u1",
            org_id="o1",
            email="t@t.com",
            role="admin",
            code_challenge="ch",
            redirect_uri="http://localhost",
            scopes=["read"],
            ttl_seconds=-1,
        )
        assert repository.get_authorization_code("expired-code") is None

    def test_delete_code(self, repository):
        repository.save_authorization_code(
            "delete-me",
            client_id="c1",
            user_id="u1",
            org_id="o1",
            email="t@t.com",
            role="admin",
            code_challenge="ch",
            redirect_uri="http://localhost",
            scopes=["read"],
        )
        repository.delete_authorization_code("delete-me")
        assert repository.get_authorization_code("delete-me") is None


class TestAccessTokenCRUD:
    def test_save_and_get_token(self, repository):
        repository.save_access_token(
            "hash-123",
            user_id="u1",
            org_id="o1",
            client_id="c1",
            scopes=["read"],
        )
        result = repository.get_access_token("hash-123")
        assert result is not None
        assert result["user_id"] == "u1"

    def test_get_nonexistent_token(self, repository):
        assert repository.get_access_token("nonexistent") is None

    def test_delete_token(self, repository):
        repository.save_access_token(
            "del-hash", user_id="u1", org_id="o1", client_id="c1", scopes=["read"]
        )
        repository.delete_access_token("del-hash")
        assert repository.get_access_token("del-hash") is None


class TestRefreshTokenCRUD:
    def test_save_and_get_refresh(self, repository):
        repository.save_refresh_token(
            "ref-hash",
            user_id="u1",
            org_id="o1",
            email="t@t.com",
            role="admin",
            client_id="c1",
            scopes=["read", "write"],
        )
        result = repository.get_refresh_token("ref-hash")
        assert result is not None
        assert result["email"] == "t@t.com"

    def test_get_nonexistent_refresh(self, repository):
        assert repository.get_refresh_token("nonexistent") is None

    def test_delete_refresh(self, repository):
        repository.save_refresh_token(
            "del-ref",
            user_id="u1",
            org_id="o1",
            email="t@t.com",
            role="admin",
            client_id="c1",
            scopes=["read"],
        )
        repository.delete_refresh_token("del-ref")
        assert repository.get_refresh_token("del-ref") is None


class TestConsentCRUD:
    def test_save_and_check_consent(self, repository):
        assert repository.has_consent("user-1", "client-1") is False
        repository.save_consent("user-1", "client-1")
        assert repository.has_consent("user-1", "client-1") is True

    def test_revoke_consent(self, repository):
        repository.save_consent("user-1", "client-1")
        repository.revoke_consent("user-1", "client-1")
        assert repository.has_consent("user-1", "client-1") is False

    def test_list_consents_by_user_returns_only_that_user(self, repository):
        repository.save_consent("user-1", "client-a", "App A")
        repository.save_consent("user-1", "client-b", "App B")
        repository.save_consent("user-2", "client-c", "App C")
        consents = repository.list_consents_by_user("user-1")
        assert len(consents) == 2
        client_ids = {c["sk"].removeprefix("CLIENT#") for c in consents}
        assert client_ids == {"client-a", "client-b"}
        # Name is denormalized on the record (no per-client lookup needed).
        assert {c["client_name"] for c in consents} == {"App A", "App B"}

    def test_list_consents_by_user_empty(self, repository):
        assert repository.list_consents_by_user("nobody") == []

    def test_list_consents_by_user_paginates(self, repository):
        # DynamoDB truncates at 1MB — the loop must follow LastEvaluatedKey.
        page1 = {"Items": [{"sk": "CLIENT#a", "client_name": "A"}], "LastEvaluatedKey": {"pk": "k"}}
        page2 = {"Items": [{"sk": "CLIENT#b", "client_name": "B"}]}
        with patch.object(repository._table, "query", side_effect=[page1, page2]) as query:
            consents = repository.list_consents_by_user("user-1")
        assert query.call_count == 2
        assert {c["sk"] for c in consents} == {"CLIENT#a", "CLIENT#b"}
        # The second page request carried the cursor from the first.
        assert query.call_args_list[1].kwargs["ExclusiveStartKey"] == {"pk": "k"}

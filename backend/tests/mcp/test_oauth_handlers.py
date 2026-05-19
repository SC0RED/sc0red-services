"""Tests for OAuth consent approval handler."""

import json
import os
from unittest.mock import patch

import boto3
import pytest
from moto import mock_aws

from src.mcp.oauth_repository import OAuthRepository


@pytest.fixture(autouse=True)
def _aws_credentials():
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"  # noqa: S105
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
    os.environ["DYNAMODB_TABLE"] = "sc0red-services-test"
    os.environ["ANALYSIS_QUEUE_URL"] = "https://sqs.us-east-1.amazonaws.com/000/test"


class MockAuth:
    user_id = "user-123"
    org_id = "org-456"
    email = "test@test.com"
    role = "admin"
    name = "Test User"


@pytest.fixture
def setup_dynamo():
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
        repo = OAuthRepository("sc0red-services-test")
        repo.save_client("client-1", {
            "client_name": "Test App",
            "redirect_uris": ["http://localhost:12345/callback"],
        })
        with patch("src.handlers.oauth_handlers._repository", repo):
            yield repo


def _make_event(body):
    return {"body": json.dumps(body)}


class TestHandleOAuthApprove:
    def test_success(self, setup_dynamo):
        from src.handlers.oauth_handlers import handle_oauth_approve

        event = _make_event({
            "client_id": "client-1",
            "redirect_uri": "http://localhost:12345/callback",
            "code_challenge": "test-challenge-abc",
            "scope": "read write",
            "state": "random-state",
        })
        result = handle_oauth_approve(event, MockAuth(), None)
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert "redirect_url" in body
        assert "code=" in body["redirect_url"]
        assert "state=random-state" in body["redirect_url"]

    def test_missing_client_id(self, setup_dynamo):
        from src.handlers.oauth_handlers import handle_oauth_approve

        event = _make_event({
            "redirect_uri": "http://localhost:12345/callback",
            "code_challenge": "ch",
        })
        result = handle_oauth_approve(event, MockAuth(), None)
        assert result["statusCode"] == 400

    def test_missing_redirect_uri(self, setup_dynamo):
        from src.handlers.oauth_handlers import handle_oauth_approve

        event = _make_event({
            "client_id": "client-1",
            "code_challenge": "ch",
        })
        result = handle_oauth_approve(event, MockAuth(), None)
        assert result["statusCode"] == 400

    def test_missing_code_challenge(self, setup_dynamo):
        from src.handlers.oauth_handlers import handle_oauth_approve

        event = _make_event({
            "client_id": "client-1",
            "redirect_uri": "http://localhost:12345/callback",
        })
        result = handle_oauth_approve(event, MockAuth(), None)
        assert result["statusCode"] == 400

    def test_unknown_client(self, setup_dynamo):
        from src.handlers.oauth_handlers import handle_oauth_approve

        event = _make_event({
            "client_id": "nonexistent",
            "redirect_uri": "http://localhost:12345/callback",
            "code_challenge": "ch",
        })
        result = handle_oauth_approve(event, MockAuth(), None)
        assert result["statusCode"] == 400

    def test_invalid_redirect_uri(self, setup_dynamo):
        from src.handlers.oauth_handlers import handle_oauth_approve

        event = _make_event({
            "client_id": "client-1",
            "redirect_uri": "http://evil.com/callback",
            "code_challenge": "ch",
        })
        result = handle_oauth_approve(event, MockAuth(), None)
        assert result["statusCode"] == 400

    def test_saves_consent(self, setup_dynamo):
        from src.handlers.oauth_handlers import handle_oauth_approve

        event = _make_event({
            "client_id": "client-1",
            "redirect_uri": "http://localhost:12345/callback",
            "code_challenge": "ch",
            "scope": "read",
        })
        handle_oauth_approve(event, MockAuth(), None)
        assert setup_dynamo.has_consent("user-123", "client-1") is True

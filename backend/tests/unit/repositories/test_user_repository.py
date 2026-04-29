"""Tests for DynamoDBUserRepository and DynamoDBOrganizationRepository."""

import pytest
from moto import mock_aws

from src.repositories.dynamodb.user_repository import (
    DynamoDBOrganizationRepository,
    DynamoDBUserRepository,
)


class TestUserRepository:
    @mock_aws
    def test_create_and_get(self, dynamodb_table):
        repo = DynamoDBUserRepository(dynamodb_table)
        user_id = repo.create(
            {
                "name": "Test User",
                "email": "test@example.com",
                "password_hash": "hashed",
                "org_id": "org-1",
                "role": "admin",
            }
        )

        assert user_id is not None

        result = repo.get_by_id(user_id)
        assert result is not None
        assert result["email"] == "test@example.com"

    @mock_aws
    def test_find_by_email(self, dynamodb_table):
        repo = DynamoDBUserRepository(dynamodb_table)
        repo.create(
            {
                "email": "alice@example.com",
                "name": "Alice",
                "org_id": "org-1",
            }
        )

        result = repo.find_by_email("alice@example.com")
        assert result is not None
        assert result["name"] == "Alice"

    @mock_aws
    def test_find_by_email_not_found(self, dynamodb_table):
        repo = DynamoDBUserRepository(dynamodb_table)
        result = repo.find_by_email("nobody@example.com")
        assert result is None

    @mock_aws
    def test_has_email(self, dynamodb_table):
        repo = DynamoDBUserRepository(dynamodb_table)
        repo.create({"email": "exists@test.com", "org_id": "org-1"})

        assert repo.has_email("exists@test.com") is True
        assert repo.has_email("missing@test.com") is False

    # ── find_by_cognito_sub (fix-actor-attribution) ────────────────────

    @mock_aws
    def test_find_by_cognito_sub_returns_match(self, dynamodb_table):
        """A user record created with `cognito_sub` is queryable via GSI5."""
        repo = DynamoDBUserRepository(dynamodb_table)
        repo.create(
            {
                "id": "u-1",
                "email": "alice@example.com",
                "name": "Alice",
                "org_id": "org-1",
                "cognito_sub": "cognito-abc-123",
            }
        )

        result = repo.find_by_cognito_sub("cognito-abc-123")
        assert result is not None
        assert result["id"] == "u-1"
        assert result["name"] == "Alice"

    @mock_aws
    def test_find_by_cognito_sub_returns_none_for_unknown_sub(self, dynamodb_table):
        repo = DynamoDBUserRepository(dynamodb_table)
        repo.create(
            {
                "id": "u-1",
                "email": "alice@example.com",
                "org_id": "org-1",
                "cognito_sub": "cognito-known",
            }
        )

        assert repo.find_by_cognito_sub("cognito-ghost") is None

    @mock_aws
    def test_find_by_cognito_sub_returns_none_for_empty_input(self, dynamodb_table):
        """Defensive: empty string short-circuits without hitting the GSI."""
        repo = DynamoDBUserRepository(dynamodb_table)
        assert repo.find_by_cognito_sub("") is None

    @mock_aws
    def test_create_writes_gsi5_when_cognito_sub_supplied(self, dynamodb_table):
        """`create()` populates GSI5PK/SK so the new user is immediately
        queryable via `find_by_cognito_sub` — no backfill needed for
        records written after this change ships.
        """
        repo = DynamoDBUserRepository(dynamodb_table)
        repo.create(
            {
                "id": "u-new",
                "email": "new@example.com",
                "org_id": "org-1",
                "cognito_sub": "cognito-new-sub",
            }
        )

        # Round-trip through GSI5 — proves both the write and the query.
        result = repo.find_by_cognito_sub("cognito-new-sub")
        assert result is not None
        assert result["id"] == "u-new"

    @mock_aws
    def test_create_skips_gsi5_when_no_cognito_sub_supplied(self, dynamodb_table):
        """Legacy callers (no sub provided) still create the user, but
        the record lacks GSI5PK and is not queryable by sub until the
        post-deploy backfill writes it.
        """
        repo = DynamoDBUserRepository(dynamodb_table)
        repo.create(
            {
                "id": "u-legacy",
                "email": "legacy@example.com",
                "org_id": "org-1",
                # No cognito_sub.
            }
        )

        # Reading the raw item to check that GSI5PK isn't there.
        raw = dynamodb_table.get_item(pk="USER#u-legacy", sk="USER#METADATA")
        assert raw is not None
        assert "GSI5PK" not in raw
        # But find_by_email still works (GSI4 is populated unconditionally).
        assert repo.find_by_email("legacy@example.com") is not None

class TestOrganizationRepository:
    @mock_aws
    def test_create_and_get(self, dynamodb_table):
        repo = DynamoDBOrganizationRepository(dynamodb_table)
        org_id = repo.create({"name": "Test Org"})

        assert org_id is not None

        result = repo.get_by_id(org_id)
        assert result is not None
        assert result["name"] == "Test Org"

    @mock_aws
    def test_get_nonexistent(self, dynamodb_table):
        repo = DynamoDBOrganizationRepository(dynamodb_table)
        assert repo.get_by_id("nonexistent") is None

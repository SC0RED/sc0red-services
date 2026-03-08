"""Tests for DynamoDBUserRepository and DynamoDBOrganizationRepository."""

import bcrypt
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

    @mock_aws
    def test_verify_password_valid(self, dynamodb_table):
        repo = DynamoDBUserRepository(dynamodb_table)
        password_hash = bcrypt.hashpw(b"correct-password", bcrypt.gensalt(10)).decode()
        repo.create(
            {
                "email": "user@example.com",
                "name": "User",
                "org_id": "org-1",
                "role": "admin",
                "password_hash": password_hash,
            }
        )

        result = repo.verify_password("user@example.com", "correct-password")
        assert result is not None
        assert result["email"] == "user@example.com"
        assert result["orgId"] == "org-1"
        assert result["role"] == "admin"

    @mock_aws
    def test_verify_password_invalid(self, dynamodb_table):
        repo = DynamoDBUserRepository(dynamodb_table)
        password_hash = bcrypt.hashpw(b"correct-password", bcrypt.gensalt(10)).decode()
        repo.create(
            {
                "email": "user@example.com",
                "password_hash": password_hash,
                "org_id": "org-1",
            }
        )

        result = repo.verify_password("user@example.com", "wrong-password")
        assert result is None

    @mock_aws
    def test_verify_password_no_user(self, dynamodb_table):
        repo = DynamoDBUserRepository(dynamodb_table)
        result = repo.verify_password("nobody@example.com", "password")
        assert result is None

    @mock_aws
    def test_verify_password_no_hash_raises(self, dynamodb_table):
        repo = DynamoDBUserRepository(dynamodb_table)
        repo.create({"email": "nohash@example.com", "org_id": "org-1"})

        with pytest.raises(RuntimeError, match="missing password_hash"):
            repo.verify_password("nohash@example.com", "password")


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

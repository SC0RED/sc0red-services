"""Tests for DynamoDBCompanyRepository."""

from moto import mock_aws

from src.repositories.dynamodb.company_repository import DynamoDBCompanyRepository


class TestCompanyRepository:
    @mock_aws
    def test_save_and_get(self, dynamodb_table):
        repo = DynamoDBCompanyRepository(dynamodb_table)

        company_id = repo.save(
            {
                "id": "comp-123",
                "company_name": "Acme Corp",
                "url": "https://acme.com",
                "org_id": "org-1",
            }
        )

        assert company_id == "comp-123"

        result = repo.get_by_id("comp-123")
        assert result is not None
        assert result["company_name"] == "Acme Corp"
        assert result["url"] == "https://acme.com"

    @mock_aws
    def test_save_generates_id(self, dynamodb_table):
        repo = DynamoDBCompanyRepository(dynamodb_table)
        company_id = repo.save({"company_name": "No ID Corp"})
        assert company_id is not None
        assert len(company_id) > 0

    @mock_aws
    def test_get_nonexistent(self, dynamodb_table):
        repo = DynamoDBCompanyRepository(dynamodb_table)
        result = repo.get_by_id("nonexistent")
        assert result is None

    @mock_aws
    def test_update(self, dynamodb_table):
        repo = DynamoDBCompanyRepository(dynamodb_table)
        repo.save({"id": "comp-1", "company_name": "Old Name"})

        repo.update("comp-1", {"company_name": "New Name"})
        result = repo.get_by_id("comp-1")
        assert result["company_name"] == "New Name"

    @mock_aws
    def test_delete(self, dynamodb_table):
        repo = DynamoDBCompanyRepository(dynamodb_table)
        repo.save({"id": "comp-del", "company_name": "To Delete"})

        repo.delete("comp-del")
        result = repo.get_by_id("comp-del")
        assert result is None

    @mock_aws
    def test_find_by_org(self, dynamodb_table):
        repo = DynamoDBCompanyRepository(dynamodb_table)
        repo.save({"id": "c1", "company_name": "Company 1", "org_id": "org-A"})
        repo.save({"id": "c2", "company_name": "Company 2", "org_id": "org-A"})
        repo.save({"id": "c3", "company_name": "Company 3", "org_id": "org-B"})

        results, cursor = repo.find_by_org("org-A")
        assert len(results) == 2
        assert cursor is None

        results_b, cursor_b = repo.find_by_org("org-B")
        assert len(results_b) == 1
        assert cursor_b is None

    @mock_aws
    def test_find_by_org_with_limit(self, dynamodb_table):
        repo = DynamoDBCompanyRepository(dynamodb_table)
        repo.save({"id": "c1", "company_name": "Company 1", "org_id": "org-A"})
        repo.save({"id": "c2", "company_name": "Company 2", "org_id": "org-A"})
        repo.save({"id": "c3", "company_name": "Company 3", "org_id": "org-A"})

        results, cursor = repo.find_by_org("org-A", limit=2)
        assert len(results) == 2
        # Cursor may or may not be set depending on DynamoDB page boundaries

    @mock_aws
    def test_save_with_explicit_id(self, dynamodb_table):
        repo = DynamoDBCompanyRepository(dynamodb_table)
        repo.save({"id": "comp-sc", "company_name": "SaveCompany Test"})

        result = repo.get_by_id("comp-sc")
        assert result is not None
        assert result["company_name"] == "SaveCompany Test"

"""Tests for DynamoDBScanRepository."""

from moto import mock_aws

from src.repositories.dynamodb.scan_repository import DynamoDBScanRepository


class TestScanRepository:
    @mock_aws
    def test_create_and_get(self, dynamodb_table):
        repo = DynamoDBScanRepository(dynamodb_table)
        scan_id = repo.create({
            "url": "https://pe-firm.com",
            "status": "pending",
            "org_id": "org-1",
        })

        assert scan_id is not None

        result = repo.get_by_id(scan_id)
        assert result is not None
        assert result["url"] == "https://pe-firm.com"

    @mock_aws
    def test_update(self, dynamodb_table):
        repo = DynamoDBScanRepository(dynamodb_table)
        scan_id = repo.create({"status": "pending", "org_id": "org-1"})

        repo.update(scan_id, {"status": "complete", "progress": 100})

        result = repo.get_by_id(scan_id)
        assert result["status"] == "complete"

    @mock_aws
    def test_find_by_org(self, dynamodb_table):
        repo = DynamoDBScanRepository(dynamodb_table)
        repo.create({"org_id": "org-A", "status": "done"})
        repo.create({"org_id": "org-A", "status": "done"})
        repo.create({"org_id": "org-B", "status": "done"})

        results = repo.find_by_org("org-A")
        assert len(results) == 2

    @mock_aws
    def test_link_and_get_companies(self, dynamodb_table):
        repo = DynamoDBScanRepository(dynamodb_table)
        scan_id = repo.create({"org_id": "org-1", "status": "pending"})

        repo.link_company(scan_id, "comp-1", "Company One")
        repo.link_company(scan_id, "comp-2", "Company Two")

        companies = repo.get_scan_companies(scan_id)
        assert len(companies) == 2
        names = {c.get("company_name") for c in companies}
        assert "Company One" in names
        assert "Company Two" in names

    @mock_aws
    def test_delete(self, dynamodb_table):
        repo = DynamoDBScanRepository(dynamodb_table)
        scan_id = repo.create({"org_id": "org-1", "status": "pending"})

        repo.delete(scan_id)
        assert repo.get_by_id(scan_id) is None

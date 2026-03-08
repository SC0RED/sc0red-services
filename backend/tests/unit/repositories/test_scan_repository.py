"""Tests for DynamoDBScanRepository."""

import json

import pytest
from moto import mock_aws

from src.repositories.dynamodb.scan_repository import DynamoDBScanRepository


class TestScanRepository:
    @mock_aws
    def test_create_and_get(self, dynamodb_table):
        repo = DynamoDBScanRepository(dynamodb_table)
        scan_id = repo.create(
            {
                "url": "https://pe-firm.com",
                "status": "pending",
                "org_id": "org-1",
            }
        )

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

    @mock_aws
    def test_create_with_portfolio_companies(self, dynamodb_table):
        """portfolio_companies list is JSON-serialized on create."""
        repo = DynamoDBScanRepository(dynamodb_table)
        companies = [{"name": "Acme", "url": "https://acme.com"}]
        scan_id = repo.create(
            {
                "status": "pending",
                "org_id": "org-1",
                "portfolio_companies": companies,
            }
        )

        # Read raw item to verify serialization
        raw = dynamodb_table.get_item(pk=f"SCAN#{scan_id}", sk="SCAN#METADATA")
        assert isinstance(raw["portfolio_companies"], str)
        assert json.loads(raw["portfolio_companies"]) == companies

        # get_by_id should deserialize it back
        result = repo.get_by_id(scan_id)
        assert isinstance(result["portfolio_companies"], list)
        assert result["portfolio_companies"] == companies

    @mock_aws
    def test_create_without_org_id(self, dynamodb_table):
        """When org_id is absent, no GSI2 attributes are written."""
        repo = DynamoDBScanRepository(dynamodb_table)
        scan_id = repo.create({"status": "pending"})

        raw = dynamodb_table.get_item(pk=f"SCAN#{scan_id}", sk="SCAN#METADATA")
        assert "GSI2PK" not in raw
        assert "GSI2SK" not in raw

    @mock_aws
    def test_update_with_dict_and_list_fields(self, dynamodb_table):
        """Dict and list values are JSON-serialized during update."""
        repo = DynamoDBScanRepository(dynamodb_table)
        scan_id = repo.create({"status": "pending", "org_id": "org-1"})

        repo.update(
            scan_id,
            {
                "status": "complete",
                "portfolio_companies": [{"name": "X"}],
                "metadata": {"key": "value"},
            },
        )

        raw = dynamodb_table.get_item(pk=f"SCAN#{scan_id}", sk="SCAN#METADATA")
        assert raw["status"] == "complete"
        assert isinstance(raw["portfolio_companies"], str)
        assert json.loads(raw["portfolio_companies"]) == [{"name": "X"}]
        assert isinstance(raw["metadata"], str)
        assert json.loads(raw["metadata"]) == {"key": "value"}

    @mock_aws
    def test_deserialize_invalid_json_raises(self, dynamodb_table):
        """Invalid JSON in portfolio_companies raises JSONDecodeError — corrupt data must not be silently swallowed."""
        repo = DynamoDBScanRepository(dynamodb_table)
        scan_id = "test-invalid"

        # Write a raw item with invalid JSON directly
        dynamodb_table.put_item(
            {
                "pk": f"SCAN#{scan_id}",
                "sk": "SCAN#METADATA",
                "id": scan_id,
                "entity_type": "scan",
                "portfolio_companies": "not-valid-json{{{",
            }
        )

        with pytest.raises(json.JSONDecodeError):
            repo.get_by_id(scan_id)

    @mock_aws
    def test_find_recent_by_org(self, dynamodb_table):
        """Return scans sorted by created_at descending, respecting limit."""
        repo = DynamoDBScanRepository(dynamodb_table)
        repo.create({"org_id": "org-A", "status": "done", "created_at": "2026-01-01"})
        repo.create({"org_id": "org-A", "status": "done", "created_at": "2026-03-01"})
        repo.create({"org_id": "org-A", "status": "done", "created_at": "2026-02-01"})
        repo.create({"org_id": "org-B", "status": "done", "created_at": "2026-01-01"})

        # With limit
        results = repo.find_recent_by_org("org-A", limit=2)
        assert len(results) == 2
        assert results[0]["created_at"] == "2026-03-01"

        # Without limit (all scans)
        all_results = repo.find_recent_by_org("org-A", limit=None)
        assert len(all_results) == 3

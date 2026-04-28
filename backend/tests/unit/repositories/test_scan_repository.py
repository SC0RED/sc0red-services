"""Tests for DynamoDBScanRepository."""

import json

import pytest
from botocore.exceptions import ClientError
from moto import mock_aws

from src.repositories.dynamodb._tombstones import (
    DELETED_AT_FIELD,
    TTL_FIELD,
)
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
    def test_link_company_persists_url_and_order_index(self, dynamodb_table):
        """link_company writes company_url + order_index when provided."""
        repo = DynamoDBScanRepository(dynamodb_table)
        scan_id = repo.create({"org_id": "org-1", "status": "pending"})

        repo.link_company(
            scan_id,
            "comp-1",
            "Company One",
            company_url="https://one.example.com",
            order_index=0,
        )
        repo.link_company(
            scan_id,
            "comp-2",
            "Company Two",
            company_url="https://two.example.com",
            order_index=1,
        )

        companies = repo.get_scan_companies(scan_id)
        by_id = {c["company_id"]: c for c in companies}
        assert by_id["comp-1"]["company_url"] == "https://one.example.com"
        assert by_id["comp-1"]["order_index"] == 0
        assert by_id["comp-2"]["company_url"] == "https://two.example.com"
        assert by_id["comp-2"]["order_index"] == 1

    @mock_aws
    def test_link_company_legacy_call_omits_new_fields(self, dynamodb_table):
        """Legacy call shape (no kwargs) does not write company_url/order_index.

        Models the migration scenario: a record written by an older
        Lambda version is read by the new code without crashing.
        """
        repo = DynamoDBScanRepository(dynamodb_table)
        scan_id = repo.create({"org_id": "org-1", "status": "pending"})

        repo.link_company(scan_id, "comp-1", "Company One")

        companies = repo.get_scan_companies(scan_id)
        assert len(companies) == 1
        assert "company_url" not in companies[0]
        assert "order_index" not in companies[0]

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

    @mock_aws
    def test_unlink_company(self, dynamodb_table):
        """unlink_company removes a single scan→company link item."""
        repo = DynamoDBScanRepository(dynamodb_table)
        scan_id = repo.create({"org_id": "org-1", "status": "running"})
        repo.link_company(scan_id, "c-1", "Company One")
        repo.link_company(scan_id, "c-2", "Company Two")

        repo.unlink_company(scan_id, "c-1")

        companies = repo.get_scan_companies(scan_id)
        assert len(companies) == 1
        assert companies[0]["company_id"] == "c-2"

    @mock_aws
    def test_delete_all_company_links(self, dynamodb_table):
        """delete_all_company_links removes all scan→company link items."""
        repo = DynamoDBScanRepository(dynamodb_table)
        scan_id = repo.create({"org_id": "org-1", "status": "running"})
        repo.link_company(scan_id, "c-1", "Company One")
        repo.link_company(scan_id, "c-2", "Company Two")
        repo.link_company(scan_id, "c-3", "Company Three")

        repo.delete_all_company_links(scan_id)

        companies = repo.get_scan_companies(scan_id)
        assert len(companies) == 0
        # Scan metadata should still exist
        assert repo.get_by_id(scan_id) is not None

    @mock_aws
    def test_delete_all_company_links_no_links(self, dynamodb_table):
        """delete_all_company_links is a no-op when no links exist."""
        repo = DynamoDBScanRepository(dynamodb_table)
        scan_id = repo.create({"org_id": "org-1", "status": "running"})

        repo.delete_all_company_links(scan_id)

        assert repo.get_scan_companies(scan_id) == []

    # ── Soft-delete (tombstone) tests ────────────────────────────────

    @mock_aws
    def test_tombstone_hides_from_get_by_id(self, dynamodb_table):
        repo = DynamoDBScanRepository(dynamodb_table)
        scan_id = repo.create({"org_id": "org-A", "status": "complete"})
        assert repo.get_by_id(scan_id) is not None

        repo.tombstone(scan_id)
        assert repo.get_by_id(scan_id) is None

    @mock_aws
    def test_tombstone_hides_from_find_recent_by_org(self, dynamodb_table):
        repo = DynamoDBScanRepository(dynamodb_table)
        live_id = repo.create(
            {"org_id": "org-A", "status": "complete", "created_at": "2026-01-02"}
        )
        doomed_id = repo.create(
            {"org_id": "org-A", "status": "complete", "created_at": "2026-01-01"}
        )
        repo.tombstone(doomed_id)

        results = repo.find_recent_by_org("org-A", limit=None)
        assert [scan["id"] for scan in results] == [live_id]

    @mock_aws
    def test_get_by_id_with_deleted_returns_tombstoned(self, dynamodb_table):
        repo = DynamoDBScanRepository(dynamodb_table)
        scan_id = repo.create({"org_id": "org-A", "status": "complete"})
        repo.tombstone(scan_id)

        item = repo.get_by_id_with_deleted(scan_id)
        assert item is not None
        assert item["id"] == scan_id
        assert item.get(DELETED_AT_FIELD)

    @mock_aws
    def test_restore_clears_tombstone(self, dynamodb_table):
        repo = DynamoDBScanRepository(dynamodb_table)
        scan_id = repo.create({"org_id": "org-A", "status": "complete"})
        repo.tombstone(scan_id)
        assert repo.get_by_id(scan_id) is None

        repo.restore(scan_id)
        item = repo.get_by_id(scan_id)
        assert item is not None
        assert DELETED_AT_FIELD not in item
        assert TTL_FIELD not in item

    @mock_aws
    def test_tombstone_link_hides_from_get_scan_companies(self, dynamodb_table):
        """Tombstoned link records are filtered out of the live cascade read."""
        repo = DynamoDBScanRepository(dynamodb_table)
        scan_id = repo.create({"org_id": "org-A", "status": "running"})
        repo.link_company(scan_id, "c-1", "Company One")
        repo.link_company(scan_id, "c-2", "Company Two")

        repo.tombstone_link(scan_id, "c-1")

        live = repo.get_scan_companies(scan_id)
        assert [link["company_id"] for link in live] == ["c-2"]

        # The recovery-aware variant still surfaces the tombstoned link.
        all_links = repo.get_scan_companies_with_deleted(scan_id)
        ids = sorted(link["company_id"] for link in all_links)
        assert ids == ["c-1", "c-2"]

    @mock_aws
    def test_restore_link_clears_tombstone(self, dynamodb_table):
        repo = DynamoDBScanRepository(dynamodb_table)
        scan_id = repo.create({"org_id": "org-A", "status": "running"})
        repo.link_company(scan_id, "c-1", "Company One")
        repo.tombstone_link(scan_id, "c-1")
        assert repo.get_scan_companies(scan_id) == []

        repo.restore_link(scan_id, "c-1")
        live = repo.get_scan_companies(scan_id)
        assert [link["company_id"] for link in live] == ["c-1"]

    @mock_aws
    def test_find_tombstoned_by_org_returns_only_deleted(self, dynamodb_table):
        repo = DynamoDBScanRepository(dynamodb_table)
        live_id = repo.create({"org_id": "org-A", "status": "complete"})
        doomed_id = repo.create({"org_id": "org-A", "status": "complete"})
        other_id = repo.create({"org_id": "org-B", "status": "complete"})
        repo.tombstone(doomed_id)
        repo.tombstone(other_id)  # different org — must NOT surface

        results = repo.find_tombstoned_by_org("org-A")
        ids = [scan["id"] for scan in results]
        assert ids == [doomed_id]
        assert live_id not in ids

    @mock_aws
    def test_restore_raises_when_row_was_ttl_evicted(self, dynamodb_table):
        """Eviction-race guard: see the matching company-repo test for
        the full rationale.
        """
        repo = DynamoDBScanRepository(dynamodb_table)
        with pytest.raises(ClientError) as error_info:
            repo.restore("ghost-scan")
        assert (
            error_info.value.response["Error"]["Code"] == "ConditionalCheckFailedException"
        )
        assert dynamodb_table.get_item(pk="SCAN#ghost-scan", sk="SCAN#METADATA") is None

    @mock_aws
    def test_restore_link_raises_when_row_was_ttl_evicted(self, dynamodb_table):
        """Eviction-race guard for link records — same posture as
        `test_restore_raises_when_row_was_ttl_evicted`.
        """
        repo = DynamoDBScanRepository(dynamodb_table)
        with pytest.raises(ClientError) as error_info:
            repo.restore_link("ghost-scan", "ghost-company")
        assert (
            error_info.value.response["Error"]["Code"] == "ConditionalCheckFailedException"
        )
        assert (
            dynamodb_table.get_item(pk="SCAN#ghost-scan", sk="COMPANY#ghost-company") is None
        )

    @mock_aws
    def test_delete_all_company_links_drains_tombstoned_links(self, dynamodb_table):
        """The hard-delete sweeper must catch tombstoned links too.

        Cleanup scripts (and post-TTL housekeeping) need to be able to
        drain a scan completely. If `delete_all_company_links` only saw
        live links, tombstoned ones would survive forever as orphan
        records pinned to a parent scan that's already gone.
        """
        repo = DynamoDBScanRepository(dynamodb_table)
        scan_id = repo.create({"org_id": "org-A", "status": "running"})
        repo.link_company(scan_id, "c-live", "Company Live")
        repo.link_company(scan_id, "c-tomb", "Company Tomb")
        repo.tombstone_link(scan_id, "c-tomb")

        repo.delete_all_company_links(scan_id)

        assert repo.get_scan_companies(scan_id) == []
        assert repo.get_scan_companies_with_deleted(scan_id) == []

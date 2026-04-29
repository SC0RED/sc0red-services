"""Tests for DynamoDBCompanyRepository."""

import time

import pytest
from botocore.exceptions import ClientError
from moto import mock_aws

from src.repositories.dynamodb._tombstones import (
    DELETED_AT_FIELD,
    TOMBSTONE_TTL_DAYS,
    TTL_FIELD,
)
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

    # ── Soft-delete (tombstone) tests ────────────────────────────────

    @mock_aws
    def test_tombstone_hides_from_get_by_id(self, dynamodb_table):
        """Tombstoned records are invisible to the live read path."""
        repo = DynamoDBCompanyRepository(dynamodb_table)
        repo.save({"id": "c-tomb", "company_name": "Doomed", "org_id": "org-A"})
        assert repo.get_by_id("c-tomb") is not None

        repo.tombstone("c-tomb")
        assert repo.get_by_id("c-tomb") is None

    @mock_aws
    def test_tombstone_hides_from_find_by_org(self, dynamodb_table):
        """Tombstoned records are filtered out of org-scoped GSI listings."""
        repo = DynamoDBCompanyRepository(dynamodb_table)
        repo.save({"id": "live-1", "company_name": "Live", "org_id": "org-A"})
        repo.save({"id": "live-2", "company_name": "Also Live", "org_id": "org-A"})
        repo.save({"id": "doomed", "company_name": "Doomed", "org_id": "org-A"})
        repo.tombstone("doomed")

        results, _cursor = repo.find_by_org("org-A")
        ids = sorted(item["id"] for item in results)
        assert ids == ["live-1", "live-2"]

    @mock_aws
    def test_tombstone_hides_from_get_by_ids(self, dynamodb_table):
        """BatchGetItem path filters tombstones the same way GetItem does."""
        repo = DynamoDBCompanyRepository(dynamodb_table)
        repo.save({"id": "live", "company_name": "Live", "org_id": "org-A"})
        repo.save({"id": "doomed", "company_name": "Doomed", "org_id": "org-A"})
        repo.tombstone("doomed")

        results = repo.get_by_ids(["live", "doomed"])
        assert [item["id"] for item in results] == ["live"]

    @mock_aws
    def test_tombstone_sets_ttl_90_days_out(self, dynamodb_table):
        """`tombstone` writes both `deleted_at` (ISO) and `ttl` (epoch seconds)."""
        repo = DynamoDBCompanyRepository(dynamodb_table)
        repo.save({"id": "c-ttl", "company_name": "TTL Check", "org_id": "org-A"})

        before = int(time.time())
        repo.tombstone("c-ttl")
        after = int(time.time())

        # Bypass the live filter to read the markers we just wrote.
        item = repo.get_by_id_with_deleted("c-ttl")
        assert item is not None
        assert isinstance(item.get(DELETED_AT_FIELD), str)
        ttl_seconds = int(item[TTL_FIELD])
        # TTL is `now + TOMBSTONE_TTL_DAYS` ± a couple of seconds for clock drift.
        expected_min = before + TOMBSTONE_TTL_DAYS * 86_400 - 5
        expected_max = after + TOMBSTONE_TTL_DAYS * 86_400 + 5
        assert expected_min <= ttl_seconds <= expected_max

    @mock_aws
    def test_get_by_id_with_deleted_returns_tombstoned_records(self, dynamodb_table):
        """The recovery-aware accessor returns tombstoned items unchanged."""
        repo = DynamoDBCompanyRepository(dynamodb_table)
        repo.save({"id": "c-rec", "company_name": "Recoverable", "org_id": "org-A"})
        repo.tombstone("c-rec")

        item = repo.get_by_id_with_deleted("c-rec")
        assert item is not None
        assert item["id"] == "c-rec"
        assert item.get(DELETED_AT_FIELD)

    @mock_aws
    def test_restore_clears_tombstone(self, dynamodb_table):
        """`restore` REMOVEs both `deleted_at` and `ttl`; record reappears in live reads."""
        repo = DynamoDBCompanyRepository(dynamodb_table)
        repo.save({"id": "c-restore", "company_name": "Restored", "org_id": "org-A"})
        repo.tombstone("c-restore")
        assert repo.get_by_id("c-restore") is None

        repo.restore("c-restore")
        item = repo.get_by_id("c-restore")
        assert item is not None
        # Both markers must be REMOVED, not nulled — TTL service expects
        # absent-or-numeric, not None.
        assert DELETED_AT_FIELD not in item
        assert TTL_FIELD not in item

    @mock_aws
    def test_find_tombstoned_by_org_returns_only_deleted(self, dynamodb_table):
        """Phase 2 admin recovery feed surfaces ONLY tombstoned org records."""
        repo = DynamoDBCompanyRepository(dynamodb_table)
        repo.save({"id": "live", "company_name": "Live", "org_id": "org-A"})
        repo.save({"id": "tomb-1", "company_name": "Doomed", "org_id": "org-A"})
        repo.save({"id": "tomb-2", "company_name": "Also Doomed", "org_id": "org-A"})
        repo.save({"id": "other-org", "company_name": "Other Org", "org_id": "org-B"})
        repo.tombstone("tomb-1")
        repo.tombstone("tomb-2")
        repo.tombstone("other-org")  # should NOT appear — different org

        results = repo.find_tombstoned_by_org("org-A")
        ids = sorted(item["id"] for item in results)
        assert ids == ["tomb-1", "tomb-2"]
        for item in results:
            assert item.get(DELETED_AT_FIELD)

    @mock_aws
    def test_find_tombstoned_by_org_respects_window_start(self, dynamodb_table):
        """`window_start` filters tombstones to those deleted ON OR AFTER it.

        Phase 2 admin UI uses this to power the 24h/7d/30d/90d window
        chips. We back-date one row's `deleted_at` to a year ago and
        verify it falls outside any in-window query.
        """
        from datetime import UTC, datetime, timedelta

        repo = DynamoDBCompanyRepository(dynamodb_table)
        repo.save({"id": "recent", "company_name": "Recent", "org_id": "org-A"})
        repo.save({"id": "ancient", "company_name": "Ancient", "org_id": "org-A"})
        repo.tombstone("recent")  # `deleted_at` ~ now
        # Force `ancient`'s tombstone to a year ago via a direct write —
        # `tombstone()` always writes the current timestamp.
        ancient_when = (datetime.now(UTC) - timedelta(days=365)).isoformat()
        dynamodb_table.update_item(
            pk="COMPANY#ancient",
            sk="COMPANY#METADATA",
            updates={"deleted_at": ancient_when, "ttl": 0},
        )

        # Window of 30 days catches the recent one only.
        cutoff = datetime.now(UTC) - timedelta(days=30)
        results = repo.find_tombstoned_by_org("org-A", window_start=cutoff)
        ids = [item["id"] for item in results]
        assert ids == ["recent"]

        # Default (no window) sees both — backward compatible.
        all_results = repo.find_tombstoned_by_org("org-A")
        all_ids = sorted(item["id"] for item in all_results)
        assert all_ids == ["ancient", "recent"]

    @mock_aws
    def test_restore_raises_when_row_was_ttl_evicted(self, dynamodb_table):
        """Recovery flow reads the tombstoned row, then TTL evicts it
        before the `restore()` UpdateItem lands. Without the guard,
        DynamoDB would create an empty `{pk, sk}` shell that looks
        restored but has lost every data field. With the guard the
        call raises ConditionalCheckFailedException — recovery
        callers translate that to `ttl_expired`.
        """
        repo = DynamoDBCompanyRepository(dynamodb_table)
        # Note: never `save`d. Simulates the post-eviction state where
        # the recovery flow had a snapshot but the row is now gone.
        with pytest.raises(ClientError) as error_info:
            repo.restore("ghost-company")
        assert (
            error_info.value.response["Error"]["Code"] == "ConditionalCheckFailedException"
        )

        # And the ghost-company shell was NOT created.
        assert dynamodb_table.get_item(pk="COMPANY#ghost-company", sk="COMPANY#METADATA") is None

    @mock_aws
    def test_legacy_records_without_deleted_at_treated_as_live(self, dynamodb_table):
        """Records written before the tombstone change ship without
        `deleted_at` — they must still surface in live reads.
        """
        repo = DynamoDBCompanyRepository(dynamodb_table)
        repo.save({"id": "legacy", "company_name": "Pre-tombstone", "org_id": "org-A"})
        # No tombstone call. Item has no `deleted_at` attribute.

        item = repo.get_by_id("legacy")
        assert item is not None
        assert DELETED_AT_FIELD not in item

        results, _cursor = repo.find_by_org("org-A")
        assert any(record["id"] == "legacy" for record in results)

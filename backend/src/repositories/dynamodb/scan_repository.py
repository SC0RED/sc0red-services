"""DynamoDB scan tracking repository.

Single-table keys:
  pk = SCAN#{id}    sk = SCAN#METADATA
  pk = SCAN#{id}    sk = COMPANY#{company_id}    (link records)
  GSI2: pk=ORG#{org_id}  sk=SCAN#{id}

Soft-delete contract (see `soft-delete-recovery` change):
  All read methods filter out tombstoned records (where `deleted_at`
  is set) by default. Methods that intentionally return tombstoned
  records — used by the engineer-assisted recovery path and by the
  Phase 2 admin UI — carry a `_with_deleted` suffix. New methods
  that bypass the filter MUST follow that naming convention so the
  filter behaviour is grep-able.
"""

from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING, Any

from src.repositories.dynamodb._tombstones import (
    DELETED_AT_FIELD,
    TTL_FIELD,
    filter_live,
    tombstone_attributes,
)

if TYPE_CHECKING:
    from datetime import datetime

    from src.repositories.dynamodb.client import DynamoDBTable


class DynamoDBScanRepository:
    """Repository for scan documents in DynamoDB."""

    def __init__(self, table: DynamoDBTable) -> None:
        self._table = table

    def create(self, scan: dict[str, Any]) -> str:
        """Persist a new scan document and return its ID."""
        scan_id = scan.get("id") or str(uuid.uuid4())
        item = {
            "pk": f"SCAN#{scan_id}",
            "sk": "SCAN#METADATA",
            "id": scan_id,
            "entity_type": "scan",
            **{k: v for k, v in scan.items() if k != "id"},
        }

        # Serialize portfolio_companies list
        if "portfolio_companies" in item and isinstance(item["portfolio_companies"], list):
            item["portfolio_companies"] = json.dumps(item["portfolio_companies"])

        # GSI2 for org-level scan queries
        org_id = scan.get("org_id")
        if org_id:
            item["GSI2PK"] = f"ORG#{org_id}"
            item["GSI2SK"] = f"SCAN#{scan_id}"

        self._table.put_item(item)
        return scan_id

    def get_by_id(self, scan_id: str) -> dict[str, Any] | None:
        """Return the scan metadata item, or None if not found OR tombstoned.

        Treats tombstoned and not-found identically — callers that need
        to inspect tombstoned records (recovery flows) use
        `get_by_id_with_deleted`.
        """
        item = self._table.get_item(pk=f"SCAN#{scan_id}", sk="SCAN#METADATA")
        # Inline the live check (rather than calling `is_live`) so the
        # type checker narrows `item` to `dict` for the `_deserialize`
        # call. Equivalent semantically.
        if item is None or item.get(DELETED_AT_FIELD):
            return None
        self._deserialize(item)
        return item

    def get_by_id_with_deleted(self, scan_id: str) -> dict[str, Any] | None:
        """Return the scan metadata item EVEN IF tombstoned.

        Recovery-aware variant for the restore path. Returns None only
        when the record genuinely doesn't exist.
        """
        item = self._table.get_item(pk=f"SCAN#{scan_id}", sk="SCAN#METADATA")
        if item:
            self._deserialize(item)
        return item

    def update(self, scan_id: str, changes: dict[str, Any]) -> None:
        """Apply attribute-level updates to an existing scan document."""
        # Serialize list/dict fields
        serialized = {}
        for k, v in changes.items():
            if isinstance(v, (list, dict)):
                serialized[k] = json.dumps(v)
            else:
                serialized[k] = v
        self._table.update_item(
            pk=f"SCAN#{scan_id}",
            sk="SCAN#METADATA",
            updates=serialized,
        )

    def delete(self, scan_id: str) -> None:
        """Hard-delete the scan metadata item.

        Reserved for cleanup-script and test paths; production handlers
        use `tombstone()` so the record is recoverable for 90 days.
        """
        self._table.delete_item(pk=f"SCAN#{scan_id}", sk="SCAN#METADATA")

    def tombstone(self, scan_id: str, *, actor_id: str | None = None) -> None:
        """Mark the scan metadata as soft-deleted with a 90-day TTL.

        Reads through `get_by_id` / `find_recent_by_org` will no longer
        return this record. DynamoDB TTL evicts the row 90 days after
        `deleted_at`. Use `restore()` to clear the markers.

        Pass ``actor_id`` to attribute the delete to a user — see
        `DynamoDBCompanyRepository.tombstone` for full semantics.

        Note: this does NOT cascade to scan→company link records or to
        the linked companies/assessments. Callers that want a full
        cascade tombstone use `tombstone_link()` per link, plus the
        company/assessment tombstone methods on their respective repos.
        """
        self._table.update_item(
            pk=f"SCAN#{scan_id}",
            sk="SCAN#METADATA",
            updates=tombstone_attributes(actor_id=actor_id),
        )

    def restore(self, scan_id: str) -> None:
        """Clear the tombstone markers on the scan metadata item.

        Counterpart of `tombstone()`. Does NOT auto-restore link
        records or linked companies/assessments — callers re-stitch
        whatever the recovery flow demands.

        Guarded by ``require_exists=True`` to surface the TTL-eviction
        race (see `DynamoDBCompanyRepository.restore` for the full
        rationale).
        """
        self._table.remove_attributes(
            pk=f"SCAN#{scan_id}",
            sk="SCAN#METADATA",
            attribute_names=[DELETED_AT_FIELD, TTL_FIELD],
            require_exists=True,
        )

    def link_company(
        self,
        scan_id: str,
        company_id: str,
        company_name: str,
        *,
        company_url: str | None = None,
        order_index: int | None = None,
    ) -> None:
        """Create a scan→company association item.

        ``company_url`` and ``order_index`` are persisted when provided so
        the portfolio view can render every company card from t=0 in
        submission order — even before a worker has created the
        corresponding ``companies`` record. Reads tolerate their absence
        on records written before this change shipped (see
        ``get_scan_companies``).
        """
        item: dict[str, Any] = {
            "pk": f"SCAN#{scan_id}",
            "sk": f"COMPANY#{company_id}",
            "entity_type": "scan_company",
            "company_id": company_id,
            "company_name": company_name,
        }
        if company_url is not None:
            item["company_url"] = company_url
        if order_index is not None:
            item["order_index"] = order_index
        self._table.put_item(item)

    def unlink_company(self, scan_id: str, company_id: str) -> None:
        """Hard-delete a single scan→company association item.

        Reserved for cleanup-script and test paths; production handlers
        use `tombstone_link()` so the link is recoverable for 90 days.
        """
        self._table.delete_item(pk=f"SCAN#{scan_id}", sk=f"COMPANY#{company_id}")

    def tombstone_link(self, scan_id: str, company_id: str, *, actor_id: str | None = None) -> None:
        """Soft-delete a scan→company link with a 90-day TTL.

        The cascade-decision read in `analysis_handlers` (whether all
        companies under a scan are gone) goes through
        `get_scan_companies`, which filters tombstones — so a
        tombstoned link looks identical to a hard-deleted one for
        live-traffic purposes, and recovery is a REMOVE on the same
        attributes.

        Pass ``actor_id`` to attribute the delete to a user — see
        `DynamoDBCompanyRepository.tombstone` for full semantics.
        """
        self._table.update_item(
            pk=f"SCAN#{scan_id}",
            sk=f"COMPANY#{company_id}",
            updates=tombstone_attributes(actor_id=actor_id),
        )

    def restore_link(self, scan_id: str, company_id: str) -> None:
        """Clear tombstone markers on a scan→company link record.

        Guarded by ``require_exists=True`` to surface the TTL-eviction
        race (see `DynamoDBCompanyRepository.restore` for the full
        rationale).
        """
        self._table.remove_attributes(
            pk=f"SCAN#{scan_id}",
            sk=f"COMPANY#{company_id}",
            attribute_names=[DELETED_AT_FIELD, TTL_FIELD],
            require_exists=True,
        )

    def delete_all_company_links(self, scan_id: str) -> None:
        """Hard-delete all scan→company association items for the given scan.

        Reserved for cleanup-script and test paths; the production
        bulk-delete path tombstones each link individually so the
        scan can be restored end-to-end.

        Trade-off: ``link_company`` always writes ``company_id``, so an
        anomalous link record (direct DynamoDB write or data corruption)
        is the only path to a missing field. We skip such records rather
        than ``KeyError``-ing the entire batch — partial corruption
        shouldn't block the rest of the cascade. This matches the read
        guard in ``handle_scan_status`` for consistency. Strict
        fail-fast would raise here; we accept the small drift to keep
        the delete cascade resilient.
        """
        # Hard-delete path needs to see tombstoned records too — otherwise
        # cleanup scripts can't remove them after the TTL window.
        links = self.get_scan_companies_with_deleted(scan_id)
        keys = [
            {"pk": f"SCAN#{scan_id}", "sk": f"COMPANY#{link['company_id']}"}
            for link in links
            if link.get("company_id")
        ]
        if keys:
            self._table.batch_delete(keys)

    def get_scan_companies(self, scan_id: str) -> list[dict[str, Any]]:
        """Return all live (non-tombstoned) company association items for the scan.

        Uses a strongly-consistent read so callers in the bulk-delete
        cascade pass observe their own prior `tombstone_link` writes
        within the same handler invocation. The default eventually-
        consistent read can lag by ~100ms — enough to leave orphan
        scans on the cascade decision. See
        `analysis_handlers.handle_bulk_delete_analyses`.
        """
        items = self._table.query(
            pk=f"SCAN#{scan_id}",
            sk_prefix="COMPANY#",
            consistent_read=True,
        )
        return filter_live(items)

    def get_scan_companies_with_deleted(self, scan_id: str) -> list[dict[str, Any]]:
        """Return ALL company association items for the scan, including tombstoned.

        Recovery-aware variant. Used by:
          - Engineer-assisted recovery to find the link records to restore
          - The `delete_all_company_links` hard-delete path so cleanup
            scripts can drain a scan completely (live + tombstoned).
        """
        return self._table.query(
            pk=f"SCAN#{scan_id}",
            sk_prefix="COMPANY#",
            consistent_read=True,
        )

    def find_recent_by_org(self, org_id: str, limit: int | None = 10) -> list[dict[str, Any]]:
        """Return live scans for the given organisation, sorted by created_at descending.

        Filters tombstoned records before sorting + limiting so callers
        always see exactly `limit` live scans (not `limit` minus
        tombstones).

        Pass limit=None to return all live scans (useful for deriving count).
        """
        items, _cursor = self._table.query_gsi(
            index_name="GSI2",
            pk_attr="GSI2PK",
            pk_value=f"ORG#{org_id}",
        )
        live = filter_live(items)
        for item in live:
            self._deserialize(item)
        live.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return live[:limit] if limit is not None else live

    def find_tombstoned_by_org(
        self,
        org_id: str,
        window_start: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Return ONLY tombstoned scans for the given org.

        Used by the Phase 2 admin recovery UI. Filters in-memory after
        the GSI query — at sc0red Services volumes the filter cost is negligible;
        revisit with a `deleted_at` GSI if volumes ever justify it.

        Pass ``window_start`` to filter records to those tombstoned
        ON OR AFTER that timestamp. See the matching method on
        ``DynamoDBCompanyRepository`` for the same window semantics.
        """
        items, _cursor = self._table.query_gsi(
            index_name="GSI2",
            pk_attr="GSI2PK",
            pk_value=f"ORG#{org_id}",
        )
        tombstoned = [item for item in items if item.get(DELETED_AT_FIELD)]
        if window_start is not None:
            cutoff = window_start.isoformat()
            tombstoned = [item for item in tombstoned if item[DELETED_AT_FIELD] >= cutoff]
        for item in tombstoned:
            self._deserialize(item)
        return tombstoned

    @staticmethod
    def _deserialize(item: dict[str, Any]) -> None:
        if "portfolio_companies" in item and isinstance(item["portfolio_companies"], str):
            item["portfolio_companies"] = json.loads(item["portfolio_companies"])
        if "discovery_verdict" in item and isinstance(item["discovery_verdict"], str):
            item["discovery_verdict"] = json.loads(item["discovery_verdict"])

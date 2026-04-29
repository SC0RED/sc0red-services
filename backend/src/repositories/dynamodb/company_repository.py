"""DynamoDB implementation of company entity storage.

Single-table keys:
  pk = COMPANY#{id}    sk = COMPANY#METADATA
  GSI1: pk=ORG#{org_id}  sk=COMPANY#{id}

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
    is_live,
    tombstone_attributes,
)

if TYPE_CHECKING:
    from datetime import datetime

    from src.repositories.dynamodb.client import DynamoDBTable


class DynamoDBCompanyRepository:
    """Repository for company entities in DynamoDB."""

    def __init__(self, table: DynamoDBTable) -> None:
        self._table = table

    # ── EntityRepository-style methods ───────────────────────────────

    def get_by_id(self, company_id: str) -> dict[str, Any] | None:
        """Return the company metadata item, or None if not found OR tombstoned.

        Treats tombstoned and not-found identically — callers that need
        to inspect tombstoned records (recovery flows) use
        `get_by_id_with_deleted`.
        """
        item = self._table.get_item(
            pk=f"COMPANY#{company_id}",
            sk="COMPANY#METADATA",
        )
        return item if is_live(item) else None

    def get_by_id_with_deleted(self, company_id: str) -> dict[str, Any] | None:
        """Return the company metadata item EVEN IF tombstoned.

        Recovery-aware variant for the restore path. Returns None only
        when the record genuinely doesn't exist.
        """
        return self._table.get_item(
            pk=f"COMPANY#{company_id}",
            sk="COMPANY#METADATA",
        )

    def get_by_ids(self, company_ids: list[str]) -> list[dict[str, Any]]:
        """Fetch multiple companies in a single BatchGetItem call. Filters tombstones."""
        if not company_ids:
            return []
        keys = [{"pk": f"COMPANY#{cid}", "sk": "COMPANY#METADATA"} for cid in company_ids]
        return filter_live(self._table.batch_get(keys))

    def save(self, entity: dict[str, Any]) -> str:
        """Persist a full company entity document and return its ID."""
        company_id = entity.get("id") or str(uuid.uuid4())
        item = {
            "pk": f"COMPANY#{company_id}",
            "sk": "COMPANY#METADATA",
            "id": company_id,
            "entity_type": "company",
            **{k: v for k, v in entity.items() if k != "id"},
        }

        # GSI1 for org-level queries
        org_id = entity.get("org_id")
        if org_id:
            item["GSI1PK"] = f"ORG#{org_id}"
            item["GSI1SK"] = f"COMPANY#{company_id}"

        self._table.put_item(item)
        return company_id

    def update(self, company_id: str, changes: dict[str, Any]) -> None:
        """Apply attribute-level updates to an existing company item."""
        self._table.update_item(
            pk=f"COMPANY#{company_id}",
            sk="COMPANY#METADATA",
            updates=changes,
        )

    def update_company_metadata(self, company_id: str, metadata: dict[str, Any]) -> None:
        """Serialize and store arbitrary metadata on a company item."""
        self.update(company_id, {"metadata_json": json.dumps(metadata)})

    def delete(self, company_id: str) -> None:
        """Hard-delete the company metadata item.

        Reserved for cleanup-script and test paths; production handlers
        use `tombstone()` so the record is recoverable for 90 days.
        """
        self._table.delete_item(
            pk=f"COMPANY#{company_id}",
            sk="COMPANY#METADATA",
        )

    def tombstone(self, company_id: str) -> None:
        """Mark the company as soft-deleted with a 90-day TTL.

        Reads through `get_by_id` / `get_by_ids` / `find_by_org` will
        no longer return this record. DynamoDB TTL evicts the row 90
        days after `deleted_at`. Recovery via `restore()` clears the
        markers.
        """
        self._table.update_item(
            pk=f"COMPANY#{company_id}",
            sk="COMPANY#METADATA",
            updates=tombstone_attributes(),
        )

    def restore(self, company_id: str) -> None:
        """Clear the tombstone markers, making the company live again.

        Guarded by ``require_exists=True`` to surface the TTL-eviction
        race: if the row was hard-evicted by DynamoDB TTL between the
        recovery flow's read and this write, the conditional check
        fails and ``ClientError(Code=ConditionalCheckFailedException)``
        propagates — recovery callers translate that to a
        ``ttl_expired`` outcome rather than silently writing an empty
        ``{pk, sk}`` shell that looks restored but has lost all data.
        """
        self._table.remove_attributes(
            pk=f"COMPANY#{company_id}",
            sk="COMPANY#METADATA",
            attribute_names=[DELETED_AT_FIELD, TTL_FIELD],
            require_exists=True,
        )

    def find_by_org(
        self,
        org_id: str,
        limit: int | None = None,
        cursor: dict[str, Any] | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
        """Return live (non-tombstoned) companies for the given org.

        Pagination caveat: ``limit`` is the DynamoDB page cap, applied
        BEFORE tombstones are filtered. A page can therefore return
        fewer than ``limit`` items even when more live records exist on
        subsequent pages — callers must drive pagination off
        ``next_cursor``, not off the size of the returned slice. At
        Janus volumes (low tombstone density) page rag is negligible;
        revisit with a server-side ``FilterExpression`` if heavy
        tombstone density distorts pagination.
        """
        items, next_cursor = self._table.query_gsi(
            index_name="GSI1",
            pk_attr="GSI1PK",
            pk_value=f"ORG#{org_id}",
            sk_attr="GSI1SK",
            sk_prefix="COMPANY#",
            limit=limit,
            cursor=cursor,
        )
        return filter_live(items), next_cursor

    def find_tombstoned_by_org(
        self,
        org_id: str,
        window_start: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Return ONLY tombstoned companies for the given org.

        Used by the Phase 2 admin recovery UI. Phase 1 ships this so
        engineer-assisted recovery has a quick listing path. Filters
        in-memory after the GSI query — at Janus volumes the filter
        cost is negligible; revisit with a `deleted_at` GSI if volumes
        ever justify it.

        Pass ``window_start`` to filter records to those tombstoned
        ON OR AFTER that timestamp. ``deleted_at`` is an ISO 8601
        string with timezone, so string comparison is lexically
        correct against the supplied datetime's ISO form. Records
        without a ``deleted_at`` (live) are filtered out regardless.
        """
        items, _cursor = self._table.query_gsi(
            index_name="GSI1",
            pk_attr="GSI1PK",
            pk_value=f"ORG#{org_id}",
            sk_attr="GSI1SK",
            sk_prefix="COMPANY#",
        )
        tombstoned = [item for item in items if item.get(DELETED_AT_FIELD)]
        if window_start is None:
            return tombstoned
        cutoff = window_start.isoformat()
        return [item for item in tombstoned if item[DELETED_AT_FIELD] >= cutoff]

"""DynamoDB implementation of company entity storage.

Single-table keys:
  pk = COMPANY#{id}    sk = COMPANY#METADATA
  GSI1: pk=ORG#{org_id}  sk=COMPANY#{id}
"""

from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.repositories.dynamodb.client import DynamoDBTable


class DynamoDBCompanyRepository:
    """Repository for company entities in DynamoDB."""

    def __init__(self, table: DynamoDBTable) -> None:
        self._table = table

    # ── EntityRepository-style methods ───────────────────────────────

    def get_by_id(self, company_id: str) -> dict[str, Any] | None:
        """Return the company metadata item for the given ID, or None if not found."""
        return self._table.get_item(
            pk=f"COMPANY#{company_id}",
            sk="COMPANY#METADATA",
        )

    def get_by_ids(self, company_ids: list[str]) -> list[dict[str, Any]]:
        """Fetch multiple companies in a single BatchGetItem call."""
        if not company_ids:
            return []
        keys = [{"pk": f"COMPANY#{cid}", "sk": "COMPANY#METADATA"} for cid in company_ids]
        return self._table.batch_get(keys)

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
        """Delete the company metadata item for the given ID."""
        self._table.delete_item(
            pk=f"COMPANY#{company_id}",
            sk="COMPANY#METADATA",
        )

    def find_by_org(self, org_id: str) -> list[dict[str, Any]]:
        """Return all companies belonging to the given organisation ID."""
        return self._table.query_gsi(
            index_name="GSI1",
            pk_attr="GSI1PK",
            pk_value=f"ORG#{org_id}",
            sk_attr="GSI1SK",
            sk_prefix="COMPANY#",
        )

"""DynamoDB scan tracking repository.

Single-table keys:
  pk = SCAN#{id}    sk = SCAN#METADATA
  GSI2: pk=ORG#{org_id}  sk=SCAN#{id}
"""

from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
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
        """Return the scan metadata item for the given ID, or None if not found."""
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
        """Delete the scan metadata item for the given ID."""
        self._table.delete_item(pk=f"SCAN#{scan_id}", sk="SCAN#METADATA")

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
        """Delete a single scan→company association item."""
        self._table.delete_item(pk=f"SCAN#{scan_id}", sk=f"COMPANY#{company_id}")

    def delete_all_company_links(self, scan_id: str) -> None:
        """Delete all scan→company association items for the given scan."""
        links = self.get_scan_companies(scan_id)
        # Match the defensive guard in scan_handlers:_handle_scan_status —
        # the link record's `company_id` is guaranteed by `link_company`
        # but skip any anomaly defensively rather than raising KeyError.
        keys = [
            {"pk": f"SCAN#{scan_id}", "sk": f"COMPANY#{link['company_id']}"}
            for link in links
            if link.get("company_id")
        ]
        if keys:
            self._table.batch_delete(keys)

    def get_scan_companies(self, scan_id: str) -> list[dict[str, Any]]:
        """Return all company association items linked to the given scan ID."""
        return self._table.query(pk=f"SCAN#{scan_id}", sk_prefix="COMPANY#")

    def find_recent_by_org(self, org_id: str, limit: int | None = 10) -> list[dict[str, Any]]:
        """Return scans for the given organisation, sorted by created_at descending.

        Pass limit=None to return all scans (useful for deriving count).
        """
        items, _cursor = self._table.query_gsi(
            index_name="GSI2",
            pk_attr="GSI2PK",
            pk_value=f"ORG#{org_id}",
        )
        for item in items:
            self._deserialize(item)
        items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return items[:limit] if limit is not None else items

    @staticmethod
    def _deserialize(item: dict[str, Any]) -> None:
        if "portfolio_companies" in item and isinstance(item["portfolio_companies"], str):
            item["portfolio_companies"] = json.loads(item["portfolio_companies"])

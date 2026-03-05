"""DynamoDB scan tracking repository.

Single-table keys:
  pk = SCAN#{id}    sk = SCAN#METADATA
  GSI2: pk=ORG#{org_id}  sk=SCAN#{id}
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from src.repositories.dynamodb.client import DynamoDBTable


class DynamoDBScanRepository:
    """Repository for scan documents in DynamoDB."""

    def __init__(self, table: DynamoDBTable) -> None:
        self._table = table

    def create(self, scan: dict[str, Any]) -> str:
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
        item = self._table.get_item(pk=f"SCAN#{scan_id}", sk="SCAN#METADATA")
        if item:
            self._deserialize(item)
        return item

    def update(self, scan_id: str, changes: dict[str, Any]) -> None:
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
        self._table.delete_item(pk=f"SCAN#{scan_id}", sk="SCAN#METADATA")

    def find_by_org(self, org_id: str) -> list[dict[str, Any]]:
        items = self._table.query_gsi(
            index_name="GSI2",
            pk_attr="GSI2PK",
            pk_value=f"ORG#{org_id}",
        )
        for item in items:
            self._deserialize(item)
        return items

    def link_company(self, scan_id: str, company_id: str, company_name: str) -> None:
        """Create a scan→company association item."""
        self._table.put_item({
            "pk": f"SCAN#{scan_id}",
            "sk": f"COMPANY#{company_id}",
            "entity_type": "scan_company",
            "company_id": company_id,
            "company_name": company_name,
        })

    def get_scan_companies(self, scan_id: str) -> list[dict[str, Any]]:
        return self._table.query(pk=f"SCAN#{scan_id}", sk_prefix="COMPANY#")

    @staticmethod
    def _deserialize(item: dict[str, Any]) -> None:
        if "portfolio_companies" in item and isinstance(item["portfolio_companies"], str):
            try:
                item["portfolio_companies"] = json.loads(item["portfolio_companies"])
            except json.JSONDecodeError:
                item["portfolio_companies"] = []

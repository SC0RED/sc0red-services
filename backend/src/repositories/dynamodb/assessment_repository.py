"""DynamoDB implementation of assessment storage.

Single-table keys:
  Assessment: pk=ASSESSMENT#{id}  sk=ASSESSMENT#METADATA
  RiskScore:  pk=ASSESSMENT#{id}  sk=RISK#{category}
  Opportunity: pk=ASSESSMENT#{id}  sk=OPP#{sort_order}
  GSI3: pk=COMPANY#{company_id}  (for company→assessment lookup)
"""

from __future__ import annotations

import contextlib
import json
import uuid
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.repositories.dynamodb.client import DynamoDBTable


class DynamoDBAssessmentRepository:
    """Repository for assessments, risk scores, and opportunities in DynamoDB."""

    def __init__(self, table: DynamoDBTable) -> None:
        self._table = table

    # ── Assessment operations ────────────────────────────────────────

    def get_by_id(self, assessment_id: str) -> dict[str, Any] | None:
        """Return the assessment metadata item for the given ID, or None if not found."""
        return self._table.get_item(
            pk=f"ASSESSMENT#{assessment_id}",
            sk="ASSESSMENT#METADATA",
        )

    def save(self, assessment: dict[str, Any]) -> str:
        """Persist a full assessment document and return its ID."""
        assessment_id = assessment.get("id") or str(uuid.uuid4())
        item = {
            "pk": f"ASSESSMENT#{assessment_id}",
            "sk": "ASSESSMENT#METADATA",
            "id": assessment_id,
            "entity_type": "assessment",
            **{k: v for k, v in assessment.items() if k != "id"},
        }

        # Serialize list/dict fields
        for field in ("top_risks",):
            if field in item and isinstance(item[field], list):
                item[field] = json.dumps(item[field])

        # GSI3 for company→assessment lookup
        company_id = assessment.get("company_id")
        if company_id:
            item["GSI3PK"] = f"COMPANY#{company_id}"
            item["GSI3SK"] = f"ASSESSMENT#{assessment_id}"

        self._table.put_item(item)
        return assessment_id

    def save_assessment(self, assessment_id: str, doc: dict[str, Any]) -> None:
        """Save an assessment document under the given ID."""
        doc["id"] = assessment_id
        self.save(doc)

    def find_by_company(self, company_id: str) -> list[dict[str, Any]]:
        """Return all assessments associated with the given company ID."""
        return self._table.query_gsi(
            index_name="GSI3",
            pk_attr="GSI3PK",
            pk_value=f"COMPANY#{company_id}",
        )

    def delete(self, assessment_id: str) -> None:
        """Delete an assessment and all its child items (risk scores, opportunities)."""
        # Delete all items under this assessment (metadata, risk scores, opportunities)
        items = self._table.query(pk=f"ASSESSMENT#{assessment_id}")
        keys = [{"pk": item["pk"], "sk": item["sk"]} for item in items]
        self._table.batch_delete(keys)

    # ── Risk score operations ────────────────────────────────────────

    def save_risk_score(self, assessment_id: str, category: str, data: dict[str, Any]) -> None:
        """Persist a single risk score item for the given assessment and category."""
        item = {
            "pk": f"ASSESSMENT#{assessment_id}",
            "sk": f"RISK#{category}",
            "entity_type": "risk_score",
            "assessment_id": assessment_id,
            "category": category,
            **data,
        }
        self._table.put_item(item)

    def get_risk_scores(self, assessment_id: str) -> list[dict[str, Any]]:
        """Return all risk score items for the given assessment ID."""
        return self._table.query(
            pk=f"ASSESSMENT#{assessment_id}",
            sk_prefix="RISK#",
        )

    # ── Opportunity operations ───────────────────────────────────────

    def save_opportunity(self, assessment_id: str, sort_order: int, data: dict[str, Any]) -> None:
        """Persist a single opportunity item for the given assessment."""
        item = {
            "pk": f"ASSESSMENT#{assessment_id}",
            "sk": f"OPP#{sort_order:04d}",
            "entity_type": "opportunity",
            "assessment_id": assessment_id,
            "sort_order": sort_order,
        }

        # Serialize complex fields
        for key, value in data.items():
            if isinstance(value, (list, dict)):
                item[key] = json.dumps(value)
            else:
                item[key] = value

        self._table.put_item(item)

    def get_opportunities(self, assessment_id: str) -> list[dict[str, Any]]:
        """Return all opportunity items for the given assessment ID."""
        items = self._table.query(
            pk=f"ASSESSMENT#{assessment_id}",
            sk_prefix="OPP#",
        )
        # Deserialize JSON fields
        for item in items:
            for field in ("implementation_steps", "related_services"):
                if field in item and isinstance(item[field], str):
                    with contextlib.suppress(json.JSONDecodeError):
                        item[field] = json.loads(item[field])
        return items

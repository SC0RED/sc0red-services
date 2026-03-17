"""DynamoDB implementation of assessment storage.

Single-table keys:
  Assessment:  pk=ASSESSMENT#{id}  sk=ASSESSMENT#METADATA
  RiskScore:   pk=ASSESSMENT#{id}  sk=RISK#{category}
  Opportunity: pk=ASSESSMENT#{id}  sk=OPP#{sort_order}
  EbitdaTree:  pk=ASSESSMENT#{id}  sk=EBITDA_TREE
  Document:    pk=ASSESSMENT#{id}  sk=DOC#{doc_id}
  GSI3: pk=COMPANY#{company_id}  (for company→assessment lookup)
"""

from __future__ import annotations

import contextlib
import json
import uuid
from typing import TYPE_CHECKING, Any

from src.documents.extract_text import join_document_texts

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

    def batch_save_risk_scores(self, assessment_id: str, scores: list[dict[str, Any]]) -> None:
        """Persist multiple risk score items in a single batch write."""
        items = [
            {
                "pk": f"ASSESSMENT#{assessment_id}",
                "sk": f"RISK#{score['category']}",
                "entity_type": "risk_score",
                "assessment_id": assessment_id,
                "category": score["category"],
                "score": score["score"],
                "rationale": score["rationale"],
            }
            for score in scores
        ]
        self._table.batch_write(items)

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

    def batch_save_opportunities(
        self, assessment_id: str, opportunities: list[dict[str, Any]]
    ) -> None:
        """Persist multiple opportunity items in a single batch write."""
        items = []
        for i, data in enumerate(opportunities):
            item: dict[str, Any] = {
                "pk": f"ASSESSMENT#{assessment_id}",
                "sk": f"OPP#{i:04d}",
                "entity_type": "opportunity",
                "assessment_id": assessment_id,
                "sort_order": i,
            }
            for key, value in data.items():
                if isinstance(value, (list, dict)):
                    item[key] = json.dumps(value)
                else:
                    item[key] = value
            items.append(item)
        self._table.batch_write(items)

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

    # ── EBITDA tree operations ────────────────────────────────────────

    def save_ebitda_tree(self, assessment_id: str, data: dict[str, Any]) -> None:
        """Persist the EBITDA decomposition tree for the given assessment."""
        item = {
            "pk": f"ASSESSMENT#{assessment_id}",
            "sk": "EBITDA_TREE",
            "entity_type": "ebitda_tree",
            "assessment_id": assessment_id,
            "tree_data": json.dumps(data["tree_data"]),
            "revenue_estimate": data["revenue_estimate"],
            "ebitda_estimate": data["ebitda_estimate"],
            "business_model_summary": data["business_model_summary"],
        }
        self._table.put_item(item)

    def get_ebitda_tree(self, assessment_id: str) -> dict[str, Any] | None:
        """Return the EBITDA tree for the given assessment, or None if not found."""
        item = self._table.get_item(
            pk=f"ASSESSMENT#{assessment_id}",
            sk="EBITDA_TREE",
        )
        if not item:
            return None

        tree_data = item.get("tree_data", "[]")
        if isinstance(tree_data, str):
            with contextlib.suppress(json.JSONDecodeError):
                tree_data = json.loads(tree_data)

        return {
            "treeData": tree_data,
            "revenueEstimate": item["revenue_estimate"],
            "ebitdaEstimate": item["ebitda_estimate"],
            "businessModelSummary": item["business_model_summary"],
        }

    # ── Document operations ────────────────────────────────────────────

    def save_document(self, assessment_id: str, document: dict[str, Any]) -> None:
        """Persist a document metadata + extracted text item for the given assessment."""
        item = {
            "pk": f"ASSESSMENT#{assessment_id}",
            "sk": f"DOC#{document['id']}",
            "entity_type": "document",
            "assessment_id": assessment_id,
            "id": document["id"],
            "filename": document["filename"],
            "file_type": document["file_type"],
            "extracted_text": document["extracted_text"],
            "char_count": document["char_count"],
            "uploaded_at": document["uploaded_at"],
        }
        self._table.put_item(item)

    def get_documents(self, assessment_id: str) -> list[dict[str, Any]]:
        """Return all document items for the given assessment ID."""
        items = self._table.query(
            pk=f"ASSESSMENT#{assessment_id}",
            sk_prefix="DOC#",
        )
        return [
            {
                "id": item["id"],
                "filename": item["filename"],
                "fileType": item["file_type"],
                "charCount": item["char_count"],
                "uploadedAt": item["uploaded_at"],
            }
            for item in items
        ]

    def delete_document(self, assessment_id: str, document_id: str) -> None:
        """Delete a single document from the given assessment."""
        self._table.delete_item(
            pk=f"ASSESSMENT#{assessment_id}",
            sk=f"DOC#{document_id}",
        )

    def get_combined_document_text(self, assessment_id: str) -> str:
        """Fetch all documents and return combined extracted text, capped at MAX_CHARS_COMBINED."""
        items = self._table.query(
            pk=f"ASSESSMENT#{assessment_id}",
            sk_prefix="DOC#",
        )
        texts = [item["extracted_text"] for item in items]
        if not texts:
            return ""
        return join_document_texts(texts)

    def delete_analysis_results(self, assessment_id: str) -> None:
        """Delete risk scores, opportunities, and EBITDA tree but keep documents and metadata."""
        items = self._table.query(pk=f"ASSESSMENT#{assessment_id}")
        keys_to_delete = [
            {"pk": item["pk"], "sk": item["sk"]}
            for item in items
            if item["sk"].startswith(("RISK#", "OPP#", "EBITDA_TREE"))
        ]
        if keys_to_delete:
            self._table.batch_delete(keys_to_delete)

"""DynamoDB implementation of assessment storage.

Single-table keys:
  Assessment:  pk=ASSESSMENT#{id}  sk=ASSESSMENT#METADATA
  RiskScore:   pk=ASSESSMENT#{id}  sk=RISK#{category}
  Opportunity: pk=ASSESSMENT#{id}  sk=OPP#{sort_order}
  EbitdaTree:  pk=ASSESSMENT#{id}  sk=EBITDA_TREE
  Document:    pk=ASSESSMENT#{id}  sk=DOC#{doc_id}
  GSI3: pk=COMPANY#{company_id}  (for company→assessment lookup)

Soft-delete contract (see `soft-delete-recovery` change):
  Read methods filter out tombstoned records (where `deleted_at` is
  set) by default. Methods that intentionally surface tombstoned
  records — used by the engineer-assisted recovery path and by the
  Phase 2 admin UI — carry a `_with_deleted` suffix. Sub-record
  getters (risk scores, opportunities, EBITDA tree, value chain,
  documents) inherit the parent assessment's tombstone — once the
  metadata item is tombstoned, the whole assessment is invisible
  to live reads. We do NOT tombstone every child item individually;
  it would multiply the write volume with no behavioural gain.
"""

from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING, Any

from src.documents.extract_text import join_document_texts
from src.repositories.dynamodb import _assessment_subrecord_ops
from src.repositories.dynamodb._tombstones import (
    DELETED_AT_FIELD,
    TTL_FIELD,
    filter_live,
    is_live,
    tombstone_attributes,
)

if TYPE_CHECKING:
    from src.repositories.dynamodb.client import DynamoDBTable


class DynamoDBAssessmentRepository:
    """Repository for assessments, risk scores, and opportunities in DynamoDB."""

    def __init__(self, table: DynamoDBTable) -> None:
        self._table = table

    # ── Assessment operations ────────────────────────────────────────

    def get_by_id(self, assessment_id: str) -> dict[str, Any] | None:
        """Return the assessment metadata item, or None if not found OR tombstoned.

        Treats tombstoned and not-found identically — callers that need
        to inspect tombstoned records (recovery flows) use
        `get_by_id_with_deleted`.
        """
        item = self._table.get_item(
            pk=f"ASSESSMENT#{assessment_id}",
            sk="ASSESSMENT#METADATA",
        )
        return item if is_live(item) else None

    def get_by_id_with_deleted(self, assessment_id: str) -> dict[str, Any] | None:
        """Return the assessment metadata item EVEN IF tombstoned.

        Recovery-aware variant for the restore path. Returns None only
        when the record genuinely doesn't exist.
        """
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

    def find_by_company(self, company_id: str) -> list[dict[str, Any]]:
        """Return live (non-tombstoned) assessments for the given company ID."""
        items, _cursor = self._table.query_gsi(
            index_name="GSI3",
            pk_attr="GSI3PK",
            pk_value=f"COMPANY#{company_id}",
        )
        return filter_live(items)

    def find_by_company_with_deleted(self, company_id: str) -> list[dict[str, Any]]:
        """Return ALL assessments (including tombstoned) for the given company ID.

        Recovery-aware variant. Used by the engineer-assisted recovery
        path to surface every assessment that needs restoring when a
        company is restored.
        """
        items, _cursor = self._table.query_gsi(
            index_name="GSI3",
            pk_attr="GSI3PK",
            pk_value=f"COMPANY#{company_id}",
        )
        return items

    def delete(self, assessment_id: str) -> None:
        """Hard-delete an assessment and all its child items.

        Reserved for cleanup-script and test paths; production handlers
        use `tombstone()` so the record is recoverable for 90 days.
        """
        # Delete all items under this assessment (metadata, risk scores, opportunities)
        items = self._table.query(pk=f"ASSESSMENT#{assessment_id}")
        keys = [{"pk": item["pk"], "sk": item["sk"]} for item in items]
        self._table.batch_delete(keys)

    def tombstone(self, assessment_id: str, *, actor_id: str | None = None) -> None:
        """Mark the assessment metadata as soft-deleted with a 90-day TTL.

        Only the metadata item is tombstoned — risk scores,
        opportunities, EBITDA tree, value chain, and documents remain
        in the table untouched. Reads of those sub-records are gated
        through `get_by_id` (callers fetch the assessment first); once
        the metadata is tombstoned, the assessment is invisible to
        live traffic.

        Pass ``actor_id`` to attribute the delete to a user — see
        `DynamoDBCompanyRepository.tombstone` for full semantics.

        DynamoDB TTL evicts the metadata row 90 days after `deleted_at`.
        We rely on a follow-up cleanup pass to drain orphan child
        items after TTL eviction; the cleanup script's existing
        orphan-detection logic catches them.
        """
        self._table.update_item(
            pk=f"ASSESSMENT#{assessment_id}",
            sk="ASSESSMENT#METADATA",
            updates=tombstone_attributes(actor_id=actor_id),
        )

    def restore(self, assessment_id: str) -> None:
        """Clear the tombstone markers, making the assessment live again.

        Sub-records (risk scores, opportunities, etc.) are unaffected by
        tombstone/restore — they were never tombstoned.

        Guarded by ``require_exists=True`` to surface the TTL-eviction
        race (see `DynamoDBCompanyRepository.restore` for the full
        rationale).
        """
        self._table.remove_attributes(
            pk=f"ASSESSMENT#{assessment_id}",
            sk="ASSESSMENT#METADATA",
            attribute_names=[DELETED_AT_FIELD, TTL_FIELD],
            require_exists=True,
        )

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
        # Deserialize JSON fields; scrub the removed `related_services` attribute
        # from historical rows so it never leaks to the API response.
        for item in items:
            item.pop("related_services", None)
            if "implementation_steps" in item and isinstance(item["implementation_steps"], str):
                item["implementation_steps"] = json.loads(item["implementation_steps"])
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
            "grounded": data["grounded"],
            "insufficient_data_reason": data["insufficient_data_reason"],
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
            tree_data = json.loads(tree_data)

        return {
            "treeData": tree_data,
            "revenueEstimate": item["revenue_estimate"],
            "ebitdaEstimate": item["ebitda_estimate"],
            "businessModelSummary": item["business_model_summary"],
            # Records stored before the grounding contract default to grounded
            # (they carry real tree_data). insufficient_data_reason is null then.
            "grounded": item.get("grounded", True),
            "insufficientDataReason": item.get("insufficient_data_reason"),
        }

    # ── Value Chain operations (delegates to `_assessment_subrecord_ops.py`) ──

    def save_value_chain(self, assessment_id: str, data: dict[str, Any]) -> None:
        """Persist the value chain analysis for the given assessment."""
        _assessment_subrecord_ops.save_value_chain(self._table, assessment_id, data)

    def get_value_chain(self, assessment_id: str) -> dict[str, Any] | None:
        """Return the value chain for the given assessment, or None if not found."""
        return _assessment_subrecord_ops.get_value_chain(self._table, assessment_id)

    # ── Strategy Map operations (delegates to `_assessment_subrecord_ops.py`) ──

    def save_strategy_map(self, assessment_id: str, data: dict[str, Any]) -> None:
        """Persist the AI-generated strategy map for the given assessment."""
        _assessment_subrecord_ops.save_strategy_map(self._table, assessment_id, data)

    def clear_strategy_map(self, assessment_id: str) -> None:
        """Remove the persisted strategy map for the given assessment.

        Called by the re-analyse handler to invalidate a stale map
        before regenerating the underlying diagnosis. Idempotent —
        safe to call when no map exists.
        """
        _assessment_subrecord_ops.clear_strategy_map(self._table, assessment_id)

    def get_strategy_map(self, assessment_id: str) -> dict[str, Any] | None:
        """Return the strategy map for the given assessment, or None if not found."""
        return _assessment_subrecord_ops.get_strategy_map(self._table, assessment_id)

    # ── PDF Export operations (delegates to `_assessment_subrecord_ops.py`) ──

    def save_pdf_export(self, assessment_id: str, data: dict[str, Any]) -> None:
        """Persist the PDF export sub-record (rendering / ready / failed)."""
        _assessment_subrecord_ops.save_pdf_export(self._table, assessment_id, data)

    def clear_pdf_export(self, assessment_id: str) -> None:
        """Remove the PDF export sub-record. Idempotent."""
        _assessment_subrecord_ops.clear_pdf_export(self._table, assessment_id)

    def get_pdf_export(self, assessment_id: str) -> dict[str, Any] | None:
        """Return the PDF export sub-record, or None if not found."""
        return _assessment_subrecord_ops.get_pdf_export(self._table, assessment_id)

    # ── Document operations (delegates to `_assessment_subrecord_ops.py`) ──

    def save_document(self, assessment_id: str, document: dict[str, Any]) -> None:
        """Persist a document metadata + extracted text item."""
        _assessment_subrecord_ops.save_document(self._table, assessment_id, document)

    def get_documents(self, assessment_id: str) -> list[dict[str, Any]]:
        """Return all document items for the given assessment ID."""
        return _assessment_subrecord_ops.get_documents(self._table, assessment_id)

    def delete_document(self, assessment_id: str, document_id: str) -> None:
        """Delete a single document from the given assessment."""
        _assessment_subrecord_ops.delete_document(self._table, assessment_id, document_id)

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

    # Sort-key shapes the analysis-results section of an assessment uses:
    #   - PREFIX_SK_PATTERNS: legitimately prefix-keyed (`RISK#cat`, `OPP#0`).
    #   - EXACT_SK_VALUES: single-row blobs (one ebitda tree, one value chain,
    #     one strategy map per assessment).
    # Splitting the two prevents `startswith` from matching a future versioned
    # sk like `STRATEGY_MAP_V2` or `EBITDA_TREE_HISTORICAL` and silently
    # over-deleting. Exact-match strings stay exact-match.
    _PREFIX_SK_PATTERNS = ("RISK#", "OPP#")
    _EXACT_SK_VALUES = frozenset({"EBITDA_TREE", "VALUE_CHAIN", "STRATEGY_MAP", "PDF_EXPORT"})

    def delete_analysis_results(self, assessment_id: str) -> None:
        """Delete risk scores, opps, EBITDA, value chain, strategy map; keep docs + metadata."""
        items = self._table.query(pk=f"ASSESSMENT#{assessment_id}")
        keys_to_delete = [
            {"pk": item["pk"], "sk": item["sk"]}
            for item in items
            if item["sk"].startswith(self._PREFIX_SK_PATTERNS)
            or item["sk"] in self._EXACT_SK_VALUES
        ]
        if keys_to_delete:
            self._table.batch_delete(keys_to_delete)

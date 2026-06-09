"""Sub-record persistence helpers for the assessment repository.

Extracted from `assessment_repository.py` to keep that file under
the 400-line budget. Currently holds strategy-map and value-chain
ops (the two newest sub-records), with the same JSON-blob-on-a-
single-item shape — `pk = ASSESSMENT#{id}`, distinct `sk`,
`payload` (or named) attribute holding the camelCase data the API
returns directly to the frontend.

Operations are exposed as free functions taking the `DynamoDBTable`
client; the repository class delegates to them.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.repositories.dynamodb.client import DynamoDBTable


# Sort key for the per-analysis cached PDF export record (one row per analysis).
PDF_EXPORT_SK = "PDF_EXPORT"


def save_strategy_map(table: DynamoDBTable, assessment_id: str, data: dict[str, Any]) -> None:
    """Persist the AI-generated strategy map for the given assessment.

    The full strategy map is JSON-encoded into a single `payload`
    attribute. This keeps the persistence simple — the map is read
    as one blob rather than reassembled from many sub-items. The
    camelCase shape produced here is what the API returns directly
    to the frontend (no further conversion in `analysis_payload`).
    """
    item = {
        "pk": f"ASSESSMENT#{assessment_id}",
        "sk": "STRATEGY_MAP",
        "entity_type": "strategy_map",
        "assessment_id": assessment_id,
        "payload": json.dumps(data),
    }
    table.put_item(item)


def clear_strategy_map(table: DynamoDBTable, assessment_id: str) -> None:
    """Remove the persisted strategy map for the given assessment.

    Used by the re-analyse handler to invalidate a stale map before
    the analysis pipeline regenerates the underlying diagnosis.
    Idempotent — safe to call when no map exists.
    """
    table.delete_item(pk=f"ASSESSMENT#{assessment_id}", sk="STRATEGY_MAP")


def get_strategy_map(table: DynamoDBTable, assessment_id: str) -> dict[str, Any] | None:
    """Return the strategy map for the given assessment, or None if not found.

    Raises `KeyError` if the STRATEGY_MAP item exists but has no
    `payload` attribute — that indicates a corrupt or partially-
    written record, and silently returning `{}` would push the
    failure into the frontend (which conditionally renders on
    truthy `strategyMap`). Fail-fast here so the error surfaces in
    CloudWatch.
    """
    item = table.get_item(
        pk=f"ASSESSMENT#{assessment_id}",
        sk="STRATEGY_MAP",
    )
    if not item:
        return None

    payload = item["payload"]
    if isinstance(payload, str):
        payload = json.loads(payload)

    return payload


# ── Value Chain ────────────────────────────────────────────────────────────


def save_value_chain(table: DynamoDBTable, assessment_id: str, data: dict[str, Any]) -> None:
    """Persist the value chain analysis for the given assessment."""
    item = {
        "pk": f"ASSESSMENT#{assessment_id}",
        "sk": "VALUE_CHAIN",
        "entity_type": "value_chain",
        "assessment_id": assessment_id,
        "steps": json.dumps(data["steps"]),
        "summary": data["summary"],
        "grounded": data["grounded"],
        "insufficient_data_reason": data["insufficient_data_reason"],
        "provenance_basis": data["provenance_basis"],
    }
    table.put_item(item)


def get_value_chain(table: DynamoDBTable, assessment_id: str) -> dict[str, Any] | None:
    """Return the value chain for the given assessment, or None if not found.

    Raises `KeyError` if the VALUE_CHAIN item exists but is missing
    `steps` or `summary` — that indicates a corrupt or partially-
    written record. Same fail-fast posture as `get_strategy_map`
    (per CLAUDE.md "no silent fallback on required schema fields"):
    a missing field on a present record is a programming bug or
    write-path corruption, not a normal return path. Surface it
    in CloudWatch rather than letting the frontend render a
    half-empty value chain.
    """
    item = table.get_item(
        pk=f"ASSESSMENT#{assessment_id}",
        sk="VALUE_CHAIN",
    )
    if not item:
        return None

    steps = item["steps"]
    if isinstance(steps, str):
        steps = json.loads(steps)

    return {
        "steps": steps,
        "summary": item["summary"],
        # Records stored before the grounding contract default to grounded
        # (they carry real steps). The reason/basis are null then.
        "grounded": item.get("grounded", True),
        "insufficientDataReason": item.get("insufficient_data_reason"),
        "provenanceBasis": item.get("provenance_basis"),
    }


# ── PDF Export ─────────────────────────────────────────────────────────────


def save_pdf_export(table: DynamoDBTable, assessment_id: str, data: dict[str, Any]) -> None:
    """Persist a PDF export sub-record for the given assessment.

    Used by the POST endpoint to write the initial ``rendering`` state
    with a fresh ``started_at`` anchor. The PDF Lambda subsequently
    transitions the row to ``ready`` (or ``failed``) via a conditional
    UpdateItem that guards on this ``started_at`` timestamp, so a
    concurrent re-analyse that clears the row can't be silently
    overwritten by a stale render.

    Expected keys in ``data``: ``status``, ``s3_key``, ``started_at``
    (ISO8601 string), and optionally ``generated_at`` or ``error``.
    """
    item: dict[str, Any] = {
        "pk": f"ASSESSMENT#{assessment_id}",
        "sk": PDF_EXPORT_SK,
        "entity_type": "pdf_export",
        "assessment_id": assessment_id,
        "status": data["status"],
        "s3_key": data["s3_key"],
        "started_at": data["started_at"],
    }
    if "generated_at" in data and data["generated_at"] is not None:
        item["generated_at"] = data["generated_at"]
    if "error" in data and data["error"] is not None:
        item["error"] = data["error"]
    table.put_item(item)


def clear_pdf_export(table: DynamoDBTable, assessment_id: str) -> None:
    """Remove the PDF export sub-record for the given assessment.

    Called by the re-analyse handler. Does NOT delete the S3 object —
    callers that own object-lifecycle responsibilities (re-analyse)
    issue ``s3:DeleteObject`` separately. Idempotent: a no-op when no
    record exists.
    """
    table.delete_item(pk=f"ASSESSMENT#{assessment_id}", sk=PDF_EXPORT_SK)


def get_pdf_export(table: DynamoDBTable, assessment_id: str) -> dict[str, Any] | None:
    """Return the PDF export sub-record, or ``None`` if not present.

    Returns the raw DynamoDB attribute shape (``status``, ``s3_key``,
    ``started_at``, optional ``generated_at`` / ``error``). Callers
    parse the timestamps as needed.
    """
    item = table.get_item(
        pk=f"ASSESSMENT#{assessment_id}",
        sk=PDF_EXPORT_SK,
    )
    if not item:
        return None

    result: dict[str, Any] = {
        "status": item["status"],
        "s3_key": item["s3_key"],
        "started_at": item["started_at"],
    }
    if "generated_at" in item:
        result["generated_at"] = item["generated_at"]
    if "error" in item:
        result["error"] = item["error"]
    return result


# ── Documents ──────────────────────────────────────────────────────────────


def save_document(table: DynamoDBTable, assessment_id: str, document: dict[str, Any]) -> None:
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
    table.put_item(item)


def get_documents(table: DynamoDBTable, assessment_id: str) -> list[dict[str, Any]]:
    """Return all document items for the given assessment ID."""
    items = table.query(pk=f"ASSESSMENT#{assessment_id}", sk_prefix="DOC#")
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


def delete_document(table: DynamoDBTable, assessment_id: str, document_id: str) -> None:
    """Delete a single document from the given assessment."""
    table.delete_item(pk=f"ASSESSMENT#{assessment_id}", sk=f"DOC#{document_id}")

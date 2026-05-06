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

    Used by the re-analyse handler (per the strategy-map-on-demand spec) to
    invalidate a stale map before the analysis pipeline regenerates the
    underlying diagnosis. Idempotent — safe to call when no map exists.
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

    return {"steps": steps, "summary": item["summary"]}

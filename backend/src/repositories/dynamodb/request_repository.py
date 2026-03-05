"""DynamoDB implementation of pipeline request tracking.

Single-table keys:
  pk = REQUEST#{id}    sk = REQUEST#STATUS
"""

from __future__ import annotations

import time
import uuid
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.repositories.dynamodb.client import DynamoDBTable


class DynamoDBRequestRepository:
    """Repository for pipeline request tracking documents."""

    def __init__(self, table: DynamoDBTable) -> None:
        self._table = table

    def create(self, request: dict[str, Any]) -> str:
        """Persist a new pipeline request document and return its ID."""
        request_id = request.get("request_id") or str(uuid.uuid4())
        item = {
            "pk": f"REQUEST#{request_id}",
            "sk": "REQUEST#STATUS",
            "request_id": request_id,
            "entity_type": "request",
            "created_at": str(int(time.time())),
            **{k: v for k, v in request.items() if k != "request_id"},
        }
        self._table.put_item(item)
        return request_id

    def update_status(self, request_id: str, update_data: dict[str, Any]) -> None:
        """Apply attribute-level updates to an existing request status item."""
        self._table.update_item(
            pk=f"REQUEST#{request_id}",
            sk="REQUEST#STATUS",
            updates=update_data,
        )

    def add_details(self, request_id: str, details: dict[str, Any]) -> None:
        """Merge detail fields into the request document."""
        flat = {}
        for key, value in details.items():
            flat[f"detail_{key}"] = value
        self._table.update_item(
            pk=f"REQUEST#{request_id}",
            sk="REQUEST#STATUS",
            updates=flat,
        )

    def find_by_request_id(self, request_id: str) -> dict[str, Any] | None:
        """Return the request status item for the given ID, or None if not found."""
        return self._table.get_item(
            pk=f"REQUEST#{request_id}",
            sk="REQUEST#STATUS",
        )

    def delete(self, request_id: str) -> None:
        """Delete the request status item for the given ID."""
        self._table.delete_item(
            pk=f"REQUEST#{request_id}",
            sk="REQUEST#STATUS",
        )

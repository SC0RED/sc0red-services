"""DynamoDB user and organization repositories.

Single-table keys:
  User: pk=USER#{id}  sk=USER#METADATA  GSI4: pk=EMAIL#{email}
  Organization: pk=ORG#{id}  sk=ORG#METADATA
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.repositories.dynamodb.client import DynamoDBTable


class DynamoDBUserRepository:
    """Repository for user entities in DynamoDB."""

    def __init__(self, table: DynamoDBTable) -> None:
        self._table = table

    def get_by_id(self, user_id: str) -> dict[str, Any] | None:
        """Return the user metadata item for the given ID, or None if not found."""
        return self._table.get_item(pk=f"USER#{user_id}", sk="USER#METADATA")

    def find_by_email(self, email: str) -> dict[str, Any] | None:
        """Return the user item matching the given email address, or None if not found."""
        items = self._table.query_gsi(
            index_name="GSI4",
            pk_attr="GSI4PK",
            pk_value=f"EMAIL#{email}",
        )
        return items[0] if items else None

    def create(self, user: dict[str, Any]) -> str:
        """Persist a new user document and return its ID."""
        user_id = user.get("id") or str(uuid.uuid4())
        item = {
            "pk": f"USER#{user_id}",
            "sk": "USER#METADATA",
            "id": user_id,
            "entity_type": "user",
            "GSI4PK": f"EMAIL#{user.get('email', '')}",
            "GSI4SK": f"USER#{user_id}",
            **{k: v for k, v in user.items() if k != "id"},
        }
        self._table.put_item(item)
        return user_id

    def has_email(self, email: str) -> bool:
        """Return True if a user with the given email address exists."""
        return self.find_by_email(email) is not None


class DynamoDBOrganizationRepository:
    """Repository for organization entities in DynamoDB."""

    def __init__(self, table: DynamoDBTable) -> None:
        self._table = table

    def get_by_id(self, org_id: str) -> dict[str, Any] | None:
        """Return the organisation metadata item for the given ID, or None if not found."""
        return self._table.get_item(pk=f"ORG#{org_id}", sk="ORG#METADATA")

    def create(self, org: dict[str, Any]) -> str:
        """Persist a new organisation document and return its ID."""
        org_id = org.get("id") or str(uuid.uuid4())
        item = {
            "pk": f"ORG#{org_id}",
            "sk": "ORG#METADATA",
            "id": org_id,
            "entity_type": "organization",
            **{k: v for k, v in org.items() if k != "id"},
        }
        self._table.put_item(item)
        return org_id

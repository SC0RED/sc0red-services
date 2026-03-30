"""DynamoDB user and organization repositories.

Single-table keys:
  User: pk=USER#{id}  sk=USER#METADATA  GSI4: pk=EMAIL#{email}
  Organization: pk=ORG#{id}  sk=ORG#METADATA
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import bcrypt

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
        # GSI1 for org-level user queries
        org_id = user.get("org_id")
        if org_id:
            item["GSI1PK"] = f"ORG#{org_id}"
            item["GSI1SK"] = f"USER#{user_id}"
        self._table.put_item(item)
        return user_id

    def find_by_org(self, org_id: str) -> list[dict[str, Any]]:
        """Return all users belonging to the given organisation."""
        return self._table.query_gsi(
            index_name="GSI1",
            pk_attr="GSI1PK",
            pk_value=f"ORG#{org_id}",
            sk_attr="GSI1SK",
            sk_prefix="USER#",
        )

    def delete(self, user_id: str) -> None:
        """Delete a user by ID."""
        self._table.delete_item(pk=f"USER#{user_id}", sk="USER#METADATA")

    def has_email(self, email: str) -> bool:
        """Return True if a user with the given email address exists."""
        return self.find_by_email(email) is not None

    def verify_password(self, email: str, password: str) -> dict[str, Any] | None:
        """Verify credentials and return user info if valid, None otherwise."""
        user = self.find_by_email(email)
        if not user:
            return None

        stored_hash = user.get("password_hash")
        if not stored_hash:
            raise RuntimeError(f"User record for {email!r} is missing password_hash — corrupt data")

        if not bcrypt.checkpw(password.encode(), stored_hash.encode()):
            return None

        return {
            "id": user.get("id", ""),
            "email": user.get("email", ""),
            "name": user.get("name", ""),
            "orgId": user.get("org_id", ""),
            "role": user.get("role", "analyst"),
        }


class DynamoDBInvitationRepository:
    """Repository for org invitation records in DynamoDB.

    Single-table keys:
      pk = ORG#{org_id}  sk = INVITE#{id}
      GSI4: pk = EMAIL#{email}  sk = INVITE#{id}
    """

    def __init__(self, table: DynamoDBTable) -> None:
        self._table = table

    def create(self, invitation: dict[str, Any]) -> str:
        """Persist a new invitation and return its ID."""
        invite_id = invitation.get("id") or str(uuid.uuid4())
        org_id = invitation["org_id"]
        email = invitation.get("email", "")
        item = {
            "pk": f"ORG#{org_id}",
            "sk": f"INVITE#{invite_id}",
            "id": invite_id,
            "entity_type": "invitation",
            "GSI4PK": f"EMAIL#{email}",
            "GSI4SK": f"INVITE#{invite_id}",
            **{k: v for k, v in invitation.items() if k not in ("id",)},
        }
        self._table.put_item(item)
        return invite_id

    def find_by_org(self, org_id: str) -> list[dict[str, Any]]:
        """Return all invitations for the given organisation."""
        return self._table.query(pk=f"ORG#{org_id}", sk_prefix="INVITE#")

    def find_by_email(self, email: str) -> list[dict[str, Any]]:
        """Return all invitations for the given email address."""
        return self._table.query_gsi(
            index_name="GSI4",
            pk_attr="GSI4PK",
            pk_value=f"EMAIL#{email}",
            sk_attr="GSI4SK",
            sk_prefix="INVITE#",
        )

    def update_status(self, org_id: str, invite_id: str, status: str) -> None:
        """Update the status of an invitation."""
        self._table.update_item(
            pk=f"ORG#{org_id}",
            sk=f"INVITE#{invite_id}",
            updates={"status": status},
        )


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

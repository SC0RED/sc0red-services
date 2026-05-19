"""DynamoDB repository for OAuth records — clients, codes, tokens, refresh tokens."""

from __future__ import annotations

import time
from typing import Any

import boto3


class OAuthRepository:
    """CRUD operations for OAuth records in the sc0red Services DynamoDB single-table."""

    def __init__(self, table_name: str, endpoint_url: str | None = None) -> None:
        """Initialize with DynamoDB table name."""
        kwargs: dict[str, Any] = {}
        if endpoint_url:
            kwargs["endpoint_url"] = endpoint_url
        self._table = boto3.resource("dynamodb", **kwargs).Table(table_name)  # type: ignore[reportUnknownMemberType]

    # ── Clients ──────────────────────────────────────────────────────────────

    def save_client(self, client_id: str, client_data: dict[str, Any]) -> None:
        """Store an OAuth client registration."""
        self._table.put_item(
            Item={
                "pk": f"OAUTH_CLIENT#{client_id}",
                "sk": "CLIENT#METADATA",
                **client_data,
                "created_at": int(time.time()),
            }
        )

    def get_client(self, client_id: str) -> dict[str, Any] | None:
        """Retrieve an OAuth client by ID."""
        response = self._table.get_item(
            Key={"pk": f"OAUTH_CLIENT#{client_id}", "sk": "CLIENT#METADATA"}
        )
        return response.get("Item")

    # ── Authorization Codes ──────────────────────────────────────────────────

    def save_authorization_code(
        self,
        code: str,
        *,
        client_id: str,
        user_id: str,
        org_id: str,
        email: str,
        role: str,
        code_challenge: str,
        redirect_uri: str,
        scopes: list[str],
        ttl_seconds: int = 600,
    ) -> None:
        """Store an authorization code with TTL."""
        now = int(time.time())
        self._table.put_item(
            Item={
                "pk": f"OAUTH_CODE#{code}",
                "sk": "CODE#METADATA",
                "client_id": client_id,
                "user_id": user_id,
                "org_id": org_id,
                "email": email,
                "role": role,
                "code_challenge": code_challenge,
                "redirect_uri": redirect_uri,
                "scopes": scopes,
                "created_at": now,
                "ttl": now + ttl_seconds,
            }
        )

    def get_authorization_code(self, code: str) -> dict[str, Any] | None:
        """Retrieve and validate an authorization code."""
        response = self._table.get_item(Key={"pk": f"OAUTH_CODE#{code}", "sk": "CODE#METADATA"})
        item = response.get("Item")
        if not item:
            return None
        if int(item.get("ttl", 0)) < int(time.time()):  # type: ignore[arg-type]
            return None
        return item

    def delete_authorization_code(self, code: str) -> None:
        """Delete a used authorization code (single use)."""
        self._table.delete_item(Key={"pk": f"OAUTH_CODE#{code}", "sk": "CODE#METADATA"})

    # ── Access Tokens ────────────────────────────────────────────────────────

    def save_access_token(
        self,
        token_hash: str,
        *,
        user_id: str,
        org_id: str,
        client_id: str,
        scopes: list[str],
        ttl_seconds: int = 3600,
    ) -> None:
        """Store an access token record with TTL."""
        now = int(time.time())
        self._table.put_item(
            Item={
                "pk": f"OAUTH_TOKEN#{token_hash}",
                "sk": "TOKEN#METADATA",
                "user_id": user_id,
                "org_id": org_id,
                "client_id": client_id,
                "scopes": scopes,
                "created_at": now,
                "ttl": now + ttl_seconds,
            }
        )

    def get_access_token(self, token_hash: str) -> dict[str, Any] | None:
        """Retrieve an access token record."""
        response = self._table.get_item(
            Key={"pk": f"OAUTH_TOKEN#{token_hash}", "sk": "TOKEN#METADATA"}
        )
        item = response.get("Item")
        if not item:
            return None
        if int(item.get("ttl", 0)) < int(time.time()):  # type: ignore[arg-type]
            return None
        return item

    def delete_access_token(self, token_hash: str) -> None:
        """Delete an access token (revocation)."""
        self._table.delete_item(Key={"pk": f"OAUTH_TOKEN#{token_hash}", "sk": "TOKEN#METADATA"})

    # ── Refresh Tokens ───────────────────────────────────────────────────────

    def save_refresh_token(
        self,
        token_hash: str,
        *,
        user_id: str,
        org_id: str,
        email: str,
        role: str,
        client_id: str,
        scopes: list[str],
        ttl_seconds: int = 2592000,
    ) -> None:
        """Store a refresh token record with TTL (default 30 days)."""
        now = int(time.time())
        self._table.put_item(
            Item={
                "pk": f"OAUTH_REFRESH#{token_hash}",
                "sk": "REFRESH#METADATA",
                "user_id": user_id,
                "org_id": org_id,
                "email": email,
                "role": role,
                "client_id": client_id,
                "scopes": scopes,
                "created_at": now,
                "ttl": now + ttl_seconds,
            }
        )

    def get_refresh_token(self, token_hash: str) -> dict[str, Any] | None:
        """Retrieve a refresh token record."""
        response = self._table.get_item(
            Key={"pk": f"OAUTH_REFRESH#{token_hash}", "sk": "REFRESH#METADATA"}
        )
        item = response.get("Item")
        if not item:
            return None
        if int(item.get("ttl", 0)) < int(time.time()):  # type: ignore[arg-type]
            return None
        return item

    def delete_refresh_token(self, token_hash: str) -> None:
        """Delete a refresh token (revocation or rotation)."""
        self._table.delete_item(Key={"pk": f"OAUTH_REFRESH#{token_hash}", "sk": "REFRESH#METADATA"})

    # ── Consent Records ──────────────────────────────────────────────────────

    def save_consent(self, user_id: str, client_id: str) -> None:
        """Record that a user has consented to a client."""
        self._table.put_item(
            Item={
                "pk": f"OAUTH_CONSENT#{user_id}",
                "sk": f"CLIENT#{client_id}",
                "consented_at": int(time.time()),
            }
        )

    def has_consent(self, user_id: str, client_id: str) -> bool:
        """Check if a user has previously consented to a client."""
        response = self._table.get_item(
            Key={"pk": f"OAUTH_CONSENT#{user_id}", "sk": f"CLIENT#{client_id}"}
        )
        return "Item" in response

    def revoke_consent(self, user_id: str, client_id: str) -> None:
        """Revoke a user's consent for a client."""
        self._table.delete_item(Key={"pk": f"OAUTH_CONSENT#{user_id}", "sk": f"CLIENT#{client_id}"})

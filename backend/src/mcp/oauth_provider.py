"""Janus OAuth Authorization Server provider for the MCP SDK.

Implements OAuthAuthorizationServerProvider with DynamoDB-backed storage.
The MCP SDK auto-mounts OAuth endpoints when this provider is passed to FastMCP.
"""

from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.parse import urlencode

import jwt
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

from src.mcp.token_utils import (
    compute_token_hash,
    create_signed_access_token,
    generate_refresh_token,
    verify_access_token,
)

if TYPE_CHECKING:
    from mcp.server.auth.provider import AuthorizationParams

    from src.mcp.oauth_repository import OAuthRepository

logger = logging.getLogger(__name__)


@dataclass
class StoredAuthorizationCode:
    """Authorization code stored in DynamoDB."""

    code: str
    client_id: str
    user_id: str
    org_id: str
    email: str
    role: str
    code_challenge: str
    redirect_uri: str
    redirect_uri_provided_explicitly: bool
    scopes: list[str]


@dataclass
class StoredRefreshToken:
    """Refresh token stored in DynamoDB."""

    token_hash: str
    user_id: str
    org_id: str
    email: str
    role: str
    client_id: str
    scopes: list[str]


@dataclass
class StoredAccessToken:
    """Access token stored in DynamoDB."""

    token_hash: str
    user_id: str
    org_id: str
    client_id: str
    scopes: list[str]


class JanusOAuthProvider:
    """OAuth provider backed by DynamoDB, used by MCP SDK to handle OAuth flows."""

    def __init__(
        self,
        *,
        repository: OAuthRepository,
        private_key_pem: str,
        public_key_pem: str,
        issuer_url: str,
        consent_base_url: str,
    ) -> None:
        """Initialize the OAuth provider.

        Args:
            repository: DynamoDB repository for OAuth records.
            private_key_pem: RSA private key for signing JWTs.
            public_key_pem: RSA public key for verifying JWTs.
            issuer_url: The MCP server URL (issuer in JWTs).
            consent_base_url: The Janus frontend URL for the consent page.
        """
        self._repository = repository
        self._private_key_pem = private_key_pem
        self._public_key_pem = public_key_pem
        self._issuer_url = issuer_url
        self._consent_base_url = consent_base_url

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        """Retrieve a registered OAuth client by ID."""
        record = self._repository.get_client(client_id)
        if not record:
            return None
        return OAuthClientInformationFull(
            client_id=client_id,
            client_name=record.get("client_name"),
            redirect_uris=record.get("redirect_uris", []),
            grant_types=record.get("grant_types", ["authorization_code"]),
            response_types=record.get("response_types", ["code"]),
            token_endpoint_auth_method=record.get("token_endpoint_auth_method", "none"),
            scope=record.get("scope"),
        )

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        """Register a new OAuth client (Dynamic Client Registration)."""
        if not client_info.client_id:
            client_info.client_id = f"dyn_{secrets.token_urlsafe(16)}"

        self._repository.save_client(
            client_info.client_id,
            {
                "client_name": client_info.client_name,
                "redirect_uris": [str(uri) for uri in (client_info.redirect_uris or [])],
                "grant_types": client_info.grant_types,
                "response_types": client_info.response_types,
                "token_endpoint_auth_method": client_info.token_endpoint_auth_method,
                "scope": client_info.scope,
            },
        )
        logger.info(
            "Registered OAuth client: %s (%s)", client_info.client_id, client_info.client_name
        )

    async def authorize(
        self, client: OAuthClientInformationFull, params: AuthorizationParams
    ) -> str:
        """Redirect to the Janus consent UI for user authorization.

        Returns the URL to redirect the browser to.
        """
        if not client.client_id:
            message = "Cannot authorize: client has no client_id"
            raise ValueError(message)

        query_params: dict[str, str] = {
            "client_id": client.client_id,
            "client_name": client.client_name or "Unknown App",
            "redirect_uri": str(params.redirect_uri),
            "code_challenge": params.code_challenge,
            "scope": " ".join(params.scopes) if params.scopes else "read write",
        }
        if params.state:
            query_params["state"] = params.state

        return f"{self._consent_base_url}/oauth/authorize?{urlencode(query_params)}"

    async def load_authorization_code(
        self,
        client: OAuthClientInformationFull,
        authorization_code: str,
    ) -> StoredAuthorizationCode | None:
        """Load an authorization code from DynamoDB."""
        record = self._repository.get_authorization_code(authorization_code)
        if not record:
            return None
        if record.get("client_id") != client.client_id:
            return None
        return StoredAuthorizationCode(
            code=authorization_code,
            client_id=record["client_id"],
            user_id=record["user_id"],
            org_id=record["org_id"],
            email=record["email"],
            role=record["role"],
            code_challenge=record["code_challenge"],
            redirect_uri=record["redirect_uri"],
            redirect_uri_provided_explicitly=True,
            scopes=record.get("scopes", ["read", "write"]),
        )

    async def exchange_authorization_code(
        self,
        client: OAuthClientInformationFull,
        authorization_code: StoredAuthorizationCode,
    ) -> OAuthToken:
        """Exchange an authorization code for access + refresh tokens."""
        access_token = create_signed_access_token(
            private_key_pem=self._private_key_pem,
            user_id=authorization_code.user_id,
            email=authorization_code.email,
            org_id=authorization_code.org_id,
            role=authorization_code.role,
            client_id=authorization_code.client_id,
            scopes=authorization_code.scopes,
            issuer=self._issuer_url,
        )
        refresh_token = generate_refresh_token()

        self._repository.save_access_token(
            compute_token_hash(access_token),
            user_id=authorization_code.user_id,
            org_id=authorization_code.org_id,
            client_id=authorization_code.client_id,
            scopes=authorization_code.scopes,
        )
        self._repository.save_refresh_token(
            compute_token_hash(refresh_token),
            user_id=authorization_code.user_id,
            org_id=authorization_code.org_id,
            email=authorization_code.email,
            role=authorization_code.role,
            client_id=authorization_code.client_id,
            scopes=authorization_code.scopes,
        )

        self._repository.delete_authorization_code(authorization_code.code)

        logger.info(
            "Issued tokens for user %s via client %s",
            authorization_code.user_id,
            authorization_code.client_id,
        )

        return OAuthToken(
            access_token=access_token,
            token_type="Bearer",  # noqa: S106  # nosec B106
            expires_in=3600,
            refresh_token=refresh_token,
            scope=" ".join(authorization_code.scopes),
        )

    async def load_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: str,
    ) -> StoredRefreshToken | None:
        """Load a refresh token from DynamoDB."""
        record = self._repository.get_refresh_token(compute_token_hash(refresh_token))
        if not record:
            return None
        if record.get("client_id") != client.client_id:
            return None
        return StoredRefreshToken(
            token_hash=compute_token_hash(refresh_token),
            user_id=record["user_id"],
            org_id=record["org_id"],
            email=record["email"],
            role=record["role"],
            client_id=record["client_id"],
            scopes=record.get("scopes", ["read", "write"]),
        )

    async def exchange_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: StoredRefreshToken,
        scopes: list[str],
    ) -> OAuthToken:
        """Exchange a refresh token for new access + refresh tokens (rotation)."""
        effective_scopes = scopes if scopes else refresh_token.scopes

        new_access_token = create_signed_access_token(
            private_key_pem=self._private_key_pem,
            user_id=refresh_token.user_id,
            email=refresh_token.email,
            org_id=refresh_token.org_id,
            role=refresh_token.role,
            client_id=refresh_token.client_id,
            scopes=effective_scopes,
            issuer=self._issuer_url,
        )
        new_refresh_token = generate_refresh_token()

        self._repository.save_access_token(
            compute_token_hash(new_access_token),
            user_id=refresh_token.user_id,
            org_id=refresh_token.org_id,
            client_id=refresh_token.client_id,
            scopes=effective_scopes,
        )
        self._repository.save_refresh_token(
            compute_token_hash(new_refresh_token),
            user_id=refresh_token.user_id,
            org_id=refresh_token.org_id,
            email=refresh_token.email,
            role=refresh_token.role,
            client_id=refresh_token.client_id,
            scopes=effective_scopes,
        )

        self._repository.delete_refresh_token(refresh_token.token_hash)

        return OAuthToken(
            access_token=new_access_token,
            token_type="Bearer",  # noqa: S106  # nosec B106
            expires_in=3600,
            refresh_token=new_refresh_token,
            scope=" ".join(effective_scopes),
        )

    async def load_access_token(self, token: str) -> StoredAccessToken | None:
        """Verify and load an access token."""
        try:
            payload = verify_access_token(
                token,
                public_key_pem=self._public_key_pem,
                issuer=self._issuer_url,
            )
        except jwt.InvalidTokenError:
            return None

        record = self._repository.get_access_token(compute_token_hash(token))
        if not record:
            return None

        return StoredAccessToken(
            token_hash=compute_token_hash(token),
            user_id=payload["sub"],
            org_id=payload["org_id"],
            client_id=payload.get("client_id", ""),
            scopes=payload.get("scope", "").split(),
        )

    async def revoke_token(
        self,
        token: StoredAccessToken | StoredRefreshToken,
    ) -> None:
        """Revoke an access or refresh token."""
        if isinstance(token, StoredAccessToken):
            self._repository.delete_access_token(token.token_hash)
        else:
            self._repository.delete_refresh_token(token.token_hash)

"""Janus MCP server — Lambda entry point.

Uses FastMCP with Streamable HTTP transport, wrapped by Mangum for Lambda.
OAuth handled by the MCP SDK via JanusOAuthProvider.
"""

from __future__ import annotations

import json
import logging
import os
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

import boto3
import httpx
from mangum import Mangum
from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions, RevocationOptions
from mcp.server.fastmcp import FastMCP

from src.mcp.oauth_provider import JanusOAuthProvider
from src.mcp.oauth_repository import OAuthRepository

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────────────

DYNAMODB_TABLE = os.environ.get("DYNAMODB_TABLE", "janus-dev")
API_URL = os.environ.get("API_URL", "http://localhost:8001")
OAUTH_SIGNING_KEY_SECRET_ARN = os.environ.get("OAUTH_SIGNING_KEY_SECRET_ARN", "")
STAGE = os.environ.get("STAGE", "development")


def _load_signing_keys() -> tuple[str, str]:
    """Load RSA key pair from Secrets Manager or generate for local dev."""
    if OAUTH_SIGNING_KEY_SECRET_ARN:
        secrets_client = boto3.client("secretsmanager")  # type: ignore[reportUnknownMemberType]
        response = secrets_client.get_secret_value(  # type: ignore[reportUnknownMemberType,reportUnknownVariableType]
            SecretId=OAUTH_SIGNING_KEY_SECRET_ARN,
        )
        secret: dict[str, str] = json.loads(response["SecretString"])  # type: ignore[arg-type]
        return secret["private_key"], secret["public_key"]

    from src.mcp.token_utils import generate_rsa_key_pair

    logger.warning("No signing key ARN configured — generating ephemeral key pair for local dev")
    return generate_rsa_key_pair()


# ── Server setup ─────────────────────────────────────────────────────────────

_private_key, _public_key = _load_signing_keys()

_issuer_url = os.environ.get("MCP_ISSUER_URL", f"https://mcp.{STAGE}.janus.sc0red.com")
_consent_base_url = os.environ.get("CONSENT_BASE_URL", f"https://{STAGE}.janus.sc0red.com")

_repository = OAuthRepository(DYNAMODB_TABLE)
_oauth_provider = JanusOAuthProvider(
    repository=_repository,
    private_key_pem=_private_key,
    public_key_pem=_public_key,
    issuer_url=_issuer_url,
    consent_base_url=_consent_base_url,
)

_authentication_settings = AuthSettings(
    issuer_url=_issuer_url,  # type: ignore[arg-type]
    resource_server_url=_issuer_url,  # type: ignore[arg-type]
    client_registration_options=ClientRegistrationOptions(
        enabled=True,
        valid_scopes=["read", "write"],
        default_scopes=["read", "write"],
    ),
    revocation_options=RevocationOptions(enabled=True),
)


@asynccontextmanager
async def _lifespan(_server: FastMCP) -> AsyncIterator[dict[str, Any]]:  # type: ignore[type-arg]
    """Initialize shared resources for the MCP server."""
    async with httpx.AsyncClient(base_url=API_URL, timeout=30.0) as http_client:
        yield {"http_client": http_client, "api_url": API_URL}


mcp = FastMCP(
    name="Janus",
    instructions=(
        "Janus is a PE AI Risk Intelligence Platform. Use these tools to analyze companies "
        "for AI-driven risks and opportunities, manage portfolio scans, and generate reports."
    ),
    auth_server_provider=_oauth_provider,
    auth=_authentication_settings,
    lifespan=_lifespan,
)


# ── Tools ────────────────────────────────────────────────────────────────────

from src.mcp.tools_read import register_read_tools  # noqa: E402

register_read_tools(mcp)


# ── Lambda handler ───────────────────────────────────────────────────────────

_app = mcp.streamable_http_app()
handle_event = Mangum(_app)

"""sc0red Services MCP server — Lambda entry point.

Uses FastMCP with Streamable HTTP transport, wrapped by Mangum for Lambda.
OAuth handled by the MCP SDK via Sc0redServicesOAuthProvider.
"""

from __future__ import annotations

import json
import logging
import os

import boto3
from mangum import Mangum
from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions, RevocationOptions
from mcp.server.fastmcp import FastMCP

from src.mcp.oauth_provider import Sc0redServicesOAuthProvider
from src.mcp.oauth_repository import OAuthRepository

logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────────────

DYNAMODB_TABLE = os.environ.get("DYNAMODB_TABLE", "sc0red-services-dev")
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

_issuer_url = os.environ.get("MCP_ISSUER_URL", f"https://mcp.{STAGE}.sc0red-services.sc0red.com")
_consent_base_url = os.environ.get("CONSENT_BASE_URL", f"https://{STAGE}.sc0red-services.sc0red.com")

_repository = OAuthRepository(DYNAMODB_TABLE)
_oauth_provider = Sc0redServicesOAuthProvider(
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


mcp = FastMCP(
    name="sc0red Services",
    instructions=(
        "sc0red Services is a PE AI Risk Intelligence Platform. Use these tools to analyze "
        "companies for AI-driven risks and opportunities, manage portfolio scans, and "
        "generate reports."
    ),
    auth_server_provider=_oauth_provider,
    auth=_authentication_settings,
)


# ── Tools ────────────────────────────────────────────────────────────────────

from src.mcp.tools_read import register_read_tools  # noqa: E402
from src.mcp.tools_search import register_search_tools  # noqa: E402
from src.repositories.dynamodb.provider import DynamoDBStorageProvider  # noqa: E402

_storage = DynamoDBStorageProvider()
register_read_tools(mcp, _storage)
register_search_tools(mcp, _storage)


# ── Lambda handler ───────────────────────────────────────────────────────────

_app = mcp.streamable_http_app()
handle_event = Mangum(_app)

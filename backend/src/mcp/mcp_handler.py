"""Janus MCP server — Lambda entry point.

Uses FastMCP with Streamable HTTP transport, wrapped by Mangum for Lambda.
OAuth handled by the MCP SDK via JanusOAuthProvider.
"""

from __future__ import annotations

import json
import logging
import os

import boto3
from mangum import Mangum
from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions, RevocationOptions
from mcp.server.fastmcp import FastMCP

from src.mcp.oauth_provider import JanusOAuthProvider
from src.mcp.oauth_repository import OAuthRepository

logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────────────

DYNAMODB_TABLE = os.environ.get("DYNAMODB_TABLE", "janus-dev")
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

# Phase 2 host cutover defaults (rename-janus-to-sc0red-advisory): the
# public sc0red Advisory hosts are ``dev.advisory.sc0red.com``,
# ``testing.advisory.sc0red.com``, and ``advisory.sc0red.com`` (production
# has no per-env subdomain). ``CONSENT_BASE_URL`` is injected by CDK
# (``infrastructure/stacks/mcp_construct.py``) for every deployed env, so
# the default below only fires under local-dev. ``MCP_ISSUER_URL`` is
# NOT injected today — every deployed environment also falls through to
# the default. This is a pre-existing wiring gap; the new
# ``advisory.sc0red.com`` default is a better placeholder than the old
# ``janus.sc0red.com`` one but is still a placeholder, not the live
# issuer host. When the MCP OAuth issuer URL becomes operationally
# relevant (e.g. external clients validating tokens), wire it through
# ``mcp_construct.py`` from the Lambda Function URL or an explicit
# config key, matching the pattern used for ``CONSENT_BASE_URL``.
# The ``STAGE`` env var carries the CDK environment name
# (``development`` / ``staging`` / ``testing`` / ``production``), which
# is intentionally NOT the same as the public hostname prefix
# (``dev`` / ``testing`` / no-prefix). The placeholder defaults here use
# the CDK stage name verbatim, since no operator should be routing
# traffic to them.
_DEFAULT_STAGE_PREFIX = "" if STAGE == "production" else f"{STAGE}."
_issuer_url = os.environ.get(
    "MCP_ISSUER_URL", f"https://mcp.{_DEFAULT_STAGE_PREFIX}advisory.sc0red.com"
)
_consent_base_url = os.environ.get(
    "CONSENT_BASE_URL", f"https://{_DEFAULT_STAGE_PREFIX}advisory.sc0red.com"
)

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


mcp = FastMCP(
    name="sc0red Advisory",
    instructions=(
        "sc0red Advisory is a PE AI Risk Intelligence Platform. Use these tools to analyze "
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

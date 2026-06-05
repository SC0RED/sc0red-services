"""sc0red Services MCP server — Lambda entry point.

Serves the FastMCP Streamable HTTP app via uvicorn behind the AWS Lambda Web
Adapter (LWA). LWA runs this as a real ASGI server inside the Lambda container,
so the ASGI lifespan (which starts ``StreamableHTTPSessionManager``) runs once
per cold start — unlike Mangum, which re-ran the lifespan per invocation and
tripped the manager's run-once guard on the second warm request (see
``openspec/changes/janus-mcp-server/design.md`` Decision 8). OAuth handled by
the MCP SDK via Sc0redServicesOAuthProvider.
"""

from __future__ import annotations

import json
import logging
import os
from typing import TYPE_CHECKING

import boto3
from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions, RevocationOptions
from mcp.server.fastmcp import FastMCP
from starlette.responses import PlainTextResponse

from src.mcp.oauth_provider import Sc0redServicesOAuthProvider
from src.mcp.oauth_repository import OAuthRepository

if TYPE_CHECKING:
    from starlette.requests import Request

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
        # The CDK construct currently creates this secret with a placeholder
        # body and never populates the RSA keypair (Bug X — full auto-generation
        # fix tracked as a follow-up). A missing key here means the secret was
        # never populated post-deploy; fail with an actionable message instead
        # of an opaque KeyError so the operator knows exactly what to run.
        if "private_key" not in secret or "public_key" not in secret:
            raise RuntimeError(
                f"OAuth signing-key secret {OAUTH_SIGNING_KEY_SECRET_ARN} is missing "
                "'private_key'/'public_key' — the CDK construct creates it empty "
                "and it was never populated. Populate it with an RSA keypair "
                "(private_key + public_key PEM); see design.md Decision 8 / the "
                "migration doc for the exact put-secret-value command."
            )
        return secret["private_key"], secret["public_key"]

    from src.mcp.token_utils import generate_rsa_key_pair

    logger.warning("No signing key ARN configured — generating ephemeral key pair for local dev")
    return generate_rsa_key_pair()


# ── Server setup ─────────────────────────────────────────────────────────────

_private_key, _public_key = _load_signing_keys()

# Deployed environments always have both env vars set by ``MCPConstruct``
# (``MCP_ISSUER_URL`` → the Lambda Function URL; ``CONSENT_BASE_URL`` → the
# environment's frontend). The defaults below are the LOCAL-DEV fallbacks only.
# (They previously defaulted to ``mcp.{stage}.sc0red-services.sc0red.com`` /
# ``{stage}.sc0red-services.sc0red.com`` — hosts that never existed, which made
# a missing env var fail confusingly instead of obviously. Localhost is the
# honest local default.)
_issuer_url = os.environ.get("MCP_ISSUER_URL", "http://localhost:8080")
_consent_base_url = os.environ.get("CONSENT_BASE_URL", "http://localhost:3000")

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
    # ── Lambda statelessness (see design.md Decision 8) ──────────────────────
    # Under LWA the ASGI lifespan runs once per cold start, so the run-once
    # guard on ``StreamableHTTPSessionManager.run()`` is no longer tripped (that
    # was the Mangum failure mode — Bug B). These flags remain because they are
    # still the right posture for a serverless deployment: ``stateless_http``
    # drops the persistent ``Mcp-Session-Id`` session lifecycle so each request
    # is self-contained across scaled-out containers, and ``json_response``
    # returns plain JSON instead of SSE, which keeps responses simple and
    # avoids needing response-streaming wiring for the read-tool workload.
    stateless_http=True,
    json_response=True,
)


# ── Tools ────────────────────────────────────────────────────────────────────

from src.mcp.tools_read import register_read_tools  # noqa: E402
from src.mcp.tools_search import register_search_tools  # noqa: E402
from src.repositories.dynamodb.provider import DynamoDBStorageProvider  # noqa: E402

_storage = DynamoDBStorageProvider()
register_read_tools(mcp, _storage)
register_search_tools(mcp, _storage)


# ── Health check ──────────────────────────────────────────────────────────────
# LWA performs a readiness probe before routing traffic. The MCP endpoint mounts
# at ``/mcp`` (and requires POST + auth), so it is unsuitable as a probe target.
# Expose a dedicated unauthenticated ``/health`` and point LWA at it via
# ``AWS_LWA_READINESS_CHECK_PATH=/health`` (set in mcp_construct.py). Registered
# before ``streamable_http_app()`` so the route is included in the built app.
@mcp.custom_route("/health", methods=["GET"])
async def check_health(_request: Request) -> PlainTextResponse:
    """Liveness/readiness probe for the Lambda Web Adapter."""
    return PlainTextResponse("ok")


# ── ASGI app ──────────────────────────────────────────────────────────────────
# Served by uvicorn under the AWS Lambda Web Adapter (see module docstring +
# design.md Decision 8). ``run_mcp.sh`` is the Lambda handler; it execs
# ``uvicorn src.mcp.mcp_handler:app``.
app = mcp.streamable_http_app()

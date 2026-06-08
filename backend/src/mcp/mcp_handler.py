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
from mcp.server.transport_security import TransportSecuritySettings
from starlette.responses import PlainTextResponse

from src.mcp.cors import add_cors_middleware
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


def _resolve_issuer_url() -> str:
    """Resolve the OAuth issuer URL — must be the host clients actually reach.

    Resolution order:
      1. ``MCP_ISSUER_URL`` env var, if set explicitly (e.g. a custom domain).
      2. ``MCP_ISSUER_URL_SSM_PARAMETER`` — the SSM parameter holding the Lambda's
         own Function URL. ``MCPConstruct`` can't inject the Function URL into
         the Lambda's env directly (CloudFormation circular dependency), so it
         stashes it in SSM and passes only the static parameter NAME. We read it
         here at cold start. See mcp_construct.py for the dependency rationale.
      3. ``http://localhost:8080`` — local-dev fallback.
    """
    # Trailing slash is stripped from every resolved value: Lambda Function URLs
    # always end in "/", but the OAuth issuer is used verbatim as the JWT ``iss``
    # claim, and strict clients (mcp-inspector) compare ``iss`` against a
    # slash-stripped issuer (RFC 8414). Keep it slash-free everywhere.
    explicit = os.environ.get("MCP_ISSUER_URL")
    if explicit:
        return explicit.rstrip("/")
    ssm_parameter_name = os.environ.get("MCP_ISSUER_URL_SSM_PARAMETER")
    if ssm_parameter_name:
        ssm_client = boto3.client("ssm")  # type: ignore[reportUnknownMemberType]
        response = ssm_client.get_parameter(Name=ssm_parameter_name)  # type: ignore[reportUnknownMemberType,reportUnknownVariableType]
        issuer = str(response["Parameter"]["Value"])  # type: ignore[reportUnknownArgumentType]
        return issuer.rstrip("/")
    return "http://localhost:8080"


# Deployed environments resolve the issuer to the Lambda Function URL (via SSM);
# ``CONSENT_BASE_URL`` is set by ``MCPConstruct`` to the environment's frontend.
# The localhost defaults are the LOCAL-DEV fallbacks only.
_issuer_url = _resolve_issuer_url()
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
    # ── DNS-rebinding / Host validation (see design.md) ──────────────────────
    # FastMCP's default bind host is 127.0.0.1, so when ``transport_security``
    # is left unset it AUTO-ENABLES DNS-rebinding protection with
    # ``allowed_hosts=["127.0.0.1:*", "localhost:*", "[::1]:*"]``. Under the
    # Lambda Web Adapter the request reaches uvicorn with the Function URL as
    # the Host header (e.g. ``…lambda-url.us-east-1.on.aws``), which is not in
    # that localhost allow-list → the transport returns HTTP 421 "Invalid Host
    # header" on every authenticated POST /mcp (Bug L). DNS-rebinding protection
    # guards *localhost-bound* dev servers from browser-driven rebinding; it does
    # not apply to this deployment, which is a public, TLS-terminated endpoint
    # gated by an OAuth bearer token (RequireAuthMiddleware runs before the
    # transport, so unauthenticated requests never reach a tool). Disable it —
    # this is exactly the posture the SDK uses when no settings are passed.
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
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

# Browser MCP clients (e.g. MCP Inspector) connect to the authenticated ``/mcp``
# transport with an ``Authorization`` header, which the SDK leaves un-CORS'd —
# the unauthenticated preflight 401s with no ACAO and the browser reports
# "Failed to fetch". Add an outermost CORS layer so the preflight is answered
# before auth runs. See ``src/mcp/cors.py``.
add_cors_middleware(app)

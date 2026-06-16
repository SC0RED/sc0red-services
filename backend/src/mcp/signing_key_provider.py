"""Deploy-time population of the MCP OAuth signing-key secret (Bug X).

The CDK ``MCPConstruct`` creates the Secrets Manager secret with a placeholder
body; this handler — invoked by a ``custom_resources.Provider`` during the
stack deploy — generates an RSA-2048 keypair and writes
``{"private_key", "public_key"}`` (PEM) into it. Each environment therefore
self-populates on first deploy, instead of requiring a manual
``put-secret-value`` (which is how staging was bootstrapped).

Idempotent by design: it NEVER overwrites an existing keypair. That:
  • preserves a hand-populated key (staging), and
  • avoids rotating the key on every redeploy — rotation would invalidate
    every live access token (they're signed with the old private key).
Rotation, if ever needed, is a deliberate separate operation.
"""

from __future__ import annotations

import json
from typing import Any, cast

import boto3

from src.mcp.token_utils import generate_rsa_key_pair


def handle(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    """Generate + store the RSA keypair for a Create/Update; no-op on Delete.

    Returns the secret ARN as the physical resource id so the custom resource
    is stable across updates.
    """
    request_type = event["RequestType"]
    secret_arn = event["ResourceProperties"]["SecretArn"]
    physical_id = {"PhysicalResourceId": secret_arn}

    if request_type == "Delete":
        # The secret's lifecycle is owned by the stack's removal policy;
        # there is nothing to undo here.
        return physical_id

    client = boto3.client("secretsmanager")  # type: ignore[reportUnknownMemberType]
    current = cast("dict[str, Any]", client.get_secret_value(SecretId=secret_arn))  # type: ignore[reportUnknownMemberType]
    body: dict[str, str] = json.loads(current["SecretString"])

    # Idempotent: a populated secret is left untouched (preserve a
    # hand-populated key; never rotate on redeploy).
    if body.get("private_key") and body.get("public_key"):
        return physical_id

    private_key_pem, public_key_pem = generate_rsa_key_pair()
    client.put_secret_value(  # type: ignore[reportUnknownMemberType]
        SecretId=secret_arn,
        SecretString=json.dumps({"private_key": private_key_pem, "public_key": public_key_pem}),
    )
    return physical_id

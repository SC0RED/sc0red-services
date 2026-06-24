"""Tests for the signing-key custom-resource handler (Bug X)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from src.mcp.signing_key_provider import handle

SECRET_ARN = "arn:aws:secretsmanager:us-east-1:123:secret:sc0red-services-mcp-signing-key-x"


def _event(request_type: str) -> dict[str, object]:
    return {"RequestType": request_type, "ResourceProperties": {"SecretArn": SECRET_ARN}}


def test_create_populates_empty_secret() -> None:
    client = MagicMock()
    # Placeholder body (no keypair) — the state the CDK construct creates.
    client.get_secret_value.return_value = {"SecretString": json.dumps({"note": "placeholder"})}
    with patch("src.mcp.signing_key_provider.boto3.client", return_value=client):
        result = handle(_event("Create"), None)

    assert result["PhysicalResourceId"] == SECRET_ARN
    client.put_secret_value.assert_called_once()
    kwargs = client.put_secret_value.call_args.kwargs
    assert kwargs["SecretId"] == SECRET_ARN
    stored = json.loads(kwargs["SecretString"])
    assert "BEGIN PRIVATE KEY" in stored["private_key"]
    assert "BEGIN PUBLIC KEY" in stored["public_key"]


def test_create_is_noop_when_already_populated() -> None:
    # Idempotency guard: a hand-populated key (staging) or a prior deploy's key
    # must NOT be overwritten — rotating would invalidate live tokens.
    client = MagicMock()
    client.get_secret_value.return_value = {
        "SecretString": json.dumps({"private_key": "EXISTING", "public_key": "EXISTING"})
    }
    with patch("src.mcp.signing_key_provider.boto3.client", return_value=client):
        result = handle(_event("Update"), None)

    assert result["PhysicalResourceId"] == SECRET_ARN
    client.put_secret_value.assert_not_called()


def test_delete_is_noop() -> None:
    client = MagicMock()
    with patch("src.mcp.signing_key_provider.boto3.client", return_value=client):
        result = handle(_event("Delete"), None)

    assert result["PhysicalResourceId"] == SECRET_ARN
    client.get_secret_value.assert_not_called()
    client.put_secret_value.assert_not_called()

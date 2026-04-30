"""Tests for the PDF render proxy handler.

Covers env-var contract (missing ARN → 500), body validation (missing
fields → 400), boto3 invoke failures (→ 502), and the happy-path
forwarding of the Node.js Lambda's base64-encoded PDF response.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

import src.handlers.pdf_render_handlers as pdf_render_handlers
from src.handlers.auth_middleware import AuthContext
from src.handlers.pdf_render_handlers import (
    PDF_RENDER_LAMBDA_ARN_ENV,
    handle_render_pdf,
)


def _auth() -> AuthContext:
    return AuthContext(user_id="user-1", org_id="org-1", email="u@example.com", role="admin")


def _event(body: Any) -> dict[str, Any]:
    return {"body": json.dumps(body) if isinstance(body, dict) else body}


def _valid_body() -> dict[str, Any]:
    return {
        "analysisId": "a-1",
        "token": "t.signed.token",
        "frontendBaseUrl": "https://app.example.com",
        "companyName": "Acme Corp",
    }


@pytest.fixture(autouse=True)
def _reset_lambda_client() -> None:
    """Each test starts with a fresh boto3 client cache."""
    pdf_render_handlers._lambda_client = None


def test_returns_500_when_arn_env_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(PDF_RENDER_LAMBDA_ARN_ENV, raising=False)
    response = handle_render_pdf(_event(_valid_body()), _auth())
    assert response["statusCode"] == 500


def test_returns_400_when_body_not_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(PDF_RENDER_LAMBDA_ARN_ENV, "arn:aws:lambda:us-east-1:1:function:render")
    response = handle_render_pdf(_event("not-json"), _auth())
    assert response["statusCode"] == 400


def test_returns_400_when_required_field_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(PDF_RENDER_LAMBDA_ARN_ENV, "arn:aws:lambda:us-east-1:1:function:render")
    body = _valid_body()
    del body["token"]
    response = handle_render_pdf(_event(body), _auth())
    assert response["statusCode"] == 400


def test_returns_502_when_boto3_invoke_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(PDF_RENDER_LAMBDA_ARN_ENV, "arn:aws:lambda:us-east-1:1:function:render")
    mock_client = MagicMock()
    mock_client.invoke.side_effect = ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "no perms"}}, "Invoke"
    )
    with patch("src.handlers.pdf_render_handlers._get_lambda_client", return_value=mock_client):
        response = handle_render_pdf(_event(_valid_body()), _auth())
    assert response["statusCode"] == 502


def test_returns_502_when_payload_undecodable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(PDF_RENDER_LAMBDA_ARN_ENV, "arn:aws:lambda:us-east-1:1:function:render")
    mock_client = MagicMock()
    mock_payload = MagicMock()
    mock_payload.read.return_value = b"not-json"
    mock_client.invoke.return_value = {"Payload": mock_payload}
    with patch("src.handlers.pdf_render_handlers._get_lambda_client", return_value=mock_client):
        response = handle_render_pdf(_event(_valid_body()), _auth())
    assert response["statusCode"] == 502


def test_forwards_lambda_error_status(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(PDF_RENDER_LAMBDA_ARN_ENV, "arn:aws:lambda:us-east-1:1:function:render")
    mock_client = MagicMock()
    mock_payload = MagicMock()
    mock_payload.read.return_value = json.dumps(
        {"statusCode": 401, "body": json.dumps({"error": "Invalid token"})}
    ).encode("utf-8")
    mock_client.invoke.return_value = {"Payload": mock_payload}
    with patch("src.handlers.pdf_render_handlers._get_lambda_client", return_value=mock_client):
        response = handle_render_pdf(_event(_valid_body()), _auth())
    assert response["statusCode"] == 401


def test_happy_path_returns_pdf_with_correct_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(PDF_RENDER_LAMBDA_ARN_ENV, "arn:aws:lambda:us-east-1:1:function:render")
    pdf_b64 = "JVBERi1tb2NrLWJ5dGVz"  # base64 of "%PDF-mock-bytes"
    mock_client = MagicMock()
    mock_payload = MagicMock()
    mock_payload.read.return_value = json.dumps(
        {
            "statusCode": 200,
            "body": pdf_b64,
            "isBase64Encoded": True,
            "headers": {"Content-Type": "application/pdf"},
        }
    ).encode("utf-8")
    mock_client.invoke.return_value = {"Payload": mock_payload}
    with patch("src.handlers.pdf_render_handlers._get_lambda_client", return_value=mock_client):
        response = handle_render_pdf(_event(_valid_body()), _auth())
    assert response["statusCode"] == 200
    assert response["headers"]["Content-Type"] == "application/pdf"
    assert response["headers"]["Cache-Control"] == "no-store"
    assert response["isBase64Encoded"] is True
    assert response["body"] == pdf_b64


def test_only_forwards_required_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cognito claims and other auth context MUST NOT leak into the Lambda payload."""
    monkeypatch.setenv(PDF_RENDER_LAMBDA_ARN_ENV, "arn:aws:lambda:us-east-1:1:function:render")
    mock_client = MagicMock()
    mock_payload = MagicMock()
    mock_payload.read.return_value = json.dumps(
        {"statusCode": 200, "body": "QQ==", "isBase64Encoded": True}
    ).encode("utf-8")
    mock_client.invoke.return_value = {"Payload": mock_payload}

    body = _valid_body()
    body["EXTRA_FIELD"] = "should-not-pass-through"
    with patch("src.handlers.pdf_render_handlers._get_lambda_client", return_value=mock_client):
        handle_render_pdf(_event(body), _auth())

    invoke_call = mock_client.invoke.call_args
    payload_bytes = invoke_call.kwargs["Payload"]
    forwarded = json.loads(json.loads(payload_bytes)["body"])
    assert "EXTRA_FIELD" not in forwarded
    assert set(forwarded.keys()) == {"analysisId", "token", "frontendBaseUrl", "companyName"}

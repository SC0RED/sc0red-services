"""Tests for the async PDF export handlers.

Covers the six scenarios from
``openspec/changes/async-pdf-export-with-cache/tasks.md`` §1.5.1:

1. First click (no ``pdf_export``) → 202 + async-invoke called once
2. Cached path (``status = ready``) → 200 with presigned URL, no invoke
3. In-flight non-stale (``status = rendering``) → 202, no duplicate invoke
4. Stale rendering (>60 s old) → POST re-enqueues a fresh render
5. Status endpoint stale detection → returns ``failed`` without mutating
6. Failed state → POST re-enqueues fresh render

Plus configuration / not-found edge cases. Tests are written against the
handler functions directly (bypassing the router) so we don't have to
spin up the full ``APIGatewayHandler`` for each case.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from src.handlers import pdf_export_handlers, pdf_token_secret
from src.handlers.auth_middleware import AuthContext
from src.handlers.pdf_export_handlers import (
    FRONTEND_BASE_URL_ENVIRONMENT_NAME,
    PDF_EXPORTS_BUCKET_ENVIRONMENT_NAME,
    PDF_RENDER_LAMBDA_ARN_ENVIRONMENT_NAME,
    RENDERING_STALE_AFTER_SECONDS,
    delete_cached_pdf,
    handle_get_export_status,
    handle_post_export,
)
from src.handlers.pdf_token_secret import PDF_TOKEN_SECRET_ARN_ENVIRONMENT_NAME

ANALYSIS_ID = "a-1"
ORG_ID = "org-1"
USER_ID = "user-1"
BUCKET = "janus-development-pdf-exports"
RENDER_ARN = "arn:aws:lambda:us-east-1:1:function:janus-pdf-render-development"
TOKEN_SECRET_ARN = "arn:aws:secretsmanager:us-east-1:1:secret:janus/dev/pdf-token-secret"
FRONTEND_BASE_URL = "https://development.d1234abcdef.amplifyapp.com"


def _auth() -> AuthContext:
    return AuthContext(user_id=USER_ID, org_id=ORG_ID, email="u@example.com", role="admin")


def _company() -> dict[str, Any]:
    return {
        "id": ANALYSIS_ID,
        "org_id": ORG_ID,
        "company_name": "Acme Corp",
        "company_url": "https://acme.test",
        "created_at": "2026-05-18T10:00:00+00:00",
    }


def _storage_with(company: dict[str, Any] | None, pdf_export: dict[str, Any] | None) -> MagicMock:
    storage = MagicMock()
    company_repo = MagicMock()
    company_repo.get_by_id.return_value = company
    storage.create_company_repository.return_value = company_repo
    assessment_repo = MagicMock()
    assessment_repo.get_pdf_export.return_value = pdf_export
    storage.create_assessment_repository.return_value = assessment_repo
    return storage


@pytest.fixture(autouse=True)
def _reset_module_clients() -> None:
    """Reset module-level boto3 client + secret caches between tests."""
    pdf_export_handlers._lambda_client = None
    pdf_export_handlers._s3_client = None
    pdf_token_secret._reset_caches_for_tests()


@pytest.fixture
def _configured_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set the required env vars for happy-path tests."""
    monkeypatch.setenv(PDF_EXPORTS_BUCKET_ENVIRONMENT_NAME, BUCKET)
    monkeypatch.setenv(PDF_RENDER_LAMBDA_ARN_ENVIRONMENT_NAME, RENDER_ARN)
    monkeypatch.setenv(PDF_TOKEN_SECRET_ARN_ENVIRONMENT_NAME, TOKEN_SECRET_ARN)
    monkeypatch.setenv(FRONTEND_BASE_URL_ENVIRONMENT_NAME, FRONTEND_BASE_URL)


@pytest.fixture
def _mocked_token_secret() -> Any:
    """Patch the Secrets Manager fetch for token-signing happy paths.

    All ``handle_post_export`` cold-path tests need the token secret
    resolvable. Without this fixture, real boto3 Secrets Manager
    requests would be attempted (or fail noisily).
    """
    mock_secrets = MagicMock()
    mock_secrets.get_secret_value.return_value = {"SecretString": "test-pdf-token-secret"}
    with patch.object(pdf_token_secret, "_get_secrets_client", return_value=mock_secrets):
        yield mock_secrets


# ── POST /api/export/pdf/<id> ────────────────────────────────────────────────


def test_post_returns_500_when_env_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(PDF_EXPORTS_BUCKET_ENVIRONMENT_NAME, raising=False)
    monkeypatch.delenv(PDF_RENDER_LAMBDA_ARN_ENVIRONMENT_NAME, raising=False)
    monkeypatch.delenv(PDF_TOKEN_SECRET_ARN_ENVIRONMENT_NAME, raising=False)
    monkeypatch.delenv(FRONTEND_BASE_URL_ENVIRONMENT_NAME, raising=False)
    storage = _storage_with(_company(), None)
    response = handle_post_export({}, _auth(), storage, ANALYSIS_ID)
    assert response["statusCode"] == 500


def test_post_returns_500_when_frontend_base_url_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """All four env vars must be set for the cold path to work."""
    monkeypatch.setenv(PDF_EXPORTS_BUCKET_ENVIRONMENT_NAME, BUCKET)
    monkeypatch.setenv(PDF_RENDER_LAMBDA_ARN_ENVIRONMENT_NAME, RENDER_ARN)
    monkeypatch.setenv(PDF_TOKEN_SECRET_ARN_ENVIRONMENT_NAME, TOKEN_SECRET_ARN)
    monkeypatch.delenv(FRONTEND_BASE_URL_ENVIRONMENT_NAME, raising=False)
    storage = _storage_with(_company(), None)
    response = handle_post_export({}, _auth(), storage, ANALYSIS_ID)
    assert response["statusCode"] == 500


def test_post_returns_500_when_token_secret_arn_unset(
    _configured_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Missing PDF_TOKEN_SECRET_ARN raises RuntimeError → 500 NOT_CONFIGURED."""
    monkeypatch.delenv(PDF_TOKEN_SECRET_ARN_ENVIRONMENT_NAME, raising=False)
    storage = _storage_with(_company(), None)
    response = handle_post_export({}, _auth(), storage, ANALYSIS_ID)
    assert response["statusCode"] == 500


def test_post_returns_500_when_secrets_manager_raises(_configured_env: None) -> None:
    """Secrets Manager ClientError (throttle / access denied / etc) → 500.

    Exercises the actual boto3 client path — not just the env-var-unset
    branch — so the ``except ClientError`` catch in ``handle_post_export``
    has regression coverage.
    """
    mock_secrets = MagicMock()
    mock_secrets.get_secret_value.side_effect = ClientError(
        {"Error": {"Code": "AccessDeniedException", "Message": "denied"}}, "GetSecretValue"
    )
    storage = _storage_with(_company(), None)
    with patch.object(pdf_token_secret, "_get_secrets_client", return_value=mock_secrets):
        response = handle_post_export({}, _auth(), storage, ANALYSIS_ID)
    assert response["statusCode"] == 500


def test_post_returns_404_when_analysis_missing(_configured_env: None) -> None:
    storage = _storage_with(None, None)
    response = handle_post_export({}, _auth(), storage, ANALYSIS_ID)
    assert response["statusCode"] == 404


def test_post_returns_404_when_analysis_belongs_to_other_org(_configured_env: None) -> None:
    other_org_company = {**_company(), "org_id": "org-other"}
    storage = _storage_with(other_org_company, None)
    response = handle_post_export({}, _auth(), storage, ANALYSIS_ID)
    assert response["statusCode"] == 404


def test_post_first_click_enqueues_render_and_writes_rendering(
    _configured_env: None, _mocked_token_secret: Any
) -> None:
    storage = _storage_with(_company(), None)
    assessment_repo = storage.create_assessment_repository.return_value

    mock_lambda = MagicMock()
    with patch.object(pdf_export_handlers, "_get_lambda_client", return_value=mock_lambda):
        response = handle_post_export({}, _auth(), storage, ANALYSIS_ID)

    assert response["statusCode"] == 202
    body = json.loads(response["body"])
    assert body["status"] == "rendering"
    assert "startedAt" in body

    # Wrote rendering record with the new started_at.
    assessment_repo.save_pdf_export.assert_called_once()
    saved_args = assessment_repo.save_pdf_export.call_args
    assert saved_args.args[0] == ANALYSIS_ID
    record = saved_args.args[1]
    assert record["status"] == "rendering"
    assert record["s3_key"] == f"pdf-exports/{ANALYSIS_ID}.pdf"
    assert record["started_at"] == body["startedAt"]

    # Lambda async-invoked exactly once with Event invocation type.
    mock_lambda.invoke.assert_called_once()
    invoke_kwargs = mock_lambda.invoke.call_args.kwargs
    assert invoke_kwargs["FunctionName"] == RENDER_ARN
    assert invoke_kwargs["InvocationType"] == "Event"
    payload = json.loads(invoke_kwargs["Payload"])
    assert payload["analysisId"] == ANALYSIS_ID
    assert payload["s3Key"] == f"pdf-exports/{ANALYSIS_ID}.pdf"
    assert payload["startedAt"] == body["startedAt"]
    assert payload["companyName"] == "Acme Corp"
    # Phase 2: payload now includes a signed token + frontend URL so
    # the Lambda's headless browser can navigate /print/<id>?t=<token>.
    assert payload["frontendBaseUrl"] == FRONTEND_BASE_URL
    assert isinstance(payload["token"], str)
    assert "." in payload["token"]  # base64url(payload).base64url(sig)


def test_post_cached_path_returns_presigned_url_no_invoke(_configured_env: None) -> None:
    pdf_export = {
        "status": "ready",
        "s3_key": f"pdf-exports/{ANALYSIS_ID}.pdf",
        "started_at": "2026-05-18T09:00:00+00:00",
        "generated_at": "2026-05-18T09:00:13+00:00",
    }
    storage = _storage_with(_company(), pdf_export)
    assessment_repo = storage.create_assessment_repository.return_value

    mock_s3 = MagicMock()
    mock_s3.generate_presigned_url.return_value = "https://s3.example/signed-url"
    mock_lambda = MagicMock()
    with (
        patch.object(pdf_export_handlers, "_get_s3_client", return_value=mock_s3),
        patch.object(pdf_export_handlers, "_get_lambda_client", return_value=mock_lambda),
    ):
        response = handle_post_export({}, _auth(), storage, ANALYSIS_ID)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["status"] == "ready"
    assert body["url"] == "https://s3.example/signed-url"
    assert body["generatedAt"] == "2026-05-18T09:00:13+00:00"

    # No re-enqueue, no fresh record write.
    mock_lambda.invoke.assert_not_called()
    assessment_repo.save_pdf_export.assert_not_called()

    # Presigned URL minted against the right bucket + key, with attachment disposition.
    mock_s3.generate_presigned_url.assert_called_once()
    presign_args = mock_s3.generate_presigned_url.call_args
    assert presign_args.args[0] == "get_object"
    params = presign_args.kwargs["Params"]
    assert params["Bucket"] == BUCKET
    assert params["Key"] == f"pdf-exports/{ANALYSIS_ID}.pdf"
    assert params["ResponseContentType"] == "application/pdf"
    assert "attachment; filename=" in params["ResponseContentDisposition"]
    assert presign_args.kwargs["ExpiresIn"] == 60


def test_post_in_flight_non_stale_dedupes(_configured_env: None) -> None:
    recent_started = (datetime.now(UTC) - timedelta(seconds=5)).isoformat()
    pdf_export = {
        "status": "rendering",
        "s3_key": f"pdf-exports/{ANALYSIS_ID}.pdf",
        "started_at": recent_started,
    }
    storage = _storage_with(_company(), pdf_export)
    assessment_repo = storage.create_assessment_repository.return_value

    mock_lambda = MagicMock()
    with patch.object(pdf_export_handlers, "_get_lambda_client", return_value=mock_lambda):
        response = handle_post_export({}, _auth(), storage, ANALYSIS_ID)

    assert response["statusCode"] == 202
    body = json.loads(response["body"])
    assert body["status"] == "rendering"
    # ``started_at`` unchanged — no fresh enqueue.
    assert body["startedAt"] == recent_started
    mock_lambda.invoke.assert_not_called()
    assessment_repo.save_pdf_export.assert_not_called()


def test_post_stale_rendering_triggers_fresh_render(
    _configured_env: None, _mocked_token_secret: Any
) -> None:
    stale_started = (
        datetime.now(UTC) - timedelta(seconds=RENDERING_STALE_AFTER_SECONDS + 30)
    ).isoformat()
    pdf_export = {
        "status": "rendering",
        "s3_key": f"pdf-exports/{ANALYSIS_ID}.pdf",
        "started_at": stale_started,
    }
    storage = _storage_with(_company(), pdf_export)
    assessment_repo = storage.create_assessment_repository.return_value

    mock_lambda = MagicMock()
    with patch.object(pdf_export_handlers, "_get_lambda_client", return_value=mock_lambda):
        response = handle_post_export({}, _auth(), storage, ANALYSIS_ID)

    assert response["statusCode"] == 202
    body = json.loads(response["body"])
    assert body["status"] == "rendering"
    # Fresh started_at — different from the stale one.
    assert body["startedAt"] != stale_started
    assessment_repo.save_pdf_export.assert_called_once()
    mock_lambda.invoke.assert_called_once()


def test_post_failed_state_triggers_fresh_render(
    _configured_env: None, _mocked_token_secret: Any
) -> None:
    pdf_export = {
        "status": "failed",
        "s3_key": f"pdf-exports/{ANALYSIS_ID}.pdf",
        "started_at": "2026-05-18T09:00:00+00:00",
        "error": "Render Lambda crashed",
    }
    storage = _storage_with(_company(), pdf_export)
    assessment_repo = storage.create_assessment_repository.return_value

    mock_lambda = MagicMock()
    with patch.object(pdf_export_handlers, "_get_lambda_client", return_value=mock_lambda):
        response = handle_post_export({}, _auth(), storage, ANALYSIS_ID)

    assert response["statusCode"] == 202
    assessment_repo.save_pdf_export.assert_called_once()
    mock_lambda.invoke.assert_called_once()


def test_post_marks_failed_when_async_invoke_raises(
    _configured_env: None, _mocked_token_secret: Any
) -> None:
    storage = _storage_with(_company(), None)
    assessment_repo = storage.create_assessment_repository.return_value

    mock_lambda = MagicMock()
    mock_lambda.invoke.side_effect = ClientError(
        {"Error": {"Code": "Throttling", "Message": "rate limit"}}, "Invoke"
    )
    with patch.object(pdf_export_handlers, "_get_lambda_client", return_value=mock_lambda):
        response = handle_post_export({}, _auth(), storage, ANALYSIS_ID)

    assert response["statusCode"] == 502
    # Two writes: first the rendering, then the failed override.
    assert assessment_repo.save_pdf_export.call_count == 2
    final_record = assessment_repo.save_pdf_export.call_args_list[-1].args[1]
    assert final_record["status"] == "failed"
    assert "error" in final_record


# ── GET /api/export/pdf/<id>/status ──────────────────────────────────────────


def test_status_returns_500_when_bucket_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(PDF_EXPORTS_BUCKET_ENVIRONMENT_NAME, raising=False)
    storage = _storage_with(_company(), None)
    response = handle_get_export_status({}, _auth(), storage, ANALYSIS_ID)
    assert response["statusCode"] == 500


def test_status_returns_404_when_analysis_missing(_configured_env: None) -> None:
    storage = _storage_with(None, None)
    response = handle_get_export_status({}, _auth(), storage, ANALYSIS_ID)
    assert response["statusCode"] == 404


def test_status_returns_none_when_record_absent(_configured_env: None) -> None:
    storage = _storage_with(_company(), None)
    response = handle_get_export_status({}, _auth(), storage, ANALYSIS_ID)
    assert response["statusCode"] == 200
    assert json.loads(response["body"])["status"] == "none"


def test_status_stale_rendering_returns_synthetic_failed_without_mutating(
    _configured_env: None,
) -> None:
    stale_started = (
        datetime.now(UTC) - timedelta(seconds=RENDERING_STALE_AFTER_SECONDS + 30)
    ).isoformat()
    pdf_export = {
        "status": "rendering",
        "s3_key": f"pdf-exports/{ANALYSIS_ID}.pdf",
        "started_at": stale_started,
    }
    storage = _storage_with(_company(), pdf_export)
    assessment_repo = storage.create_assessment_repository.return_value

    response = handle_get_export_status({}, _auth(), storage, ANALYSIS_ID)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["status"] == "failed"
    assert "stuck" in body["error"].lower()

    # The persisted record is NOT modified by the read.
    assessment_repo.save_pdf_export.assert_not_called()
    assessment_repo.clear_pdf_export.assert_not_called()


def test_status_ready_returns_fresh_presigned_url(_configured_env: None) -> None:
    pdf_export = {
        "status": "ready",
        "s3_key": f"pdf-exports/{ANALYSIS_ID}.pdf",
        "started_at": "2026-05-18T09:00:00+00:00",
        "generated_at": "2026-05-18T09:00:13+00:00",
    }
    storage = _storage_with(_company(), pdf_export)

    mock_s3 = MagicMock()
    mock_s3.generate_presigned_url.return_value = "https://s3.example/ready-url"
    with patch.object(pdf_export_handlers, "_get_s3_client", return_value=mock_s3):
        response = handle_get_export_status({}, _auth(), storage, ANALYSIS_ID)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["status"] == "ready"
    assert body["url"] == "https://s3.example/ready-url"


def test_status_rendering_returns_started_at(_configured_env: None) -> None:
    recent_started = (datetime.now(UTC) - timedelta(seconds=5)).isoformat()
    pdf_export = {
        "status": "rendering",
        "s3_key": f"pdf-exports/{ANALYSIS_ID}.pdf",
        "started_at": recent_started,
    }
    storage = _storage_with(_company(), pdf_export)

    response = handle_get_export_status({}, _auth(), storage, ANALYSIS_ID)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["status"] == "rendering"
    assert body["startedAt"] == recent_started


def test_status_failed_returns_stored_error(_configured_env: None) -> None:
    pdf_export = {
        "status": "failed",
        "s3_key": f"pdf-exports/{ANALYSIS_ID}.pdf",
        "started_at": "2026-05-18T09:00:00+00:00",
        "error": "Puppeteer crashed",
    }
    storage = _storage_with(_company(), pdf_export)

    response = handle_get_export_status({}, _auth(), storage, ANALYSIS_ID)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["status"] == "failed"
    assert body["error"] == "Puppeteer crashed"


# ── delete_cached_pdf helper ─────────────────────────────────────────────────


def test_delete_cached_pdf_returns_false_when_bucket_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(PDF_EXPORTS_BUCKET_ENVIRONMENT_NAME, raising=False)
    assert delete_cached_pdf("pdf-exports/anything.pdf") is False


def test_delete_cached_pdf_calls_s3_delete(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(PDF_EXPORTS_BUCKET_ENVIRONMENT_NAME, BUCKET)
    mock_s3 = MagicMock()
    with patch.object(pdf_export_handlers, "_get_s3_client", return_value=mock_s3):
        result = delete_cached_pdf(f"pdf-exports/{ANALYSIS_ID}.pdf")
    assert result is True
    mock_s3.delete_object.assert_called_once_with(
        Bucket=BUCKET,
        Key=f"pdf-exports/{ANALYSIS_ID}.pdf",
    )


def test_delete_cached_pdf_returns_false_on_s3_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(PDF_EXPORTS_BUCKET_ENVIRONMENT_NAME, BUCKET)
    mock_s3 = MagicMock()
    mock_s3.delete_object.side_effect = ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "denied"}}, "DeleteObject"
    )
    with patch.object(pdf_export_handlers, "_get_s3_client", return_value=mock_s3):
        # Returns False — never raises (re-analyse must not be blocked by S3).
        assert delete_cached_pdf(f"pdf-exports/{ANALYSIS_ID}.pdf") is False

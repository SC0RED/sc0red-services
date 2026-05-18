"""Async PDF export handlers — POST + GET status.

POST /api/export/pdf/<id>: serves cached (200 + presigned URL) or
async-enqueues a render (202). Concurrent clicks on a non-stale
``rendering`` row dedupe to 202 without a second invoke.

GET /api/export/pdf/<id>/status: the frontend's polling target. Folds
``rendering`` older than 60 s into a synthetic ``failed`` so the
frontend exits the polling loop without mutating the persisted record;
the next POST re-triggers naturally.

See ``openspec/changes/async-pdf-export-with-cache/`` for the full design.
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from src.handlers.api_gateway_handler import (
    NOT_CONFIGURED,
    build_error,
    build_json_response,
    check_org_access,
)
from src.handlers.pdf_token_secret import (
    read_pdf_token_secret,
)
from src.utilities.pdf_token import sign_pdf_token

if TYPE_CHECKING:
    from src.handlers.api_gateway_handler import LambdaResponse
    from src.handlers.auth_middleware import AuthContext
    from src.handlers.router import Router
    from src.repositories.dynamodb.provider import DynamoDBStorageProvider

logger = logging.getLogger(__name__)

# A ``rendering`` sub-record older than this window is treated as stale
# (the PDF Lambda likely crashed mid-render). The status endpoint reports
# such records as ``failed`` so the frontend exits polling; the next POST
# is permitted to enqueue a fresh render. 60 s comfortably exceeds the
# typical render time after the 2026-05-18 memory bump (~13 s).
RENDERING_STALE_AFTER_SECONDS = 60

# Presigned URL TTL. 60 s is plenty for the browser to follow the
# redirect; a tighter window than ``ExpiresIn`` defaults (3600 s)
# limits the blast radius if the URL is ever logged or shared.
PRESIGNED_URL_EXPIRES_SECONDS = 60

# S3 object key prefix. One object per analysis — re-renders overwrite
# the same key. Re-analyse explicitly deletes the object as part of
# its invalidation step (see ``handle_reanalyze``).
S3_KEY_PREFIX = "pdf-exports"

PDF_EXPORTS_BUCKET_ENVIRONMENT_NAME = "PDF_EXPORTS_BUCKET"
PDF_RENDER_LAMBDA_ARN_ENVIRONMENT_NAME = "PDF_RENDER_LAMBDA_ARN"
FRONTEND_BASE_URL_ENVIRONMENT_NAME = "FRONTEND_BASE_URL"


# Module-level boto3 clients survive Lambda warm-restart, avoiding the
# per-invoke client init cost (~50 ms each). The token-secret client +
# cache live in ``pdf_token_secret.py``.
_lambda_client: Any = None
_s3_client: Any = None


def _get_lambda_client() -> Any:
    """Cached boto3 Lambda client. Module-level cache survives container reuse."""
    global _lambda_client
    if _lambda_client is None:
        _lambda_client = boto3.client("lambda")
    return _lambda_client


def _get_s3_client() -> Any:
    """Cached boto3 S3 client. Used to mint presigned URLs."""
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client("s3")
    return _s3_client


def _sanitize_filename_segment(text: str) -> str:
    """Strip non-alphanum/underscore/dash characters; collapse runs; truncate.

    Used to derive the download filename's company-name portion from the
    arbitrary user-controlled ``company_name`` field. We never want a
    raw company name in a ``Content-Disposition`` header — header
    injection (CR/LF), filesystem-hostile characters, etc.
    """
    sanitized = re.sub(r"[^\w\-]+", "_", text).strip("_")
    return sanitized[:80] or "analysis"


def _build_download_filename(company: dict[str, Any]) -> str:
    """Build a sensible PDF download filename: ``<CompanyName>_<YYYY-MM-DD>.pdf``."""
    company_name = _sanitize_filename_segment(str(company.get("company_name", "analysis")))
    created_at = company.get("created_at", "")
    if isinstance(created_at, str) and "T" in created_at:
        date_part = created_at.split("T", 1)[0]
    else:
        date_part = datetime.now(UTC).strftime("%Y-%m-%d")
    return f"{company_name}_{date_part}.pdf"


def _mint_pdf_url(bucket: str, s3_key: str, filename: str) -> str:
    """Mint a short-lived presigned ``GetObject`` URL for the cached PDF.

    The ``ResponseContentDisposition`` override forces the browser to
    treat the response as a download with our sanitized filename rather
    than displaying it inline. This matches the existing synchronous
    handler's UX (a download dialog, not an in-tab preview).
    """
    return _get_s3_client().generate_presigned_url(
        "get_object",
        Params={
            "Bucket": bucket,
            "Key": s3_key,
            "ResponseContentType": "application/pdf",
            "ResponseContentDisposition": f'attachment; filename="{filename}"',
        },
        ExpiresIn=PRESIGNED_URL_EXPIRES_SECONDS,
    )


def delete_cached_pdf(s3_key: str) -> bool:
    """Best-effort delete of a cached PDF object from the exports bucket.

    Used by the re-analyse handler to invalidate the cached PDF when
    the underlying analysis is regenerated. Returns ``True`` on success,
    ``False`` if the bucket is unconfigured or the delete failed. Never
    raises — re-analyse must not be blocked by an S3 outage. The
    DynamoDB ``pdf_export`` row is cleared separately by the caller;
    the object lifecycle is independent.

    A missing key (``NoSuchKey``) is also treated as success — DeleteObject
    is idempotent in S3's API anyway, and "object already gone" is the
    desired post-state.
    """
    bucket = os.environ.get(PDF_EXPORTS_BUCKET_ENVIRONMENT_NAME, "")
    if not bucket:
        logger.warning("delete_cached_pdf_bucket_not_configured", extra={"s3_key": s3_key})
        return False
    try:
        _get_s3_client().delete_object(Bucket=bucket, Key=s3_key)
    except (BotoCoreError, ClientError):
        logger.warning(
            "delete_cached_pdf_failed",
            extra={"s3_key": s3_key},
            exc_info=True,
        )
        return False
    return True


def _parse_iso_datetime(value: str) -> datetime:
    """Parse an ISO8601 string (with or without trailing ``Z``).

    DynamoDB stores timestamps as opaque strings. We round-trip them
    through ``datetime.fromisoformat`` for arithmetic; Python 3.12
    accepts ``+00:00`` but not the legacy ``Z`` suffix, so normalize
    first.
    """
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


def _is_rendering_stale(started_at_iso: str, now: datetime) -> bool:
    """Return True if a ``rendering`` record is older than the stale window.

    Corrupt timestamps (unparseable) are treated as stale so callers
    re-trigger a render rather than getting stuck forever — better to
    pay an extra render than to lock the user out.
    """
    try:
        started_at = _parse_iso_datetime(started_at_iso)
    except ValueError:
        logger.warning(
            "pdf_export_unparseable_started_at",
            extra={"value": started_at_iso},
        )
        return True
    return (now - started_at).total_seconds() > RENDERING_STALE_AFTER_SECONDS


def register_routes(router: Router, storage: DynamoDBStorageProvider) -> None:
    """Wire async PDF export routes — both Cognito-protected."""
    router.protected(
        "POST",
        "/api/export/pdf/{analysis_id}",
        lambda event, authentication, analysis_id: handle_post_export(
            event, authentication, storage, analysis_id
        ),
    )
    router.protected(
        "GET",
        "/api/export/pdf/{analysis_id}/status",
        lambda event, authentication, analysis_id: handle_get_export_status(
            event, authentication, storage, analysis_id
        ),
    )


def handle_post_export(
    _event: dict[str, Any],
    authentication: AuthContext,
    storage: DynamoDBStorageProvider,
    analysis_id: str,
) -> LambdaResponse:
    """POST /api/export/pdf/<analysisId> — kick off or serve a cached PDF."""
    bucket = os.environ.get(PDF_EXPORTS_BUCKET_ENVIRONMENT_NAME, "")
    render_arn = os.environ.get(PDF_RENDER_LAMBDA_ARN_ENVIRONMENT_NAME, "")
    frontend_base_url = os.environ.get(FRONTEND_BASE_URL_ENVIRONMENT_NAME, "")
    if not bucket or not render_arn or not frontend_base_url:
        logger.error(
            "pdf_export_not_configured",
            extra={
                "bucket_set": bool(bucket),
                "render_arn_set": bool(render_arn),
                "frontend_base_url_set": bool(frontend_base_url),
            },
        )
        return build_error("PDF export not configured", 500, NOT_CONFIGURED)

    company_repo = storage.create_company_repository()
    company = company_repo.get_by_id(analysis_id)
    if error := check_org_access(company, authentication):
        return error

    assessment_repo = storage.create_assessment_repository()
    record = assessment_repo.get_pdf_export(analysis_id)
    now = datetime.now(UTC)

    # Cache hit — return a fresh presigned URL.
    if record and record["status"] == "ready":
        filename = _build_download_filename(company)
        url = _mint_pdf_url(bucket, record["s3_key"], filename)
        return build_json_response({
            "status": "ready",
            "url": url,
            "generatedAt": record.get("generated_at"),
        })

    # In-flight, not stale — dedupe: return existing ``started_at`` without re-enqueueing.
    if (
        record
        and record["status"] == "rendering"
        and not _is_rendering_stale(record["started_at"], now)
    ):
        return build_json_response(
            {
                "status": "rendering",
                "startedAt": record["started_at"],
            },
            202,
        )

    # Absent / failed / stale-rendering — write fresh ``rendering`` + async-invoke.
    s3_key = f"{S3_KEY_PREFIX}/{analysis_id}.pdf"
    started_at_iso = now.isoformat()
    assessment_repo.save_pdf_export(
        analysis_id,
        {
            "status": "rendering",
            "s3_key": s3_key,
            "started_at": started_at_iso,
        },
    )

    # Mint a fresh URL token for the Lambda's headless browser to
    # navigate ``/print/<id>?t=<token>``. The print route verifies the
    # HMAC server-side. 60-second TTL covers the typical ~13 s render.
    try:
        token = sign_pdf_token(
            analysis_id=analysis_id,
            org_id=authentication.org_id,
            secret=read_pdf_token_secret(),
        )
    except (RuntimeError, ClientError):
        logger.exception("pdf_export_token_sign_failed", extra={"analysis_id": analysis_id})
        return build_error("PDF export token unavailable", 500, NOT_CONFIGURED)

    payload = {
        "analysisId": analysis_id,
        "s3Key": s3_key,
        "startedAt": started_at_iso,
        "companyName": company.get("company_name", ""),
        "token": token,
        "frontendBaseUrl": frontend_base_url,
    }
    try:
        _get_lambda_client().invoke(
            FunctionName=render_arn,
            InvocationType="Event",
            Payload=json.dumps(payload).encode("utf-8"),
        )
    except (BotoCoreError, ClientError):
        # Couldn't enqueue — mark failed so the next click re-triggers
        # instead of polling forever. Detail goes to CloudWatch; the
        # user-facing message stays generic.
        logger.exception(
            "pdf_export_async_invoke_failed",
            extra={"analysis_id": analysis_id},
        )
        assessment_repo.save_pdf_export(
            analysis_id,
            {
                "status": "failed",
                "s3_key": s3_key,
                "started_at": started_at_iso,
                "error": "Async invocation failed",
            },
        )
        return build_error("PDF export failed to enqueue", 502)

    logger.info(
        "pdf_export_enqueued",
        extra={
            "user_id": authentication.user_id,
            "org_id": authentication.org_id,
            "analysis_id": analysis_id,
        },
    )
    return build_json_response(
        {
            "status": "rendering",
            "startedAt": started_at_iso,
        },
        202,
    )


def handle_get_export_status(
    _event: dict[str, Any],
    authentication: AuthContext,
    storage: DynamoDBStorageProvider,
    analysis_id: str,
) -> LambdaResponse:
    """GET /api/export/pdf/<analysisId>/status — frontend polling target."""
    bucket = os.environ.get(PDF_EXPORTS_BUCKET_ENVIRONMENT_NAME, "")
    if not bucket:
        logger.error("pdf_export_status_not_configured")
        return build_error("PDF export not configured", 500, NOT_CONFIGURED)

    company_repo = storage.create_company_repository()
    company = company_repo.get_by_id(analysis_id)
    if error := check_org_access(company, authentication):
        return error

    assessment_repo = storage.create_assessment_repository()
    record = assessment_repo.get_pdf_export(analysis_id)
    if record is None:
        return build_json_response({"status": "none"})

    status = record["status"]
    now = datetime.now(UTC)

    # Stale rendering — surface as ``failed`` without persisting the
    # transition. The next POST sees the same stale window and is
    # permitted to enqueue a fresh render (see ``handle_post_export``).
    if status == "rendering" and _is_rendering_stale(record["started_at"], now):
        return build_json_response({
            "status": "failed",
            "error": "Render appears stuck; try again.",
        })

    if status == "ready":
        filename = _build_download_filename(company)
        url = _mint_pdf_url(bucket, record["s3_key"], filename)
        return build_json_response({
            "status": "ready",
            "url": url,
            "generatedAt": record.get("generated_at"),
        })

    if status == "failed":
        return build_json_response({
            "status": "failed",
            "error": record.get("error", "Render failed"),
        })

    return build_json_response({
        "status": "rendering",
        "startedAt": record["started_at"],
    })

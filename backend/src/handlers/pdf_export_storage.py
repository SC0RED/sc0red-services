"""S3 helpers for the async PDF export flow.

Houses the bucket-facing primitives that ``pdf_export_handlers`` and
the re-analyse handler both use: presigned-URL minting, the
``delete_cached_pdf`` helper, and the filename-sanitization logic that
shapes the user-facing download name.

Extracted from ``pdf_export_handlers.py`` so that file stays under the
400-line backend limit. Module-level boto3 client survives Lambda
warm-restart, avoiding the ~50 ms client init per invocation.
"""

from __future__ import annotations

import logging
import os
import re
from datetime import UTC, datetime
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger(__name__)

PDF_EXPORTS_BUCKET_ENVIRONMENT_NAME = "PDF_EXPORTS_BUCKET"

# Presigned URL TTL. 60 s is plenty for the browser to follow the
# redirect; a tighter window than ``ExpiresIn`` defaults (3600 s) limits
# the blast radius if the URL is ever logged or shared.
PRESIGNED_URL_EXPIRES_SECONDS = 60

# S3 object key prefix. One object per analysis — re-renders overwrite
# the same key. Re-analyse explicitly deletes the object as part of
# its invalidation step.
S3_KEY_PREFIX = "pdf-exports"


_s3_client: Any = None


def get_s3_client() -> Any:
    """Cached boto3 S3 client (module-level cache survives container reuse).

    Pinned to SigV4 + virtual-hosted-style addressing explicitly. Both
    are normally boto3 defaults for non-us-east-1 buckets, but on some
    boto3 versions the default resolution can drift between
    ``generate_presigned_url``'s URL output and S3's reconstructed
    canonical request — observed as a ``SignatureDoesNotMatch`` 403 on
    us-east-2 even though both the URL host and the credential scope
    referenced ``us-east-2`` correctly. Making the signing config
    explicit eliminates the drift surface.

    The ``region_name`` falls back to the Lambda runtime's
    ``AWS_REGION`` (always set by Lambda). Pinning it explicitly avoids
    any default-region resolution path.
    """
    global _s3_client
    if _s3_client is None:
        region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
        _s3_client = boto3.client(
            "s3",
            region_name=region,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "virtual"},
            ),
        )
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


def build_download_filename(company: dict[str, Any]) -> str:
    """Build a sensible PDF download filename: ``<CompanyName>_<YYYY-MM-DD>.pdf``."""
    company_name = _sanitize_filename_segment(str(company.get("company_name", "analysis")))
    created_at = company.get("created_at", "")
    if isinstance(created_at, str) and "T" in created_at:
        date_part = created_at.split("T", 1)[0]
    else:
        date_part = datetime.now(UTC).strftime("%Y-%m-%d")
    return f"{company_name}_{date_part}.pdf"


def mint_pdf_url(bucket: str, s3_key: str, filename: str) -> str:  # noqa: NAMING001 mint is a verb (mint a URL); not in the script's heuristic verb list
    """Mint a short-lived presigned ``GetObject`` URL for the cached PDF.

    The ``ResponseContentDisposition`` override forces the browser to
    treat the response as a download with our sanitized filename rather
    than displaying it inline.
    """
    return get_s3_client().generate_presigned_url(
        "get_object",
        Params={
            "Bucket": bucket,
            "Key": s3_key,
            "ResponseContentType": "application/pdf",
            "ResponseContentDisposition": f'attachment; filename="{filename}"',
        },
        ExpiresIn=PRESIGNED_URL_EXPIRES_SECONDS,
    )


def delete_cached_pdf(s3_key: str) -> bool:  # noqa: NAMING001  action verb; bool is success/failure
    """Best-effort delete of a cached PDF object from the exports bucket.

    Used by the re-analyse handler to invalidate the cached PDF when
    the underlying analysis is regenerated. Returns ``True`` on success,
    ``False`` if the bucket is unconfigured or the delete failed. Never
    raises — re-analyse must not be blocked by an S3 outage. The
    DynamoDB ``pdf_export`` row is cleared separately by the caller;
    the object lifecycle is independent.

    A missing key (``NoSuchKey``) is treated as success — ``DeleteObject``
    is idempotent in S3's API anyway.
    """
    bucket = os.environ.get(PDF_EXPORTS_BUCKET_ENVIRONMENT_NAME, "")
    if not bucket:
        logger.warning("delete_cached_pdf_bucket_not_configured", extra={"s3_key": s3_key})
        return False
    try:
        get_s3_client().delete_object(Bucket=bucket, Key=s3_key)
    except (BotoCoreError, ClientError):
        logger.warning(
            "delete_cached_pdf_failed",
            extra={"s3_key": s3_key},
            exc_info=True,
        )
        return False
    return True


def _reset_caches_for_tests() -> None:
    """Reset the module-level boto3 client cache between tests."""
    global _s3_client
    _s3_client = None

"""Document handlers — upload URL, create document, delete document."""

from __future__ import annotations

import base64
import json
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from botocore.exceptions import ClientError

from src.documents.extract_text import SUPPORTED_TYPES, extract_text
from src.handlers.api_gateway_handler import (
    NOT_CONFIGURED,
    NOT_FOUND,
    VALIDATION_ERROR,
    build_error,
    build_json_response,
    check_org_access,
)

if TYPE_CHECKING:
    from src.handlers.api_gateway_handler import LambdaResponse
    from src.handlers.auth_middleware import AuthContext
    from src.repositories.dynamodb.provider import DynamoDBStorageProvider


def handle_upload_url(
    event: dict[str, Any],
    authentication: AuthContext,
    storage: DynamoDBStorageProvider,
    s3: Any,
    documents_bucket: str,
    analysis_id: str,
) -> LambdaResponse:
    """Handle POST /api/analysis/{analysis_id}/upload-url."""
    if not s3 or not documents_bucket:
        return build_error("Document uploads via S3 not configured", 501, NOT_CONFIGURED)

    body = json.loads(event.get("body") or "{}")
    filename = body.get("filename", "")
    file_type = body.get("fileType", "")
    if not filename or not file_type:
        return build_error("filename and fileType required", code=VALIDATION_ERROR)

    if file_type not in SUPPORTED_TYPES:
        return build_error(f"Unsupported file type: {file_type}", code=VALIDATION_ERROR)

    company_repo = storage.create_company_repository()
    company = company_repo.get_by_id(analysis_id)
    if error := check_org_access(company, authentication):
        return error

    document_key = f"uploads/{analysis_id}/{uuid.uuid4()}.{file_type}"

    upload_url = s3.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": documents_bucket,
            "Key": document_key,
            "ContentType": "application/octet-stream",
        },
        ExpiresIn=300,
    )

    return build_json_response({"uploadUrl": upload_url, "documentKey": document_key})


def handle_create_document(
    event: dict[str, Any],
    authentication: AuthContext,
    storage: DynamoDBStorageProvider,
    s3: Any,
    documents_bucket: str,
    analysis_id: str,
) -> LambdaResponse:
    """Handle POST /api/analysis/{analysis_id}/documents."""
    body = json.loads(event.get("body") or "{}")
    filename = body.get("filename", "")
    file_type = body.get("fileType", "")
    document_key = body.get("documentKey", "")
    file_content_b64 = body.get("fileContent", "")

    if not filename or not file_type:
        return build_error("filename and fileType required", code=VALIDATION_ERROR)

    company_repo = storage.create_company_repository()
    company = company_repo.get_by_id(analysis_id)
    if error := check_org_access(company, authentication):
        return error

    # Get file bytes — from S3 if documentKey provided, else from base64 body
    if document_key:
        if not s3 or not documents_bucket:
            return build_error(
                "S3 not configured — cannot retrieve uploaded file",
                500,
                NOT_CONFIGURED,
            )
        expected_prefix = f"uploads/{analysis_id}/"
        if not document_key.startswith(expected_prefix):
            return build_error("Invalid documentKey", 400, VALIDATION_ERROR)
        try:
            response = s3.get_object(
                Bucket=documents_bucket,
                Key=document_key,
            )
            file_bytes = response["Body"].read()
        except ClientError as error:
            code = error.response["Error"]["Code"]
            if code == "NoSuchKey":
                return build_error(
                    "Uploaded file not found — presigned URL may have expired",
                    404,
                    NOT_FOUND,
                )
            raise
    elif file_content_b64:
        file_bytes = base64.b64decode(file_content_b64)
    else:
        return build_error("documentKey or fileContent required", code=VALIDATION_ERROR)

    try:
        extracted_text = extract_text(file_bytes, file_type)
    except ValueError as error:
        return build_error(str(error))

    assessment_repo = storage.create_assessment_repository()
    assessments = assessment_repo.find_by_company(analysis_id)
    if not assessments:
        return build_error("No assessment found for this analysis", 404, NOT_FOUND)

    assessment_id = assessments[0]["id"]
    document_id = str(uuid.uuid4())
    document = {
        "id": document_id,
        "filename": filename,
        "file_type": file_type,
        "extracted_text": extracted_text,
        "char_count": len(extracted_text),
        "uploaded_at": datetime.now(UTC).isoformat(),
    }
    assessment_repo.save_document(assessment_id, document)

    return build_json_response(
        {
            "id": document_id,
            "filename": filename,
            "fileType": file_type,
            "charCount": len(extracted_text),
        },
        201,
    )


def handle_delete_document(
    _event: dict[str, Any],
    authentication: AuthContext,
    storage: DynamoDBStorageProvider,
    analysis_id: str,
    document_id: str,
) -> LambdaResponse:
    """Handle DELETE /api/analysis/{analysis_id}/documents/{document_id}."""
    company_repo = storage.create_company_repository()
    company = company_repo.get_by_id(analysis_id)
    if error := check_org_access(company, authentication):
        return error

    assessment_repo = storage.create_assessment_repository()
    assessments = assessment_repo.find_by_company(analysis_id)
    if not assessments:
        return build_error("No assessment found", 404, NOT_FOUND)

    assessment_repo.delete_document(assessments[0]["id"], document_id)
    return build_json_response({"ok": True})

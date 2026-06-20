"""Company-list upload handler — parse a customer CSV/PDF into scan candidates.

Stateless on purpose: this turns an uploaded file into ``{name, url}``
candidates that the portfolio confirmation screen merges into its editable list,
then scans through the existing confirm path. It does not mutate scan state, so
it needs no scan id — only that the caller is an authenticated org member, which
the protected route enforces.
"""

from __future__ import annotations

import base64
import binascii
import json
from typing import TYPE_CHECKING, Any

from src.documents.parse_company_list import SUPPORTED_LIST_TYPES, parse_company_list
from src.handlers.api_gateway_handler import VALIDATION_ERROR, build_error, build_json_response

if TYPE_CHECKING:
    from src.handlers.api_gateway_handler import LambdaResponse
    from src.handlers.auth_middleware import AuthContext


def handle_parse_company_list(
    event: dict[str, Any],
    _authentication: AuthContext,
) -> LambdaResponse:
    """Handle POST /api/portfolio/parse-company-list.

    Body: ``{"fileType": "csv", "fileContent": "<base64>"}``. Returns the parsed
    candidates plus counts so the UI can tell the customer how many still need a
    URL before the scan can run.
    """
    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError as error:
        return build_error(f"Invalid JSON body: {error}", code=VALIDATION_ERROR)
    file_type = body.get("fileType", "")
    file_content_b64 = body.get("fileContent", "")

    if not file_type or not file_content_b64:
        return build_error("fileType and fileContent required", code=VALIDATION_ERROR)
    if file_type.lower().strip(".") not in SUPPORTED_LIST_TYPES:
        return build_error(f"Unsupported file type: {file_type}", code=VALIDATION_ERROR)

    try:
        file_bytes = base64.b64decode(file_content_b64, validate=True)
    except (binascii.Error, ValueError):
        return build_error("fileContent must be valid base64", code=VALIDATION_ERROR)

    try:
        companies = parse_company_list(file_bytes, file_type)
    except ValueError as error:
        return build_error(str(error), code=VALIDATION_ERROR)

    with_url = sum(1 for company in companies if company["url"])
    return build_json_response(
        {
            "companies": companies,
            "count": len(companies),
            "withUrl": with_url,
            "needsUrl": len(companies) - with_url,
        }
    )

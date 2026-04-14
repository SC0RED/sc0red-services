"""OAuth consent approval handler.

Called by the frontend consent UI when the user clicks "Allow Access".
Generates an authorization code and returns the redirect URL.
"""

from __future__ import annotations

import json
import logging
import os
from typing import TYPE_CHECKING, Any
from urllib.parse import urlencode

from src.mcp.oauth_repository import OAuthRepository
from src.mcp.token_utils import generate_authorization_code

if TYPE_CHECKING:
    from src.handlers.auth_middleware import AuthContext
    from src.repositories.dynamodb.provider import DynamoDBStorageProvider

logger = logging.getLogger(__name__)

_TABLE_NAME = os.environ.get("DYNAMODB_TABLE", "janus-dev")
_repository = OAuthRepository(_TABLE_NAME)


def handle_oauth_approve(
    event: dict[str, Any],
    authentication: AuthContext,
    _storage: DynamoDBStorageProvider,
) -> dict[str, Any]:
    """Generate authorization code and return redirect URL.

    Called after user consents on the OAuth authorize page.
    """
    from src.handlers.api_gateway_handler import build_error, build_json_response

    body = json.loads(event.get("body") or "{}")

    client_id = body.get("client_id", "")
    redirect_uri = body.get("redirect_uri", "")
    code_challenge = body.get("code_challenge", "")
    scope = body.get("scope", "read write")
    state = body.get("state", "")

    if not client_id or not redirect_uri or not code_challenge:
        return build_error("client_id, redirect_uri, and code_challenge are required", 400)

    client = _repository.get_client(client_id)
    if not client:
        return build_error("Unknown client_id", 400)

    if redirect_uri not in client.get("redirect_uris", []):
        return build_error("Invalid redirect_uri", 400)

    code = generate_authorization_code()
    scopes = scope.split() if isinstance(scope, str) else scope

    _repository.save_authorization_code(
        code,
        client_id=client_id,
        user_id=authentication.user_id,
        org_id=authentication.org_id,
        email=authentication.email,
        role=authentication.role,
        code_challenge=code_challenge,
        redirect_uri=redirect_uri,
        scopes=scopes,
    )

    _repository.save_consent(authentication.user_id, client_id)

    query_params: dict[str, str] = {"code": code}
    if state:
        query_params["state"] = state

    separator = "&" if "?" in redirect_uri else "?"
    redirect_url = f"{redirect_uri}{separator}{urlencode(query_params)}"

    logger.info(
        "OAuth consent approved: user=%s client=%s",
        authentication.user_id,
        client_id,
    )

    return build_json_response({"redirect_url": redirect_url})

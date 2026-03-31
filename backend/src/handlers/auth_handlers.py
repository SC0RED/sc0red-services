"""Authentication handlers — registration with Cognito + DynamoDB."""

from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING, Any

from src.handlers.api_gateway_handler import build_error, build_json_response
from src.handlers.cognito_client import CognitoClient

if TYPE_CHECKING:
    from src.handlers.api_gateway_handler import LambdaResponse
    from src.repositories.dynamodb.provider import DynamoDBStorageProvider


def handle_register(event: dict[str, Any], storage: DynamoDBStorageProvider) -> LambdaResponse:
    """Handle POST /api/auth/register — create org + user in DynamoDB and Cognito."""
    body = json.loads(event.get("body") or "{}")
    name = body.get("name", "")
    email = body.get("email", "")
    password = body.get("password", "")
    org_name = body.get("orgName", "")
    org_type = body.get("orgType", "company")

    if not all([name, email, password, org_name]):
        return build_error("All fields required")

    user_repo = storage.create_user_repository()
    org_repo = storage.create_organization_repository()

    if user_repo.has_email(email):
        return build_error("Email already registered")

    org_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())

    # Create org in DynamoDB
    org_repo.create({"id": org_id, "name": org_name, "type": org_type})

    # Create user in Cognito (with permanent password, CONFIRMED status)
    cognito_client = CognitoClient()
    cognito_sub = cognito_client.create_user_with_password(
        email=email,
        password=password,
        name=name,
        org_id=org_id,
        role="admin",
        legacy_user_id=user_id,
    )

    # Create user in DynamoDB (for org membership and internal references)
    user_repo.create(
        {
            "id": user_id,
            "org_id": org_id,
            "email": email,
            "name": name,
            "role": "admin",
            "cognito_sub": cognito_sub,
        }
    )

    return build_json_response({"success": True})

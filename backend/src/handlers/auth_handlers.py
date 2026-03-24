"""Authentication handlers — register and login."""

from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING, Any

import bcrypt

from src.handlers.api_gateway_handler import error_response, json_response

if TYPE_CHECKING:
    from src.handlers.api_gateway_handler import LambdaResponse
    from src.repositories.dynamodb.provider import DynamoDBStorageProvider


def handle_register(event: dict[str, Any], storage: DynamoDBStorageProvider) -> LambdaResponse:
    """Handle POST /api/auth/register."""
    body = json.loads(event.get("body") or "{}")
    name = body.get("name", "")
    email = body.get("email", "")
    password = body.get("password", "")
    org_name = body.get("orgName", "")
    org_type = body.get("orgType", "company")

    if not all([name, email, password, org_name]):
        return error_response("All fields required")

    user_repo = storage.create_user_repository()
    org_repo = storage.create_organization_repository()

    if user_repo.has_email(email):
        return error_response("Email already registered")

    org_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt(10)).decode()

    org_repo.create({"id": org_id, "name": org_name, "type": org_type})
    user_repo.create(
        {
            "id": user_id,
            "org_id": org_id,
            "email": email,
            "password_hash": password_hash,
            "name": name,
            "role": "admin",
        }
    )

    return json_response({"success": True})


def handle_login(event: dict[str, Any], storage: DynamoDBStorageProvider) -> LambdaResponse:
    """Handle POST /api/auth/login."""
    body = json.loads(event.get("body") or "{}")
    email = body.get("email", "")
    password = body.get("password", "")

    if not email or not password:
        return error_response("Email and password required")

    user_repo = storage.create_user_repository()
    user_info = user_repo.verify_password(email, password)
    if not user_info:
        return error_response("Invalid credentials", 401)

    return json_response({"success": True, "user": user_info})

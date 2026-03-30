"""Invitation and org member management handlers.

Admin users can invite members, list org members, and remove members.
Invited users accept invitations by setting their Cognito password.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from src.handlers.api_gateway_handler import build_error, build_json_response
from src.handlers.cognito_client import CognitoClient

if TYPE_CHECKING:
    from src.handlers.api_gateway_handler import LambdaResponse
    from src.handlers.auth_middleware import AuthContext
    from src.repositories.dynamodb.provider import DynamoDBStorageProvider


def handle_invite_member(
    event: dict[str, Any],
    authentication: AuthContext,
    storage: DynamoDBStorageProvider,
) -> LambdaResponse:
    """Handle POST /api/org/invite — admin invites a new member."""
    if authentication.role != "admin":
        return build_error("Only admins can invite members", 403)

    body = json.loads(event.get("body") or "{}")
    email = body.get("email", "").strip().lower()
    role = body.get("role", "analyst")

    if not email:
        return build_error("Email is required")

    if role not in ("analyst", "viewer"):
        return build_error("Role must be 'analyst' or 'viewer'")

    user_repo = storage.create_user_repository()
    if user_repo.has_email(email):
        return build_error("A user with this email already exists")

    invite_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    expires_at = now + timedelta(days=7)

    # Create Cognito user (sends invitation email with temp password)
    cognito_client = CognitoClient()
    cognito_sub = cognito_client.invite_user(
        email=email,
        org_id=authentication.org_id,
        role=role,
    )

    # Store invitation record in DynamoDB
    invitation = {
        "id": invite_id,
        "org_id": authentication.org_id,
        "email": email,
        "role": role,
        "invited_by": authentication.user_id,
        "cognito_sub": cognito_sub,
        "status": "pending",
        "created_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
    }

    invitation_repo = storage.create_invitation_repository()
    invitation_repo.create(invitation)

    return build_json_response({"invitationId": invite_id, "email": email}, 201)


def handle_list_members(
    _event: dict[str, Any],
    authentication: AuthContext,
    storage: DynamoDBStorageProvider,
) -> LambdaResponse:
    """Handle GET /api/org/members — list all org members."""
    user_repo = storage.create_user_repository()
    users = user_repo.find_by_org(authentication.org_id)

    members = [
        {
            "id": user.get("id", ""),
            "email": user.get("email", ""),
            "name": user.get("name", ""),
            "role": user.get("role", "analyst"),
        }
        for user in users
    ]

    # Also include pending invitations
    invitation_repo = storage.create_invitation_repository()
    invitations = invitation_repo.find_by_org(authentication.org_id)
    pending = [
        {
            "id": invitation["id"],
            "email": invitation.get("email", ""),
            "role": invitation.get("role", "analyst"),
            "status": "pending",
            "invitedAt": invitation.get("created_at", ""),
        }
        for invitation in invitations
        if invitation.get("status") == "pending"
    ]

    return build_json_response({"members": members, "pendingInvitations": pending})


def handle_remove_member(
    _event: dict[str, Any],
    authentication: AuthContext,
    storage: DynamoDBStorageProvider,
    user_id: str,
) -> LambdaResponse:
    """Handle DELETE /api/org/members/{user_id} — admin removes a member."""
    if authentication.role != "admin":
        return build_error("Only admins can remove members", 403)

    if user_id == authentication.user_id:
        return build_error("Cannot remove yourself")

    user_repo = storage.create_user_repository()
    user = user_repo.get_by_id(user_id)

    if not user or user.get("org_id") != authentication.org_id:
        return build_error("Member not found", 404)

    # Delete from Cognito
    email = user.get("email", "")
    if email:
        cognito_client = CognitoClient()
        cognito_client.delete_user(email)

    # Delete from DynamoDB
    user_repo.delete(user_id)

    return build_json_response({"deleted": True})

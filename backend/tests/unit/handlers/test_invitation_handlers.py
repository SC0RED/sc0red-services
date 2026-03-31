"""Tests for invitation and org member management handlers."""

import json
from unittest.mock import MagicMock, patch

from src.handlers.auth_middleware import AuthContext
from src.handlers.invitation_handlers import (
    handle_invite_member,
    handle_list_members,
    handle_remove_member,
    handle_resend_invite,
    handle_revoke_invite,
)


def _make_auth(role: str = "admin", org_id: str = "org-1", user_id: str = "user-1") -> AuthContext:
    return AuthContext(user_id=user_id, org_id=org_id, email="admin@test.com", role=role)


def _make_event(body: dict | None = None) -> dict:
    return {"body": json.dumps(body or {})}


class TestInviteMember:
    @patch("src.handlers.invitation_handlers.CognitoClient")
    def test_successful_invite(self, mock_cognito_cls):
        mock_cognito = MagicMock()
        mock_cognito.invite_user.return_value = "cognito-sub-123"
        mock_cognito_cls.return_value = mock_cognito

        storage = MagicMock()
        storage.create_user_repository.return_value.has_email.return_value = False
        storage.create_invitation_repository.return_value = MagicMock()

        event = _make_event({"email": "analyst@test.com", "role": "analyst"})
        result = handle_invite_member(event, _make_auth(), storage)

        assert result["statusCode"] == 201
        body = json.loads(result["body"])
        assert "invitationId" in body
        assert body["email"] == "analyst@test.com"

        mock_cognito.invite_user.assert_called_once()

    def test_non_admin_rejected(self):
        storage = MagicMock()
        event = _make_event({"email": "a@b.com", "role": "analyst"})
        result = handle_invite_member(event, _make_auth(role="analyst"), storage)

        assert result["statusCode"] == 403

    def test_missing_email_rejected(self):
        storage = MagicMock()
        event = _make_event({"role": "analyst"})
        result = handle_invite_member(event, _make_auth(), storage)

        assert result["statusCode"] == 400

    def test_invalid_role_rejected(self):
        storage = MagicMock()
        event = _make_event({"email": "a@b.com", "role": "superadmin"})
        result = handle_invite_member(event, _make_auth(), storage)

        assert result["statusCode"] == 400

    def test_existing_email_rejected(self):
        storage = MagicMock()
        storage.create_user_repository.return_value.has_email.return_value = True

        event = _make_event({"email": "existing@test.com", "role": "analyst"})
        result = handle_invite_member(event, _make_auth(), storage)

        assert result["statusCode"] == 400
        assert "already exists" in json.loads(result["body"])["error"]


class TestListMembers:
    def test_returns_members_and_pending(self):
        storage = MagicMock()
        storage.create_user_repository.return_value.find_by_org.return_value = [
            {"id": "u1", "email": "a@b.com", "name": "Alice", "role": "admin"},
        ]
        storage.create_invitation_repository.return_value.find_by_org.return_value = [
            {"id": "inv1", "email": "b@b.com", "role": "analyst", "status": "pending", "created_at": "2026-01-01"},
        ]

        result = handle_list_members({}, _make_auth(), storage)

        body = json.loads(result["body"])
        assert len(body["members"]) == 1
        assert body["members"][0]["email"] == "a@b.com"
        assert len(body["pendingInvitations"]) == 1
        assert body["pendingInvitations"][0]["email"] == "b@b.com"


class TestResendInvite:
    @patch("src.handlers.invitation_handlers.CognitoClient")
    def test_successful_resend(self, mock_cognito_cls):
        mock_cognito = MagicMock()
        mock_cognito_cls.return_value = mock_cognito

        storage = MagicMock()
        event = _make_event({"email": "pending@test.com"})
        result = handle_resend_invite(event, _make_auth(), storage)

        assert result["statusCode"] == 200
        mock_cognito.resend_invitation.assert_called_once_with("pending@test.com")

    def test_non_admin_rejected(self):
        storage = MagicMock()
        event = _make_event({"email": "a@b.com"})
        result = handle_resend_invite(event, _make_auth(role="analyst"), storage)
        assert result["statusCode"] == 403

    def test_missing_email_rejected(self):
        storage = MagicMock()
        event = _make_event({})
        result = handle_resend_invite(event, _make_auth(), storage)
        assert result["statusCode"] == 400


class TestRevokeInvite:
    @patch("src.handlers.invitation_handlers.CognitoClient")
    def test_successful_revoke(self, mock_cognito_cls):
        mock_cognito = MagicMock()
        mock_cognito_cls.return_value = mock_cognito

        storage = MagicMock()
        storage.create_invitation_repository.return_value.find_by_org.return_value = [
            {"id": "inv-1", "email": "pending@test.com", "status": "pending"},
        ]

        result = handle_revoke_invite({}, _make_auth(), storage, "inv-1")

        assert result["statusCode"] == 200
        mock_cognito.delete_user.assert_called_once_with("pending@test.com")
        storage.create_invitation_repository.return_value.update_status.assert_called_once_with(
            "org-1", "inv-1", "revoked"
        )

    def test_non_admin_rejected(self):
        storage = MagicMock()
        result = handle_revoke_invite({}, _make_auth(role="analyst"), storage, "inv-1")
        assert result["statusCode"] == 403

    def test_invitation_not_found(self):
        storage = MagicMock()
        storage.create_invitation_repository.return_value.find_by_org.return_value = []

        result = handle_revoke_invite({}, _make_auth(), storage, "nonexistent")
        assert result["statusCode"] == 404


class TestRemoveMember:
    @patch("src.handlers.invitation_handlers.CognitoClient")
    def test_successful_remove(self, mock_cognito_cls):
        mock_cognito = MagicMock()
        mock_cognito_cls.return_value = mock_cognito

        storage = MagicMock()
        storage.create_user_repository.return_value.get_by_id.return_value = {
            "id": "user-2",
            "org_id": "org-1",
            "email": "removed@test.com",
        }

        result = handle_remove_member({}, _make_auth(), storage, "user-2")

        assert result["statusCode"] == 200
        mock_cognito.delete_user.assert_called_once_with("removed@test.com")

    def test_non_admin_rejected(self):
        storage = MagicMock()
        result = handle_remove_member({}, _make_auth(role="analyst"), storage, "user-2")
        assert result["statusCode"] == 403

    def test_cannot_remove_self(self):
        storage = MagicMock()
        result = handle_remove_member({}, _make_auth(user_id="user-1"), storage, "user-1")
        assert result["statusCode"] == 400

    def test_member_not_found(self):
        storage = MagicMock()
        storage.create_user_repository.return_value.get_by_id.return_value = None

        result = handle_remove_member({}, _make_auth(), storage, "nonexistent")
        assert result["statusCode"] == 404

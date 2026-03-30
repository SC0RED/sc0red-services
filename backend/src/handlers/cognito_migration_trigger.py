"""Cognito User Migration Lambda trigger.

Transparently migrates existing DynamoDB users to Cognito on first login.
Handles two trigger sources:
- UserMigration_Authentication: validates bcrypt password, creates Cognito user
- UserMigration_ForgotPassword: enables password reset for unmigrated users
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import bcrypt

if TYPE_CHECKING:
    from src.repositories.dynamodb.user_repository import DynamoDBUserRepository

logger = logging.getLogger(__name__)


def handle_migration(
    event: dict[str, Any],
    user_repo: DynamoDBUserRepository,
) -> dict[str, Any]:
    """Handle Cognito UserMigration trigger events.

    Looks up the user in DynamoDB, validates credentials (for auth trigger),
    and returns user attributes so Cognito creates the user automatically.
    """
    trigger_source = event["triggerSource"]
    email = event["userName"]

    logger.info("Migration trigger: source=%s email=%s", trigger_source, email)

    user = user_repo.find_by_email(email)
    if not user:
        logger.info("User not found in DynamoDB: %s", email)
        raise UserNotFoundError(email)

    if trigger_source == "UserMigration_Authentication":
        return _handle_authentication(event, user)

    if trigger_source == "UserMigration_ForgotPassword":
        return _handle_forgot_password(event, user)

    message = f"Unsupported trigger source: {trigger_source}"
    raise ValueError(message)


def _handle_authentication(
    event: dict[str, Any],
    user: dict[str, Any],
) -> dict[str, Any]:
    """Validate bcrypt password and return user attributes for Cognito."""
    password = event["request"]["password"]
    stored_hash = user.get("password_hash")

    if not stored_hash:
        logger.warning("User %s has no password_hash — corrupt record", user.get("email"))
        raise InvalidCredentialsError

    if not bcrypt.checkpw(password.encode(), stored_hash.encode()):
        logger.info("Invalid password for migration: %s", user.get("email"))
        raise InvalidCredentialsError

    logger.info(
        "Migrating user to Cognito: email=%s user_id=%s org_id=%s",
        user.get("email"),
        user.get("id"),
        user.get("org_id"),
    )

    event["response"]["userAttributes"] = {
        "email": user["email"],
        "email_verified": "true",
        "name": user.get("name", ""),
        "custom:org_id": user.get("org_id", ""),
        "custom:role": user.get("role", "analyst"),
        "custom:legacy_user_id": user.get("id", ""),
    }
    event["response"]["finalUserStatus"] = "CONFIRMED"
    event["response"]["messageAction"] = "SUPPRESS"

    return event


def _handle_forgot_password(
    event: dict[str, Any],
    user: dict[str, Any],
) -> dict[str, Any]:
    """Enable forgot-password flow for unmigrated users.

    Returns user attributes so Cognito creates the user and sends
    the password reset code.
    """
    logger.info("Forgot-password migration for: %s", user.get("email"))

    event["response"]["userAttributes"] = {
        "email": user["email"],
        "email_verified": "true",
        "name": user.get("name", ""),
        "custom:org_id": user.get("org_id", ""),
        "custom:role": user.get("role", "analyst"),
        "custom:legacy_user_id": user.get("id", ""),
    }
    event["response"]["messageAction"] = "SUPPRESS"

    return event


class UserNotFoundError(Exception):
    """Raised when the user does not exist in DynamoDB."""

    def __init__(self, email: str) -> None:
        super().__init__(f"User not found: {email}")


class InvalidCredentialsError(Exception):
    """Raised when the password does not match."""

    def __init__(self) -> None:
        super().__init__("Invalid credentials")

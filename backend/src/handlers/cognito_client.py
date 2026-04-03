"""Cognito admin operations wrapper.

Provides methods for user management via the Cognito Admin API:
invite users, create users, set passwords, list/remove members.
"""

from __future__ import annotations

import logging
import os

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class CognitoClient:
    """Wrapper around boto3 cognito-idp for admin operations."""

    client_error = ClientError

    def __init__(self) -> None:
        self._client = boto3.client("cognito-idp")
        self._user_pool_id = os.environ["COGNITO_USER_POOL_ID"]

    def invite_user(
        self,
        email: str,
        org_id: str,
        role: str = "analyst",
    ) -> str:
        """Create a Cognito user via admin API and send invitation email.

        Returns the Cognito sub (user UUID).
        """
        response = self._client.admin_create_user(
            UserPoolId=self._user_pool_id,
            Username=email,
            UserAttributes=[
                {"Name": "email", "Value": email},
                {"Name": "email_verified", "Value": "true"},
                {"Name": "custom:org_id", "Value": org_id},
                {"Name": "custom:role", "Value": role},
            ],
            DesiredDeliveryMediums=["EMAIL"],
        )

        cognito_sub = ""
        for attr in response["User"]["Attributes"]:
            if attr["Name"] == "sub":
                cognito_sub = attr["Value"]
                break

        logger.info(
            "Invited user to Cognito: email=%s org_id=%s role=%s sub=%s",
            email,
            org_id,
            role,
            cognito_sub,
        )
        return cognito_sub

    def create_user_with_password(
        self,
        email: str,
        password: str,
        name: str,
        org_id: str,
        role: str = "admin",
        legacy_user_id: str = "",
    ) -> str:
        """Create a Cognito user with a permanent password (for signup flow).

        Returns the Cognito sub (user UUID).
        """
        attributes = [
            {"Name": "email", "Value": email},
            {"Name": "email_verified", "Value": "true"},
            {"Name": "name", "Value": name},
            {"Name": "custom:org_id", "Value": org_id},
            {"Name": "custom:role", "Value": role},
        ]
        if legacy_user_id:
            attributes.append({"Name": "custom:legacy_user_id", "Value": legacy_user_id})

        response = self._client.admin_create_user(
            UserPoolId=self._user_pool_id,
            Username=email,
            UserAttributes=attributes,
            MessageAction="SUPPRESS",
        )

        cognito_sub = ""
        for attr in response["User"]["Attributes"]:
            if attr["Name"] == "sub":
                cognito_sub = attr["Value"]
                break

        # Set permanent password — rollback Cognito user on failure
        try:
            self._client.admin_set_user_password(
                UserPoolId=self._user_pool_id,
                Username=email,
                Password=password,
                Permanent=True,
            )
        except Exception:
            logger.warning("Password set failed, rolling back Cognito user: %s", email)
            self._client.admin_delete_user(
                UserPoolId=self._user_pool_id,
                Username=email,
            )
            raise

        logger.info(
            "Created Cognito user with password: email=%s org_id=%s sub=%s",
            email,
            org_id,
            cognito_sub,
        )
        return cognito_sub

    def resend_invitation(self, email: str) -> None:
        """Resend the invitation email with a new temporary password."""
        self._client.admin_create_user(
            UserPoolId=self._user_pool_id,
            Username=email,
            MessageAction="RESEND",
            DesiredDeliveryMediums=["EMAIL"],
        )
        logger.info("Resent invitation for: %s", email)

    def delete_user(self, email: str) -> None:
        """Delete a user from Cognito by email (username)."""
        self._client.admin_delete_user(
            UserPoolId=self._user_pool_id,
            Username=email,
        )
        logger.info("Deleted Cognito user: %s", email)

    def update_user_attributes(
        self,
        email: str,
        attributes: dict[str, str],
    ) -> None:
        """Update custom attributes on a Cognito user."""
        attr_list = [{"Name": key, "Value": value} for key, value in attributes.items()]
        self._client.admin_update_user_attributes(
            UserPoolId=self._user_pool_id,
            Username=email,
            UserAttributes=attr_list,
        )

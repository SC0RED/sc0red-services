"""Tests for CognitoClient admin operations wrapper."""

from unittest.mock import MagicMock, patch

from src.handlers.cognito_client import CognitoClient


class TestCognitoClient:
    def _make_client(self) -> tuple[CognitoClient, MagicMock]:
        with patch("src.handlers.cognito_client.boto3") as mock_boto:
            mock_cognito = MagicMock()
            mock_boto.client.return_value = mock_cognito
            with patch.dict("os.environ", {"COGNITO_USER_POOL_ID": "us-east-1_TEST"}):
                client = CognitoClient()
            return client, mock_cognito

    def test_invite_user_calls_admin_create_user(self):
        client, mock_cognito = self._make_client()
        mock_cognito.admin_create_user.return_value = {
            "User": {"Attributes": [{"Name": "sub", "Value": "sub-123"}]}
        }

        result = client.invite_user("test@example.com", "org-1", "analyst")

        assert result == "sub-123"
        call_args = mock_cognito.admin_create_user.call_args
        assert call_args.kwargs["Username"] == "test@example.com"
        assert call_args.kwargs["UserPoolId"] == "us-east-1_TEST"
        attrs = {a["Name"]: a["Value"] for a in call_args.kwargs["UserAttributes"]}
        assert attrs["custom:org_id"] == "org-1"
        assert attrs["custom:role"] == "analyst"

    def test_create_user_with_password(self):
        client, mock_cognito = self._make_client()
        mock_cognito.admin_create_user.return_value = {
            "User": {"Attributes": [{"Name": "sub", "Value": "sub-456"}]}
        }

        result = client.create_user_with_password(
            "admin@test.com", "Pass1234", "Admin User", "org-1", "admin", "legacy-id"
        )

        assert result == "sub-456"
        mock_cognito.admin_set_user_password.assert_called_once_with(
            UserPoolId="us-east-1_TEST",
            Username="admin@test.com",
            Password="Pass1234",
            Permanent=True,
        )

    def test_create_user_rolls_back_on_password_failure(self):
        from botocore.exceptions import ClientError

        client, mock_cognito = self._make_client()
        mock_cognito.admin_create_user.return_value = {
            "User": {"Attributes": [{"Name": "sub", "Value": "sub-789"}]}
        }
        mock_cognito.admin_set_user_password.side_effect = ClientError(
            {"Error": {"Code": "InvalidPasswordException", "Message": "bad"}},
            "AdminSetUserPassword",
        )

        import pytest

        with pytest.raises(ClientError):
            client.create_user_with_password(
                "user@test.com", "weak", "User", "org-1"
            )

        mock_cognito.admin_delete_user.assert_called_once_with(
            UserPoolId="us-east-1_TEST",
            Username="user@test.com",
        )

    def test_delete_user(self):
        client, mock_cognito = self._make_client()
        client.delete_user("test@example.com")

        mock_cognito.admin_delete_user.assert_called_once_with(
            UserPoolId="us-east-1_TEST",
            Username="test@example.com",
        )

    def test_update_user_attributes(self):
        client, mock_cognito = self._make_client()
        client.update_user_attributes("test@example.com", {"custom:role": "admin"})

        mock_cognito.admin_update_user_attributes.assert_called_once()
        call_args = mock_cognito.admin_update_user_attributes.call_args
        assert call_args.kwargs["Username"] == "test@example.com"
        assert {"Name": "custom:role", "Value": "admin"} in call_args.kwargs["UserAttributes"]

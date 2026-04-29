"""Tests for APIGatewayHandler."""

import base64
import json
from unittest.mock import MagicMock, patch

import pytest

from src.handlers.api_gateway_handler import APIGatewayHandler, build_error, build_json_response


class TestHelperFunctions:
    def test_build_json_response_default_status(self):
        result = build_json_response({"key": "value"})
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["key"] == "value"
        assert "Content-Type" in result["headers"]

    def test_build_json_response_custom_status(self):
        result = build_json_response({"ok": True}, 201)
        assert result["statusCode"] == 201

    def test_build_json_response_cors_headers(self):
        result = build_json_response({})
        assert result["headers"]["Access-Control-Allow-Origin"] == "*"
        assert "Authorization" in result["headers"]["Access-Control-Allow-Headers"]

    def test_build_error_response(self):
        result = build_error("bad request")
        assert result["statusCode"] == 400
        body = json.loads(result["body"])
        assert body["error"] == "bad request"

    def test_build_error_custom_status(self):
        result = build_error("not found", 404)
        assert result["statusCode"] == 404

    def test_build_error_with_code(self):
        result = build_error("not found", 404, "NOT_FOUND")
        body = json.loads(result["body"])
        assert body["error"] == "not found"
        assert body["code"] == "NOT_FOUND"

    def test_build_error_without_code_omits_field(self):
        result = build_error("bad request")
        body = json.loads(result["body"])
        assert "code" not in body


class TestAPIGatewayHandler:
    def _make_handler(self):
        storage = MagicMock()
        return APIGatewayHandler(storage=storage), storage

    def test_options_preflight(self):
        handler, _ = self._make_handler()
        result = handler.handle({"httpMethod": "OPTIONS", "path": "/api/scan/start"})
        assert result["statusCode"] == 200

    @patch("src.handlers.api_gateway_handler.require_authentication")
    def test_not_found_route(self, mock_authentication):
        mock_authentication.return_value = MagicMock(org_id="org-1", user_id="user-1")
        handler, _ = self._make_handler()
        result = handler.handle(
            {
                "httpMethod": "GET",
                "path": "/api/nonexistent",
                "headers": {"Authorization": "Bearer token"},
            }
        )
        assert result["statusCode"] == 404

    @patch("src.handlers.api_gateway_handler.require_authentication")
    def test_authentication_failure(self, mock_authentication):
        mock_authentication.side_effect = ValueError("Invalid token")
        handler, _ = self._make_handler()
        result = handler.handle(
            {
                "httpMethod": "GET",
                "path": "/api/analyses",
                "headers": {},
            }
        )
        assert result["statusCode"] == 401

    def test_register_missing_fields(self):
        handler, _storage = self._make_handler()
        result = handler.handle(
            {
                "httpMethod": "POST",
                "path": "/api/auth/register",
                "headers": {},
                "body": json.dumps({"name": "Test"}),
            }
        )
        assert result["statusCode"] == 400
        body = json.loads(result["body"])
        assert "required" in body["error"].lower()
        assert body["code"] == "VALIDATION_ERROR"

    def test_register_duplicate_email(self):
        handler, storage = self._make_handler()
        user_repo = MagicMock()
        user_repo.has_email.return_value = True
        storage.create_user_repository.return_value = user_repo
        storage.create_organization_repository.return_value = MagicMock()

        result = handler.handle(
            {
                "httpMethod": "POST",
                "path": "/api/auth/register",
                "headers": {},
                "body": json.dumps(
                    {
                        "name": "Test",
                        "email": "test@example.com",
                        "password": "password123",
                        "orgName": "Test Org",
                    }
                ),
            }
        )
        assert result["statusCode"] == 400
        assert "already registered" in json.loads(result["body"])["error"]

    @patch.dict("os.environ", {"COGNITO_USER_POOL_ID": "us-east-1_TEST"})
    @patch("src.handlers.auth_handlers.CognitoClient")
    def test_register_success(self, mock_cognito_cls):
        mock_cognito = MagicMock()
        mock_cognito.create_user_with_password.return_value = "cognito-sub-123"
        mock_cognito_cls.return_value = mock_cognito

        handler, storage = self._make_handler()
        user_repo = MagicMock()
        user_repo.has_email.return_value = False
        org_repo = MagicMock()
        storage.create_user_repository.return_value = user_repo
        storage.create_organization_repository.return_value = org_repo

        result = handler.handle(
            {
                "httpMethod": "POST",
                "path": "/api/auth/register",
                "headers": {},
                "body": json.dumps(
                    {
                        "name": "Test User",
                        "email": "test@example.com",
                        "password": "password123",
                        "orgName": "Test Org",
                    }
                ),
            }
        )
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["success"] is True
        mock_cognito.create_user_with_password.assert_called_once()
        org_repo.create.assert_called_once()
        user_repo.create.assert_called_once()

        # Pin the `created_at` write that the activity-feed projection
        # (Tier 2 §5) relies on for `member_joined` events. If a future
        # refactor drops this field, member_joined silently stops
        # appearing for new signups — covered here so the regression
        # surfaces as a test failure, not a behaviour gap.
        user_record = user_repo.create.call_args[0][0]
        assert "created_at" in user_record
        assert user_record["created_at"]
        # The value parses as ISO 8601 (datetime.now(UTC).isoformat()).
        from datetime import datetime as _datetime
        _datetime.fromisoformat(user_record["created_at"])

    @patch.dict("os.environ", {"COGNITO_USER_POOL_ID": "us-east-1_TEST"})
    @patch("src.handlers.auth_handlers.CognitoClient")
    def test_register_cognito_password_error(self, mock_cognito_cls):
        from botocore.exceptions import ClientError

        mock_cognito = MagicMock()
        mock_cognito.client_error = ClientError
        mock_cognito.create_user_with_password.side_effect = ClientError(
            {"Error": {"Code": "InvalidPasswordException", "Message": "bad password"}},
            "AdminSetUserPassword",
        )
        mock_cognito_cls.return_value = mock_cognito

        handler, storage = self._make_handler()
        user_repo = MagicMock()
        user_repo.has_email.return_value = False
        storage.create_user_repository.return_value = user_repo
        storage.create_organization_repository.return_value = MagicMock()

        result = handler.handle(
            {
                "httpMethod": "POST",
                "path": "/api/auth/register",
                "headers": {},
                "body": json.dumps(
                    {
                        "name": "Test User",
                        "email": "test@example.com",
                        "password": "weak",
                        "orgName": "Test Org",
                    }
                ),
            }
        )
        assert result["statusCode"] == 400
        body = json.loads(result["body"])
        assert "password" in body["error"].lower()

    @patch.dict("os.environ", {"COGNITO_USER_POOL_ID": "us-east-1_TEST"})
    @patch("src.handlers.auth_handlers.CognitoClient")
    def test_register_cognito_user_exists_error(self, mock_cognito_cls):
        from botocore.exceptions import ClientError

        mock_cognito = MagicMock()
        mock_cognito.client_error = ClientError
        mock_cognito.create_user_with_password.side_effect = ClientError(
            {"Error": {"Code": "UsernameExistsException", "Message": "exists"}},
            "AdminCreateUser",
        )
        mock_cognito_cls.return_value = mock_cognito

        handler, storage = self._make_handler()
        user_repo = MagicMock()
        user_repo.has_email.return_value = False
        storage.create_user_repository.return_value = user_repo
        storage.create_organization_repository.return_value = MagicMock()

        result = handler.handle(
            {
                "httpMethod": "POST",
                "path": "/api/auth/register",
                "headers": {},
                "body": json.dumps(
                    {
                        "name": "Test User",
                        "email": "test@example.com",
                        "password": "Password123",
                        "orgName": "Test Org",
                    }
                ),
            }
        )
        assert result["statusCode"] == 400
        body = json.loads(result["body"])
        assert "already exists" in body["error"].lower()

    @patch("src.handlers.api_gateway_handler.require_authentication")
    def test_scan_start_missing_fields(self, mock_authentication):
        mock_authentication.return_value = MagicMock(org_id="org-1", user_id="user-1")
        handler, _ = self._make_handler()
        result = handler.handle(
            {
                "httpMethod": "POST",
                "path": "/api/scan/start",
                "headers": {"Authorization": "Bearer token"},
                "body": json.dumps({"url": ""}),
            }
        )
        assert result["statusCode"] == 400

    @patch("src.handlers.api_gateway_handler.require_authentication")
    @patch("src.handlers.api_gateway_handler.boto3")
    @patch.dict(
        "os.environ", {"ANALYSIS_QUEUE_URL": "https://sqs.us-east-1.amazonaws.com/123/queue"}
    )
    def test_scan_start_single_company_enqueues_to_sqs(self, mock_boto3, mock_authentication):
        mock_authentication.return_value = MagicMock(org_id="org-1", user_id="user-1")
        mock_sqs = MagicMock()
        mock_boto3.client.return_value = mock_sqs
        handler, storage = self._make_handler()

        scan_repo = MagicMock()
        storage.create_scan_repository.return_value = scan_repo

        result = handler.handle(
            {
                "httpMethod": "POST",
                "path": "/api/scan/start",
                "headers": {"Authorization": "Bearer token"},
                "body": json.dumps({"url": "https://example.com", "type": "single"}),
            }
        )
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["status"] == "running"
        assert body["analysisId"]
        assert "scanId" in body

        mock_sqs.send_message.assert_called_once()
        message_body = json.loads(mock_sqs.send_message.call_args[1]["MessageBody"])
        assert message_body["url"] == "https://example.com"
        assert message_body["org_id"] == "org-1"
        assert message_body["request_id"] == body["analysisId"]

    @patch("src.handlers.api_gateway_handler.require_authentication")
    @patch("src.handlers.api_gateway_handler.boto3")
    @patch.dict(
        "os.environ", {"ANALYSIS_QUEUE_URL": "https://sqs.us-east-1.amazonaws.com/123/queue"}
    )
    def test_scan_start_portfolio_dispatches_to_sqs(self, mock_boto3, mock_authentication):
        """Portfolio scan returns immediately with ``discovering`` and enqueues
        a ``portfolio_discovery`` message — no synchronous pipeline execution."""
        mock_authentication.return_value = MagicMock(org_id="org-1", user_id="user-1")
        mock_sqs = MagicMock()
        mock_boto3.client.return_value = mock_sqs
        handler, storage = self._make_handler()

        scan_repo = MagicMock()
        storage.create_scan_repository.return_value = scan_repo
        # Factory manager must NOT be invoked for portfolio scans anymore.
        handler._factory_manager = MagicMock()

        result = handler.handle(
            {
                "httpMethod": "POST",
                "path": "/api/scan/start",
                "headers": {"Authorization": "Bearer token"},
                "body": json.dumps({"url": "https://pefirm.com/portfolio", "type": "portfolio"}),
            }
        )
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["status"] == "discovering"
        assert "scanId" in body
        assert "portfolioCompanies" not in body

        handler._factory_manager.run_portfolio_discovery.assert_not_called()
        mock_sqs.send_message.assert_called_once()
        message_body = json.loads(mock_sqs.send_message.call_args[1]["MessageBody"])
        assert message_body["type"] == "portfolio_discovery"
        assert message_body["url"] == "https://pefirm.com/portfolio"
        assert message_body["org_id"] == "org-1"
        assert message_body["scan_id"] == body["scanId"]

        created_record = scan_repo.create.call_args[0][0]
        # DB record matches API response — client polling first sees the
        # same status it already has, no race where GET returns "pending".
        assert created_record["status"] == "discovering"
        assert created_record["type"] == "portfolio"

    @patch("src.handlers.api_gateway_handler.require_authentication")
    def test_scan_status_not_found(self, mock_authentication):
        mock_authentication.return_value = MagicMock(org_id="org-1", user_id="user-1")
        handler, storage = self._make_handler()

        scan_repo = MagicMock()
        scan_repo.get_by_id.return_value = None
        storage.create_scan_repository.return_value = scan_repo

        result = handler.handle(
            {
                "httpMethod": "GET",
                "path": "/api/scan/scan-123",
                "headers": {"Authorization": "Bearer token"},
            }
        )
        assert result["statusCode"] == 404

    @patch("src.handlers.api_gateway_handler.require_authentication")
    def test_scan_status_wrong_org(self, mock_authentication):
        mock_authentication.return_value = MagicMock(org_id="org-1", user_id="user-1")
        handler, storage = self._make_handler()

        scan_repo = MagicMock()
        scan_repo.get_by_id.return_value = {"org_id": "other-org"}
        storage.create_scan_repository.return_value = scan_repo

        result = handler.handle(
            {
                "httpMethod": "GET",
                "path": "/api/scan/scan-123",
                "headers": {"Authorization": "Bearer token"},
            }
        )
        assert result["statusCode"] == 404

    @patch("src.handlers.api_gateway_handler.require_authentication")
    def test_scan_status_success(self, mock_authentication):
        mock_authentication.return_value = MagicMock(org_id="org-1", user_id="user-1")
        handler, storage = self._make_handler()

        scan_repo = MagicMock()
        scan_repo.get_by_id.return_value = {
            "org_id": "org-1",
            "status": "complete",
            "type": "single",
        }
        scan_repo.get_scan_companies.return_value = [{"company_id": "c-1"}]
        company_repo = MagicMock()
        company_repo.get_by_ids.return_value = [
            {
                "id": "c-1",
                "company_name": "Test",
                "company_url": "https://test.com",
            }
        ]
        storage.create_scan_repository.return_value = scan_repo
        storage.create_company_repository.return_value = company_repo

        result = handler.handle(
            {
                "httpMethod": "GET",
                "path": "/api/scan/scan-123",
                "headers": {"Authorization": "Bearer token"},
            }
        )
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["status"] == "complete"
        assert len(body["analyses"]) == 1
        assert body["analyses"][0]["companyName"] == "Test"

    @patch("src.handlers.api_gateway_handler.require_authentication")
    def test_scan_confirm_no_companies(self, mock_authentication):
        mock_authentication.return_value = MagicMock(org_id="org-1", user_id="user-1")
        handler, _ = self._make_handler()
        result = handler.handle(
            {
                "httpMethod": "POST",
                "path": "/api/scan/scan-123/confirm",
                "headers": {"Authorization": "Bearer token"},
                "body": json.dumps({"companies": []}),
            }
        )
        assert result["statusCode"] == 400

    @patch("src.handlers.api_gateway_handler.require_authentication")
    def test_scan_confirm_not_found(self, mock_authentication):
        mock_authentication.return_value = MagicMock(org_id="org-1", user_id="user-1")
        handler, storage = self._make_handler()
        scan_repo = MagicMock()
        scan_repo.get_by_id.return_value = None
        storage.create_scan_repository.return_value = scan_repo

        result = handler.handle(
            {
                "httpMethod": "POST",
                "path": "/api/scan/scan-123/confirm",
                "headers": {"Authorization": "Bearer token"},
                "body": json.dumps({"companies": [{"name": "Co", "url": "https://co.com"}]}),
            }
        )
        assert result["statusCode"] == 404

    @patch("src.handlers.api_gateway_handler.require_authentication")
    @patch("src.handlers.api_gateway_handler.boto3")
    @patch("src.handlers.scan_handlers.boto3")
    @patch.dict(
        "os.environ",
        {
            "ANALYSIS_QUEUE_URL": "https://sqs.us-east-1.amazonaws.com/123/queue",
            "PORTFOLIO_STATE_MACHINE_ARN": "arn:aws:states:us-east-1:123:stateMachine:test",
            "WAVE_SIZE": "4",
        },
    )
    def test_scan_confirm_success(self, mock_scan_boto3, mock_api_boto3, mock_authentication):
        mock_authentication.return_value = MagicMock(org_id="org-1", user_id="user-1")
        mock_sfn = MagicMock()
        mock_scan_boto3.client.return_value = mock_sfn
        mock_sqs = MagicMock()
        mock_api_boto3.client.return_value = mock_sqs
        handler, storage = self._make_handler()
        scan_repo = MagicMock()
        scan_repo.get_by_id.return_value = {"org_id": "org-1"}
        storage.create_scan_repository.return_value = scan_repo

        result = handler.handle(
            {
                "httpMethod": "POST",
                "path": "/api/scan/scan-123/confirm",
                "headers": {"Authorization": "Bearer token"},
                "body": json.dumps(
                    {
                        "companies": [
                            {"name": "Co1", "url": "https://co1.com"},
                            {"name": "Co2", "url": "https://co2.com"},
                        ],
                    }
                ),
            }
        )
        assert result["statusCode"] == 202
        body = json.loads(result["body"])
        assert body["ok"] is True
        assert len(body["queued"]) == 2
        # 2 companies → Step Functions path, not SQS
        mock_sfn.start_execution.assert_called_once()
        mock_sqs.send_message.assert_not_called()

        # Each link_company call carries company_url + order_index in
        # submission order so the portfolio view can render every card
        # from t=0 in stable position.
        link_calls = scan_repo.link_company.call_args_list
        assert len(link_calls) == 2
        assert link_calls[0].kwargs == {
            "company_url": "https://co1.com",
            "order_index": 0,
        }
        assert link_calls[1].kwargs == {
            "company_url": "https://co2.com",
            "order_index": 1,
        }

    @patch("src.handlers.api_gateway_handler.require_authentication")
    @patch("src.handlers.api_gateway_handler.boto3")
    @patch.dict(
        "os.environ", {"ANALYSIS_QUEUE_URL": "https://sqs.us-east-1.amazonaws.com/123/queue"}
    )
    def test_scan_confirm_partial_failure(self, mock_boto3, mock_authentication):
        """Companies without a URL are skipped; valid ones are still queued."""
        mock_authentication.return_value = MagicMock(org_id="org-1", user_id="user-1")
        mock_sqs = MagicMock()
        mock_boto3.client.return_value = mock_sqs
        handler, storage = self._make_handler()
        scan_repo = MagicMock()
        scan_repo.get_by_id.return_value = {"org_id": "org-1"}
        storage.create_scan_repository.return_value = scan_repo

        result = handler.handle(
            {
                "httpMethod": "POST",
                "path": "/api/scan/scan-123/confirm",
                "headers": {"Authorization": "Bearer token"},
                "body": json.dumps(
                    {
                        "companies": [
                            {"name": "Co1", "url": "https://co1.com"},
                            {"name": "Co2"},
                        ],
                    }
                ),
            }
        )
        assert result["statusCode"] == 202
        body = json.loads(result["body"])
        assert len(body["queued"]) == 1
        assert body["queued"][0]["name"] == "Co1"
        assert mock_sqs.send_message.call_count == 1

    @patch("src.handlers.api_gateway_handler.require_authentication")
    @patch("src.handlers.api_gateway_handler.boto3")
    @patch.dict(
        "os.environ", {"ANALYSIS_QUEUE_URL": "https://sqs.us-east-1.amazonaws.com/123/queue"}
    )
    def test_scan_confirm_missing_url_in_company(self, mock_boto3, mock_authentication):
        mock_authentication.return_value = MagicMock(org_id="org-1", user_id="user-1")
        mock_sqs = MagicMock()
        mock_boto3.client.return_value = mock_sqs
        handler, storage = self._make_handler()
        scan_repo = MagicMock()
        scan_repo.get_by_id.return_value = {"org_id": "org-1"}
        storage.create_scan_repository.return_value = scan_repo

        result = handler.handle(
            {
                "httpMethod": "POST",
                "path": "/api/scan/scan-123/confirm",
                "headers": {"Authorization": "Bearer token"},
                "body": json.dumps({"companies": [{"name": "Co1"}]}),
            }
        )
        assert result["statusCode"] == 400
        body = json.loads(result["body"])
        assert "url" in body["error"]
        mock_sqs.send_message.assert_not_called()

    @patch("src.handlers.api_gateway_handler.require_authentication")
    @patch("src.handlers.api_gateway_handler.boto3")
    @patch("src.handlers.scan_handlers.boto3")
    @patch.dict(
        "os.environ",
        {
            "ANALYSIS_QUEUE_URL": "https://sqs.us-east-1.amazonaws.com/123/queue",
            "PORTFOLIO_STATE_MACHINE_ARN": "arn:aws:states:us-east-1:123:stateMachine:test",
            "WAVE_SIZE": "4",
        },
    )
    def test_scan_confirm_uses_step_functions_for_multiple_companies(
        self, mock_scan_boto3, mock_api_boto3, mock_authentication
    ):
        """Portfolio confirm with 2+ companies uses Step Functions, not SQS."""
        mock_authentication.return_value = MagicMock(org_id="org-1", user_id="user-1")
        mock_sqs = MagicMock()
        mock_sfn = MagicMock()
        mock_api_boto3.client.return_value = mock_sqs
        mock_scan_boto3.client.return_value = mock_sfn
        handler, storage = self._make_handler()
        scan_repo = MagicMock()
        scan_repo.get_by_id.return_value = {"org_id": "org-1"}
        storage.create_scan_repository.return_value = scan_repo

        result = handler.handle(
            {
                "httpMethod": "POST",
                "path": "/api/scan/scan-123/confirm",
                "headers": {"Authorization": "Bearer token"},
                "body": json.dumps(
                    {
                        "companies": [
                            {"name": "Co1", "url": "https://co1.com"},
                            {"name": "Co2", "url": "https://co2.com"},
                        ],
                    }
                ),
            }
        )
        assert result["statusCode"] == 202
        # Step Functions was called instead of SQS
        mock_sfn.start_execution.assert_called_once()
        mock_sqs.send_message.assert_not_called()

    @patch("src.handlers.api_gateway_handler.require_authentication")
    def test_delete_scan_not_found(self, mock_authentication):
        mock_authentication.return_value = MagicMock(org_id="org-1", user_id="user-1")
        handler, storage = self._make_handler()
        scan_repo = MagicMock()
        scan_repo.get_by_id.return_value = None
        storage.create_scan_repository.return_value = scan_repo

        result = handler.handle(
            {
                "httpMethod": "DELETE",
                "path": "/api/scan/scan-123",
                "headers": {"Authorization": "Bearer token"},
            }
        )
        assert result["statusCode"] == 404

    @patch("src.handlers.api_gateway_handler.require_authentication")
    def test_delete_scan_wrong_org(self, mock_authentication):
        mock_authentication.return_value = MagicMock(org_id="org-1", user_id="user-1")
        handler, storage = self._make_handler()
        scan_repo = MagicMock()
        scan_repo.get_by_id.return_value = {"org_id": "other-org"}
        storage.create_scan_repository.return_value = scan_repo

        result = handler.handle(
            {
                "httpMethod": "DELETE",
                "path": "/api/scan/scan-123",
                "headers": {"Authorization": "Bearer token"},
            }
        )
        assert result["statusCode"] == 404

    @patch("src.handlers.api_gateway_handler.require_authentication")
    def test_delete_scan_cascades_to_companies_and_assessments(self, mock_authentication):
        mock_authentication.return_value = MagicMock(org_id="org-1", user_id="user-1")
        handler, storage = self._make_handler()
        scan_repo = MagicMock()
        scan_repo.get_by_id.return_value = {"org_id": "org-1"}
        scan_repo.get_scan_companies.return_value = [
            {"company_id": "c-1"},
            {"company_id": "c-2"},
        ]
        company_repo = MagicMock()
        assessment_repo = MagicMock()
        assessment_repo.find_by_company.side_effect = [
            [{"id": "assess-1"}],
            [],
        ]
        storage.create_scan_repository.return_value = scan_repo
        storage.create_company_repository.return_value = company_repo
        storage.create_assessment_repository.return_value = assessment_repo

        result = handler.handle(
            {
                "httpMethod": "DELETE",
                "path": "/api/scan/scan-123",
                "headers": {"Authorization": "Bearer token"},
            }
        )
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["ok"] is True
        # Soft-delete: tombstone the assessment, the two companies, both
        # link records, and finally the scan itself — every call carries
        # `actor_id` so the recently-deleted UI can attribute the delete
        # to the right user. No hard deletes.
        assessment_repo.tombstone.assert_called_once_with("assess-1", actor_id="user-1")
        assert company_repo.tombstone.call_count == 2
        assert scan_repo.tombstone_link.call_count == 2
        scan_repo.tombstone_link.assert_any_call("scan-123", "c-1", actor_id="user-1")
        scan_repo.tombstone_link.assert_any_call("scan-123", "c-2", actor_id="user-1")
        scan_repo.tombstone.assert_called_once_with("scan-123", actor_id="user-1")
        # Hard-delete paths must NOT be invoked from the soft-delete handler.
        assessment_repo.delete.assert_not_called()
        company_repo.delete.assert_not_called()
        scan_repo.delete.assert_not_called()
        scan_repo.delete_all_company_links.assert_not_called()

    @patch("src.handlers.api_gateway_handler.require_authentication")
    def test_delete_scan_no_companies(self, mock_authentication):
        mock_authentication.return_value = MagicMock(org_id="org-1", user_id="user-1")
        handler, storage = self._make_handler()
        scan_repo = MagicMock()
        scan_repo.get_by_id.return_value = {"org_id": "org-1"}
        scan_repo.get_scan_companies.return_value = []
        storage.create_scan_repository.return_value = scan_repo
        storage.create_company_repository.return_value = MagicMock()
        storage.create_assessment_repository.return_value = MagicMock()

        result = handler.handle(
            {
                "httpMethod": "DELETE",
                "path": "/api/scan/scan-123",
                "headers": {"Authorization": "Bearer token"},
            }
        )
        assert result["statusCode"] == 200
        scan_repo.tombstone.assert_called_once_with("scan-123", actor_id="user-1")
        scan_repo.delete.assert_not_called()

    @patch("src.handlers.api_gateway_handler.require_authentication")
    def test_get_analysis_not_found(self, mock_authentication):
        mock_authentication.return_value = MagicMock(org_id="org-1", user_id="user-1")
        handler, storage = self._make_handler()
        company_repo = MagicMock()
        company_repo.get_by_id.return_value = None
        storage.create_company_repository.return_value = company_repo

        result = handler.handle(
            {
                "httpMethod": "GET",
                "path": "/api/analysis/a-1",
                "headers": {"Authorization": "Bearer token"},
            }
        )
        assert result["statusCode"] == 404

    @patch("src.handlers.api_gateway_handler.require_authentication")
    def test_get_analysis_success(self, mock_authentication):
        mock_authentication.return_value = MagicMock(org_id="org-1", user_id="user-1")
        handler, storage = self._make_handler()
        company_repo = MagicMock()
        company_repo.get_by_id.return_value = {
            "org_id": "org-1",
            "company_name": "Test",
            "company_url": "https://test.com",
            "industry": "SaaS",
            "overall_risk_score": 5,
            "risk_tier": "moderate",
            "metadata_json": "",
        }
        assessment_repo = MagicMock()
        assessment_repo.find_by_company.return_value = [
            {"id": "assess-1", "analysis_summary": "Summary"},
        ]
        assessment_repo.get_risk_scores.return_value = [{"category": "competitive"}]
        assessment_repo.get_opportunities.return_value = [{"title": "Opp1"}]
        storage.create_company_repository.return_value = company_repo
        storage.create_assessment_repository.return_value = assessment_repo

        result = handler.handle(
            {
                "httpMethod": "GET",
                "path": "/api/analysis/a-1",
                "headers": {"Authorization": "Bearer token"},
            }
        )
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["companyName"] == "Test"
        assert len(body["riskScores"]) == 1

    @patch("src.handlers.api_gateway_handler.require_authentication")
    def test_get_analysis_includes_scan_provenance_for_portfolio(self, mock_authentication):
        """Happy path: parent scan record provides scanType + scanSourceUrl.

        The frontend reads these to render the "Part of: {scan}" cross-reference
        on the analysis-detail page. If the join is dropped or fields rename,
        the provenance line silently disappears — this test pins the contract.
        """
        mock_authentication.return_value = MagicMock(org_id="org-1", user_id="user-1")
        handler, storage = self._make_handler()
        company_repo = MagicMock()
        company_repo.get_by_id.return_value = {
            "org_id": "org-1",
            "company_name": "Test",
            "scan_id": "scan-123",
            "metadata_json": "",
        }
        scan_repo = MagicMock()
        scan_repo.get_by_id.return_value = {
            "id": "scan-123",
            "type": "portfolio",
            "source_url": "https://perotjain.com",
        }
        assessment_repo = MagicMock()
        assessment_repo.find_by_company.return_value = []
        storage.create_company_repository.return_value = company_repo
        storage.create_scan_repository.return_value = scan_repo
        storage.create_assessment_repository.return_value = assessment_repo

        result = handler.handle(
            {
                "httpMethod": "GET",
                "path": "/api/analysis/a-1",
                "headers": {"Authorization": "Bearer token"},
            }
        )
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["scanId"] == "scan-123"
        assert body["scanType"] == "portfolio"
        assert body["scanSourceUrl"] == "https://perotjain.com"
        scan_repo.get_by_id.assert_called_once_with("scan-123")

    @patch("src.handlers.api_gateway_handler.require_authentication")
    def test_get_analysis_degrades_when_scan_record_missing(self, mock_authentication):
        """Race / cascade-delete: parent scan deleted between company load and
        scan lookup. The handler MUST NOT 500 — it returns empty strings so the
        frontend's `scanType === 'portfolio'` check fails-soft to no provenance.
        """
        mock_authentication.return_value = MagicMock(org_id="org-1", user_id="user-1")
        handler, storage = self._make_handler()
        company_repo = MagicMock()
        company_repo.get_by_id.return_value = {
            "org_id": "org-1",
            "company_name": "Test",
            "scan_id": "scan-deleted",
            "metadata_json": "",
        }
        scan_repo = MagicMock()
        scan_repo.get_by_id.return_value = None  # scan was deleted
        assessment_repo = MagicMock()
        assessment_repo.find_by_company.return_value = []
        storage.create_company_repository.return_value = company_repo
        storage.create_scan_repository.return_value = scan_repo
        storage.create_assessment_repository.return_value = assessment_repo

        result = handler.handle(
            {
                "httpMethod": "GET",
                "path": "/api/analysis/a-1",
                "headers": {"Authorization": "Bearer token"},
            }
        )
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["scanId"] == "scan-deleted"
        # Empty strings — fail-soft. Frontend's portfolio gate will return false.
        assert body["scanType"] == ""
        assert body["scanSourceUrl"] == ""

    @patch("src.handlers.api_gateway_handler.require_authentication")
    def test_get_analysis_skips_scan_lookup_when_scan_id_missing(self, mock_authentication):
        """Orphan / legacy company record without scan_id. The handler MUST NOT
        attempt the scan lookup (else KeyError) — it short-circuits via the
        ``if scan_id:`` guard and returns empty strings.
        """
        mock_authentication.return_value = MagicMock(org_id="org-1", user_id="user-1")
        handler, storage = self._make_handler()
        company_repo = MagicMock()
        company_repo.get_by_id.return_value = {
            "org_id": "org-1",
            "company_name": "Test",
            "metadata_json": "",
            # No scan_id at all
        }
        scan_repo = MagicMock()
        assessment_repo = MagicMock()
        assessment_repo.find_by_company.return_value = []
        storage.create_company_repository.return_value = company_repo
        storage.create_scan_repository.return_value = scan_repo
        storage.create_assessment_repository.return_value = assessment_repo

        result = handler.handle(
            {
                "httpMethod": "GET",
                "path": "/api/analysis/a-1",
                "headers": {"Authorization": "Bearer token"},
            }
        )
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["scanId"] == ""
        assert body["scanType"] == ""
        assert body["scanSourceUrl"] == ""
        # Crucially: no scan lookup attempted at all
        scan_repo.get_by_id.assert_not_called()

    @patch("src.handlers.api_gateway_handler.require_authentication")
    def test_get_analysis_with_metadata_json(self, mock_authentication):
        mock_authentication.return_value = MagicMock(org_id="org-1", user_id="user-1")
        handler, storage = self._make_handler()
        company_repo = MagicMock()
        company_repo.get_by_id.return_value = {
            "org_id": "org-1",
            "company_name": "Test",
            "metadata_json": json.dumps({"top_actions": ["Action 1"], "analysis_summary": "Good"}),
        }
        assessment_repo = MagicMock()
        assessment_repo.find_by_company.return_value = []
        storage.create_company_repository.return_value = company_repo
        storage.create_assessment_repository.return_value = assessment_repo

        result = handler.handle(
            {
                "httpMethod": "GET",
                "path": "/api/analysis/a-1",
                "headers": {"Authorization": "Bearer token"},
            }
        )
        body = json.loads(result["body"])
        assert body["topActions"] == ["Action 1"]
        assert body["analysisSummary"] == "Good"

    @patch("src.handlers.api_gateway_handler.require_authentication")
    def test_delete_analysis_not_found(self, mock_authentication):
        mock_authentication.return_value = MagicMock(org_id="org-1", user_id="user-1")
        handler, storage = self._make_handler()
        company_repo = MagicMock()
        company_repo.get_by_id.return_value = None
        storage.create_company_repository.return_value = company_repo

        result = handler.handle(
            {
                "httpMethod": "DELETE",
                "path": "/api/analysis/a-1",
                "headers": {"Authorization": "Bearer token"},
            }
        )
        assert result["statusCode"] == 404

    @patch("src.handlers.api_gateway_handler.require_authentication")
    def test_delete_analysis_success(self, mock_authentication):
        mock_authentication.return_value = MagicMock(org_id="org-1", user_id="user-1")
        handler, storage = self._make_handler()
        company_repo = MagicMock()
        company_repo.get_by_id.return_value = {"org_id": "org-1", "scan_id": "scan-1"}
        assessment_repo = MagicMock()
        assessment_repo.find_by_company.return_value = [{"id": "assess-1"}]
        scan_repo = MagicMock()
        scan_repo.get_scan_companies.return_value = []
        storage.create_company_repository.return_value = company_repo
        storage.create_assessment_repository.return_value = assessment_repo
        storage.create_scan_repository.return_value = scan_repo

        result = handler.handle(
            {
                "httpMethod": "DELETE",
                "path": "/api/analysis/a-1",
                "headers": {"Authorization": "Bearer token"},
            }
        )
        assert result["statusCode"] == 200
        # Soft-delete: tombstone the assessment, the company, the link,
        # and (because no live links remain) the scan itself — every
        # call carries `actor_id` (Phase 2 admin recovery feed reads
        # this back as "Deleted by Alice"). Hard-delete paths must not
        # be invoked.
        assessment_repo.tombstone.assert_called_once_with("assess-1", actor_id="user-1")
        company_repo.tombstone.assert_called_once_with("a-1", actor_id="user-1")
        scan_repo.tombstone_link.assert_called_once_with("scan-1", "a-1", actor_id="user-1")
        scan_repo.tombstone.assert_called_once_with("scan-1", actor_id="user-1")
        assessment_repo.delete.assert_not_called()
        company_repo.delete.assert_not_called()
        scan_repo.unlink_company.assert_not_called()
        scan_repo.delete.assert_not_called()

    # ── Bulk delete analyses (race-immune cascade) ────────────────────────
    # The single-DELETE endpoint cascades correctly on its own, but the
    # frontend's prior bulk flow fired N parallel requests via
    # `Promise.all` — each request's "any companies left on this scan?"
    # check could read state where peer requests' unlinks hadn't yet
    # committed, leading to orphan scans. The bulk endpoint collapses
    # the cascade decision into a single post-delete pass.

    @patch("src.handlers.api_gateway_handler.require_authentication")
    def test_bulk_delete_rejects_missing_ids(self, mock_authentication):
        mock_authentication.return_value = MagicMock(org_id="org-1", user_id="user-1")
        handler, _storage = self._make_handler()
        result = handler.handle(
            {
                "httpMethod": "POST",
                "path": "/api/analyses/bulk-delete",
                "headers": {"Authorization": "Bearer token"},
                "body": json.dumps({}),
            }
        )
        assert result["statusCode"] == 400

    @patch("src.handlers.api_gateway_handler.require_authentication")
    def test_bulk_delete_rejects_empty_id_list(self, mock_authentication):
        mock_authentication.return_value = MagicMock(org_id="org-1", user_id="user-1")
        handler, _storage = self._make_handler()
        result = handler.handle(
            {
                "httpMethod": "POST",
                "path": "/api/analyses/bulk-delete",
                "headers": {"Authorization": "Bearer token"},
                "body": json.dumps({"ids": []}),
            }
        )
        assert result["statusCode"] == 400

    @patch("src.handlers.api_gateway_handler.require_authentication")
    def test_bulk_delete_rejects_non_string_ids(self, mock_authentication):
        mock_authentication.return_value = MagicMock(org_id="org-1", user_id="user-1")
        handler, _storage = self._make_handler()
        result = handler.handle(
            {
                "httpMethod": "POST",
                "path": "/api/analyses/bulk-delete",
                "headers": {"Authorization": "Bearer token"},
                "body": json.dumps({"ids": ["a-1", 42, None]}),
            }
        )
        assert result["statusCode"] == 400

    @patch("src.handlers.api_gateway_handler.require_authentication")
    def test_bulk_delete_cascades_scan_when_all_companies_deleted(self, mock_authentication):
        """The race-immunity test: deleting every company on a scan in one
        call leaves zero remaining links and the scan IS deleted.

        Pre-fix, parallel single-DELETE calls could each read the post-
        unlink state inconsistently and BOTH conclude "scan still has
        links" — leading to the orphan scan the user reported.
        """
        mock_authentication.return_value = MagicMock(org_id="org-1", user_id="user-1")
        handler, storage = self._make_handler()

        company_repo = MagicMock()
        # Bulk path uses BatchGetItem-backed `get_by_ids` (CLAUDE.md
        # DynamoDB pattern), not per-item `get_by_id`.
        company_repo.get_by_ids.return_value = [
            {"id": analysis_id, "org_id": "org-1", "scan_id": "scan-1"}
            for analysis_id in ("a-1", "a-2", "a-3")
        ]
        assessment_repo = MagicMock()
        assessment_repo.find_by_company.return_value = []

        # The cascade-pass runs after every unlink — `get_scan_companies`
        # returns empty because the test simulates the realistic
        # post-bulk-delete state.
        scan_repo = MagicMock()
        scan_repo.get_scan_companies.return_value = []

        storage.create_company_repository.return_value = company_repo
        storage.create_assessment_repository.return_value = assessment_repo
        storage.create_scan_repository.return_value = scan_repo

        result = handler.handle(
            {
                "httpMethod": "POST",
                "path": "/api/analyses/bulk-delete",
                "headers": {"Authorization": "Bearer token"},
                "body": json.dumps({"ids": ["a-1", "a-2", "a-3"]}),
            }
        )
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert sorted(body["deleted"]) == ["a-1", "a-2", "a-3"]
        assert body["failed"] == []
        assert body["deletedScans"] == ["scan-1"]

        # Three tombstones + three link-tombstones for the same scan + one
        # scan tombstone — every call attributes the actor. Hard-delete
        # paths must remain untouched.
        assert company_repo.tombstone.call_count == 3
        assert all(
            call.kwargs == {"actor_id": "user-1"}
            for call in company_repo.tombstone.mock_calls
        )
        assert scan_repo.tombstone_link.call_count == 3
        assert all(
            call.kwargs == {"actor_id": "user-1"}
            for call in scan_repo.tombstone_link.mock_calls
        )
        scan_repo.tombstone.assert_called_once_with("scan-1", actor_id="user-1")
        company_repo.delete.assert_not_called()
        scan_repo.unlink_company.assert_not_called()
        scan_repo.delete.assert_not_called()
        # `get_scan_companies` is called ONCE (after all unlinks), not per
        # analysis. This is the race-immunity property.
        scan_repo.get_scan_companies.assert_called_once_with("scan-1")

    @patch("src.handlers.api_gateway_handler.require_authentication")
    def test_bulk_delete_keeps_scan_when_other_companies_remain(self, mock_authentication):
        """Cascade does NOT fire if remaining companies exist on the scan."""
        mock_authentication.return_value = MagicMock(org_id="org-1", user_id="user-1")
        handler, storage = self._make_handler()
        company_repo = MagicMock()
        company_repo.get_by_ids.return_value = [
            {"id": "a-1", "org_id": "org-1", "scan_id": "scan-1"},
            {"id": "a-2", "org_id": "org-1", "scan_id": "scan-1"},
        ]
        assessment_repo = MagicMock()
        assessment_repo.find_by_company.return_value = []
        scan_repo = MagicMock()
        scan_repo.get_scan_companies.return_value = [{"company_id": "untouched"}]
        storage.create_company_repository.return_value = company_repo
        storage.create_assessment_repository.return_value = assessment_repo
        storage.create_scan_repository.return_value = scan_repo

        result = handler.handle(
            {
                "httpMethod": "POST",
                "path": "/api/analyses/bulk-delete",
                "headers": {"Authorization": "Bearer token"},
                "body": json.dumps({"ids": ["a-1", "a-2"]}),
            }
        )
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["deletedScans"] == []
        scan_repo.tombstone.assert_not_called()
        scan_repo.delete.assert_not_called()

    @patch("src.handlers.api_gateway_handler.require_authentication")
    def test_bulk_delete_handles_multiple_scans_independently(self, mock_authentication):
        """Each affected scan's cascade decision is independent."""
        mock_authentication.return_value = MagicMock(org_id="org-1", user_id="user-1")
        handler, storage = self._make_handler()

        # Two scans: scan-empty has all its analyses in the batch, scan-keep
        # has one untouched.
        scan_for = {"a-1": "scan-empty", "a-2": "scan-empty", "a-3": "scan-keep"}
        company_repo = MagicMock()
        company_repo.get_by_ids.return_value = [
            {"id": analysis_id, "org_id": "org-1", "scan_id": scan_for[analysis_id]}
            for analysis_id in ("a-1", "a-2", "a-3")
        ]
        assessment_repo = MagicMock()
        assessment_repo.find_by_company.return_value = []
        scan_repo = MagicMock()
        scan_repo.get_scan_companies.side_effect = lambda scan_id: (
            [] if scan_id == "scan-empty" else [{"company_id": "remaining"}]
        )
        storage.create_company_repository.return_value = company_repo
        storage.create_assessment_repository.return_value = assessment_repo
        storage.create_scan_repository.return_value = scan_repo

        result = handler.handle(
            {
                "httpMethod": "POST",
                "path": "/api/analyses/bulk-delete",
                "headers": {"Authorization": "Bearer token"},
                "body": json.dumps({"ids": ["a-1", "a-2", "a-3"]}),
            }
        )
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert sorted(body["deleted"]) == ["a-1", "a-2", "a-3"]
        assert body["deletedScans"] == ["scan-empty"]
        scan_repo.tombstone.assert_called_once_with("scan-empty", actor_id="user-1")
        scan_repo.delete.assert_not_called()

    @patch("src.handlers.api_gateway_handler.require_authentication")
    def test_bulk_delete_skips_records_from_other_orgs(self, mock_authentication):
        """Org isolation: an id pointing to another org's record is reported
        in `failed` (as `not_found` to avoid leaking existence) and NOT
        deleted."""
        mock_authentication.return_value = MagicMock(org_id="org-1", user_id="user-1")
        handler, storage = self._make_handler()

        company_repo = MagicMock()
        # `get_by_ids` returns ONLY the records that exist; missing ids
        # don't appear in the result. The cross-org record IS returned
        # by the BatchGet (it exists in the table), but the org-id check
        # in the handler classifies it as "not_found".
        company_repo.get_by_ids.return_value = [
            {"id": "a-1", "org_id": "org-1", "scan_id": "scan-1"},
            {"id": "a-other", "org_id": "org-OTHER", "scan_id": "scan-other"},
        ]
        assessment_repo = MagicMock()
        assessment_repo.find_by_company.return_value = []
        scan_repo = MagicMock()
        scan_repo.get_scan_companies.return_value = []
        storage.create_company_repository.return_value = company_repo
        storage.create_assessment_repository.return_value = assessment_repo
        storage.create_scan_repository.return_value = scan_repo

        result = handler.handle(
            {
                "httpMethod": "POST",
                "path": "/api/analyses/bulk-delete",
                "headers": {"Authorization": "Bearer token"},
                "body": json.dumps({"ids": ["a-1", "a-other", "a-missing"]}),
            }
        )
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["deleted"] == ["a-1"]
        failed_ids = sorted(item["id"] for item in body["failed"])
        assert failed_ids == ["a-missing", "a-other"]
        # The cross-org record was never tombstoned (or hard-deleted).
        company_repo.tombstone.assert_called_once_with("a-1", actor_id="user-1")
        company_repo.delete.assert_not_called()

    @patch("src.handlers.api_gateway_handler.require_authentication")
    def test_delete_analysis_keeps_scan_with_remaining(self, mock_authentication):
        mock_authentication.return_value = MagicMock(org_id="org-1", user_id="user-1")
        handler, storage = self._make_handler()
        company_repo = MagicMock()
        company_repo.get_by_id.return_value = {"org_id": "org-1", "scan_id": "scan-1"}
        assessment_repo = MagicMock()
        assessment_repo.find_by_company.return_value = []
        scan_repo = MagicMock()
        scan_repo.get_scan_companies.return_value = [{"company_id": "other"}]
        storage.create_company_repository.return_value = company_repo
        storage.create_assessment_repository.return_value = assessment_repo
        storage.create_scan_repository.return_value = scan_repo

        result = handler.handle(
            {
                "httpMethod": "DELETE",
                "path": "/api/analysis/a-1",
                "headers": {"Authorization": "Bearer token"},
            }
        )
        assert result["statusCode"] == 200
        scan_repo.tombstone_link.assert_called_once_with("scan-1", "a-1", actor_id="user-1")
        scan_repo.unlink_company.assert_not_called()
        scan_repo.tombstone.assert_not_called()
        scan_repo.delete.assert_not_called()

    @patch("src.handlers.api_gateway_handler.require_authentication")
    def test_list_analyses(self, mock_authentication):
        mock_authentication.return_value = MagicMock(org_id="org-1", user_id="user-1")
        handler, storage = self._make_handler()
        company_repo = MagicMock()
        company_repo.find_by_org.return_value = (
            [{"id": "c-1", "company_name": "Test", "risk_tier": "low"}],
            None,
        )
        storage.create_company_repository.return_value = company_repo

        result = handler.handle(
            {
                "httpMethod": "GET",
                "path": "/api/analyses",
                "headers": {"Authorization": "Bearer token"},
            }
        )
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert len(body["analyses"]) == 1
        assert body["analyses"][0]["companyName"] == "Test"

    @patch("src.handlers.api_gateway_handler.require_authentication")
    def test_list_analyses_with_limit(self, mock_authentication):
        mock_authentication.return_value = MagicMock(org_id="org-1", user_id="user-1")
        handler, storage = self._make_handler()
        company_repo = MagicMock()
        company_repo.find_by_org.return_value = (
            [{"id": "c-1", "company_name": "Test"}],
            {"pk": "next-key"},
        )
        storage.create_company_repository.return_value = company_repo

        result = handler.handle(
            {
                "httpMethod": "GET",
                "path": "/api/analyses",
                "headers": {"Authorization": "Bearer token"},
                "queryStringParameters": {"limit": "1"},
            }
        )
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert len(body["analyses"]) == 1
        assert "cursor" in body
        company_repo.find_by_org.assert_called_once_with("org-1", limit=1, cursor=None)


class TestConfigEndpoint:
    def _make_handler(self):
        storage = MagicMock()
        return APIGatewayHandler(storage=storage), storage

    @patch("src.handlers.api_gateway_handler.require_authentication")
    @patch.dict("os.environ", {"APPSYNC_ENDPOINT": "https://appsync.example.com/graphql", "APPSYNC_API_KEY": "da2-fakekey123"})
    def test_returns_appsync_config_from_env(self, mock_authentication):
        mock_authentication.return_value = MagicMock(org_id="org-1", user_id="user-1")
        handler, _ = self._make_handler()
        result = handler.handle(
            {
                "httpMethod": "GET",
                "path": "/api/config",
                "headers": {"Authorization": "Bearer valid-token"},
            }
        )
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["appsyncEndpoint"] == "https://appsync.example.com/graphql"
        assert body["appsyncApiKey"] == "da2-fakekey123"

    @patch("src.handlers.api_gateway_handler.require_authentication")
    @patch.dict("os.environ", {}, clear=False)
    def test_returns_empty_strings_when_env_vars_not_set(self, mock_authentication):
        mock_authentication.return_value = MagicMock(org_id="org-1", user_id="user-1")
        # Remove the env vars if they exist
        import os
        os.environ.pop("APPSYNC_ENDPOINT", None)
        os.environ.pop("APPSYNC_API_KEY", None)

        handler, _ = self._make_handler()
        result = handler.handle(
            {
                "httpMethod": "GET",
                "path": "/api/config",
                "headers": {"Authorization": "Bearer valid-token"},
            }
        )
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["appsyncEndpoint"] == ""
        assert body["appsyncApiKey"] == ""

    def test_config_endpoint_requires_auth(self):
        handler, _ = self._make_handler()
        # No Authorization header at all
        result = handler.handle(
            {
                "httpMethod": "GET",
                "path": "/api/config",
                "headers": {},
            }
        )
        # Should fail without auth — 401
        assert result["statusCode"] == 401


class TestDashboardEndpoint:
    def _make_handler(self):
        storage = MagicMock()
        return APIGatewayHandler(storage=storage), storage

    @patch("src.handlers.api_gateway_handler.require_authentication")
    def test_dashboard_empty_org(self, mock_authentication):
        mock_authentication.return_value = MagicMock(org_id="org-1", user_id="user-1")
        handler, storage = self._make_handler()
        company_repo = MagicMock()
        company_repo.find_by_org.return_value = ([], None)
        scan_repo = MagicMock()
        scan_repo.find_recent_by_org.return_value = []
        storage.create_company_repository.return_value = company_repo
        storage.create_scan_repository.return_value = scan_repo

        result = handler.handle(
            {
                "httpMethod": "GET",
                "path": "/api/dashboard",
                "headers": {"Authorization": "Bearer token"},
            }
        )
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["totalAnalyses"] == 0
        assert body["avgRiskScore"] == 0
        assert body["criticalCount"] == 0
        assert body["scanCount"] == 0
        assert body["recentAnalyses"] == []
        assert body["recentScans"] == []

    @patch("src.handlers.api_gateway_handler.require_authentication")
    def test_dashboard_with_data(self, mock_authentication):
        mock_authentication.return_value = MagicMock(org_id="org-1", user_id="user-1")
        handler, storage = self._make_handler()
        company_repo = MagicMock()
        company_repo.find_by_org.return_value = (
            [
                {
                    "id": "c-1",
                    "company_name": "Company A",
                    "company_url": "https://a.com",
                    "overall_risk_score": 7.5,
                    "risk_tier": "high",
                    "analyzed_at": "2026-03-01T00:00:00",
                    "scan_id": "s-1",
                },
                {
                    "id": "c-2",
                    "company_name": "Company B",
                    "company_url": "https://b.com",
                    "overall_risk_score": 9.2,
                    "risk_tier": "critical",
                    "analyzed_at": "2026-03-02T00:00:00",
                    "scan_id": "s-1",
                },
                {
                    "id": "c-3",
                    "company_name": "Pending",
                    "overall_risk_score": None,
                    "scan_id": "s-2",
                },
            ],
            None,
        )
        scan_repo = MagicMock()
        all_scans = [
            {
                "id": "s-1",
                "source_url": "https://pe.com",
                "type": "portfolio",
                "status": "complete",
                "progress": 100,
                "completed_count": 2,
                "created_at": "2026-03-01",
            },
            {
                "id": "s-2",
                "source_url": "https://pe.com/other",
                "type": "standalone",
                "status": "complete",
                "progress": 100,
                "created_at": "2026-02-28",
            },
        ]
        scan_repo.find_recent_by_org.return_value = all_scans
        scan_repo.get_scan_companies.return_value = [{"company_id": "c-1"}, {"company_id": "c-2"}]
        storage.create_company_repository.return_value = company_repo
        storage.create_scan_repository.return_value = scan_repo

        result = handler.handle(
            {
                "httpMethod": "GET",
                "path": "/api/dashboard",
                "headers": {"Authorization": "Bearer token"},
            }
        )
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["totalAnalyses"] == 2
        assert body["avgRiskScore"] == 8.3
        assert body["criticalCount"] == 1
        assert body["scanCount"] == 2
        assert len(body["recentAnalyses"]) == 2
        assert body["recentAnalyses"][0]["companyName"] == "Company B"
        assert body["recentAnalyses"][0]["scanType"] == "portfolio"
        assert len(body["recentScans"]) == 2
        assert body["recentScans"][0]["completedCount"] == 2


class TestDocumentEndpoints:
    def _make_handler(self):
        storage = MagicMock()
        return APIGatewayHandler(storage=storage), storage

    @patch("src.handlers.api_gateway_handler.require_authentication")
    def test_create_document_with_base64_content(self, mock_authentication):
        mock_authentication.return_value = MagicMock(org_id="org-1", user_id="user-1")
        handler, storage = self._make_handler()
        company_repo = MagicMock()
        company_repo.get_by_id.return_value = {"org_id": "org-1"}
        assessment_repo = MagicMock()
        assessment_repo.find_by_company.return_value = [{"id": "assess-1"}]
        storage.create_company_repository.return_value = company_repo
        storage.create_assessment_repository.return_value = assessment_repo

        file_content = base64.b64encode(b"Hello document text").decode()
        result = handler.handle(
            {
                "httpMethod": "POST",
                "path": "/api/analysis/a-1/documents",
                "headers": {"Authorization": "Bearer token"},
                "body": json.dumps(
                    {
                        "filename": "test.txt",
                        "fileType": "txt",
                        "fileContent": file_content,
                    }
                ),
            }
        )
        assert result["statusCode"] == 201
        body = json.loads(result["body"])
        assert body["filename"] == "test.txt"
        assert body["fileType"] == "txt"
        assert body["charCount"] == len("Hello document text")
        assessment_repo.save_document.assert_called_once()

    @patch("src.handlers.api_gateway_handler.require_authentication")
    def test_create_document_not_found(self, mock_authentication):
        mock_authentication.return_value = MagicMock(org_id="org-1", user_id="user-1")
        handler, storage = self._make_handler()
        company_repo = MagicMock()
        company_repo.get_by_id.return_value = None
        storage.create_company_repository.return_value = company_repo

        result = handler.handle(
            {
                "httpMethod": "POST",
                "path": "/api/analysis/a-1/documents",
                "headers": {"Authorization": "Bearer token"},
                "body": json.dumps(
                    {"filename": "test.txt", "fileType": "txt", "fileContent": "aGVsbG8="}
                ),
            }
        )
        assert result["statusCode"] == 404

    @patch("src.handlers.api_gateway_handler.require_authentication")
    def test_create_document_missing_fields(self, mock_authentication):
        mock_authentication.return_value = MagicMock(org_id="org-1", user_id="user-1")
        handler, _ = self._make_handler()
        result = handler.handle(
            {
                "httpMethod": "POST",
                "path": "/api/analysis/a-1/documents",
                "headers": {"Authorization": "Bearer token"},
                "body": json.dumps({"filename": "test.txt"}),
            }
        )
        assert result["statusCode"] == 400

    @patch("src.handlers.api_gateway_handler.require_authentication")
    def test_create_document_unsupported_type(self, mock_authentication):
        mock_authentication.return_value = MagicMock(org_id="org-1", user_id="user-1")
        handler, storage = self._make_handler()
        company_repo = MagicMock()
        company_repo.get_by_id.return_value = {"org_id": "org-1"}
        assessment_repo = MagicMock()
        assessment_repo.find_by_company.return_value = [{"id": "assess-1"}]
        storage.create_company_repository.return_value = company_repo
        storage.create_assessment_repository.return_value = assessment_repo

        result = handler.handle(
            {
                "httpMethod": "POST",
                "path": "/api/analysis/a-1/documents",
                "headers": {"Authorization": "Bearer token"},
                "body": json.dumps(
                    {
                        "filename": "test.pptx",
                        "fileType": "pptx",
                        "fileContent": base64.b64encode(b"data").decode(),
                    }
                ),
            }
        )
        assert result["statusCode"] == 400
        assert "Unsupported" in json.loads(result["body"])["error"]

    @patch("src.handlers.api_gateway_handler.require_authentication")
    def test_create_document_no_assessment(self, mock_authentication):
        mock_authentication.return_value = MagicMock(org_id="org-1", user_id="user-1")
        handler, storage = self._make_handler()
        company_repo = MagicMock()
        company_repo.get_by_id.return_value = {"org_id": "org-1"}
        assessment_repo = MagicMock()
        assessment_repo.find_by_company.return_value = []
        storage.create_company_repository.return_value = company_repo
        storage.create_assessment_repository.return_value = assessment_repo

        result = handler.handle(
            {
                "httpMethod": "POST",
                "path": "/api/analysis/a-1/documents",
                "headers": {"Authorization": "Bearer token"},
                "body": json.dumps(
                    {
                        "filename": "test.txt",
                        "fileType": "txt",
                        "fileContent": base64.b64encode(b"content").decode(),
                    }
                ),
            }
        )
        assert result["statusCode"] == 404
        assert "assessment" in json.loads(result["body"])["error"].lower()

    @patch("src.handlers.api_gateway_handler.require_authentication")
    def test_delete_document_success(self, mock_authentication):
        mock_authentication.return_value = MagicMock(org_id="org-1", user_id="user-1")
        handler, storage = self._make_handler()
        company_repo = MagicMock()
        company_repo.get_by_id.return_value = {"org_id": "org-1"}
        assessment_repo = MagicMock()
        assessment_repo.find_by_company.return_value = [{"id": "assess-1"}]
        storage.create_company_repository.return_value = company_repo
        storage.create_assessment_repository.return_value = assessment_repo

        result = handler.handle(
            {
                "httpMethod": "DELETE",
                "path": "/api/analysis/a-1/documents/doc-1",
                "headers": {"Authorization": "Bearer token"},
            }
        )
        assert result["statusCode"] == 200
        assessment_repo.delete_document.assert_called_once_with("assess-1", "doc-1")

    @patch("src.handlers.api_gateway_handler.require_authentication")
    def test_delete_document_not_found(self, mock_authentication):
        mock_authentication.return_value = MagicMock(org_id="org-1", user_id="user-1")
        handler, storage = self._make_handler()
        company_repo = MagicMock()
        company_repo.get_by_id.return_value = None
        storage.create_company_repository.return_value = company_repo

        result = handler.handle(
            {
                "httpMethod": "DELETE",
                "path": "/api/analysis/a-1/documents/doc-1",
                "headers": {"Authorization": "Bearer token"},
            }
        )
        assert result["statusCode"] == 404

    @patch("src.handlers.api_gateway_handler.require_authentication")
    @patch("src.handlers.api_gateway_handler.boto3")
    @patch.dict(
        "os.environ",
        {"ANALYSIS_QUEUE_URL": "https://sqs.us-east-1.amazonaws.com/123/queue"},
    )
    def test_reanalyze_success(self, mock_boto3, mock_authentication):
        mock_authentication.return_value = MagicMock(org_id="org-1", user_id="user-1")
        mock_sqs = MagicMock()
        mock_boto3.client.return_value = mock_sqs
        handler, storage = self._make_handler()
        company_repo = MagicMock()
        company_repo.get_by_id.return_value = {
            "org_id": "org-1",
            "company_url": "https://test.com",
            "scan_id": "scan-1",
        }
        storage.create_company_repository.return_value = company_repo

        result = handler.handle(
            {
                "httpMethod": "POST",
                "path": "/api/analysis/a-1/reanalyze",
                "headers": {"Authorization": "Bearer token"},
            }
        )
        assert result["statusCode"] == 202
        body = json.loads(result["body"])
        assert body["status"] == "queued"
        mock_sqs.send_message.assert_called_once()
        message_body = json.loads(mock_sqs.send_message.call_args[1]["MessageBody"])
        assert message_body["reanalyze"] is True
        assert message_body["analysis_id"] == "a-1"

    @patch("src.handlers.api_gateway_handler.require_authentication")
    @patch("src.handlers.api_gateway_handler.boto3")
    @patch.dict(
        "os.environ",
        {"ANALYSIS_QUEUE_URL": "https://sqs.us-east-1.amazonaws.com/123/queue"},
    )
    def test_reanalyze_no_company_url(self, mock_boto3, mock_authentication):
        mock_authentication.return_value = MagicMock(org_id="org-1", user_id="user-1")
        mock_boto3.client.return_value = MagicMock()
        handler, storage = self._make_handler()
        company_repo = MagicMock()
        company_repo.get_by_id.return_value = {"org_id": "org-1", "company_url": ""}
        storage.create_company_repository.return_value = company_repo

        result = handler.handle(
            {
                "httpMethod": "POST",
                "path": "/api/analysis/a-1/reanalyze",
                "headers": {"Authorization": "Bearer token"},
            }
        )
        assert result["statusCode"] == 400

    @patch("src.handlers.api_gateway_handler.require_authentication")
    def test_reanalyze_not_found(self, mock_authentication):
        mock_authentication.return_value = MagicMock(org_id="org-1", user_id="user-1")
        handler, storage = self._make_handler()
        company_repo = MagicMock()
        company_repo.get_by_id.return_value = None
        storage.create_company_repository.return_value = company_repo

        result = handler.handle(
            {
                "httpMethod": "POST",
                "path": "/api/analysis/a-1/reanalyze",
                "headers": {"Authorization": "Bearer token"},
            }
        )
        assert result["statusCode"] == 404

    @patch("src.handlers.api_gateway_handler.require_authentication")
    @patch("src.handlers.api_gateway_handler.boto3")
    @patch.dict(
        "os.environ",
        {
            "ANALYSIS_QUEUE_URL": "https://sqs.us-east-1.amazonaws.com/123/queue",
            "DOCUMENTS_BUCKET": "janus-documents-test",
        },
    )
    def test_upload_url_success(self, mock_boto3, mock_authentication):
        mock_authentication.return_value = MagicMock(org_id="org-1", user_id="user-1")
        mock_s3 = MagicMock()
        mock_s3.generate_presigned_url.return_value = "https://s3.amazonaws.com/presigned"
        mock_boto3.client.side_effect = lambda service, **kw: mock_s3
        handler, storage = self._make_handler()
        company_repo = MagicMock()
        company_repo.get_by_id.return_value = {"org_id": "org-1"}
        storage.create_company_repository.return_value = company_repo

        result = handler.handle(
            {
                "httpMethod": "POST",
                "path": "/api/analysis/a-1/upload-url",
                "headers": {"Authorization": "Bearer token"},
                "body": json.dumps({"filename": "test.pdf", "fileType": "pdf"}),
            }
        )
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["uploadUrl"] == "https://s3.amazonaws.com/presigned"
        assert "documentKey" in body
        assert body["documentKey"].startswith("uploads/a-1/")
        mock_s3.generate_presigned_url.assert_called_once()

    @patch("src.handlers.api_gateway_handler.require_authentication")
    def test_upload_url_s3_not_configured(self, mock_authentication):
        mock_authentication.return_value = MagicMock(org_id="org-1", user_id="user-1")
        handler, _ = self._make_handler()

        result = handler.handle(
            {
                "httpMethod": "POST",
                "path": "/api/analysis/a-1/upload-url",
                "headers": {"Authorization": "Bearer token"},
                "body": json.dumps({"filename": "test.pdf", "fileType": "pdf"}),
            }
        )
        assert result["statusCode"] == 501
        assert "not configured" in json.loads(result["body"])["error"].lower()

    @patch("src.handlers.api_gateway_handler.require_authentication")
    @patch("src.handlers.api_gateway_handler.boto3")
    @patch.dict(
        "os.environ",
        {
            "ANALYSIS_QUEUE_URL": "https://sqs.us-east-1.amazonaws.com/123/queue",
            "DOCUMENTS_BUCKET": "janus-documents-test",
        },
    )
    def test_upload_url_missing_fields(self, mock_boto3, mock_authentication):
        mock_authentication.return_value = MagicMock(org_id="org-1", user_id="user-1")
        mock_boto3.client.return_value = MagicMock()
        handler, _ = self._make_handler()

        result = handler.handle(
            {
                "httpMethod": "POST",
                "path": "/api/analysis/a-1/upload-url",
                "headers": {"Authorization": "Bearer token"},
                "body": json.dumps({"filename": "test.pdf"}),
            }
        )
        assert result["statusCode"] == 400

    @patch("src.handlers.api_gateway_handler.require_authentication")
    @patch("src.handlers.api_gateway_handler.boto3")
    @patch.dict(
        "os.environ",
        {
            "ANALYSIS_QUEUE_URL": "https://sqs.us-east-1.amazonaws.com/123/queue",
            "DOCUMENTS_BUCKET": "janus-documents-test",
        },
    )
    def test_upload_url_rejects_unsupported_file_type(self, mock_boto3, mock_authentication):
        mock_authentication.return_value = MagicMock(org_id="org-1", user_id="user-1")
        mock_boto3.client.return_value = MagicMock()
        handler, _ = self._make_handler()

        result = handler.handle(
            {
                "httpMethod": "POST",
                "path": "/api/analysis/a-1/upload-url",
                "headers": {"Authorization": "Bearer token"},
                "body": json.dumps({"filename": "test.exe", "fileType": "exe"}),
            }
        )
        assert result["statusCode"] == 400
        assert "Unsupported" in json.loads(result["body"])["error"]

    @patch("src.handlers.api_gateway_handler.require_authentication")
    @patch("src.handlers.api_gateway_handler.boto3")
    @patch.dict(
        "os.environ",
        {
            "ANALYSIS_QUEUE_URL": "https://sqs.us-east-1.amazonaws.com/123/queue",
            "DOCUMENTS_BUCKET": "janus-documents-test",
        },
    )
    def test_upload_url_rejects_path_traversal(self, mock_boto3, mock_authentication):
        mock_authentication.return_value = MagicMock(org_id="org-1", user_id="user-1")
        mock_boto3.client.return_value = MagicMock()
        handler, _ = self._make_handler()

        result = handler.handle(
            {
                "httpMethod": "POST",
                "path": "/api/analysis/a-1/upload-url",
                "headers": {"Authorization": "Bearer token"},
                "body": json.dumps({"filename": "test", "fileType": "../../../etc/passwd"}),
            }
        )
        assert result["statusCode"] == 400
        assert "Unsupported" in json.loads(result["body"])["error"]

    @patch("src.handlers.api_gateway_handler.require_authentication")
    @patch("src.handlers.api_gateway_handler.boto3")
    @patch.dict(
        "os.environ",
        {
            "ANALYSIS_QUEUE_URL": "https://sqs.us-east-1.amazonaws.com/123/queue",
            "DOCUMENTS_BUCKET": "janus-documents-test",
        },
    )
    def test_upload_url_analysis_not_found(self, mock_boto3, mock_authentication):
        mock_authentication.return_value = MagicMock(org_id="org-1", user_id="user-1")
        mock_boto3.client.return_value = MagicMock()
        handler, storage = self._make_handler()
        company_repo = MagicMock()
        company_repo.get_by_id.return_value = None
        storage.create_company_repository.return_value = company_repo

        result = handler.handle(
            {
                "httpMethod": "POST",
                "path": "/api/analysis/a-1/upload-url",
                "headers": {"Authorization": "Bearer token"},
                "body": json.dumps({"filename": "test.pdf", "fileType": "pdf"}),
            }
        )
        assert result["statusCode"] == 404

    @patch("src.handlers.api_gateway_handler.require_authentication")
    @patch("src.handlers.api_gateway_handler.boto3")
    @patch.dict(
        "os.environ",
        {
            "ANALYSIS_QUEUE_URL": "https://sqs.us-east-1.amazonaws.com/123/queue",
            "DOCUMENTS_BUCKET": "janus-documents-test",
        },
    )
    def test_create_document_with_s3_document_key(self, mock_boto3, mock_authentication):
        mock_authentication.return_value = MagicMock(org_id="org-1", user_id="user-1")
        mock_s3 = MagicMock()
        mock_s3.get_object.return_value = {"Body": MagicMock(read=lambda: b"Hello from S3")}
        mock_boto3.client.side_effect = lambda service, **kw: mock_s3
        handler, storage = self._make_handler()
        company_repo = MagicMock()
        company_repo.get_by_id.return_value = {"org_id": "org-1"}
        assessment_repo = MagicMock()
        assessment_repo.find_by_company.return_value = [{"id": "assess-1"}]
        storage.create_company_repository.return_value = company_repo
        storage.create_assessment_repository.return_value = assessment_repo

        result = handler.handle(
            {
                "httpMethod": "POST",
                "path": "/api/analysis/a-1/documents",
                "headers": {"Authorization": "Bearer token"},
                "body": json.dumps(
                    {
                        "filename": "test.txt",
                        "fileType": "txt",
                        "documentKey": "uploads/a-1/abc.txt",
                    }
                ),
            }
        )
        assert result["statusCode"] == 201
        body = json.loads(result["body"])
        assert body["filename"] == "test.txt"
        assert body["charCount"] == len("Hello from S3")
        mock_s3.get_object.assert_called_once_with(
            Bucket="janus-documents-test", Key="uploads/a-1/abc.txt"
        )

    @patch("src.handlers.api_gateway_handler.require_authentication")
    @patch("src.handlers.api_gateway_handler.boto3")
    @patch.dict(
        "os.environ",
        {
            "ANALYSIS_QUEUE_URL": "https://sqs.us-east-1.amazonaws.com/123/queue",
            "DOCUMENTS_BUCKET": "janus-documents-test",
        },
    )
    def test_create_document_rejects_invalid_document_key_prefix(
        self, mock_boto3, mock_authentication
    ):
        mock_authentication.return_value = MagicMock(org_id="org-1", user_id="user-1")
        mock_boto3.client.return_value = MagicMock()
        handler, storage = self._make_handler()
        company_repo = MagicMock()
        company_repo.get_by_id.return_value = {"org_id": "org-1"}
        assessment_repo = MagicMock()
        assessment_repo.find_by_company.return_value = [{"id": "assess-1"}]
        storage.create_company_repository.return_value = company_repo
        storage.create_assessment_repository.return_value = assessment_repo

        result = handler.handle(
            {
                "httpMethod": "POST",
                "path": "/api/analysis/a-1/documents",
                "headers": {"Authorization": "Bearer token"},
                "body": json.dumps(
                    {
                        "filename": "test.txt",
                        "fileType": "txt",
                        "documentKey": "uploads/OTHER-ANALYSIS/abc.txt",
                    }
                ),
            }
        )
        assert result["statusCode"] == 400
        assert "Invalid documentKey" in json.loads(result["body"])["error"]

    @patch("src.handlers.api_gateway_handler.require_authentication")
    @patch("src.handlers.api_gateway_handler.boto3")
    @patch.dict(
        "os.environ",
        {
            "ANALYSIS_QUEUE_URL": "https://sqs.us-east-1.amazonaws.com/123/queue",
            "DOCUMENTS_BUCKET": "janus-documents-test",
        },
    )
    def test_create_document_s3_key_not_found(self, mock_boto3, mock_authentication):
        from botocore.exceptions import ClientError

        mock_authentication.return_value = MagicMock(org_id="org-1", user_id="user-1")
        mock_s3 = MagicMock()
        mock_s3.get_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "Not found"}}, "GetObject"
        )
        mock_boto3.client.side_effect = lambda service, **kw: mock_s3
        handler, storage = self._make_handler()
        company_repo = MagicMock()
        company_repo.get_by_id.return_value = {"org_id": "org-1"}
        assessment_repo = MagicMock()
        assessment_repo.find_by_company.return_value = [{"id": "assess-1"}]
        storage.create_company_repository.return_value = company_repo
        storage.create_assessment_repository.return_value = assessment_repo

        result = handler.handle(
            {
                "httpMethod": "POST",
                "path": "/api/analysis/a-1/documents",
                "headers": {"Authorization": "Bearer token"},
                "body": json.dumps(
                    {
                        "filename": "test.txt",
                        "fileType": "txt",
                        "documentKey": "uploads/a-1/abc.txt",
                    }
                ),
            }
        )
        assert result["statusCode"] == 404
        assert "not found" in json.loads(result["body"])["error"].lower()

    @patch("src.handlers.api_gateway_handler.require_authentication")
    def test_create_document_s3_not_configured_with_document_key(self, mock_authentication):
        mock_authentication.return_value = MagicMock(org_id="org-1", user_id="user-1")
        handler, storage = self._make_handler()
        company_repo = MagicMock()
        company_repo.get_by_id.return_value = {"org_id": "org-1"}
        assessment_repo = MagicMock()
        assessment_repo.find_by_company.return_value = [{"id": "assess-1"}]
        storage.create_company_repository.return_value = company_repo
        storage.create_assessment_repository.return_value = assessment_repo

        result = handler.handle(
            {
                "httpMethod": "POST",
                "path": "/api/analysis/a-1/documents",
                "headers": {"Authorization": "Bearer token"},
                "body": json.dumps(
                    {
                        "filename": "test.txt",
                        "fileType": "txt",
                        "documentKey": "uploads/a-1/abc.txt",
                    }
                ),
            }
        )
        assert result["statusCode"] == 500
        assert "S3 not configured" in json.loads(result["body"])["error"]

    @patch("src.handlers.api_gateway_handler.require_authentication")
    def test_create_document_no_content_or_key(self, mock_authentication):
        mock_authentication.return_value = MagicMock(org_id="org-1", user_id="user-1")
        handler, storage = self._make_handler()
        company_repo = MagicMock()
        company_repo.get_by_id.return_value = {"org_id": "org-1"}
        assessment_repo = MagicMock()
        assessment_repo.find_by_company.return_value = [{"id": "assess-1"}]
        storage.create_company_repository.return_value = company_repo
        storage.create_assessment_repository.return_value = assessment_repo

        result = handler.handle(
            {
                "httpMethod": "POST",
                "path": "/api/analysis/a-1/documents",
                "headers": {"Authorization": "Bearer token"},
                "body": json.dumps({"filename": "test.txt", "fileType": "txt"}),
            }
        )
        assert result["statusCode"] == 400
        assert "documentKey or fileContent required" in json.loads(result["body"])["error"]

    @patch("src.handlers.api_gateway_handler.require_authentication")
    def test_get_analysis_includes_documents(self, mock_authentication):
        mock_authentication.return_value = MagicMock(org_id="org-1", user_id="user-1")
        handler, storage = self._make_handler()
        company_repo = MagicMock()
        company_repo.get_by_id.return_value = {
            "org_id": "org-1",
            "company_name": "Test",
            "metadata_json": "",
        }
        assessment_repo = MagicMock()
        assessment_repo.find_by_company.return_value = [{"id": "assess-1"}]
        assessment_repo.get_risk_scores.return_value = []
        assessment_repo.get_opportunities.return_value = []
        assessment_repo.get_ebitda_tree.return_value = None
        assessment_repo.get_documents.return_value = [
            {
                "id": "doc-1",
                "filename": "report.pdf",
                "fileType": "pdf",
                "charCount": 5000,
                "uploadedAt": "2026-03-13T00:00:00",
            }
        ]
        storage.create_company_repository.return_value = company_repo
        storage.create_assessment_repository.return_value = assessment_repo

        result = handler.handle(
            {
                "httpMethod": "GET",
                "path": "/api/analysis/a-1",
                "headers": {"Authorization": "Bearer token"},
            }
        )
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert len(body["documents"]) == 1
        assert body["documents"][0]["filename"] == "report.pdf"

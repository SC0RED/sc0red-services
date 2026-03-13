"""Tests for APIGatewayHandler."""

import base64
import json
from unittest.mock import MagicMock, patch

import pytest

from src.handlers.api_gateway_handler import APIGatewayHandler, _error, _json_response


class TestHelperFunctions:
    def test_json_response_default_status(self):
        result = _json_response({"key": "value"})
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["key"] == "value"
        assert "Content-Type" in result["headers"]

    def test_json_response_custom_status(self):
        result = _json_response({"ok": True}, 201)
        assert result["statusCode"] == 201

    def test_json_response_cors_headers(self):
        result = _json_response({})
        assert result["headers"]["Access-Control-Allow-Origin"] == "*"
        assert "Authorization" in result["headers"]["Access-Control-Allow-Headers"]

    def test_error_response(self):
        result = _error("bad request")
        assert result["statusCode"] == 400
        body = json.loads(result["body"])
        assert body["error"] == "bad request"

    def test_error_custom_status(self):
        result = _error("not found", 404)
        assert result["statusCode"] == 404


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
        assert "required" in json.loads(result["body"])["error"].lower()

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

    def test_register_success(self):
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
        org_repo.create.assert_called_once()
        user_repo.create.assert_called_once()

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
    @patch.dict("os.environ", {"ANALYSIS_QUEUE_URL": "https://sqs.us-east-1.amazonaws.com/123/queue"})
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
    def test_scan_start_portfolio_success(self, mock_authentication):
        mock_authentication.return_value = MagicMock(org_id="org-1", user_id="user-1")
        handler, storage = self._make_handler()

        scan_repo = MagicMock()
        storage.create_scan_repository.return_value = scan_repo
        handler._factory_manager = MagicMock()
        handler._factory_manager.run_portfolio_discovery.return_value = {
            "details": {"portfolio_companies": [{"name": "Co1", "url": "https://co1.com"}]},
        }

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
        assert body["status"] == "awaiting_confirmation"
        assert len(body["portfolioCompanies"]) == 1

    @patch("src.handlers.api_gateway_handler.require_authentication")
    def test_scan_start_portfolio_failure(self, mock_authentication):
        mock_authentication.return_value = MagicMock(org_id="org-1", user_id="user-1")
        handler, storage = self._make_handler()

        scan_repo = MagicMock()
        storage.create_scan_repository.return_value = scan_repo
        handler._factory_manager = MagicMock()
        handler._factory_manager.run_portfolio_discovery.side_effect = RuntimeError("fail")

        with pytest.raises(RuntimeError, match="fail"):
            handler.handle(
                {
                    "httpMethod": "POST",
                    "path": "/api/scan/start",
                    "headers": {"Authorization": "Bearer token"},
                    "body": json.dumps({"url": "https://pefirm.com", "type": "portfolio"}),
                }
            )

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
        company_repo.get_by_id.return_value = {
            "id": "c-1",
            "company_name": "Test",
            "company_url": "https://test.com",
        }
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
    @patch.dict("os.environ", {"ANALYSIS_QUEUE_URL": "https://sqs.us-east-1.amazonaws.com/123/queue"})
    def test_scan_confirm_success(self, mock_boto3, mock_authentication):
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
        assert mock_sqs.send_message.call_count == 2

    @patch("src.handlers.api_gateway_handler.require_authentication")
    @patch("src.handlers.api_gateway_handler.boto3")
    @patch.dict("os.environ", {"ANALYSIS_QUEUE_URL": "https://sqs.us-east-1.amazonaws.com/123/queue"})
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
    @patch.dict("os.environ", {"ANALYSIS_QUEUE_URL": "https://sqs.us-east-1.amazonaws.com/123/queue"})
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
        assessment_repo.delete.assert_called_once_with("assess-1")
        assert company_repo.delete.call_count == 2
        scan_repo.delete_all_company_links.assert_called_once_with("scan-123")
        scan_repo.delete.assert_called_once_with("scan-123")

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
        scan_repo.delete.assert_called_once_with("scan-123")

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
        assessment_repo.delete.assert_called_once_with("assess-1")
        company_repo.delete.assert_called_once_with("a-1")
        scan_repo.unlink_company.assert_called_once_with("scan-1", "a-1")
        scan_repo.delete.assert_called_once_with("scan-1")

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
        scan_repo.unlink_company.assert_called_once_with("scan-1", "a-1")
        scan_repo.delete.assert_not_called()

    @patch("src.handlers.api_gateway_handler.require_authentication")
    def test_list_analyses(self, mock_authentication):
        mock_authentication.return_value = MagicMock(org_id="org-1", user_id="user-1")
        handler, storage = self._make_handler()
        company_repo = MagicMock()
        company_repo.find_by_org.return_value = [
            {"id": "c-1", "company_name": "Test", "risk_tier": "low"},
        ]
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


class TestLoginEndpoint:
    def _make_handler(self):
        storage = MagicMock()
        return APIGatewayHandler(storage=storage), storage

    def test_login_missing_fields(self):
        handler, _ = self._make_handler()
        result = handler.handle(
            {
                "httpMethod": "POST",
                "path": "/api/auth/login",
                "headers": {},
                "body": json.dumps({"email": "test@example.com"}),
            }
        )
        assert result["statusCode"] == 400
        assert "required" in json.loads(result["body"])["error"].lower()

    def test_login_invalid_credentials(self):
        handler, storage = self._make_handler()
        user_repo = MagicMock()
        user_repo.verify_password.return_value = None
        storage.create_user_repository.return_value = user_repo

        result = handler.handle(
            {
                "httpMethod": "POST",
                "path": "/api/auth/login",
                "headers": {},
                "body": json.dumps({"email": "test@example.com", "password": "wrong"}),
            }
        )
        assert result["statusCode"] == 401
        assert "Invalid credentials" in json.loads(result["body"])["error"]

    def test_login_success(self):
        handler, storage = self._make_handler()
        user_repo = MagicMock()
        user_repo.verify_password.return_value = {
            "id": "user-1",
            "email": "test@example.com",
            "name": "Test User",
            "orgId": "org-1",
            "role": "admin",
        }
        storage.create_user_repository.return_value = user_repo

        result = handler.handle(
            {
                "httpMethod": "POST",
                "path": "/api/auth/login",
                "headers": {},
                "body": json.dumps({"email": "test@example.com", "password": "correct"}),
            }
        )
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["success"] is True
        assert body["user"]["email"] == "test@example.com"
        assert body["user"]["orgId"] == "org-1"

    def test_login_empty_body(self):
        handler, _ = self._make_handler()
        result = handler.handle(
            {
                "httpMethod": "POST",
                "path": "/api/auth/login",
                "headers": {},
                "body": "{}",
            }
        )
        assert result["statusCode"] == 400


class TestDashboardEndpoint:
    def _make_handler(self):
        storage = MagicMock()
        return APIGatewayHandler(storage=storage), storage

    @patch("src.handlers.api_gateway_handler.require_authentication")
    def test_dashboard_empty_org(self, mock_authentication):
        mock_authentication.return_value = MagicMock(org_id="org-1", user_id="user-1")
        handler, storage = self._make_handler()
        company_repo = MagicMock()
        company_repo.find_by_org.return_value = []
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
        company_repo.find_by_org.return_value = [
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
        ]
        scan_repo = MagicMock()
        all_scans = [
            {
                "id": "s-1",
                "source_url": "https://pe.com",
                "type": "portfolio",
                "status": "complete",
                "progress": 100,
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
        message_body = json.loads(
            mock_sqs.send_message.call_args[1]["MessageBody"]
        )
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

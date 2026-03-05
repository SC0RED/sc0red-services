"""Tests for APIGatewayHandler."""

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

    @patch("src.handlers.api_gateway_handler.require_auth")
    def test_not_found_route(self, mock_auth):
        mock_auth.return_value = MagicMock(org_id="org-1", user_id="user-1")
        handler, _ = self._make_handler()
        result = handler.handle({
            "httpMethod": "GET",
            "path": "/api/nonexistent",
            "headers": {"Authorization": "Bearer token"},
        })
        assert result["statusCode"] == 404

    @patch("src.handlers.api_gateway_handler.require_auth")
    def test_auth_failure(self, mock_auth):
        mock_auth.side_effect = ValueError("Invalid token")
        handler, _ = self._make_handler()
        result = handler.handle({
            "httpMethod": "GET",
            "path": "/api/analyses",
            "headers": {},
        })
        assert result["statusCode"] == 401

    def test_register_missing_fields(self):
        handler, storage = self._make_handler()
        result = handler.handle({
            "httpMethod": "POST",
            "path": "/api/auth/register",
            "headers": {},
            "body": json.dumps({"name": "Test"}),
        })
        assert result["statusCode"] == 400
        assert "required" in json.loads(result["body"])["error"].lower()

    def test_register_duplicate_email(self):
        handler, storage = self._make_handler()
        user_repo = MagicMock()
        user_repo.email_exists.return_value = True
        storage.create_user_repository.return_value = user_repo
        storage.create_organization_repository.return_value = MagicMock()

        result = handler.handle({
            "httpMethod": "POST",
            "path": "/api/auth/register",
            "headers": {},
            "body": json.dumps({
                "name": "Test",
                "email": "test@example.com",
                "password": "password123",
                "orgName": "Test Org",
            }),
        })
        assert result["statusCode"] == 400
        assert "already registered" in json.loads(result["body"])["error"]

    def test_register_success(self):
        handler, storage = self._make_handler()
        user_repo = MagicMock()
        user_repo.email_exists.return_value = False
        org_repo = MagicMock()
        storage.create_user_repository.return_value = user_repo
        storage.create_organization_repository.return_value = org_repo

        result = handler.handle({
            "httpMethod": "POST",
            "path": "/api/auth/register",
            "headers": {},
            "body": json.dumps({
                "name": "Test User",
                "email": "test@example.com",
                "password": "password123",
                "orgName": "Test Org",
            }),
        })
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["success"] is True
        org_repo.create.assert_called_once()
        user_repo.create.assert_called_once()

    @patch("src.handlers.api_gateway_handler.require_auth")
    def test_scan_start_missing_fields(self, mock_auth):
        mock_auth.return_value = MagicMock(org_id="org-1", user_id="user-1")
        handler, _ = self._make_handler()
        result = handler.handle({
            "httpMethod": "POST",
            "path": "/api/scan/start",
            "headers": {"Authorization": "Bearer token"},
            "body": json.dumps({"url": ""}),
        })
        assert result["statusCode"] == 400

    @patch("src.handlers.api_gateway_handler.require_auth")
    def test_scan_start_single_company_success(self, mock_auth):
        mock_auth.return_value = MagicMock(org_id="org-1", user_id="user-1")
        handler, storage = self._make_handler()

        scan_repo = MagicMock()
        company_repo = MagicMock()
        storage.create_scan_repository.return_value = scan_repo
        storage.create_company_repository.return_value = company_repo
        handler._factory_manager = MagicMock()

        result = handler.handle({
            "httpMethod": "POST",
            "path": "/api/scan/start",
            "headers": {"Authorization": "Bearer token"},
            "body": json.dumps({"url": "https://example.com", "type": "single"}),
        })
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["status"] == "complete"
        assert "scanId" in body

    @patch("src.handlers.api_gateway_handler.require_auth")
    def test_scan_start_single_company_failure(self, mock_auth):
        mock_auth.return_value = MagicMock(org_id="org-1", user_id="user-1")
        handler, storage = self._make_handler()

        scan_repo = MagicMock()
        company_repo = MagicMock()
        storage.create_scan_repository.return_value = scan_repo
        storage.create_company_repository.return_value = company_repo
        handler._factory_manager = MagicMock()
        handler._factory_manager.run_company_analysis.side_effect = RuntimeError("AI error")

        result = handler.handle({
            "httpMethod": "POST",
            "path": "/api/scan/start",
            "headers": {"Authorization": "Bearer token"},
            "body": json.dumps({"url": "https://example.com", "type": "single"}),
        })
        assert result["statusCode"] == 500

    @patch("src.handlers.api_gateway_handler.require_auth")
    def test_scan_start_portfolio_success(self, mock_auth):
        mock_auth.return_value = MagicMock(org_id="org-1", user_id="user-1")
        handler, storage = self._make_handler()

        scan_repo = MagicMock()
        storage.create_scan_repository.return_value = scan_repo
        handler._factory_manager = MagicMock()
        handler._factory_manager.run_portfolio_discovery.return_value = {
            "details": {"portfolio_companies": [{"name": "Co1", "url": "https://co1.com"}]},
        }

        result = handler.handle({
            "httpMethod": "POST",
            "path": "/api/scan/start",
            "headers": {"Authorization": "Bearer token"},
            "body": json.dumps({"url": "https://pefirm.com/portfolio", "type": "portfolio"}),
        })
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["status"] == "awaiting_confirmation"
        assert len(body["portfolioCompanies"]) == 1

    @patch("src.handlers.api_gateway_handler.require_auth")
    def test_scan_start_portfolio_failure(self, mock_auth):
        mock_auth.return_value = MagicMock(org_id="org-1", user_id="user-1")
        handler, storage = self._make_handler()

        scan_repo = MagicMock()
        storage.create_scan_repository.return_value = scan_repo
        handler._factory_manager = MagicMock()
        handler._factory_manager.run_portfolio_discovery.side_effect = RuntimeError("fail")

        result = handler.handle({
            "httpMethod": "POST",
            "path": "/api/scan/start",
            "headers": {"Authorization": "Bearer token"},
            "body": json.dumps({"url": "https://pefirm.com", "type": "portfolio"}),
        })
        assert result["statusCode"] == 500

    @patch("src.handlers.api_gateway_handler.require_auth")
    def test_scan_status_not_found(self, mock_auth):
        mock_auth.return_value = MagicMock(org_id="org-1", user_id="user-1")
        handler, storage = self._make_handler()

        scan_repo = MagicMock()
        scan_repo.get_by_id.return_value = None
        storage.create_scan_repository.return_value = scan_repo

        result = handler.handle({
            "httpMethod": "GET",
            "path": "/api/scan/scan-123",
            "headers": {"Authorization": "Bearer token"},
        })
        assert result["statusCode"] == 404

    @patch("src.handlers.api_gateway_handler.require_auth")
    def test_scan_status_wrong_org(self, mock_auth):
        mock_auth.return_value = MagicMock(org_id="org-1", user_id="user-1")
        handler, storage = self._make_handler()

        scan_repo = MagicMock()
        scan_repo.get_by_id.return_value = {"org_id": "other-org"}
        storage.create_scan_repository.return_value = scan_repo

        result = handler.handle({
            "httpMethod": "GET",
            "path": "/api/scan/scan-123",
            "headers": {"Authorization": "Bearer token"},
        })
        assert result["statusCode"] == 404

    @patch("src.handlers.api_gateway_handler.require_auth")
    def test_scan_status_success(self, mock_auth):
        mock_auth.return_value = MagicMock(org_id="org-1", user_id="user-1")
        handler, storage = self._make_handler()

        scan_repo = MagicMock()
        scan_repo.get_by_id.return_value = {"org_id": "org-1", "status": "complete", "type": "single"}
        scan_repo.get_scan_companies.return_value = [{"company_id": "c-1"}]
        company_repo = MagicMock()
        company_repo.get_by_id.return_value = {
            "id": "c-1",
            "company_name": "Test",
            "company_url": "https://test.com",
        }
        storage.create_scan_repository.return_value = scan_repo
        storage.create_company_repository.return_value = company_repo

        result = handler.handle({
            "httpMethod": "GET",
            "path": "/api/scan/scan-123",
            "headers": {"Authorization": "Bearer token"},
        })
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["status"] == "complete"
        assert len(body["analyses"]) == 1

    @patch("src.handlers.api_gateway_handler.require_auth")
    def test_scan_confirm_no_companies(self, mock_auth):
        mock_auth.return_value = MagicMock(org_id="org-1", user_id="user-1")
        handler, _ = self._make_handler()
        result = handler.handle({
            "httpMethod": "POST",
            "path": "/api/scan/scan-123/confirm",
            "headers": {"Authorization": "Bearer token"},
            "body": json.dumps({"companies": []}),
        })
        assert result["statusCode"] == 400

    @patch("src.handlers.api_gateway_handler.require_auth")
    def test_scan_confirm_not_found(self, mock_auth):
        mock_auth.return_value = MagicMock(org_id="org-1", user_id="user-1")
        handler, storage = self._make_handler()
        scan_repo = MagicMock()
        scan_repo.get_by_id.return_value = None
        storage.create_scan_repository.return_value = scan_repo

        result = handler.handle({
            "httpMethod": "POST",
            "path": "/api/scan/scan-123/confirm",
            "headers": {"Authorization": "Bearer token"},
            "body": json.dumps({"companies": [{"name": "Co", "url": "https://co.com"}]}),
        })
        assert result["statusCode"] == 404

    @patch("src.handlers.api_gateway_handler.require_auth")
    def test_scan_confirm_success(self, mock_auth):
        mock_auth.return_value = MagicMock(org_id="org-1", user_id="user-1")
        handler, storage = self._make_handler()
        scan_repo = MagicMock()
        scan_repo.get_by_id.return_value = {"org_id": "org-1"}
        company_repo = MagicMock()
        storage.create_scan_repository.return_value = scan_repo
        storage.create_company_repository.return_value = company_repo
        handler._factory_manager = MagicMock()

        result = handler.handle({
            "httpMethod": "POST",
            "path": "/api/scan/scan-123/confirm",
            "headers": {"Authorization": "Bearer token"},
            "body": json.dumps({
                "companies": [
                    {"name": "Co1", "url": "https://co1.com"},
                    {"name": "Co2", "url": "https://co2.com"},
                ],
            }),
        })
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["ok"] is True
        assert len(body["results"]) == 2

    @patch("src.handlers.api_gateway_handler.require_auth")
    def test_scan_confirm_partial_failure(self, mock_auth):
        mock_auth.return_value = MagicMock(org_id="org-1", user_id="user-1")
        handler, storage = self._make_handler()
        scan_repo = MagicMock()
        scan_repo.get_by_id.return_value = {"org_id": "org-1"}
        company_repo = MagicMock()
        storage.create_scan_repository.return_value = scan_repo
        storage.create_company_repository.return_value = company_repo
        handler._factory_manager = MagicMock()
        handler._factory_manager.run_company_analysis.side_effect = [None, RuntimeError("fail")]

        result = handler.handle({
            "httpMethod": "POST",
            "path": "/api/scan/scan-123/confirm",
            "headers": {"Authorization": "Bearer token"},
            "body": json.dumps({
                "companies": [
                    {"name": "Co1", "url": "https://co1.com"},
                    {"name": "Co2", "url": "https://co2.com"},
                ],
            }),
        })
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["results"][0]["status"] == "complete"
        assert body["results"][1]["status"] == "failed"

    @patch("src.handlers.api_gateway_handler.require_auth")
    def test_get_analysis_not_found(self, mock_auth):
        mock_auth.return_value = MagicMock(org_id="org-1", user_id="user-1")
        handler, storage = self._make_handler()
        company_repo = MagicMock()
        company_repo.get_by_id.return_value = None
        storage.create_company_repository.return_value = company_repo

        result = handler.handle({
            "httpMethod": "GET",
            "path": "/api/analysis/a-1",
            "headers": {"Authorization": "Bearer token"},
        })
        assert result["statusCode"] == 404

    @patch("src.handlers.api_gateway_handler.require_auth")
    def test_get_analysis_success(self, mock_auth):
        mock_auth.return_value = MagicMock(org_id="org-1", user_id="user-1")
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

        result = handler.handle({
            "httpMethod": "GET",
            "path": "/api/analysis/a-1",
            "headers": {"Authorization": "Bearer token"},
        })
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["companyName"] == "Test"
        assert len(body["riskScores"]) == 1

    @patch("src.handlers.api_gateway_handler.require_auth")
    def test_get_analysis_with_metadata_json(self, mock_auth):
        mock_auth.return_value = MagicMock(org_id="org-1", user_id="user-1")
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

        result = handler.handle({
            "httpMethod": "GET",
            "path": "/api/analysis/a-1",
            "headers": {"Authorization": "Bearer token"},
        })
        body = json.loads(result["body"])
        assert body["topActions"] == ["Action 1"]
        assert body["analysisSummary"] == "Good"

    @patch("src.handlers.api_gateway_handler.require_auth")
    def test_delete_analysis_not_found(self, mock_auth):
        mock_auth.return_value = MagicMock(org_id="org-1", user_id="user-1")
        handler, storage = self._make_handler()
        company_repo = MagicMock()
        company_repo.get_by_id.return_value = None
        storage.create_company_repository.return_value = company_repo

        result = handler.handle({
            "httpMethod": "DELETE",
            "path": "/api/analysis/a-1",
            "headers": {"Authorization": "Bearer token"},
        })
        assert result["statusCode"] == 404

    @patch("src.handlers.api_gateway_handler.require_auth")
    def test_delete_analysis_success(self, mock_auth):
        mock_auth.return_value = MagicMock(org_id="org-1", user_id="user-1")
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

        result = handler.handle({
            "httpMethod": "DELETE",
            "path": "/api/analysis/a-1",
            "headers": {"Authorization": "Bearer token"},
        })
        assert result["statusCode"] == 200
        assessment_repo.delete.assert_called_once_with("assess-1")
        company_repo.delete.assert_called_once_with("a-1")
        scan_repo.delete.assert_called_once_with("scan-1")

    @patch("src.handlers.api_gateway_handler.require_auth")
    def test_delete_analysis_keeps_scan_with_remaining(self, mock_auth):
        mock_auth.return_value = MagicMock(org_id="org-1", user_id="user-1")
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

        result = handler.handle({
            "httpMethod": "DELETE",
            "path": "/api/analysis/a-1",
            "headers": {"Authorization": "Bearer token"},
        })
        assert result["statusCode"] == 200
        scan_repo.delete.assert_not_called()

    @patch("src.handlers.api_gateway_handler.require_auth")
    def test_list_analyses(self, mock_auth):
        mock_auth.return_value = MagicMock(org_id="org-1", user_id="user-1")
        handler, storage = self._make_handler()
        company_repo = MagicMock()
        company_repo.find_by_org.return_value = [
            {"id": "c-1", "company_name": "Test", "risk_tier": "low"},
        ]
        storage.create_company_repository.return_value = company_repo

        result = handler.handle({
            "httpMethod": "GET",
            "path": "/api/analyses",
            "headers": {"Authorization": "Bearer token"},
        })
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert len(body["analyses"]) == 1
        assert body["analyses"][0]["companyName"] == "Test"

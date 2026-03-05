"""API Gateway REST handler — routes HTTP requests to business logic.

Replaces the Next.js API routes with equivalent Python handlers.
Request/response shapes are identical to minimize frontend changes.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

import bcrypt

from src.handlers.auth_middleware import AuthContext, require_auth
from src.handlers.factory_manager import FactoryManager
from src.repositories.dynamodb.provider import DynamoDBStorageProvider

logger = logging.getLogger(__name__)

LambdaResponse = dict[str, Any]


def _json_response(body: dict, status: int = 200) -> LambdaResponse:
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
            "Access-Control-Allow-Methods": "GET,POST,DELETE,OPTIONS",
        },
        "body": json.dumps(body, default=str),
    }


def _error(message: str, status: int = 400) -> LambdaResponse:
    return _json_response({"error": message}, status)


class APIGatewayHandler:
    """Handles all API Gateway HTTP requests."""

    def __init__(self, storage: DynamoDBStorageProvider | None = None) -> None:
        self._storage = storage or DynamoDBStorageProvider()
        self._factory_manager = FactoryManager(self._storage)

    def handle(self, event: dict[str, Any]) -> LambdaResponse:
        method = event.get("httpMethod", "GET")
        path = event.get("path", "")
        headers = event.get("headers") or {}

        # CORS preflight
        if method == "OPTIONS":
            return _json_response({}, 200)

        # Public routes (no auth required)
        if path == "/api/auth/register" and method == "POST":
            return self._handle_register(event)

        # All other routes require auth
        try:
            auth = require_auth(headers)
        except ValueError as e:
            return _error(str(e), 401)

        # Route to handlers
        if path == "/api/scan/start" and method == "POST":
            return self._handle_scan_start(event, auth)
        if path.startswith("/api/scan/") and path.endswith("/confirm") and method == "POST":
            scan_id = path.split("/")[3]
            return self._handle_scan_confirm(event, auth, scan_id)
        if path.startswith("/api/scan/") and method == "GET":
            scan_id = path.split("/")[3]
            return self._handle_scan_status(auth, scan_id)
        if path.startswith("/api/analysis/") and method == "GET":
            analysis_id = path.split("/")[3]
            return self._handle_get_analysis(auth, analysis_id)
        if path.startswith("/api/analysis/") and method == "DELETE":
            analysis_id = path.split("/")[3]
            return self._handle_delete_analysis(auth, analysis_id)
        if path == "/api/analyses" and method == "GET":
            return self._handle_list_analyses(auth)

        return _error("Not found", 404)

    # ── POST /api/scan/start ─────────────────────────────────────────

    def _handle_scan_start(self, event: dict, auth: AuthContext) -> LambdaResponse:
        body = json.loads(event.get("body") or "{}")
        url = body.get("url", "")
        scan_type = body.get("type", "")

        if not url or not scan_type:
            return _error("url and type required")

        scan_repo = self._storage.create_scan_repository()
        scan_id = str(uuid.uuid4())

        scan_repo.create({
            "id": scan_id,
            "org_id": auth.org_id,
            "created_by": auth.user_id,
            "type": scan_type,
            "source_url": url,
            "status": "running",
            "progress": 0,
        })

        if scan_type == "portfolio":
            try:
                scan_repo.update(scan_id, {"progress": 5})
                result = self._factory_manager.run_portfolio_discovery(
                    url=url,
                    org_id=auth.org_id,
                    user_id=auth.user_id,
                    scan_id=scan_id,
                )
                companies = result.get("details", {}).get("portfolio_companies", [])
                scan_repo.update(scan_id, {
                    "status": "awaiting_confirmation",
                    "progress": 20,
                    "portfolio_companies": companies,
                })
                return _json_response({
                    "scanId": scan_id,
                    "status": "awaiting_confirmation",
                    "portfolioCompanies": companies,
                })
            except Exception as e:
                logger.error("Portfolio discovery failed: %s", e)
                scan_repo.update(scan_id, {"status": "failed"})
                return _error(f"Portfolio discovery failed: {e}", 500)

        # Single company analysis
        company_id = str(uuid.uuid4())
        company_repo = self._storage.create_company_repository()
        company_repo.save_company(company_id, {
            "scan_id": scan_id,
            "org_id": auth.org_id,
            "company_url": url,
            "company_name": "",
        })

        try:
            scan_repo.update(scan_id, {"progress": 10})
            self._factory_manager.run_company_analysis(
                url=url,
                org_id=auth.org_id,
                user_id=auth.user_id,
                scan_id=scan_id,
            )
            scan_repo.update(scan_id, {"status": "complete", "progress": 100})
            return _json_response({
                "scanId": scan_id,
                "status": "complete",
                "analysisId": company_id,
            })
        except Exception as e:
            logger.error("Analysis failed for %s: %s", url, e)
            company_repo.update(company_id, {"error": str(e)})
            scan_repo.update(scan_id, {"status": "failed", "progress": 0})
            return _error(str(e), 500)

    # ── GET /api/scan/{scanId} ───────────────────────────────────────

    def _handle_scan_status(self, auth: AuthContext, scan_id: str) -> LambdaResponse:
        scan_repo = self._storage.create_scan_repository()
        scan = scan_repo.get_by_id(scan_id)
        if not scan or scan.get("org_id") != auth.org_id:
            return _error("Not found", 404)

        # Get full company records linked to this scan
        company_repo = self._storage.create_company_repository()
        scan_companies = scan_repo.get_scan_companies(scan_id)
        analyses = []
        for link in scan_companies:
            company_id = link.get("company_id", "")
            if company_id:
                full = company_repo.get_by_id(company_id)
                if full:
                    analyses.append({
                        "id": full.get("id"),
                        "company_name": full.get("company_name", ""),
                        "company_url": full.get("company_url", ""),
                        "industry": full.get("industry", ""),
                        "overall_risk_score": full.get("overall_risk_score"),
                        "risk_tier": full.get("risk_tier"),
                        "error": full.get("error"),
                        "analyzed_at": full.get("analyzed_at"),
                    })

        return _json_response({
            "status": scan.get("status"),
            "progress": scan.get("progress", 0),
            "type": scan.get("type"),
            "portfolioCompanies": scan.get("portfolio_companies", []),
            "analyses": analyses,
        })

    # ── POST /api/scan/{scanId}/confirm ──────────────────────────────

    def _handle_scan_confirm(
        self, event: dict, auth: AuthContext, scan_id: str
    ) -> LambdaResponse:
        body = json.loads(event.get("body") or "{}")
        companies = body.get("companies", [])
        if not companies:
            return _error("No companies provided")

        scan_repo = self._storage.create_scan_repository()
        scan = scan_repo.get_by_id(scan_id)
        if not scan or scan.get("org_id") != auth.org_id:
            return _error("Scan not found", 404)

        scan_repo.update(scan_id, {"status": "running", "progress": 25})

        results = []
        total = len(companies)
        company_repo = self._storage.create_company_repository()

        for idx, company in enumerate(companies):
            company_id = str(uuid.uuid4())
            company_repo.save_company(company_id, {
                "scan_id": scan_id,
                "org_id": auth.org_id,
                "company_name": company.get("name", ""),
                "company_url": company.get("url", ""),
            })
            scan_repo.link_company(scan_id, company_id, company.get("name", ""))

            try:
                self._factory_manager.run_company_analysis(
                    url=company.get("url", ""),
                    org_id=auth.org_id,
                    user_id=auth.user_id,
                    scan_id=scan_id,
                    company_name=company.get("name", ""),
                )
                results.append({"name": company["name"], "status": "complete", "analysisId": company_id})
            except Exception as e:
                logger.error("Analysis failed for %s: %s", company.get("name"), e)
                company_repo.update(company_id, {"error": str(e)})
                results.append({"name": company["name"], "status": "failed", "error": str(e)})

            progress = round(25 + ((idx + 1) / total) * 70)
            scan_repo.update(scan_id, {"progress": progress})

        scan_repo.update(scan_id, {"status": "complete", "progress": 100})
        return _json_response({"ok": True, "results": results})

    # ── GET /api/analysis/{id} ───────────────────────────────────────

    def _handle_get_analysis(self, auth: AuthContext, analysis_id: str) -> LambdaResponse:
        company_repo = self._storage.create_company_repository()
        company = company_repo.get_by_id(analysis_id)
        if not company or company.get("org_id") != auth.org_id:
            return _error("Not found", 404)

        # Get assessment + risk scores + opportunities
        assessment_repo = self._storage.create_assessment_repository()
        assessments = assessment_repo.find_by_company(analysis_id)

        risk_scores = []
        opportunities = []
        analysis_summary = None
        top_actions: list[str] = []

        if assessments:
            assessment = assessments[0]
            assessment_id = assessment.get("id", "")
            risk_scores = assessment_repo.get_risk_scores(assessment_id)
            opportunities = assessment_repo.get_opportunities(assessment_id)
            analysis_summary = assessment.get("analysis_summary", "")

        # Parse metadata for top actions
        metadata_json = company.get("metadata_json", "")
        if metadata_json:
            try:
                meta = json.loads(metadata_json) if isinstance(metadata_json, str) else metadata_json
                analysis_summary = analysis_summary or meta.get("analysis_summary", "")
                top_actions = meta.get("top_actions", [])
            except (json.JSONDecodeError, TypeError):
                pass

        return _json_response({
            "companyName": company.get("company_name", ""),
            "companyUrl": company.get("company_url", ""),
            "industry": company.get("industry", ""),
            "overallRiskScore": company.get("overall_risk_score"),
            "riskTier": company.get("risk_tier"),
            "analysisSummary": analysis_summary,
            "topActions": top_actions,
            "riskScores": risk_scores,
            "opportunities": opportunities,
        })

    # ── DELETE /api/analysis/{id} ────────────────────────────────────

    def _handle_delete_analysis(self, auth: AuthContext, analysis_id: str) -> LambdaResponse:
        company_repo = self._storage.create_company_repository()
        company = company_repo.get_by_id(analysis_id)
        if not company or company.get("org_id") != auth.org_id:
            return _error("Not found", 404)

        # Delete assessment + children
        assessment_repo = self._storage.create_assessment_repository()
        assessments = assessment_repo.find_by_company(analysis_id)
        for assessment in assessments:
            assessment_repo.delete(assessment.get("id", ""))

        # Delete company
        company_repo.delete(analysis_id)

        # Check if scan has remaining companies
        scan_id = company.get("scan_id", "")
        if scan_id:
            scan_repo = self._storage.create_scan_repository()
            remaining = scan_repo.get_scan_companies(scan_id)
            if not remaining:
                scan_repo.delete(scan_id)

        return _json_response({"ok": True})

    # ── GET /api/analyses ────────────────────────────────────────────

    def _handle_list_analyses(self, auth: AuthContext) -> LambdaResponse:
        company_repo = self._storage.create_company_repository()
        companies = company_repo.find_by_org(auth.org_id)
        return _json_response({
            "analyses": [
                {
                    "id": c.get("id"),
                    "companyName": c.get("company_name", ""),
                    "companyUrl": c.get("company_url", ""),
                    "industry": c.get("industry", ""),
                    "overallRiskScore": c.get("overall_risk_score"),
                    "riskTier": c.get("risk_tier"),
                    "error": c.get("error"),
                    "analyzedAt": c.get("analyzed_at"),
                }
                for c in companies
            ]
        })

    # ── POST /api/auth/register ──────────────────────────────────────

    def _handle_register(self, event: dict) -> LambdaResponse:
        body = json.loads(event.get("body") or "{}")
        name = body.get("name", "")
        email = body.get("email", "")
        password = body.get("password", "")
        org_name = body.get("orgName", "")
        org_type = body.get("orgType", "company")

        if not all([name, email, password, org_name]):
            return _error("All fields required")

        user_repo = self._storage.create_user_repository()
        org_repo = self._storage.create_organization_repository()

        if user_repo.email_exists(email):
            return _error("Email already registered")

        org_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt(10)).decode()

        org_repo.create({"id": org_id, "name": org_name, "type": org_type})
        user_repo.create({
            "id": user_id,
            "org_id": org_id,
            "email": email,
            "password_hash": password_hash,
            "name": name,
            "role": "admin",
        })

        return _json_response({"success": True})

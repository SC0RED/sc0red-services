"""API Gateway REST handler — routes HTTP requests to business logic.

Replaces the Next.js API routes with equivalent Python handlers.
Request/response shapes are identical to minimize frontend changes.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import TYPE_CHECKING, Any

import bcrypt

from src.handlers.auth_middleware import require_authentication
from src.handlers.router import Router

if TYPE_CHECKING:
    from src.handlers.auth_middleware import AuthContext
    from src.repositories.dynamodb.scan_repository import DynamoDBScanRepository

from src.handlers.factory_manager import FactoryManager
from src.repositories.dynamodb.provider import DynamoDBStorageProvider

logger = logging.getLogger(__name__)

LambdaResponse = dict[str, Any]


def _json_response(body: dict[str, Any], status: int = 200) -> LambdaResponse:
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


def _build_company_summary(company: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": company.get("id"),
        "companyName": company.get("company_name", ""),
        "companyUrl": company.get("company_url", ""),
        "industry": company.get("industry", ""),
        "overallRiskScore": company.get("overall_risk_score"),
        "riskTier": company.get("risk_tier"),
        "error": company.get("error"),
        "analyzedAt": company.get("analyzed_at"),
    }


class APIGatewayHandler:
    """Handles all API Gateway HTTP requests."""

    def __init__(self, storage: DynamoDBStorageProvider | None = None) -> None:
        self._storage = storage or DynamoDBStorageProvider()
        self._factory_manager = FactoryManager(self._storage)
        self._router = self._build_router()

    def _build_router(self) -> Router:
        router = Router()
        router.public("POST", "/api/auth/register", self._handle_register)
        router.public("POST", "/api/auth/login", self._handle_login)
        router.protected("POST", "/api/scan/start", self._handle_scan_start)
        router.protected("GET", "/api/scan/{scan_id}", self._handle_scan_status)
        router.protected("POST", "/api/scan/{scan_id}/confirm", self._handle_scan_confirm)
        router.protected("GET", "/api/analysis/{analysis_id}", self._handle_get_analysis)
        router.protected("DELETE", "/api/analysis/{analysis_id}", self._handle_delete_analysis)
        router.protected("GET", "/api/analyses", self._handle_list_analyses)
        router.protected("GET", "/api/dashboard", self._handle_dashboard)
        return router

    def handle(self, event: dict[str, Any]) -> LambdaResponse:
        """Route an API Gateway event to the appropriate handler."""
        method = event.get("httpMethod", "GET")
        path = event.get("path", "")
        headers = event.get("headers") or {}

        if method == "OPTIONS":
            return _json_response({}, 200)

        result = self._router.dispatch(method, path)
        if result is None:
            return _error("Not found", 404)

        handler, path_params, authenticated = result
        if not authenticated:
            return handler(event, **path_params)

        try:
            auth = require_authentication(headers)
        except ValueError as e:
            return _error(str(e), 401)

        return handler(event, auth, **path_params)

    # ── POST /api/scan/start ─────────────────────────────────────────

    def _handle_scan_start(
        self, event: dict[str, Any], authentication: AuthContext
    ) -> LambdaResponse:
        body = json.loads(event.get("body") or "{}")
        url = body.get("url", "")
        scan_type = body.get("type", "")

        if not url or not scan_type:
            return _error("url and type required")

        scan_repo = self._storage.create_scan_repository()
        scan_id = self._create_scan_record(scan_repo, url, scan_type, authentication)

        if scan_type == "portfolio":
            return self._start_portfolio_scan(scan_repo, scan_id, url, authentication)
        return self._start_single_scan(scan_repo, scan_id, url, authentication)

    def _create_scan_record(
        self,
        scan_repo: DynamoDBScanRepository,
        url: str,
        scan_type: str,
        authentication: AuthContext,
    ) -> str:
        scan_id = str(uuid.uuid4())
        scan_repo.create(
            {
                "id": scan_id,
                "org_id": authentication.org_id,
                "created_by": authentication.user_id,
                "type": scan_type,
                "source_url": url,
                "status": "running",
                "progress": 0,
            }
        )
        return scan_id

    def _start_portfolio_scan(
        self,
        scan_repo: DynamoDBScanRepository,
        scan_id: str,
        url: str,
        authentication: AuthContext,
    ) -> LambdaResponse:
        scan_repo.update(scan_id, {"progress": 5})
        result = self._factory_manager.run_portfolio_discovery(
            url=url,
            org_id=authentication.org_id,
            user_id=authentication.user_id,
            scan_id=scan_id,
        )
        companies = result["details"]["portfolio_companies"]
        scan_repo.update(
            scan_id,
            {
                "status": "awaiting_confirmation",
                "progress": 20,
                "portfolio_companies": companies,
            },
        )
        return _json_response(
            {
                "scanId": scan_id,
                "status": "awaiting_confirmation",
                "portfolioCompanies": companies,
            }
        )

    def _start_single_scan(
        self,
        scan_repo: DynamoDBScanRepository,
        scan_id: str,
        url: str,
        authentication: AuthContext,
    ) -> LambdaResponse:
        scan_repo.update(scan_id, {"progress": 10})
        result = self._factory_manager.run_company_analysis(
            url=url,
            org_id=authentication.org_id,
            user_id=authentication.user_id,
            scan_id=scan_id,
        )
        analysis_id = result["request_id"]
        scan_repo.update(scan_id, {"status": "complete", "progress": 100})
        return _json_response(
            {
                "scanId": scan_id,
                "status": "complete",
                "analysisId": analysis_id,
            }
        )

    # ── GET /api/scan/{scanId} ───────────────────────────────────────

    def _handle_scan_status(
        self,
        _event: dict[str, Any],
        authentication: AuthContext,
        scan_id: str,
    ) -> LambdaResponse:
        scan_repo = self._storage.create_scan_repository()
        scan = scan_repo.get_by_id(scan_id)
        if not scan or scan.get("org_id") != authentication.org_id:
            return _error("Not found", 404)

        company_repo = self._storage.create_company_repository()
        scan_companies = scan_repo.get_scan_companies(scan_id)
        analyses = []
        for link in scan_companies:
            company_id = link.get("company_id", "")
            if company_id:
                full = company_repo.get_by_id(company_id)
                if full:
                    analyses.append(_build_company_summary(full))

        return _json_response(
            {
                "status": scan.get("status"),
                "progress": scan.get("progress", 0),
                "type": scan.get("type"),
                "portfolioCompanies": scan.get("portfolio_companies", []),
                "analyses": analyses,
            }
        )

    # ── POST /api/scan/{scanId}/confirm ──────────────────────────────

    def _handle_scan_confirm(
        self,
        event: dict[str, Any],
        authentication: AuthContext,
        scan_id: str,
    ) -> LambdaResponse:
        body = json.loads(event.get("body") or "{}")
        companies = body.get("companies", [])
        if not companies:
            return _error("No companies provided")

        scan_repo = self._storage.create_scan_repository()
        scan = scan_repo.get_by_id(scan_id)
        if not scan or scan.get("org_id") != authentication.org_id:
            return _error("Scan not found", 404)

        scan_repo.update(scan_id, {"status": "running", "progress": 25})

        results = []
        total = len(companies)

        for idx, company in enumerate(companies):
            company_name = company.get("name", "")
            company_url = company.get("url", "")
            if not company_url:
                results.append(
                    {"name": company_name, "status": "failed", "error": "url is required"}
                )
            else:
                try:
                    result = self._factory_manager.run_company_analysis(
                        url=company_url,
                        org_id=authentication.org_id,
                        user_id=authentication.user_id,
                        scan_id=scan_id,
                        company_name=company_name,
                    )
                    analysis_id = result["request_id"]
                    scan_repo.link_company(scan_id, analysis_id, company_name)
                    results.append(
                        {
                            "name": company_name,
                            "status": "complete",
                            "analysisId": analysis_id,
                        }
                    )
                except Exception as e:
                    logger.exception("Analysis failed for %s", company_name)
                    results.append({"name": company_name, "status": "failed", "error": str(e)})

            progress = round(25 + ((idx + 1) / total) * 70)
            scan_repo.update(scan_id, {"progress": progress})

        scan_repo.update(scan_id, {"status": "complete", "progress": 100})
        return _json_response({"ok": True, "results": results})

    # ── GET /api/analysis/{id} ───────────────────────────────────────

    def _handle_get_analysis(
        self,
        _event: dict[str, Any],
        authentication: AuthContext,
        analysis_id: str,
    ) -> LambdaResponse:
        company_repo = self._storage.create_company_repository()
        company = company_repo.get_by_id(analysis_id)
        if not company or company.get("org_id") != authentication.org_id:
            return _error("Not found", 404)

        assessment_repo = self._storage.create_assessment_repository()
        assessments = assessment_repo.find_by_company(analysis_id)

        risk_scores = []
        opportunities = []
        analysis_summary = ""
        top_actions: list[str] = []

        if assessments:
            assessment = assessments[0]
            assessment_id = assessment["id"]
            risk_scores = assessment_repo.get_risk_scores(assessment_id)
            opportunities = assessment_repo.get_opportunities(assessment_id)

        metadata_json = company.get("metadata_json", "")
        if metadata_json:
            meta = json.loads(metadata_json) if isinstance(metadata_json, str) else metadata_json
            analysis_summary = meta.get("analysis_summary", "")
            top_actions = meta.get("top_actions", [])

        return _json_response(
            {
                "companyName": company.get("company_name", ""),
                "companyUrl": company.get("company_url", ""),
                "industry": company.get("industry", ""),
                "overallRiskScore": company.get("overall_risk_score"),
                "riskTier": company.get("risk_tier"),
                "analysisSummary": analysis_summary,
                "topActions": top_actions,
                "riskScores": risk_scores,
                "opportunities": opportunities,
            }
        )

    # ── DELETE /api/analysis/{id} ────────────────────────────────────

    def _handle_delete_analysis(
        self,
        _event: dict[str, Any],
        authentication: AuthContext,
        analysis_id: str,
    ) -> LambdaResponse:
        company_repo = self._storage.create_company_repository()
        company = company_repo.get_by_id(analysis_id)
        if not company or company.get("org_id") != authentication.org_id:
            return _error("Not found", 404)

        assessment_repo = self._storage.create_assessment_repository()
        assessments = assessment_repo.find_by_company(analysis_id)
        for assessment in assessments:
            assessment_repo.delete(assessment["id"])

        company_repo.delete(analysis_id)

        scan_id = company.get("scan_id", "")
        if scan_id:
            scan_repo = self._storage.create_scan_repository()
            remaining = scan_repo.get_scan_companies(scan_id)
            if not remaining:
                scan_repo.delete(scan_id)

        return _json_response({"ok": True})

    # ── GET /api/analyses ────────────────────────────────────────────

    def _handle_list_analyses(
        self,
        _event: dict[str, Any],
        authentication: AuthContext,
    ) -> LambdaResponse:
        company_repo = self._storage.create_company_repository()
        companies = company_repo.find_by_org(authentication.org_id)
        return _json_response(
            {"analyses": [_build_company_summary(c) for c in companies]}
        )

    # ── POST /api/auth/login ─────────────────────────────────────────

    def _handle_login(self, event: dict[str, Any]) -> LambdaResponse:
        body = json.loads(event.get("body") or "{}")
        email = body.get("email", "")
        password = body.get("password", "")

        if not email or not password:
            return _error("Email and password required")

        user_repo = self._storage.create_user_repository()
        user_info = user_repo.verify_password(email, password)
        if not user_info:
            return _error("Invalid credentials", 401)

        return _json_response({"success": True, "user": user_info})

    # ── GET /api/dashboard ─────────────────────────────────────────

    def _handle_dashboard(
        self,
        _event: dict[str, Any],
        authentication: AuthContext,
    ) -> LambdaResponse:
        company_repo = self._storage.create_company_repository()
        scan_repo = self._storage.create_scan_repository()

        companies = company_repo.find_by_org(authentication.org_id)
        analyzed = [c for c in companies if c.get("overall_risk_score") is not None]

        total_analyses = len(analyzed)
        avg_risk_score = (
            round(sum(float(c["overall_risk_score"]) for c in analyzed) / total_analyses, 1)
            if total_analyses
            else 0
        )
        critical_count = sum(1 for c in analyzed if c.get("risk_tier") == "critical")

        all_scans = scan_repo.find_recent_by_org(authentication.org_id, limit=None)
        scan_count = len(all_scans)
        recent_scans = all_scans[:10]

        scan_type_map = {s["id"]: s.get("type", "") for s in all_scans}

        analyzed.sort(key=lambda c: c.get("analyzed_at", ""), reverse=True)
        recent_analyses = [
            {
                "id": c.get("id"),
                "companyName": c.get("company_name", ""),
                "companyUrl": c.get("company_url", ""),
                "overallRiskScore": c.get("overall_risk_score"),
                "riskTier": c.get("risk_tier"),
                "analyzedAt": c.get("analyzed_at"),
                "scanType": scan_type_map.get(c.get("scan_id", ""), ""),
            }
            for c in analyzed[:8]
        ]

        recent_scan_list = [
            {
                "id": s.get("id"),
                "sourceUrl": s.get("source_url", ""),
                "type": s.get("type", ""),
                "status": s.get("status", ""),
                "progress": s.get("progress", 0),
                "completedCount": len(scan_repo.get_scan_companies(s["id"])),
                "createdAt": s.get("created_at", ""),
            }
            for s in recent_scans
        ]

        return _json_response(
            {
                "totalAnalyses": total_analyses,
                "avgRiskScore": avg_risk_score,
                "criticalCount": critical_count,
                "scanCount": scan_count,
                "recentAnalyses": recent_analyses,
                "recentScans": recent_scan_list,
            }
        )

    # ── POST /api/auth/register ──────────────────────────────────────

    def _handle_register(self, event: dict[str, Any]) -> LambdaResponse:
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

        if user_repo.has_email(email):
            return _error("Email already registered")

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

        return _json_response({"success": True})

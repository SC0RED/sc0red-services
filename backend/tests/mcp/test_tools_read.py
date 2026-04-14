"""Tests for MCP read tools — mocks DynamoDB repositories."""

from unittest.mock import MagicMock

import pytest
from mcp.server.fastmcp import FastMCP

from src.mcp.auth_context import AuthenticatedUser, set_authenticated_user


@pytest.fixture(autouse=True)
def _set_auth_context():
    set_authenticated_user(
        AuthenticatedUser(
            user_id="test-user", org_id="test-org", email="test@test.com",
            role="admin", client_id="test-client", scopes=["read", "write"],
        )
    )


def _make_storage():
    """Create a mock DynamoDBStorageProvider with mock repositories."""
    storage = MagicMock()
    company_repo = MagicMock()
    assessment_repo = MagicMock()
    scan_repo = MagicMock()
    user_repo = MagicMock()
    invitation_repo = MagicMock()

    storage.create_company_repository.return_value = company_repo
    storage.create_assessment_repository.return_value = assessment_repo
    storage.create_scan_repository.return_value = scan_repo
    storage.create_user_repository.return_value = user_repo
    storage.create_invitation_repository.return_value = invitation_repo

    company_repo.find_by_org.return_value = ([], None)
    company_repo.get_by_id.return_value = None
    company_repo.get_by_ids.return_value = []
    scan_repo.find_recent_by_org.return_value = []
    scan_repo.get_by_id.return_value = None
    scan_repo.get_scan_companies.return_value = []
    user_repo.find_by_org.return_value = []
    invitation_repo.find_by_org.return_value = []
    assessment_repo.find_by_company.return_value = []

    return storage, company_repo, assessment_repo, scan_repo, user_repo, invitation_repo


def _make_server(storage):
    server = FastMCP("test")
    from src.mcp.tools_read import register_read_tools
    from src.mcp.tools_search import register_search_tools
    register_read_tools(server, storage)
    register_search_tools(server, storage)
    return server


def _make_company(**overrides):
    defaults = {
        "id": "c1", "company_name": "Acme", "company_url": "https://acme.com",
        "industry": "Tech", "overall_risk_score": 5.0, "risk_tier": "moderate",
        "analyzed_at": "2026-01-01", "org_id": "test-org", "scan_id": "s1",
        "metadata_json": '{"analysis_summary": "Good company", "top_actions": ["Act 1"]}',
    }
    defaults.update(overrides)
    return defaults


def _setup_assessment(assessment_repo, **overrides):
    """Configure assessment mock with defaults."""
    defaults = {
        "find_by_company": [{"id": "a1", "created_at": "2026-01-01"}],
        "get_risk_scores": [{"name": "Automation", "score": 5}],
        "get_opportunities": [],
        "get_ebitda_tree": None,
        "get_value_chain": None,
        "get_documents": [],
    }
    defaults.update(overrides)
    assessment_repo.find_by_company.return_value = defaults["find_by_company"]
    assessment_repo.get_risk_scores.return_value = defaults["get_risk_scores"]
    assessment_repo.get_opportunities.return_value = defaults["get_opportunities"]
    assessment_repo.get_ebitda_tree.return_value = defaults["get_ebitda_tree"]
    assessment_repo.get_value_chain.return_value = defaults["get_value_chain"]
    assessment_repo.get_documents.return_value = defaults["get_documents"]


class TestGetDashboard:
    @pytest.mark.asyncio
    async def test_returns_stats(self):
        storage, company_repo, _, scan_repo, *_ = _make_storage()
        company_repo.find_by_org.return_value = ([_make_company()], None)
        scan_repo.find_recent_by_org.return_value = [{"id": "s1"}]
        server = _make_server(storage)
        text = (await server.call_tool("get_dashboard", {}))[0][0].text
        assert "Companies Analyzed: 1" in text
        assert "5.0/10" in text

    @pytest.mark.asyncio
    async def test_empty(self):
        storage, *_ = _make_storage()
        server = _make_server(storage)
        text = (await server.call_tool("get_dashboard", {}))[0][0].text
        assert "Companies Analyzed: 0" in text


class TestListAnalyses:
    @pytest.mark.asyncio
    async def test_returns_list(self):
        storage, company_repo, *_ = _make_storage()
        company_repo.find_by_org.return_value = ([_make_company(), _make_company(id="c2", company_name="Beta")], None)
        server = _make_server(storage)
        text = (await server.call_tool("list_analyses", {}))[0][0].text
        assert "2 Analyses" in text

    @pytest.mark.asyncio
    async def test_empty(self):
        storage, *_ = _make_storage()
        server = _make_server(storage)
        text = (await server.call_tool("list_analyses", {}))[0][0].text
        assert "No analyses found" in text


class TestGetAnalysis:
    @pytest.mark.asyncio
    async def test_full(self):
        storage, company_repo, assessment_repo, *_ = _make_storage()
        company_repo.get_by_id.return_value = _make_company()
        _setup_assessment(assessment_repo,
            get_opportunities=[{"title": "AI Sales", "value_lever": "revenue", "impact_rating": "High"}],
            get_ebitda_tree={"revenueEstimate": "$5B", "ebitdaEstimate": "$1B", "treeData": []},
            get_value_chain={"summary": "Strong", "steps": [{"name": "Sales", "category": "primary"}]},
        )
        server = _make_server(storage)
        text = (await server.call_tool("get_analysis", {"analysis_id": "c1"}))[0][0].text
        assert "Acme" in text
        assert "Automation" in text
        assert "AI Sales" in text
        assert "EBITDA" in text
        assert "Value Chain" in text

    @pytest.mark.asyncio
    async def test_not_found(self):
        storage, *_ = _make_storage()
        server = _make_server(storage)
        text = (await server.call_tool("get_analysis", {"analysis_id": "x"}))[0][0].text
        assert "not found" in text

    @pytest.mark.asyncio
    async def test_cross_org_denied(self):
        storage, company_repo, *_ = _make_storage()
        company_repo.get_by_id.return_value = _make_company(org_id="other-org")
        server = _make_server(storage)
        text = (await server.call_tool("get_analysis", {"analysis_id": "c1"}))[0][0].text
        assert "not found" in text

    @pytest.mark.asyncio
    async def test_with_documents(self):
        storage, company_repo, assessment_repo, *_ = _make_storage()
        company_repo.get_by_id.return_value = _make_company()
        _setup_assessment(assessment_repo,
            get_documents=[{"filename": "memo.pdf", "fileType": "pdf"}],
        )
        server = _make_server(storage)
        text = (await server.call_tool("get_analysis", {"analysis_id": "c1"}))[0][0].text
        assert "memo.pdf" in text
        assert "Documents" in text

    @pytest.mark.asyncio
    async def test_minimal(self):
        storage, company_repo, *_ = _make_storage()
        company_repo.get_by_id.return_value = _make_company(metadata_json="")
        server = _make_server(storage)
        text = (await server.call_tool("get_analysis", {"analysis_id": "c1"}))[0][0].text
        assert "Acme" in text


class TestGetRiskBreakdown:
    @pytest.mark.asyncio
    async def test_returns(self):
        storage, company_repo, assessment_repo, *_ = _make_storage()
        company_repo.get_by_id.return_value = _make_company()
        _setup_assessment(assessment_repo, get_risk_scores=[{"name": "Automation", "score": 7}])
        server = _make_server(storage)
        text = (await server.call_tool("get_risk_breakdown", {"analysis_id": "c1"}))[0][0].text
        assert "Automation" in text

    @pytest.mark.asyncio
    async def test_no_scores(self):
        storage, company_repo, *_ = _make_storage()
        company_repo.get_by_id.return_value = _make_company()
        server = _make_server(storage)
        text = (await server.call_tool("get_risk_breakdown", {"analysis_id": "c1"}))[0][0].text
        assert "No risk scores" in text


class TestGetOpportunities:
    @pytest.mark.asyncio
    async def test_returns(self):
        storage, company_repo, assessment_repo, *_ = _make_storage()
        company_repo.get_by_id.return_value = _make_company()
        _setup_assessment(assessment_repo, get_opportunities=[{"title": "AI X", "value_lever": "cost", "impact_rating": "High", "description": "D"}])
        server = _make_server(storage)
        text = (await server.call_tool("get_opportunities", {"analysis_id": "c1"}))[0][0].text
        assert "AI X" in text

    @pytest.mark.asyncio
    async def test_not_found(self):
        storage, *_ = _make_storage()
        server = _make_server(storage)
        text = (await server.call_tool("get_opportunities", {"analysis_id": "x"}))[0][0].text
        assert "not found" in text

    @pytest.mark.asyncio
    async def test_no_opps(self):
        storage, company_repo, *_ = _make_storage()
        company_repo.get_by_id.return_value = _make_company()
        server = _make_server(storage)
        text = (await server.call_tool("get_opportunities", {"analysis_id": "c1"}))[0][0].text
        assert "No opportunities" in text


class TestGetEbitdaTree:
    @pytest.mark.asyncio
    async def test_returns(self):
        storage, company_repo, assessment_repo, *_ = _make_storage()
        company_repo.get_by_id.return_value = _make_company()
        _setup_assessment(assessment_repo, get_ebitda_tree={"revenueEstimate": "$5B", "ebitdaEstimate": "$1B", "treeData": [{"label": "R", "value": "$5B"}]})
        server = _make_server(storage)
        text = (await server.call_tool("get_ebitda_tree", {"analysis_id": "c1"}))[0][0].text
        assert "$5B" in text

    @pytest.mark.asyncio
    async def test_no_tree(self):
        storage, company_repo, *_ = _make_storage()
        company_repo.get_by_id.return_value = _make_company()
        server = _make_server(storage)
        text = (await server.call_tool("get_ebitda_tree", {"analysis_id": "c1"}))[0][0].text
        assert "No EBITDA tree" in text


class TestGetValueChain:
    @pytest.mark.asyncio
    async def test_returns(self):
        storage, company_repo, assessment_repo, *_ = _make_storage()
        company_repo.get_by_id.return_value = _make_company()
        _setup_assessment(assessment_repo, get_value_chain={"summary": "Strong", "steps": [{"name": "Logistics", "category": "primary"}]})
        server = _make_server(storage)
        text = (await server.call_tool("get_value_chain", {"analysis_id": "c1"}))[0][0].text
        assert "Logistics" in text

    @pytest.mark.asyncio
    async def test_no_chain(self):
        storage, company_repo, *_ = _make_storage()
        company_repo.get_by_id.return_value = _make_company()
        server = _make_server(storage)
        text = (await server.call_tool("get_value_chain", {"analysis_id": "c1"}))[0][0].text
        assert "No value chain" in text

    @pytest.mark.asyncio
    async def test_chain_no_summary(self):
        storage, company_repo, assessment_repo, *_ = _make_storage()
        company_repo.get_by_id.return_value = _make_company()
        _setup_assessment(assessment_repo, get_value_chain={"steps": [{"name": "Ops", "category": "support"}]})
        server = _make_server(storage)
        text = (await server.call_tool("get_value_chain", {"analysis_id": "c1"}))[0][0].text
        assert "Ops" in text


class TestGetScan:
    @pytest.mark.asyncio
    async def test_returns(self):
        storage, company_repo, _, scan_repo, *_ = _make_storage()
        scan_repo.get_by_id.return_value = {"id": "s1", "status": "complete", "type": "single", "progress": 100, "org_id": "test-org"}
        scan_repo.get_scan_companies.return_value = [{"company_id": "c1"}]
        company_repo.get_by_ids.return_value = [_make_company()]
        server = _make_server(storage)
        text = (await server.call_tool("get_scan", {"scan_id": "s1"}))[0][0].text
        assert "complete" in text
        assert "Acme" in text

    @pytest.mark.asyncio
    async def test_scan_no_companies(self):
        storage, _, _, scan_repo, *_ = _make_storage()
        scan_repo.get_by_id.return_value = {"id": "s1", "status": "running", "type": "portfolio", "progress": 50, "org_id": "test-org"}
        server = _make_server(storage)
        text = (await server.call_tool("get_scan", {"scan_id": "s1"}))[0][0].text
        assert "running" in text

    @pytest.mark.asyncio
    async def test_not_found(self):
        storage, *_ = _make_storage()
        server = _make_server(storage)
        text = (await server.call_tool("get_scan", {"scan_id": "x"}))[0][0].text
        assert "not found" in text


class TestListTeamMembers:
    @pytest.mark.asyncio
    async def test_returns(self):
        storage, _, _, _, user_repo, invitation_repo = _make_storage()
        user_repo.find_by_org.return_value = [{"name": "Alice", "email": "a@t.com", "role": "admin"}]
        invitation_repo.find_by_org.return_value = [{"email": "bob@t.com", "role": "analyst"}]
        server = _make_server(storage)
        text = (await server.call_tool("list_team_members", {}))[0][0].text
        assert "Alice" in text
        assert "bob@t.com" in text


class TestListDocuments:
    @pytest.mark.asyncio
    async def test_returns(self):
        storage, company_repo, assessment_repo, *_ = _make_storage()
        company_repo.get_by_id.return_value = _make_company()
        _setup_assessment(assessment_repo, get_documents=[{"id": "d1", "filename": "report.pdf", "fileType": "pdf", "charCount": 5000}])
        server = _make_server(storage)
        text = (await server.call_tool("list_documents", {"analysis_id": "c1"}))[0][0].text
        assert "report.pdf" in text

    @pytest.mark.asyncio
    async def test_no_docs(self):
        storage, company_repo, *_ = _make_storage()
        company_repo.get_by_id.return_value = _make_company()
        server = _make_server(storage)
        text = (await server.call_tool("list_documents", {"analysis_id": "c1"}))[0][0].text
        assert "No documents" in text


class TestSearchAnalyses:
    @pytest.mark.asyncio
    async def test_by_name(self):
        storage, company_repo, *_ = _make_storage()
        company_repo.find_by_org.return_value = ([_make_company(company_name="Stripe Inc"), _make_company(id="c2", company_name="Plaid")], None)
        server = _make_server(storage)
        text = (await server.call_tool("search_analyses", {"query": "stripe"}))[0][0].text
        assert "Stripe" in text
        assert "Plaid" not in text

    @pytest.mark.asyncio
    async def test_no_results(self):
        storage, *_ = _make_storage()
        server = _make_server(storage)
        text = (await server.call_tool("search_analyses", {"query": "x"}))[0][0].text
        assert "No analyses matching" in text


class TestCompareAnalyses:
    @pytest.mark.asyncio
    async def test_compare_two(self):
        storage, company_repo, assessment_repo, *_ = _make_storage()
        company_repo.get_by_id.side_effect = lambda cid: (
            _make_company(company_name="Stripe", overall_risk_score=4.5) if cid == "c1"
            else _make_company(id="c2", company_name="Plaid", overall_risk_score=6.0, risk_tier="high")
        )
        _setup_assessment(assessment_repo)
        server = _make_server(storage)
        text = (await server.call_tool("compare_analyses", {"analysis_ids": ["c1", "c2"]}))[0][0].text
        assert "Stripe" in text
        assert "Plaid" in text
        assert "Comparison" in text

    @pytest.mark.asyncio
    async def test_too_few(self):
        storage, *_ = _make_storage()
        server = _make_server(storage)
        text = (await server.call_tool("compare_analyses", {"analysis_ids": ["c1"]}))[0][0].text
        assert "at least 2" in text

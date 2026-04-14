"""Tests for MCP read tools."""

import os
from unittest.mock import AsyncMock, patch

import pytest

# Set env vars before importing tools
os.environ["MCP_DEV_USER_ID"] = "test-user"
os.environ["MCP_DEV_ORG_ID"] = "test-org"
os.environ["MCP_DEV_EMAIL"] = "test@test.com"
os.environ["MCP_DEV_ROLE"] = "admin"

from mcp.server.fastmcp import FastMCP  # noqa: E402


@pytest.fixture
def mcp_server():
    server = FastMCP("test")
    from src.mcp.tools_read import register_read_tools
    from src.mcp.tools_search import register_search_tools

    register_read_tools(server)
    register_search_tools(server)
    return server


class _mock_backend:
    """Context manager that mocks call_backend in both tool modules."""

    def __init__(self, return_value):
        self._return_value = return_value
        self._patches = []

    def __enter__(self):
        for module in ("src.mcp.tools_read", "src.mcp.tools_search"):
            p = patch(f"{module}.call_backend", new_callable=AsyncMock, return_value=self._return_value)
            p.start()
            self._patches.append(p)
        return self

    def __exit__(self, *args):
        for p in self._patches:
            p.stop()


class TestGetDashboard:
    @pytest.mark.asyncio
    async def test_returns_formatted_dashboard(self, mcp_server):
        mock_data = {
            "totalAnalyses": 5,
            "avgRiskScore": 4.5,
            "criticalCount": 1,
            "scanCount": 3,
            "recentAnalyses": [
                {"id": "a1", "companyName": "Stripe", "overallRiskScore": 4.5, "riskTier": "moderate"},
            ],
            "recentScans": [],
        }
        with _mock_backend(mock_data):
            result = await mcp_server.call_tool("get_dashboard", {})
            text = result[0][0].text
            assert "Portfolio Dashboard" in text
            assert "Companies Analyzed: 5" in text
            assert "Stripe" in text


class TestListAnalyses:
    @pytest.mark.asyncio
    async def test_returns_analyses_list(self, mcp_server):
        mock_data = {
            "analyses": [
                {"id": "a1", "companyName": "Acme", "overallRiskScore": 6.0, "riskTier": "high"},
                {"id": "a2", "companyName": "Beta", "overallRiskScore": 3.0, "riskTier": "low"},
            ]
        }
        with _mock_backend(mock_data):
            result = await mcp_server.call_tool("list_analyses", {})
            text = result[0][0].text
            assert "2 Analyses" in text
            assert "Acme" in text
            assert "Beta" in text

    @pytest.mark.asyncio
    async def test_empty_analyses(self, mcp_server):
        with _mock_backend({"analyses": []}):
            result = await mcp_server.call_tool("list_analyses", {})
            text = result[0][0].text
            assert "No analyses found" in text


class TestGetAnalysis:
    @pytest.mark.asyncio
    async def test_returns_minimal_analysis(self, mcp_server):
        mock_data = {
            "companyName": "MinCo",
            "companyUrl": "",
            "industry": "",
            "overallRiskScore": 3.0,
            "riskTier": "low",
        }
        with _mock_backend(mock_data):
            result = await mcp_server.call_tool("get_analysis", {"analysis_id": "a1"})
            text = result[0][0].text
            assert "MinCo" in text
            assert "3.0/10" in text

    @pytest.mark.asyncio
    async def test_returns_full_analysis(self, mcp_server):
        mock_data = {
            "companyName": "Stripe",
            "companyUrl": "https://stripe.com",
            "industry": "Fintech",
            "overallRiskScore": 4.5,
            "riskTier": "moderate",
            "analysisSummary": "Payment leader",
            "topActions": ["Action 1"],
            "riskScores": [{"name": "Automation", "score": 5}],
            "opportunities": [{"title": "AI Checkout", "value_lever": "revenue", "impact_rating": "High"}],
            "ebitdaTree": {"revenueEstimate": "$10B", "ebitdaEstimate": "$3B", "treeData": []},
            "valueChain": {"summary": "Strong chain", "steps": [{"name": "Sales", "category": "primary"}]},
            "documents": [],
        }
        with _mock_backend(mock_data):
            result = await mcp_server.call_tool("get_analysis", {"analysis_id": "a1"})
            text = result[0][0].text
            assert "Stripe" in text
            assert "4.5/10" in text
            assert "Automation" in text
            assert "AI Checkout" in text
            assert "EBITDA" in text
            assert "Value Chain" in text


class TestGetRiskBreakdown:
    @pytest.mark.asyncio
    async def test_returns_risk_dimensions(self, mcp_server):
        mock_data = {
            "companyName": "Acme",
            "overallRiskScore": 6.0,
            "riskTier": "high",
            "riskScores": [
                {"name": "Automation", "score": 7},
                {"name": "Data Privacy", "score": 5},
            ],
        }
        with _mock_backend(mock_data):
            result = await mcp_server.call_tool("get_risk_breakdown", {"analysis_id": "a1"})
            text = result[0][0].text
            assert "Automation" in text
            assert "Data Privacy" in text

    @pytest.mark.asyncio
    async def test_no_risk_scores(self, mcp_server):
        with _mock_backend({"companyName": "X", "riskScores": []}):
            result = await mcp_server.call_tool("get_risk_breakdown", {"analysis_id": "a1"})
            assert "No risk scores" in result[0][0].text


class TestGetOpportunitiesEmpty:
    @pytest.mark.asyncio
    async def test_no_opportunities(self, mcp_server):
        with _mock_backend({"companyName": "X", "opportunities": []}):
            result = await mcp_server.call_tool("get_opportunities", {"analysis_id": "a1"})
            assert "No opportunities" in result[0][0].text


class TestGetOpportunities:
    @pytest.mark.asyncio
    async def test_returns_opportunities(self, mcp_server):
        mock_data = {
            "companyName": "Acme",
            "opportunities": [
                {"title": "AI Sales", "value_lever": "revenue", "impact_rating": "High", "description": "Boost sales"},
            ],
        }
        with _mock_backend(mock_data):
            result = await mcp_server.call_tool("get_opportunities", {"analysis_id": "a1"})
            text = result[0][0].text
            assert "AI Sales" in text
            assert "revenue" in text


class TestGetEbitdaTree:
    @pytest.mark.asyncio
    async def test_returns_ebitda(self, mcp_server):
        mock_data = {
            "companyName": "Acme",
            "ebitdaTree": {
                "revenueEstimate": "$5B",
                "ebitdaEstimate": "$1B",
                "treeData": [{"label": "Revenue", "value": "$5B"}],
            },
        }
        with _mock_backend(mock_data):
            result = await mcp_server.call_tool("get_ebitda_tree", {"analysis_id": "a1"})
            text = result[0][0].text
            assert "$5B" in text
            assert "EBITDA" in text

    @pytest.mark.asyncio
    async def test_no_ebitda(self, mcp_server):
        with _mock_backend({"companyName": "X", "ebitdaTree": None}):
            result = await mcp_server.call_tool("get_ebitda_tree", {"analysis_id": "a1"})
            assert "No EBITDA tree" in result[0][0].text


class TestGetValueChain:
    @pytest.mark.asyncio
    async def test_returns_value_chain(self, mcp_server):
        mock_data = {
            "companyName": "Acme",
            "valueChain": {
                "summary": "Strong operations",
                "steps": [{"name": "Logistics", "category": "primary", "description": "Fast delivery"}],
            },
        }
        with _mock_backend(mock_data):
            result = await mcp_server.call_tool("get_value_chain", {"analysis_id": "a1"})
            text = result[0][0].text
            assert "Logistics" in text
            assert "Strong operations" in text


class TestGetValueChainMinimal:
    @pytest.mark.asyncio
    async def test_no_value_chain(self, mcp_server):
        with _mock_backend({"companyName": "X", "valueChain": None}):
            result = await mcp_server.call_tool("get_value_chain", {"analysis_id": "a1"})
            assert "No value chain" in result[0][0].text

    @pytest.mark.asyncio
    async def test_value_chain_no_summary(self, mcp_server):
        mock_data = {
            "companyName": "Y",
            "valueChain": {
                "steps": [{"name": "Ops", "category": "support"}],
            },
        }
        with _mock_backend(mock_data):
            result = await mcp_server.call_tool("get_value_chain", {"analysis_id": "a1"})
            text = result[0][0].text
            assert "Ops" in text


class TestGetScan:
    @pytest.mark.asyncio
    async def test_returns_scan_details(self, mcp_server):
        mock_data = {
            "status": "complete",
            "type": "portfolio",
            "progress": 100,
            "analyses": [{"id": "a1", "companyName": "Stripe", "overallRiskScore": 4.5}],
        }
        with _mock_backend(mock_data):
            result = await mcp_server.call_tool("get_scan", {"scan_id": "s1"})
            text = result[0][0].text
            assert "complete" in text
            assert "Stripe" in text


class TestListTeamMembers:
    @pytest.mark.asyncio
    async def test_returns_members(self, mcp_server):
        mock_data = {
            "members": [{"name": "Alice", "email": "a@t.com", "role": "admin"}],
            "pendingInvitations": [{"email": "bob@t.com", "role": "analyst"}],
        }
        with _mock_backend(mock_data):
            result = await mcp_server.call_tool("list_team_members", {})
            text = result[0][0].text
            assert "Alice" in text
            assert "bob@t.com" in text


class TestListDocuments:
    @pytest.mark.asyncio
    async def test_returns_documents(self, mcp_server):
        mock_data = {
            "companyName": "Acme",
            "documents": [{"id": "d1", "filename": "report.pdf", "fileType": "pdf", "charCount": 5000}],
        }
        with _mock_backend(mock_data):
            result = await mcp_server.call_tool("list_documents", {"analysis_id": "a1"})
            text = result[0][0].text
            assert "report.pdf" in text

    @pytest.mark.asyncio
    async def test_no_documents(self, mcp_server):
        with _mock_backend({"companyName": "X", "documents": []}):
            result = await mcp_server.call_tool("list_documents", {"analysis_id": "a1"})
            assert "No documents" in result[0][0].text


class TestSearchAnalyses:
    @pytest.mark.asyncio
    async def test_search_by_name(self, mcp_server):
        mock_data = {
            "analyses": [
                {"id": "a1", "companyName": "Stripe Inc", "companyUrl": "", "industry": "Fintech"},
                {"id": "a2", "companyName": "Plaid", "companyUrl": "", "industry": "Fintech"},
            ]
        }
        with _mock_backend(mock_data):
            result = await mcp_server.call_tool("search_analyses", {"query": "stripe"})
            text = result[0][0].text
            assert "Stripe" in text
            assert "Plaid" not in text

    @pytest.mark.asyncio
    async def test_no_results(self, mcp_server):
        with _mock_backend({"analyses": []}):
            result = await mcp_server.call_tool("search_analyses", {"query": "nonexistent"})
            assert "No analyses matching" in result[0][0].text


class TestCompareAnalyses:
    @pytest.mark.asyncio
    async def test_compare_two(self, mcp_server):
        call_count = 0

        async def mock_call(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {
                    "companyName": "Stripe",
                    "overallRiskScore": 4.5,
                    "riskTier": "moderate",
                    "industry": "Fintech",
                    "opportunities": [{"title": "X"}],
                    "riskScores": [{"name": "Automation", "score": 5}],
                }
            return {
                "companyName": "Plaid",
                "overallRiskScore": 6.0,
                "riskTier": "high",
                "industry": "Fintech",
                "opportunities": [],
                "riskScores": [{"name": "Automation", "score": 7}],
            }

        with patch("src.mcp.tools_search.call_backend", side_effect=mock_call):
            result = await mcp_server.call_tool("compare_analyses", {"analysis_ids": ["a1", "a2"]})
            text = result[0][0].text
            assert "Stripe" in text
            assert "Plaid" in text
            assert "Comparison" in text

    @pytest.mark.asyncio
    async def test_too_few_ids(self, mcp_server):
        result = await mcp_server.call_tool("compare_analyses", {"analysis_ids": ["a1"]})
        assert "at least 2" in result[0][0].text

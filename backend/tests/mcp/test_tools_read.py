"""Tests for MCP read tools — mocks DynamoDB repositories."""

from unittest.mock import MagicMock

import pytest
from mcp.server.fastmcp import FastMCP

from src.mcp.auth_context import AuthenticatedUser, set_authenticated_user


@pytest.fixture(autouse=True)
def _set_auth_context():
    set_authenticated_user(
        AuthenticatedUser(
            user_id="test-user",
            org_id="test-org",
            email="test@test.com",
            role="admin",
            client_id="test-client",
            scopes=["read", "write"],
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
        "id": "c1",
        "company_name": "Acme",
        "company_url": "https://acme.com",
        "industry": "Tech",
        "overall_risk_score": 5.0,
        "risk_tier": "moderate",
        "analyzed_at": "2026-01-01",
        "org_id": "test-org",
        "scan_id": "s1",
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
        company_repo.find_by_org.return_value = (
            [_make_company(), _make_company(id="c2", company_name="Beta")],
            None,
        )
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
        _setup_assessment(
            assessment_repo,
            get_opportunities=[
                {"title": "AI Sales", "value_lever": "revenue", "impact_rating": "High"}
            ],
            get_ebitda_tree={"revenueEstimate": "$5B", "ebitdaEstimate": "$1B", "treeData": []},
            get_value_chain={
                "summary": "Strong",
                "steps": [{"label": "Sales", "category": "primary"}],
            },
        )
        server = _make_server(storage)
        text = (await server.call_tool("get_analysis", {"analysis_id": "c1"}))[0][0].text
        assert "Acme" in text
        assert "Automation" in text
        assert "AI Sales" in text
        assert "EBITDA" in text
        assert "Value Chain" in text

    @pytest.mark.asyncio
    async def test_ungrounded_ebitda_shows_reason_not_empty_header(self):
        storage, company_repo, assessment_repo, *_ = _make_storage()
        company_repo.get_by_id.return_value = _make_company()
        _setup_assessment(
            assessment_repo,
            get_ebitda_tree={
                "treeData": [],
                "grounded": False,
                "insufficientDataReason": "Could not establish a revenue model.",
            },
        )
        server = _make_server(storage)
        text = (await server.call_tool("get_analysis", {"analysis_id": "c1"}))[0][0].text
        assert "EBITDA Impact Model" in text
        assert "Could not establish a revenue model." in text

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
        _setup_assessment(
            assessment_repo,
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
        _setup_assessment(
            assessment_repo,
            get_opportunities=[
                {
                    "title": "AI X",
                    "value_lever": "cost",
                    "impact_rating": "High",
                    "description": "D",
                }
            ],
        )
        server = _make_server(storage)
        text = (await server.call_tool("get_opportunities", {"analysis_id": "c1"}))[0][0].text
        assert "AI X" in text

    @pytest.mark.asyncio
    async def test_surfaces_full_opportunity_contract(self):
        # Drift guard: the formatter must surface strategic_category, timeline,
        # investment (range + numeric estimate), ROI (narrative + numeric %),
        # and implementation_steps — not just title/lever/impact (Bug E).
        storage, company_repo, assessment_repo, *_ = _make_storage()
        company_repo.get_by_id.return_value = _make_company()
        _setup_assessment(
            assessment_repo,
            get_opportunities=[
                {
                    "title": "Automate support",
                    "strategic_category": "Cost Side",
                    "impact_rating": "High",
                    "value_lever": "Cost Side",
                    "timeline": "Quick Win (1-3 months)",
                    "investment_range": "$100K-$500K",
                    "investment_value_usd": 300000,
                    "roi_estimate": "30% deflection",
                    "roi_estimate_pct": 30,
                    "implementation_steps": ["Pilot a bot", "Roll out"],
                }
            ],
        )
        server = _make_server(storage)
        text = (await server.call_tool("get_opportunities", {"analysis_id": "c1"}))[0][0].text
        assert "Category: Cost Side" in text
        assert "Timeline: Quick Win (1-3 months)" in text
        assert "$100K-$500K" in text
        assert "$300,000" in text
        assert "30% deflection" in text
        assert "30%)" in text
        assert "1. Pilot a bot" in text
        assert "2. Roll out" in text

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
        _setup_assessment(
            assessment_repo,
            get_ebitda_tree={
                "revenueEstimate": "$5B",
                "ebitdaEstimate": "$1B",
                # Each node is shaped per `EbitdaNode.model_dump()` — snake_case
                # `value_range`, NOT `value`. The legacy fixture used `value`
                # which masked a bug where the tool always rendered blank values.
                "treeData": [{"label": "Revenue", "value_range": "$5B"}],
            },
        )
        server = _make_server(storage)
        text = (await server.call_tool("get_ebitda_tree", {"analysis_id": "c1"}))[0][0].text
        assert "Revenue: $5B" in text

    @pytest.mark.asyncio
    async def test_renders_value_range_field_not_legacy_value(self):
        """Regression guard: persisted nodes use snake_case `value_range`, not `value`.

        Reading `value` (which doesn't exist on the dumped shape) made every
        node render as `- {label}: ` with an empty trailing string. This test
        fails the moment that regression returns.
        """
        storage, company_repo, assessment_repo, *_ = _make_storage()
        company_repo.get_by_id.return_value = _make_company()
        _setup_assessment(
            assessment_repo,
            get_ebitda_tree={
                "revenueEstimate": "$10M-$15M",
                "ebitdaEstimate": "$1M-$3M",
                "treeData": [
                    {"label": "Subscriptions", "value_range": "$8M-$12M"},
                    {"label": "Cloud Infrastructure", "value_range": "$1M-$2M"},
                ],
            },
        )
        server = _make_server(storage)
        text = (await server.call_tool("get_ebitda_tree", {"analysis_id": "c1"}))[0][0].text
        assert "Subscriptions: $8M-$12M" in text
        assert "Cloud Infrastructure: $1M-$2M" in text
        # Negative regression: no node line should end on an empty trailing colon-space.
        for line in text.splitlines():
            if line.startswith("- "):
                assert not line.endswith(": "), f"empty value rendered for line: {line!r}"

    @pytest.mark.asyncio
    async def test_no_tree(self):
        storage, company_repo, *_ = _make_storage()
        company_repo.get_by_id.return_value = _make_company()
        server = _make_server(storage)
        text = (await server.call_tool("get_ebitda_tree", {"analysis_id": "c1"}))[0][0].text
        assert "No EBITDA tree" in text

    @pytest.mark.asyncio
    async def test_ungrounded_surfaces_reason_not_na(self):
        """Fact-vs-forecast: an ungrounded tree returns the honest reason, not
        empty 'N/A' figures that read like a fabricated/missing model."""
        storage, company_repo, assessment_repo, *_ = _make_storage()
        company_repo.get_by_id.return_value = _make_company()
        _setup_assessment(
            assessment_repo,
            get_ebitda_tree={
                "treeData": [],
                "revenueEstimate": "",
                "ebitdaEstimate": "",
                "grounded": False,
                "insufficientDataReason": "Could not establish a revenue model.",
            },
        )
        server = _make_server(storage)
        text = (await server.call_tool("get_ebitda_tree", {"analysis_id": "c1"}))[0][0].text
        assert "Not available" in text
        assert "Could not establish a revenue model." in text
        assert "N/A" not in text

    @pytest.mark.asyncio
    async def test_tree_with_confidence_fields_does_not_break_tool(self):
        """Smoke test for the ebitda-tree-confidence capability: nodes carrying
        the additive confidence_level / confidence_basis fields must not break
        the existing MCP tool surface. The tool ignores unknown fields, so the
        new keys flow through the boundary harmlessly.
        """
        storage, company_repo, assessment_repo, *_ = _make_storage()
        company_repo.get_by_id.return_value = _make_company()
        _setup_assessment(
            assessment_repo,
            get_ebitda_tree={
                "revenueEstimate": "$5B",
                "ebitdaEstimate": "$1B",
                "treeData": [
                    {
                        "label": "Revenue",
                        "value_range": "$5B",
                        "confidence_level": "high",
                        "confidence_basis": (
                            "Revenue derived from a SaaS template (matched on business model) "
                            "applied to a known size bracket ('Mid-market 200-1000')."
                        ),
                    },
                ],
            },
        )
        server = _make_server(storage)
        text = (await server.call_tool("get_ebitda_tree", {"analysis_id": "c1"}))[0][0].text
        # Existing surface still renders label + value_range; the additive
        # confidence_* fields flow through harmlessly (the tool ignores them).
        assert "Revenue: $5B" in text

    @pytest.mark.asyncio
    async def test_node_links_resolve_to_opportunity_titles(self):
        # Bug E: a node's linked_opportunity_indices should render as the
        # opportunity titles, not raw indices.
        storage, company_repo, assessment_repo, *_ = _make_storage()
        company_repo.get_by_id.return_value = _make_company()
        _setup_assessment(
            assessment_repo,
            get_opportunities=[{"title": "Automate support"}, {"title": "Upsell engine"}],
            get_ebitda_tree={
                "revenueEstimate": "$5B",
                "ebitdaEstimate": "$1B",
                "treeData": [
                    {
                        "label": "Support Cost",
                        "value_range": "$2M",
                        "linked_opportunity_indices": [0],
                    },
                ],
            },
        )
        server = _make_server(storage)
        text = (await server.call_tool("get_ebitda_tree", {"analysis_id": "c1"}))[0][0].text
        assert "addresses: Automate support" in text


class TestGetValueChain:
    @pytest.mark.asyncio
    async def test_returns(self):
        storage, company_repo, assessment_repo, *_ = _make_storage()
        company_repo.get_by_id.return_value = _make_company()
        # Production steps are ValueChainStep.model_dump() — the activity name is
        # `label` (the formatter previously read `name` and rendered every step
        # as "?"; the fixture wrongly used `name` too, masking the bug).
        _setup_assessment(
            assessment_repo,
            get_value_chain={
                "summary": "Strong",
                "steps": [{"label": "Logistics", "category": "primary"}],
            },
        )
        server = _make_server(storage)
        text = (await server.call_tool("get_value_chain", {"analysis_id": "c1"}))[0][0].text
        assert "Logistics" in text

    @pytest.mark.asyncio
    async def test_surfaces_enriched_step_fields(self):
        # Bug E: surface risk areas, opportunity linkage (resolved to titles),
        # confidence, and the chain-level provenance basis.
        storage, company_repo, assessment_repo, *_ = _make_storage()
        company_repo.get_by_id.return_value = _make_company()
        _setup_assessment(
            assessment_repo,
            get_opportunities=[{"title": "Automate support"}, {"title": "Upsell engine"}],
            get_value_chain={
                "summary": "Strong",
                # camelCase: this is the container-level key the repo returns
                # (get_value_chain → "provenanceBasis"), unlike the snake_case
                # per-step keys below.
                "provenanceBasis": "Operating model researched for a SaaS company",
                "steps": [
                    {
                        "label": "Customer Service",
                        "category": "primary",
                        "description": "Support ops",
                        "risk_categories": ["automation", "data_ip"],
                        "opportunity_indices": [0],
                        "confidence_level": "high",
                        "confidence_basis": "Disclosed on the company site",
                    }
                ],
            },
        )
        server = _make_server(storage)
        text = (await server.call_tool("get_value_chain", {"analysis_id": "c1"}))[0][0].text
        assert "Customer Service" in text
        assert "Operating model researched for a SaaS company" in text
        assert "automation, data_ip" in text
        assert "Automate support" in text  # opportunity_indices[0] resolved to title
        assert "high — Disclosed on the company site" in text

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
        _setup_assessment(
            assessment_repo, get_value_chain={"steps": [{"label": "Ops", "category": "support"}]}
        )
        server = _make_server(storage)
        text = (await server.call_tool("get_value_chain", {"analysis_id": "c1"}))[0][0].text
        assert "Ops" in text

    @pytest.mark.asyncio
    async def test_ungrounded_surfaces_reason(self):
        """Fact-vs-forecast: an ungrounded value chain returns the honest reason
        rather than an empty (or fabricated) operating model."""
        storage, company_repo, assessment_repo, *_ = _make_storage()
        company_repo.get_by_id.return_value = _make_company()
        _setup_assessment(
            assessment_repo,
            get_value_chain={
                "steps": [],
                "summary": "",
                "grounded": False,
                "insufficientDataReason": "Could not determine how this business operates.",
            },
        )
        server = _make_server(storage)
        text = (await server.call_tool("get_value_chain", {"analysis_id": "c1"}))[0][0].text
        assert "Not available" in text
        assert "Could not determine how this business operates." in text


class TestGetScan:
    @pytest.mark.asyncio
    async def test_returns(self):
        storage, company_repo, _, scan_repo, *_ = _make_storage()
        scan_repo.get_by_id.return_value = {
            "id": "s1",
            "status": "complete",
            "type": "single",
            "progress": 100,
            "org_id": "test-org",
        }
        scan_repo.get_scan_companies.return_value = [{"company_id": "c1"}]
        company_repo.get_by_ids.return_value = [_make_company()]
        server = _make_server(storage)
        text = (await server.call_tool("get_scan", {"scan_id": "s1"}))[0][0].text
        assert "complete" in text
        assert "Acme" in text

    @pytest.mark.asyncio
    async def test_scan_no_companies(self):
        storage, _, _, scan_repo, *_ = _make_storage()
        scan_repo.get_by_id.return_value = {
            "id": "s1",
            "status": "running",
            "type": "portfolio",
            "progress": 50,
            "org_id": "test-org",
        }
        server = _make_server(storage)
        text = (await server.call_tool("get_scan", {"scan_id": "s1"}))[0][0].text
        assert "running" in text

    @pytest.mark.asyncio
    async def test_not_found(self):
        storage, *_ = _make_storage()
        server = _make_server(storage)
        text = (await server.call_tool("get_scan", {"scan_id": "x"}))[0][0].text
        assert "not found" in text


def _strategy_map_fixture():
    """A minimal camelCase strategy map matching the persisted wire shape
    (model_dump(by_alias=True))."""
    objective = {
        "id": "F1",
        "title": "Grow recurring revenue",
        "definition": "Expand ARR via land-and-expand. Second sentence ignored.",
        "confidence": "HIGH",
        "linked_opportunity_indices": [0],
    }
    return {
        "vision": {"statement": "Be the category leader", "synthesised": True},
        "mission": {"statement": "Help PE firms see AI risk"},
        "valueProposition": {"primary": "product_leadership"},
        "strategicPriorities": [{"name": "Expand", "result": "Double ARR"}],
        "financial": {"objectives": [objective]},
        "customer": {
            "objectives": [
                {"id": "C1", "title": "I trust the data", "definition": "Customers rely on us."}
            ]
        },
        "internalProcesses": {
            "themes": [
                {
                    "name": "Data quality",
                    "objectives": [
                        {"id": "I1.1", "title": "Clean pipelines", "definition": "Keep data fresh."}
                    ],
                }
            ]
        },
        "organizationalCapacity": {
            "people": {"id": "O.P", "title": "Hire experts", "definition": "Recruit ML talent."},
            "technology": {
                "id": "O.T",
                "title": "Scale infra",
                "definition": "Invest in platform.",
            },
            "culture": {"id": "O.C", "title": "Ship fast", "definition": "Bias to action."},
        },
        "coreValues": {"values": ["Rigor", "Speed", "Trust"], "synthesised": True},
    }


class TestGetStrategyMap:
    @pytest.mark.asyncio
    async def test_returns_perspectives_and_objectives(self):
        storage, company_repo, assessment_repo, *_ = _make_storage()
        company_repo.get_by_id.return_value = _make_company()
        assessment_repo.find_by_company.return_value = [{"id": "a1", "created_at": "2026-01-01"}]
        assessment_repo.get_strategy_map.return_value = _strategy_map_fixture()
        assessment_repo.get_opportunities.return_value = [{"title": "Automate support"}]
        server = _make_server(storage)
        text = (await server.call_tool("get_strategy_map", {"analysis_id": "c1"}))[0][0].text
        assert "Strategy Map — Acme" in text
        assert "Be the category leader (synthesised)" in text
        assert "### Financial" in text
        assert "Grow recurring revenue" in text
        # First sentence only — the second sentence must be dropped.
        assert "Expand ARR via land-and-expand." in text
        assert "Second sentence ignored" not in text
        # linked_opportunity_indices resolved to the opportunity title.
        assert "opportunities: Automate support" in text
        assert "Core Values (inferred)" in text

    @pytest.mark.asyncio
    async def test_no_strategy_map(self):
        storage, company_repo, assessment_repo, *_ = _make_storage()
        company_repo.get_by_id.return_value = _make_company()
        assessment_repo.find_by_company.return_value = [{"id": "a1", "created_at": "2026-01-01"}]
        assessment_repo.get_strategy_map.return_value = None
        server = _make_server(storage)
        text = (await server.call_tool("get_strategy_map", {"analysis_id": "c1"}))[0][0].text
        assert "No strategy map" in text

    @pytest.mark.asyncio
    async def test_no_assessment_at_all(self):
        # No assessment for the company → _latest_assessment_id returns None →
        # get_strategy_map is never called. Covers the `aid is None` guard.
        storage, company_repo, assessment_repo, *_ = _make_storage()
        company_repo.get_by_id.return_value = _make_company()
        assessment_repo.find_by_company.return_value = []
        server = _make_server(storage)
        text = (await server.call_tool("get_strategy_map", {"analysis_id": "c1"}))[0][0].text
        assert "No strategy map" in text
        assessment_repo.get_strategy_map.assert_not_called()

    @pytest.mark.asyncio
    async def test_cross_org_denied(self):
        storage, company_repo, *_ = _make_storage()
        company_repo.get_by_id.return_value = _make_company(org_id="other-org")
        server = _make_server(storage)
        text = (await server.call_tool("get_strategy_map", {"analysis_id": "c1"}))[0][0].text
        assert "not found" in text


class TestListScans:
    @pytest.mark.asyncio
    async def test_returns_scans(self):
        storage, _, _, scan_repo, *_ = _make_storage()
        scan_repo.find_recent_by_org.return_value = [
            {
                "id": "s1",
                "status": "complete",
                "type": "single",
                "progress": 100,
                "created_at": "2026-01-02",
            },
            {"id": "s2", "status": "running", "type": "portfolio", "progress": 40},
        ]
        server = _make_server(storage)
        text = (await server.call_tool("list_scans", {}))[0][0].text
        assert "Scans (2)" in text
        assert "s1 — complete (single, 100%)" in text
        assert "2026-01-02" in text
        assert "s2 — running (portfolio, 40%)" in text

    @pytest.mark.asyncio
    async def test_empty(self):
        storage, *_ = _make_storage()
        server = _make_server(storage)
        text = (await server.call_tool("list_scans", {}))[0][0].text
        assert "No scans found" in text


class TestListTeamMembers:
    @pytest.mark.asyncio
    async def test_returns(self):
        storage, _, _, _, user_repo, invitation_repo = _make_storage()
        user_repo.find_by_org.return_value = [
            {"name": "Alice", "email": "a@t.com", "role": "admin"}
        ]
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
        _setup_assessment(
            assessment_repo,
            get_documents=[
                {"id": "d1", "filename": "report.pdf", "fileType": "pdf", "charCount": 5000}
            ],
        )
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
        company_repo.find_by_org.return_value = (
            [
                _make_company(company_name="Stripe Inc"),
                _make_company(id="c2", company_name="Plaid"),
            ],
            None,
        )
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
            _make_company(company_name="Stripe", overall_risk_score=4.5)
            if cid == "c1"
            else _make_company(
                id="c2", company_name="Plaid", overall_risk_score=6.0, risk_tier="high"
            )
        )
        _setup_assessment(assessment_repo)
        server = _make_server(storage)
        text = (await server.call_tool("compare_analyses", {"analysis_ids": ["c1", "c2"]}))[0][
            0
        ].text
        assert "Stripe" in text
        assert "Plaid" in text
        assert "Comparison" in text

    @pytest.mark.asyncio
    async def test_too_few(self):
        storage, *_ = _make_storage()
        server = _make_server(storage)
        text = (await server.call_tool("compare_analyses", {"analysis_ids": ["c1"]}))[0][0].text
        assert "at least 2" in text

"""Tests for MCP write tools — mocks repositories, SQS, and the rate limiter."""

from unittest.mock import MagicMock, patch

import pytest
from mcp.server.fastmcp import FastMCP

from src.mcp.auth_context import AuthenticatedUser, set_authenticated_user
from src.mcp.scan_rate_limiter import ScanRateLimitedError
from src.mcp.tools_write import register_write_tools

QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/000/analysis"


def _set_user(scopes):
    set_authenticated_user(
        AuthenticatedUser(
            user_id="user-1",
            org_id="org-1",
            email="t@t.com",
            role="admin",
            client_id="client-1",
            scopes=scopes,
        )
    )


@pytest.fixture(autouse=True)
def _default_user():
    _set_user(["read", "write"])


@pytest.fixture
def harness():
    storage = MagicMock()
    scan_repo = MagicMock()
    storage.create_scan_repository.return_value = scan_repo
    sqs = MagicMock()
    limiter = MagicMock()
    server = FastMCP("test")
    register_write_tools(server, storage, sqs_client=sqs, queue_url=QUEUE_URL, rate_limiter=limiter)
    return server, scan_repo, sqs, limiter


async def _call(server, tool, args):
    return (await server.call_tool(tool, args))[0][0].text


class TestStartCompanyScan:
    @pytest.mark.asyncio
    async def test_success_creates_record_and_enqueues(self, harness):
        server, scan_repo, sqs, limiter = harness
        text = await _call(server, "start_company_scan", {"url": "https://acme.com"})
        limiter.check_and_increment.assert_called_once_with("org-1")
        scan_repo.create.assert_called_once()
        record = scan_repo.create.call_args.args[0]
        assert record["org_id"] == "org-1"
        # "standalone" matches the type the web UI persists for single scans,
        # so MCP-started scans render identically in the UI.
        assert record["type"] == "standalone"
        sqs.send_message.assert_called_once()
        assert sqs.send_message.call_args.kwargs["QueueUrl"] == QUEUE_URL
        assert "Scan started" in text
        assert "get_scan" in text
        assert "get_analysis" in text

    @pytest.mark.asyncio
    async def test_invalid_url_writes_nothing(self, harness):
        server, scan_repo, sqs, limiter = harness
        text = await _call(server, "start_company_scan", {"url": "acme.com"})
        assert "http://" in text
        scan_repo.create.assert_not_called()
        sqs.send_message.assert_not_called()
        limiter.check_and_increment.assert_not_called()

    @pytest.mark.asyncio
    async def test_read_only_scope_is_refused(self, harness):
        server, scan_repo, sqs, _ = harness
        _set_user(["read"])
        text = await _call(server, "start_company_scan", {"url": "https://acme.com"})
        assert "write" in text
        assert "read-only" in text
        scan_repo.create.assert_not_called()
        sqs.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_rate_limited_writes_nothing(self, harness):
        server, scan_repo, sqs, limiter = harness
        limiter.check_and_increment.side_effect = ScanRateLimitedError(
            "Scan rate limit reached: 5 scans/hour per organization. Try again after T."
        )
        text = await _call(server, "start_company_scan", {"url": "https://acme.com"})
        assert "5 scans/hour" in text
        scan_repo.create.assert_not_called()
        sqs.send_message.assert_not_called()


class TestStartPortfolioScan:
    @pytest.mark.asyncio
    async def test_success_guides_to_confirm(self, harness):
        server, scan_repo, sqs, _ = harness
        text = await _call(server, "start_portfolio_scan", {"url": "https://pefirm.com"})
        record = scan_repo.create.call_args.args[0]
        assert record["type"] == "portfolio"
        assert record["status"] == "discovering"
        sqs.send_message.assert_called_once()
        assert "discovering" in text
        assert "confirm_portfolio_scan" in text

    @pytest.mark.asyncio
    async def test_read_only_scope_is_refused(self, harness):
        server, scan_repo, *_ = harness
        _set_user(["read"])
        text = await _call(server, "start_portfolio_scan", {"url": "https://pefirm.com"})
        assert "write" in text
        scan_repo.create.assert_not_called()


class TestConfirmPortfolioScan:
    def _scan(self, **overrides):
        scan = {
            "id": "scan-1",
            "org_id": "org-1",
            "type": "portfolio",
            "status": "awaiting_confirmation",
            "portfolio_companies": [
                {"name": "Acme", "url": "https://acme.com"},
                {"name": "Beta", "url": "https://beta.com"},
            ],
        }
        scan.update(overrides)
        return scan

    @pytest.mark.asyncio
    async def test_single_company_enqueues_with_discovered_name(self, harness):
        server, scan_repo, sqs, limiter = harness
        scan_repo.get_by_id.return_value = self._scan()
        text = await _call(
            server,
            "confirm_portfolio_scan",
            {"scan_id": "scan-1", "company_urls": ["https://acme.com"]},
        )
        limiter.check_and_increment.assert_called_once_with("org-1")
        # Name resolved from the discovery results.
        link_args = scan_repo.link_company.call_args.args
        assert link_args[2] == "Acme"
        sqs.send_message.assert_called_once()
        assert "1 companies queued" in text
        assert "Acme" in text

    @pytest.mark.asyncio
    async def test_multiple_companies_dispatch_via_step_functions(self, harness):
        server, scan_repo, sqs, _ = harness
        scan_repo.get_by_id.return_value = self._scan()
        sfn = MagicMock()
        with (
            patch("src.handlers.scan_core.boto3.client", return_value=sfn),
            patch.dict(
                "os.environ", {"PORTFOLIO_STATE_MACHINE_ARN": "arn:aws:states:us-east-1:0:sm/x"}
            ),
        ):
            text = await _call(
                server,
                "confirm_portfolio_scan",
                {"scan_id": "scan-1", "company_urls": ["https://acme.com", "https://beta.com"]},
            )
        sfn.start_execution.assert_called_once()
        sqs.send_message.assert_not_called()
        assert "2 companies queued" in text

    @pytest.mark.asyncio
    async def test_cross_org_scan_not_found(self, harness):
        server, scan_repo, sqs, limiter = harness
        scan_repo.get_by_id.return_value = self._scan(org_id="other-org")
        text = await _call(
            server,
            "confirm_portfolio_scan",
            {"scan_id": "scan-1", "company_urls": ["https://acme.com"]},
        )
        assert "not found" in text
        sqs.send_message.assert_not_called()
        # A denied call must not consume a rate-limit slot.
        limiter.check_and_increment.assert_not_called()

    @pytest.mark.asyncio
    async def test_already_running_scan_refused(self, harness):
        # Re-confirming a running scan would duplicate the fan-out (an LLM has
        # no UI guardrail preventing this). No writes, no rate slot consumed.
        server, scan_repo, sqs, limiter = harness
        scan_repo.get_by_id.return_value = self._scan(status="running")
        text = await _call(
            server,
            "confirm_portfolio_scan",
            {"scan_id": "scan-1", "company_urls": ["https://acme.com"]},
        )
        assert "not awaiting confirmation" in text
        assert "running" in text
        scan_repo.update.assert_not_called()
        sqs.send_message.assert_not_called()
        limiter.check_and_increment.assert_not_called()

    @pytest.mark.asyncio
    async def test_non_portfolio_scan_refused(self, harness):
        server, scan_repo, sqs, limiter = harness
        scan_repo.get_by_id.return_value = self._scan(type="single", status="running")
        text = await _call(
            server,
            "confirm_portfolio_scan",
            {"scan_id": "scan-1", "company_urls": ["https://acme.com"]},
        )
        assert "not a portfolio scan" in text
        sqs.send_message.assert_not_called()
        limiter.check_and_increment.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_urls_rejected(self, harness):
        server, scan_repo, sqs, _ = harness
        text = await _call(
            server, "confirm_portfolio_scan", {"scan_id": "scan-1", "company_urls": []}
        )
        assert "At least one company URL is required." in text
        scan_repo.get_by_id.assert_not_called()
        sqs.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_invalid_urls_rejected_after_org_check(self, harness):
        server, scan_repo, sqs, _ = harness
        scan_repo.get_by_id.return_value = self._scan()
        text = await _call(
            server, "confirm_portfolio_scan", {"scan_id": "scan-1", "company_urls": ["acme.com"]}
        )
        assert "At least one company with a url is required" in text
        sqs.send_message.assert_not_called()

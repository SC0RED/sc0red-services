# MCP Write Tools — Scans

## Why

The MCP server is read-only: AI assistants can browse analyses but cannot start one, so the core "analyze acme.com" / "discover this PE firm's portfolio" workflows still require the web UI. The read tools even advertise a `start_company_scan` tool in their empty-state messages that does not exist — an AI client will try to call it and fail. This is the scoped-down successor to janus-mcp-server's planned PR 3, unblocked now that the OAuth + transport chain is validated end-to-end.

## What Changes

- Add three MCP write tools, reusing the exact backend code paths the web UI uses (`handle_scan_start` / `handle_scan_confirm` shared logic):
  - `start_company_scan(url)` — initiate a single-company analysis; returns the scan id.
  - `start_portfolio_scan(url)` — initiate PE portfolio discovery; returns the scan id.
  - `confirm_portfolio_scan(scan_id, company_urls)` — confirm discovered companies for analysis.
- Add per-org scan rate limiting enforced at the MCP layer: 5 scans/hour, 30 scans/day. Scans trigger paid AI pipeline runs; an LLM client can loop where a human would not.
- Gate write tools on the OAuth `write` scope (read tools stay available to read-only tokens). Consent already grants `read write`, so existing connections keep working.
- Grant the MCP Lambda send access to the analysis SQS queue + the `ANALYSIS_QUEUE_URL` env var (it currently has neither).
- Fix the read-tool empty-state strings so they describe the now-real tools accurately.
- Explicitly deferred (out of scope): `poll_scan_until_complete` (clients poll `get_scan`; a blocking tool would hold a Lambda invocation open for minutes), `upload_document`, `reanalyze_with_documents` (base64-over-MCP + S3 is its own change).

## Capabilities

### New Capabilities
- `mcp-scan-tools`: starting and confirming company/portfolio scans from an MCP client, with org scoping and write-scope gating.
- `mcp-scan-rate-limiting`: per-org rate limits on MCP-initiated scans (hourly + daily windows), with clear retry-after messaging to the AI client.

### Modified Capabilities

<!-- none — the read-tool empty-state string fix is an implementation correction, not a requirement change -->

## Impact

- **Backend**: new `src/mcp/tools_write.py` (+ registration in `mcp_handler.py`); a rate-limit store on the existing DynamoDB single-table; reuse of `src/handlers/scan_handlers.py` shared functions and `src/handlers/sqs_messages.py` schemas.
- **Infrastructure**: `MCPConstruct` gains the analysis queue reference (`grant_send_messages` + `ANALYSIS_QUEUE_URL`). Same stack — no cross-stack or circular-dependency risk.
- **Auth**: `RequireAuthMiddleware`/scope plumbing already carries scopes on the access token; write tools check for `write`.
- **Cost/abuse surface**: MCP becomes able to trigger paid pipeline runs — bounded by the rate limits and existing per-org auth.
- **Clients**: after deploy, connected AI assistants see 3 new tools (16 total). No breaking changes to existing tools.

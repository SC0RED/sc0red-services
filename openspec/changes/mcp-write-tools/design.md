# Design — MCP Write Tools (Scans)

## Context

The MCP server (FastMCP on Lambda, validated end-to-end) exposes 15 read/search tools that talk to DynamoDB directly through the same repositories the API uses. Scans, however, are initiated through `src/handlers/scan_handlers.py`: `handle_scan_start` creates the scan record and enqueues work on the analysis SQS queue; `handle_scan_confirm` fans confirmed portfolio companies out to the queue. The MCP Lambda currently has no SQS access. The MCP auth context (`AuthenticatedUser`) carries `user_id`, `org_id`, `email`, `role`, and `scopes` — structurally a superset of the `AuthContext` the scan handlers consume.

Constraints: scans trigger paid AI pipeline runs; the 400-line file cap applies (`scan_handlers.py` is near it); local dev/e2e must exercise the same code paths as production.

## Goals / Non-Goals

**Goals:**
- Start single-company and portfolio scans, and confirm portfolio discoveries, from any connected MCP client.
- Zero duplicated business logic — MCP tools and HTTP handlers share one scan-start/confirm core.
- Per-org rate limits that an enthusiastic LLM cannot blow through.
- Write tools gated on the `write` OAuth scope.

**Non-Goals:**
- `poll_scan_until_complete` (a blocking tool would pin a Lambda invocation for minutes; clients poll `get_scan`).
- Document upload / re-analysis over MCP.
- Rate limiting the web UI (human-paced; unchanged).
- Per-company accounting for portfolio confirms (a confirm counts as one scan, matching the product's notion of "a scan").

## Decisions

### D1 — Reuse via an extracted shared core, not synthetic HTTP events

`handle_scan_start` is HTTP-shaped (event dict in, `LambdaResponse` out). Rather than having MCP tools fabricate fake HTTP events and parse HTTP envelopes (workable but dishonest plumbing), extract the existing private helpers into a public seam — `start_scan(...)` and `confirm_scan(...)` returning plain dicts — consumed by BOTH the HTTP handlers (which wrap them in `build_json_response`) and the MCP tools (which format Markdown). This follows the codebase's shared-location rule and keeps `handle_scan_start`/`handle_scan_confirm` as thin envelopes. The MCP `AuthenticatedUser` satisfies the `AuthContext` fields the core reads (`org_id`, `user_id`).

*Alternative considered:* call `handle_scan_start` with a synthetic `{"body": json.dumps(...)}` event — rejected: couples MCP to the HTTP envelope, and error mapping (HTTP codes → tool strings) gets murky.

### D2 — Rate limiting: conditional atomic counters on the existing single-table

New module owns it (e.g. `src/mcp/scan_rate_limiter.py`). Per org, two window counters:

```
pk=RATE_LIMIT#{org_id}  sk=SCAN#HOUR#2026-06-11T14   counter, ttl (+2h)
pk=RATE_LIMIT#{org_id}  sk=SCAN#DAY#2026-06-11       counter, ttl (+2d)
```

One `update_item` per window with `ADD counter 1` and `ConditionExpression: attribute_not_exists(counter) OR counter < :limit`; a `ConditionalCheckFailedException` means rate-limited. Single write, no read-modify-race, auto-cleanup via the table's existing TTL attribute. Limits: 5/hour, 30/day per org (from the original PR 3 plan). The tool returns a clear message with the window that tripped ("Scan rate limit reached: 5 scans/hour per organization. Try again after …") so the AI client can relay it and stop retrying.

*Alternative considered:* increment-then-check (no condition) — simpler but rejected attempts consume slots; conditional write is the same cost and cleaner.

### D3 — Scope gating inside the tools, not the transport

`RequireAuthMiddleware` enforces token validity at the transport; per-tool scope checks happen in the tool body (`"write" in get_authenticated_user().scopes` → friendly refusal string). The SDK's `required_scopes` setting is all-or-nothing per server, which would break read-only tokens for read tools. Consent currently grants `read write`, so existing connections are unaffected; the gate is the future lever for read-only connections.

### D4 — Infra: pass the queue into MCPConstruct (+ Step Functions, found during implementation)

The analysis queue already lives in the same stack (the API Lambda has `ANALYSIS_QUEUE_URL`). `MCPConstruct` gains a `analysis_queue` parameter → `queue.grant_send_messages(mcp_lambda)` + `ANALYSIS_QUEUE_URL` env. Same-stack reference, no circular dependency (queue does not reference the MCP Lambda).

**Amendment:** multi-company confirms dispatch via **Step Functions** (`scan_core.confirm_scan` reads `PORTFOLIO_STATE_MACHINE_ARN` + starts an execution), not SQS — so the MCP Lambda also needs `states:StartExecution` on the batch coordinator + the ARN/`WAVE_SIZE` envs. Wired post-construction in the stack (the batch coordinator is created after `MCPConstruct`), mirroring the api_handler lines.

### D5 — Tool surface and output shape

`tools_write.py` registers exactly three tools mirroring the read-tool style (Markdown strings, org-scoped, explicit dependencies passed to `register_write_tools(mcp, storage, sqs_client, queue_url, rate_limiter)`):
- `start_company_scan(url)` → scan id + "poll with get_scan" guidance
- `start_portfolio_scan(url)` → scan id + "confirm with confirm_portfolio_scan once status is awaiting_confirmation"
- `confirm_portfolio_scan(scan_id, company_urls)` → confirmation summary

Each validates inputs first (fail-fast, before any write), checks scope, then rate limit, then delegates to the shared core. Cross-org `scan_id` access re-uses `_verify_org_access`.

## Risks / Trade-offs

- [LLM triggers costly runs] → rate limits (D2) + MCP clients require human approval for tool calls by default; limits are per-org so a single org cannot exhaust shared capacity.
- [Confirm fan-out: one "scan" may enqueue N companies] → accepted: matches the product's scan granularity; the discovery step itself is rate-limited, bounding total fan-out.
- [Refactor risk in scan_handlers (D1)] → behavior-preserving extraction with the existing handler tests as the safety net; e2e suite covers the HTTP path.
- [Clock-window edges (burst at hour boundary allows up to 2×hourly briefly)] → accepted for v1; fixed-window is simple and the daily cap bounds it.
- [Local/e2e parity] → the MCP service in local/e2e compose must get `ANALYSIS_QUEUE_URL` pointed at localstack, same as the API worker pair, or write tools silently diverge from prod.

## Migration Plan

Single PR, backend + infra together (the env var/grant deploy with the code that needs it). No data migration; rate-limit rows are created on demand. Rollback = revert; counters expire via TTL.

## Open Questions

- None blocking. (Limit values are config-by-constant for now; making them per-org-configurable is a future concern.)

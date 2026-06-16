# Tasks — MCP Write Tools (Scans)

## 1. Shared scan core (D1 — extraction, behavior-preserving)

- [x] 1.1 Extract the scan-start core from `scan_handlers.py` into public functions returning plain dicts (e.g. `start_scan(scan_repo, url, scan_type, authentication, sqs, queue_url) -> dict`), keeping `handle_scan_start` as a thin HTTP envelope over it. Watch the 400-line cap — split into a `_scan_core.py`-style module if needed.
- [x] 1.2 Same for the confirm path: extract the core of `handle_scan_confirm` (validation of scan state + per-company enqueue) into a public seam usable without an HTTP event.
- [x] 1.3 Existing handler + e2e tests still green (the extraction must not change HTTP behavior).

## 2. Rate limiter (D2)

- [x] 2.1 `src/mcp/scan_rate_limiter.py`: conditional atomic counters on the single-table (`RATE_LIMIT#{org}` / `SCAN#HOUR#…`, `SCAN#DAY#…`), `ADD counter 1` with `ConditionExpression counter < :limit`, TTL attribute set; `ConditionalCheckFailedException` → limited. Limits as module constants: 5/hour, 30/day.
- [x] 2.2 Unit tests: within-limit increments both windows; hourly limit trips at 6th call with retry-after messaging; daily limit trips; windows are per-org (org A's limit does not affect org B); TTL attribute present.

## 3. Write tools (D3, D5)

- [x] 3.1 `src/mcp/tools_write.py` with `register_write_tools(mcp, storage, sqs_client, queue_url, rate_limiter)`: `start_company_scan(url)`, `start_portfolio_scan(url)`, `confirm_portfolio_scan(scan_id, company_urls)`. Order per tool: validate inputs → `write`-scope check → org access check (confirm) → rate limit → shared core → Markdown result with next-step guidance (`get_scan` / confirm flow).
- [x] 3.2 Register in `mcp_handler.py` (SQS client + `ANALYSIS_QUEUE_URL` env wiring, matching the storage-provider pattern).
- [x] 3.3 Fix the read-tool empty-state strings (`list_analyses`, `list_scans`) to match the now-real tool surface.
- [x] 3.4 Unit tests per tool: success path (record + enqueue via mocks), validation errors (no writes), missing `write` scope (no writes), cross-org confirm → not-found, rate-limited call (no writes).

## 4. Infrastructure (D4)

- [x] 4.1 `MCPConstruct` gains `analysis_queue`; `grant_send_messages(mcp_lambda)` + `ANALYSIS_QUEUE_URL` env, wired from the stack. **Plus (discovered in 1.2):** multi-company confirms dispatch via Step Functions, so the stack also grants `states:StartExecution` + sets `PORTFOLIO_STATE_MACHINE_ARN`/`WAVE_SIZE` on the MCP Lambda (post-construction — the batch coordinator is created after MCPConstruct), mirroring the api_handler wiring.
- [x] 4.2 Local/e2e parity — **finding: there is NO MCP service in local/e2e compose at all** (pre-existing gap, predates this change; the MCP server runs locally via manual `uvicorn src.mcp.mcp_handler:app` with env vars passed directly, so `ANALYSIS_QUEUE_URL` is supplied the same way as `DYNAMODB_TABLE`). Adding an MCP compose service is its own follow-up (tracked in janus-mcp-server), out of scope for write tools.

## 5. Quality gates + ship

- [x] 5.1 Backend gates: `ruff check` + `ruff format`, `pyright`, naming validators, full `pytest` ≥95% coverage.
- [x] 5.2 Architecture-reviewer pass — 0 critical; fixed the MEDIUM (hard env access for ANALYSIS_QUEUE_URL so a missing queue crashes at cold start instead of orphaning scan records) + LOW (dead `(scan or {})` defensiveness).
- [x] 5.3 Conventional commit on feat/mcp-write-tools; local E2E suite green (45/45). PR open — awaiting user merge approval.

## 6. Staging validation

- [x] 6.1 After deploy: connect with mcp-inspector (Direct mode) → tools list shows 17 tools (10 read + 2 scan-read + 2 search + 3 write) → `start_company_scan` on a test URL → `get_scan` shows progress → analysis completes and `get_analysis` returns it.
- [x] 6.2 Portfolio flow: `start_portfolio_scan` → poll to `awaiting_confirmation` → `confirm_portfolio_scan` → companies analyze.
- [x] 6.3 Rate limit: 6th scan call within the hour returns the limit message (and the web UI can still start scans).
- [x] 6.4 janus-mcp-server PR 3 marked superseded-by-`mcp-write-tools` (poll/document tools deferred to a future change).

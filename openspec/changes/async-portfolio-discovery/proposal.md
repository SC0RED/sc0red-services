## Why

Portfolio discovery runs synchronously inside the API Gateway handler (`_start_portfolio_scan` in `scan_handlers.py`). Large firms like perotjain.com trigger ~22 parallel AI validation calls plus a page-extraction call, which regularly exceeds the 29-second API Gateway integration timeout and returns 504 to the user. The recent "validate-only-remainder" fix (#152) reduced AI calls from 50 → 22 but did not remove the hard synchronous ceiling — any firm with >15 non-intersection companies, slow AI responses, or transient network latency will still time out. The single-company scan path already solves this problem by dispatching to an SQS worker Lambda; portfolio discovery should use the same pattern.

## What Changes

- **Move `DiscoverPortfolio` + `ValidatePortfolioCompanies` execution from the API Lambda to the SQS worker Lambda.** The API handler creates the scan record, pushes a `portfolio_discovery` SQS message, and returns immediately with `status: "discovering"`.
- **Worker-side dispatch**: `SQSHandler._process_message` gains a new branch for `type: "portfolio_discovery"` that invokes `FactoryManager.run_portfolio_discovery()` and writes the result to the scan record (`status: "awaiting_confirmation"`, `portfolio_companies: [...]`).
- **Scan status lifecycle**: adds a `discovering` state between initial creation and `awaiting_confirmation`. Existing `running` / `complete` states for per-company analysis are unchanged.
- **Frontend polling**: existing `GET /api/scan/{id}` already returns status; frontend must tolerate the new `discovering` state and keep polling until `awaiting_confirmation` (or `failed`).
- **Error handling on failure**: worker writes `status: "failed"` + `error` to the scan record so the UI can surface the reason.
- **Observability**: AppSync progress notifications at discovery start, AI extraction done, validation done, and final merge — mirroring the per-company scan pattern.

## Capabilities

### New Capabilities
- `async-portfolio-scan`: SQS-backed asynchronous portfolio discovery pipeline — message schema, worker dispatch, scan state lifecycle (`pending` → `discovering` → `awaiting_confirmation` → `running` → `complete`), and failure surfacing.

### Modified Capabilities
_(No existing specs in `openspec/specs/` to modify — this is the first capability introduced via OpenSpec.)_

## Impact

- **Modified**: `src/handlers/scan_handlers.py` — `_start_portfolio_scan` becomes an SQS dispatch (no pipeline execution, no 504 surface).
- **Modified**: `src/handlers/sqs_handler.py` — new message-type branch for `portfolio_discovery`.
- **Modified**: `src/handlers/sqs_messages.py` — new `build_portfolio_discovery_message(...)`.
- **Modified**: `src/handlers/factory_manager.py` — `run_portfolio_discovery` already exists; may need small adjustments to persist results via the repository layer instead of returning them to an HTTP caller.
- **Modified**: `src/repositories/dynamodb/scan_repository.py` — add `discovering` / `failed` status handling if not already supported.
- **Modified**: `frontend/src/**` scan status page — render a `discovering` state (spinner + "Finding portfolio companies…").
- **No infrastructure changes required**: worker Lambda + SQS queue already exist from the per-company analysis pipeline. Worker Lambda timeout (configured at 15 min) accommodates discovery + validation comfortably.
- **Tests**: unit tests for new SQS message builder + worker dispatch branch; update `test_scan_handlers.py` to assert SQS dispatch instead of synchronous pipeline call.
- **Backward compatibility**: once deployed, any in-flight portfolio scans created under the old synchronous path will not exist — the API return shape changes (returns `discovering` not `awaiting_confirmation`), so frontend + backend must deploy together.

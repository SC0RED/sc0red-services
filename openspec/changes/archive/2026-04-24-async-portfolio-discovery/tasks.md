## 1. Backend — SQS message schema

- [x] 1.1 Add `build_portfolio_discovery_message(*, url, org_id, user_id, scan_id)` to `src/handlers/sqs_messages.py`; include `type: "portfolio_discovery"` discriminator
- [x] 1.2 Unit tests for the new builder in `tests/unit/handlers/test_sqs_messages.py` (or new file) — assert JSON shape and all required fields

## 2. Backend — API handler dispatches to SQS

- [x] 2.1 Rewrite `_start_portfolio_scan` in `src/handlers/scan_handlers.py` to: create scan record (`status="pending"`), call `sqs.send_message(...)` with the new builder, return `{scanId, status: "discovering"}`
- [x] 2.2 Remove the synchronous `factory_manager.run_portfolio_discovery` call from the API handler path
- [x] 2.3 Update `handle_scan_start` signature/wiring to pass `sqs` + `queue_url` into `_start_portfolio_scan` (it currently only has `factory_manager`)
- [x] 2.4 Update tests in `tests/unit/handlers/test_scan_handlers.py` — assert SQS send, assert no synchronous pipeline invocation, assert response shape

## 3. Backend — Worker dispatch

- [x] 3.1 Add `_process_portfolio_discovery(self, message)` to `src/handlers/sqs_handler.py` that calls `FactoryManager.run_portfolio_discovery(...)` and persists results to the scan record via `DynamoDBScanRepository.update`
- [x] 3.2 Extend `_process_message` to branch on `message.get("type") == "portfolio_discovery"` (alongside the existing `reanalyze` branch)
- [x] 3.3 On entry to the branch, update scan to `status="discovering"` (so UI can distinguish "queued" from "in progress")
- [x] 3.4 On success, update scan with `status="awaiting_confirmation"`, `portfolio_companies=<list>`, `progress=20`
- [x] 3.5 On domain exception (`EngineError`, `ValueError`, `RuntimeError`), update scan with `status="failed"`, `error=<message>`; swallow the exception so SQS does not retry
- [x] 3.6 Programming errors (`KeyError`, `AttributeError`, `TypeError`) propagate to outer handler → `batchItemFailures` → retry
- [x] 3.7 Unit tests in `tests/unit/handlers/test_sqs_handler.py` covering: dispatch on type, successful completion, domain-error failure path, programming-error propagation

## 4. Backend — Factory manager adjustment

- [x] 4.1 Audit `FactoryManager.run_portfolio_discovery` to confirm it does NOT rely on being called from an HTTP context; adjust signature if needed so the worker can invoke it cleanly
- [x] 4.2 Verify it writes no scan-record side effects itself — the worker owns state transitions (enforces separation of concerns)

## 5. Backend — Scan repository / state validation

- [x] 5.1 Check `src/repositories/dynamodb/scan_repository.py` and `src/models/model_literals.py` for a status enum/whitelist; add `discovering` and ensure `failed` is present — **no enum/whitelist exists**, status is free-form; no change required
- [x] 5.2 If a status validator exists (e.g. in the DTO/response layer), update it to accept `discovering` — **no validator exists**; no change required
- [x] 5.3 Update `scan_handlers.handle_scan_status` / response builder to echo `discovering` and `error` fields cleanly

## 6. Backend — AppSync progress notifications

- [x] 6.1 In `_process_portfolio_discovery`, emit `notify_progress(scan_id, progress=5, label="Starting discovery…")` at entry
- [x] 6.2 Emit `progress=15, label="Finding companies…"` between `DiscoverPortfolio` and `ValidatePortfolioCompanies` (or use a hook in the pipeline factory) — wired via `_PROGRESS_MAP` in `JanusRequestExecutor`; `scan_id` plumbed through `PortfolioScanFactory` → executor so per-step `_report_progress` fires AppSync notifications automatically
- [x] 6.3 Emit `progress=20, label="Ready for confirmation", status="awaiting_confirmation"` on success

## 7. Frontend — Render `discovering` state

- [x] 7.1 In the scan progress page/component, map `status === "discovering"` to a loading indicator with copy "Finding portfolio companies…"
- [x] 7.2 Ensure polling cadence continues through `discovering` (no early exit) — existing hook only stops on terminal states; discovering falls through
- [x] 7.3 Add render logic for `status === "failed"` surfacing `error` to the user (if not already present) — now prefers `data.error` over generic copy
- [x] 7.4 Vitest + RTL tests covering: renders discovering state, transitions to confirmation on status change, surfaces failed state

## 8. Tests & quality gates

- [x] 8.1 Backend: `uv run pytest tests/ -q` — 703 tests pass; coverage at 95.00% (floor)
- [x] 8.2 Backend: `uv run ruff check src/` — zero errors
- [x] 8.3 Backend: `uv run ruff format --check src/` — zero diffs
- [x] 8.4 Backend: `uv run pyright src/` — 329 vs 336 (net **−7 errors**, no new regressions)
- [x] 8.5 Frontend: `npm run lint && npx tsc --noEmit && npm test` — lint clean, typecheck clean, 391 tests pass
- [x] 8.6 E2E: `scripts/e2e-test.sh` in `E2E_MODE=full` — portfolio scan happy path passes (44/44)
- [x] 8.7 Manual smoke test: perotjain.com scan in staging — no 504, `discovering` → `awaiting_confirmation` transition verified, companies list populated (#153, #154)
- [x] 8.8 Architecture review via `architecture-reviewer` agent — CRITICAL + MEDIUM findings resolved (status-lie fixed by creating record as `discovering`; silent-fallback fixed with bare key access; docker-compose parity gap documented). LOW polling-ref finding is pre-existing and out of scope.

## 9. Deploy & verify

- [x] 9.1 Backend + frontend merged back-to-back: #153 (worker discovery) then #154 (awaiting_confirmation transition)
- [x] 9.2 Deployed to staging (dev account) via CI
- [x] 9.3 Ran perotjain.com scan against staging — sub-second API response + full discovery under worker verified
- [x] 9.4 Promoted to testing, then production

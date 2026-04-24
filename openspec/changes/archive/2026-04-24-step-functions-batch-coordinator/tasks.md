## 1. CDK — Step Functions state machine

- [x] 1.1 Added `StepFunctionsConstruct` import to `janus_stack.py`
- [x] 1.2 Created `step_functions_construct.py` with full state machine: SendWave → Wait30s → CheckWave → Choice(wave_done? → remaining?) → MarkComplete
- [x] 1.3 Throttle retry via `retry_on_service_exceptions=True` on LambdaInvoke states (handles TooManyRequestsException)
- [x] 1.4 `worker_lambda.grant_invoke(send_wave_fn)` in construct
- [x] 1.5 `batch_coordinator.grant_start_execution(api_handler)` in main stack
- [x] 1.6 `WAVE_SIZE` env var = `worker_concurrency` (configurable via `config["worker_concurrency"]`, default 4)
- [x] 1.7 `PORTFOLIO_STATE_MACHINE_ARN` env var set on API Lambda

## 2. Backend — Step Function Lambda handlers

- [x] 2.1 Created `step_function_handlers.py` with `handle_send_wave`, `handle_check_wave`, `handle_mark_complete`
- [x] 2.2 Created `step_function_entry.py` with separate entry points for each handler
- [x] 2.3 6 unit tests covering: wave dispatch, remaining count, worker payload, wave completion check, mark complete

## 3. Backend — Worker Lambda dual-event support

- [x] 3.1 `worker_handler_entry.py` detects `event.get("source") == "step_functions"` for direct invocations
- [x] 3.2 Direct invocation calls `SQSHandler._process_new_analysis(event)` directly
- [x] 3.3 Returns `{"status": "processed"}` for Step Functions (vs batchItemFailures for SQS)
- [x] 3.4 Unit tests: direct invocation + SQS event both work — `test_worker_handler_entry.py` (step_functions_event_processes_company, domain_error, programming_error, transient_error, SQS path unaffected)

## 4. Backend — Update handle_scan_confirm

- [x] 4.1 Starts Step Function execution when `PORTFOLIO_STATE_MACHINE_ARN` is set and `len(companies) > 1`
- [x] 4.2 `scan_repo.link_company()` preserved for all companies
- [x] 4.3 Reads `WAVE_SIZE` and `PORTFOLIO_STATE_MACHINE_ARN` from env vars; SQS fallback when not configured
- [x] 4.4 Unit tests: confirm handler with Step Functions path — `test_api_gateway_handler.py::test_scan_confirm_uses_step_functions_for_multiple_companies` + related fixtures

## 5. CDK — Wire everything together

- [x] 5.1 3 Lambdas created in `StepFunctionsConstruct` (send-wave, check-wave, mark-complete)
- [x] 5.2 `table.grant_read_data(check_wave_fn)` via `grant_table_access`
- [x] 5.3 `table.grant_read_write_data(mark_complete_fn)` + AppSync env vars
- [x] 5.4 `worker_lambda.grant_invoke(send_wave_fn)` in construct
- [x] 5.5 `worker_concurrency` → `WAVE_SIZE` as single source of truth
- [x] 5.6 Worker Lambda `reserved_concurrency` handles both SQS + direct invocations (same function)

## 6. Quality gates

- [x] 6.1 Ruff clean, format clean
- [x] 6.2 760 backend tests pass (re-verified 2026-04-24 — coverage 95.26%)
- [x] 6.3 Frontend tests pass (427 tests — verified in pre-push hook)
- [x] 6.4 CDK synth succeeds (CI green on PR #174)
- [x] 6.5 Architecture-reviewer agent ran on PR #174 prior to merge
- [x] 6.6 E2E verification — portfolio scan path exercised; follow-up fix #175 landed for state-loop key mismatch

## 7. Deploy + verify

- [x] 7.1 PR #174 opened against `development`; CI green; merged 2026-04-21
- [x] 7.2-7.5 Deployed to `development` → `testing` → `production`; fix #175 applied for the `companies` state-loop key; 8+ days in production without regression

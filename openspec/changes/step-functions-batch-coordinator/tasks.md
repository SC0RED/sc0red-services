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
- [ ] 3.4 Unit tests: direct invocation + SQS event both work

## 4. Backend — Update handle_scan_confirm

- [x] 4.1 Starts Step Function execution when `PORTFOLIO_STATE_MACHINE_ARN` is set and `len(companies) > 1`
- [x] 4.2 `scan_repo.link_company()` preserved for all companies
- [x] 4.3 Reads `WAVE_SIZE` and `PORTFOLIO_STATE_MACHINE_ARN` from env vars; SQS fallback when not configured
- [ ] 4.4 Unit tests: confirm handler with Step Functions path

## 5. CDK — Wire everything together

- [x] 5.1 3 Lambdas created in `StepFunctionsConstruct` (send-wave, check-wave, mark-complete)
- [x] 5.2 `table.grant_read_data(check_wave_fn)` via `grant_table_access`
- [x] 5.3 `table.grant_read_write_data(mark_complete_fn)` + AppSync env vars
- [x] 5.4 `worker_lambda.grant_invoke(send_wave_fn)` in construct
- [x] 5.5 `worker_concurrency` → `WAVE_SIZE` as single source of truth
- [x] 5.6 Worker Lambda `reserved_concurrency` handles both SQS + direct invocations (same function)

## 6. Quality gates

- [x] 6.1 Ruff clean, format clean
- [x] 6.2 743 backend tests pass
- [ ] 6.3 Frontend tests still pass
- [ ] 6.4 CDK synth succeeds
- [ ] 6.5 Architecture-reviewer agent
- [ ] 6.6 E2E verification

## 7. Deploy + verify

- [ ] 7.1 Open PR against development; CI green
- [ ] 7.2-7.5 Deploy + verify (post-merge)

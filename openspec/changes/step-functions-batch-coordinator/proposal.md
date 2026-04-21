## Why

Portfolio scans with 69 companies lose 4-5 companies to the DLQ. Root cause: the API Lambda sends all 69 SQS messages at once. Lambda's SQS poller reads messages faster than workers can process them (`reserved_concurrency=4`). Each throttled read increments `ReceiveCount`. After `max_receive_count` throttled reads, messages go to DLQ — without the worker ever running.

We raised `max_receive_count` to 20 as a band-aid, but the fundamental problem remains: SQS + Lambda event source mapping doesn't respect concurrency limits during polling. Messages become invisible for `visibility_timeout=600s` after a throttled read, causing 10-minute stalls even when workers are free.

The problem worsens with concurrent users: 3 users confirming simultaneously = 200+ messages competing for 4 workers.

## What Changes

Replace the "dump all messages to SQS" pattern with an **AWS Step Functions batch coordinator** for portfolio scans.

### Architecture

**API Lambda** (`handle_scan_confirm`): instead of sending N SQS messages, starts a Step Function execution with the full list of confirmed companies and a `wave_size` derived from `reserved_concurrency`.

**Step Function** state machine orchestrates waves:
1. **SendWave** (Map state): directly invokes `wave_size` Worker Lambdas in parallel using `lambda.invoke()` — NOT via SQS. Step Functions handles throttle retries with configurable exponential backoff.
2. **WaitForWave**: polls DynamoDB every 30s to check if all wave companies have `analyzedAt` or `error`.
3. **Choice**: wave done → more companies? → loop to SendWave. No more → MarkComplete.
4. **MarkComplete**: updates scan `status=complete`, sends AppSync event.

**Worker Lambda**: unchanged pipeline code. Accepts a direct invocation event (company payload) in addition to the existing SQS event. Same entry point, event shape detection dispatches to the same `_process_new_analysis`.

**Single-company scans**: completely unchanged — still use the existing SQS path (`_start_single_scan` → 1 SQS message → worker).

### Why Step Functions over SQS for portfolio waves

| Aspect | SQS (current) | Step Functions (proposed) |
|--------|--------------|--------------------------|
| Throttle handling | Poller reads message, throttled → invisible 600s, ReceiveCount++ → DLQ | `lambda.invoke()` throttled → retry after 30s (configurable), no ReceiveCount, no DLQ |
| Over-dispatch | All N messages at once | Only `wave_size` at a time |
| Idle cost | N/A | Wait states are free (no compute) |
| Concurrent users | All scans compete for same queue | Each execution self-paces; waves from different users share workers, Step Functions retries handle contention |
| Visibility into progress | CloudWatch logs only | Visual execution graph in AWS console |

### Auto-configured wave size

`wave_size` is derived from `reserved_concurrency` in CDK — single source of truth. The API Lambda reads it from an environment variable and passes it to the Step Function input. Changing concurrency from 4 to 6 automatically adjusts waves to 6.

## Capabilities

### New Capabilities
- `portfolio-batch-coordinator`: Step Functions state machine that dispatches portfolio company analyses in waves, using direct Lambda invocation with throttle-safe retry.

### Modified Capabilities
_(No existing specs to modify.)_

## Impact

- **New**: Step Functions state machine (CDK construct)
- **New**: 3 small Lambda functions (or 1 with discriminator): send-wave, check-wave, mark-complete
- **Modified**: `handle_scan_confirm` — starts Step Function execution instead of N × `sqs.send_message()`
- **Modified**: Worker Lambda handler — accepts direct invocation event in addition to SQS event
- **Modified**: `janus_stack.py` — Step Functions construct, `wave_size` env var, IAM permissions
- **Unchanged**: single-company scan path, worker pipeline code, AppSync events, DynamoDB schema, frontend
- **Tests**: unit tests for new Step Function Lambdas, updated confirm handler tests, worker dual-event tests

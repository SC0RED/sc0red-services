## Context

```
CURRENT:
  confirm 69 companies → 69 × sqs.send_message() → SQS Queue
  → Lambda poller reads all → invokes 4, throttles 65
  → throttled messages: invisible 600s, ReceiveCount++, eventual DLQ

PROPOSED:
  confirm 69 companies → stepfunctions.start_execution({companies, wave_size})
  → Step Fn sends wave of 4 via lambda.invoke() (not SQS)
  → throttled? Step Fn retries in 30s (not 600s)
  → wave done? send next wave
  → all done? mark scan complete
```

## Goals / Non-Goals

**Goals:**
- Zero company loss from throttle-induced DLQ
- Wave size auto-configured from reserved_concurrency
- Handle concurrent multi-user portfolio scans without starving
- Single-company scans completely unchanged
- Worker pipeline code completely unchanged

**Non-Goals:**
- Migrating single-company scans to Step Functions (they work fine via SQS)
- Changing the AI pipeline steps or retry logic
- Real-time per-company progress from Step Functions (existing AppSync from workers handles this)

## Decisions

### Decision 1: Direct lambda.invoke() from Step Functions Map state, not SQS

**Decision**: each wave uses a Step Functions Map state that directly invokes Worker Lambdas. The SQS queue is NOT used for portfolio company dispatching.

**Why**: SQS poller throttle is the root cause. Removing SQS from the portfolio path removes the problem entirely. Direct `lambda.invoke()` with Step Functions retry handles throttling gracefully — configurable backoff, no ReceiveCount, no DLQ risk.

**Throttle retry configuration**:
```json
{
  "ErrorEquals": ["Lambda.TooManyRequestsException"],
  "IntervalSeconds": 30,
  "MaxAttempts": 10,
  "BackoffRate": 2.0
}
```
Total retry window: 30 + 60 + 120 + ... ≈ hours. More than enough for any concurrency contention.

**Alternative considered**: keep SQS but stagger with DelaySeconds. Rejected — 900s cap, doesn't handle concurrent users, still subject to poller throttle within each wave.

### Decision 2: Worker Lambda handles both SQS events and direct invocations

**Decision**: the Worker Lambda entry point detects the event shape and dispatches accordingly:
- SQS event: `{"Records": [...]}` → existing path (single-company scans)
- Direct invocation: `{"url": "...", "company_name": "...", ...}` → same `_process_new_analysis`

**Why**: avoids creating a second Lambda with duplicate code. Same pipeline, same error handling, same AppSync events. The only difference is how the event arrives.

**Alternative considered**: separate Lambda for portfolio processing. Rejected — code duplication, double maintenance, same pipeline code.

### Decision 3: wave_size = reserved_concurrency (single source of truth in CDK)

**Decision**: CDK defines `reserved_concurrency` once. An environment variable `WAVE_SIZE` is set on the API Lambda to the same value. `handle_scan_confirm` reads it and passes it to the Step Function input.

**Why**: changing concurrency from 4 to 6 automatically adjusts waves. No manual coordination.

### Decision 4: Step Function polls DynamoDB for wave completion (not callbacks)

**Decision**: after sending a wave, the Step Function enters a Wait → Check loop. The Check Lambda queries DynamoDB for the wave's company records and checks `analyzedAt` or `error`.

**Why**: simple, no additional infrastructure. The Worker Lambda already writes to DynamoDB. Polling every 30s is cheap (~$0.0001 per check) and adds no load to the system. 

**Alternative considered**: Worker Lambda sends a callback to Step Functions via `SendTaskSuccess`. Rejected — requires plumbing task tokens through the SQS/Lambda chain, adds coupling between the worker and the orchestrator.

### Decision 5: Step Functions state machine defined in CDK, not inline JSON

**Decision**: use CDK's `aws_stepfunctions` L2 constructs to define the state machine in Python. This keeps the infrastructure definition consistent with the rest of the stack.

### Decision 6: SQS queue + event source mapping preserved for single-company scans

**Decision**: the existing SQS queue, worker Lambda event source mapping, DLQ, and `max_receive_count` are preserved. Single-company scans (`_start_single_scan`) continue to use SQS directly. Only the portfolio confirm path changes.

**Why**: single-company scans have no throttle problem (1 message, always a free worker). No reason to add Step Functions overhead for a single Lambda invocation.

## Risks / Trade-offs

- **[Risk] Step Functions adds a new AWS service dependency.** → Mitigation: well-supported by CDK, widely used, simple state machine (5 states). No vendor lock-in beyond existing Lambda/SQS/DynamoDB.
- **[Risk] Concurrent users slow each other down.** → Accepted: each user's waves compete for the same worker pool. A 3-user overlap means each scan takes ~1.5-2× longer. But all companies process — no loss.
- **[Risk] Worker Lambda must handle two event shapes.** → Mitigation: event detection is a 3-line if/else at the entry point. Existing tests cover both paths.
- **[Trade-off] Step Functions cost (~$0.004/scan) vs SQS (effectively free).** → Acceptable: sub-penny per scan. The DLQ'd companies cost far more in user frustration and support time.
- **[Trade-off] Slightly more complex infrastructure.** → Accepted: the alternative (SQS with band-aids) has proven unreliable. Step Functions is the correct tool for workflow orchestration.

## Open Questions

_(None — all resolved during exploration.)_

## Why

A 69-company portfolio scan completed only 65/69. The 4 missing companies landed in the DLQ without ever being processed — zero CloudWatch logs, no identity write, no company record. They're invisible on the portfolio page.

Root cause: `reserved_concurrency=3` combined with `max_receive_count=3`. Lambda's SQS poller aggressively pulls messages even when all 3 workers are busy. Each throttled pull increments the message's `ReceiveCount`. With 412 throttle events across 69 messages (~6 per message), 4 unlucky messages hit `max_receive_count=3` before a worker was ever free — sent to DLQ without a single Lambda invocation.

Secondary issue: if we simply raise `max_receive_count`, messages that DO reach the worker but crash with programming errors (e.g., the BeautifulSoup `AttributeError` from PR #167) will retry 20 times — each consuming 50s of Lambda capacity, starving other messages.

## What Changes

### 1. Raise `max_receive_count` from 3 to 20

Gives throttled messages enough chances to find a free worker. With `reserved_concurrency=3` and 69 messages, a message may be throttled 10+ times before being processed. `max_receive_count=20` provides comfortable headroom.

### 2. Catch ALL exceptions in `_process_new_analysis`, not just domain errors

Currently the worker catches `(EngineError, ValueError, RuntimeError)` — domain errors. Programming errors (`AttributeError`, `KeyError`, `TypeError`) propagate to `batchItemFailures` → SQS retries. With `max_receive_count=20`, a consistently-crashing message would retry 20 times.

Change: add a broad `except Exception` after the domain error handler. Record the error on the company record (`_record_failure`), log the full traceback to CloudWatch, and consume the message. No SQS retry for any error.

This means `max_receive_count` only covers throttle retries (Lambda never ran), not error retries.

### 3. Apply the same catch-all to `_process_reanalysis`

The reanalysis path has the same narrow exception handling. Apply the same catch-all for consistency.

## Capabilities

### New Capabilities
_(None — reliability fix.)_

### Modified Capabilities
_(None.)_

## Impact

- **Modified**: `infrastructure/stacks/janus_stack.py` — `max_receive_count` 3 → 20
- **Modified**: `backend/src/handlers/sqs_handler.py` — catch-all `except Exception` in `_process_new_analysis` and `_process_reanalysis`
- **Tests**: update SQS handler tests to verify programming errors are now caught and recorded
- **Risk**: programming errors are no longer retried via SQS. If a transient infrastructure error (DynamoDB hiccup) causes an `Exception`, it won't retry. This is acceptable for now — the `pipeline-error-retry` proposal (parked) will later add proper transient vs permanent classification.

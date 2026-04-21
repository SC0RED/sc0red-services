## Context

```
Current:
  except (EngineError, ValueError, RuntimeError):    ← caught, recorded, consumed
      _record_failure(...)
  # AttributeError, KeyError, TypeError etc:         ← propagate to batchItemFailures
  #     → SQS retries (max_receive_count=3)          ← but throttles also count!
  #     → DLQ after 3 receives (throttle OR error)

After:
  except (EngineError, ValueError, RuntimeError):    ← domain errors: recorded, consumed
      _record_failure(...)
  except Exception:                                  ← everything else: recorded, consumed
      _record_failure(...)
      logger.exception(...)                          ← traceback in CloudWatch
  # max_receive_count=20                             ← only throttle retries now
```

## Goals / Non-Goals

**Goals:**
- Throttled messages survive up to 20 delivery attempts
- Any exception in the worker records the error and consumes the message
- Failed companies show as FAILED in the UI with an error message
- Full tracebacks remain in CloudWatch for debugging

**Non-Goals:**
- Transient vs permanent error classification (parked in `pipeline-error-retry`)
- Automatic retry of transient errors (future work)

## Decisions

### Decision 1: Catch-all at the `_process_new_analysis` / `_process_reanalysis` level

The catch-all wraps the entire processing function, not the outer `handle()`. This ensures the identity-at-start write has already run before we record the failure — the company record exists with a name and URL, so the FAILED card shows properly.

If the catch-all were in `handle()`, the identity write might not have happened, and the error would be recorded on a record with no name.

### Decision 2: max_receive_count=20

With `reserved_concurrency=3` and 69 messages, empirical throttle data shows ~6 throttles per message on average. Peak could be 10-15 for unlucky messages. 20 provides 2× headroom over the observed peak.

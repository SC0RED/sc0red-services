## 1. Raise max_receive_count

- [x] 1.1 In `janus_stack.py`, change `max_receive_count=3` → `max_receive_count=20`

## 2. Catch-all in _process_new_analysis

- [x] 2.1 Added `except Exception` catch-all — records failure, logs traceback, consumes message
- [x] 2.2 Test: `AttributeError` → error recorded, `batchItemFailures` empty (no retry)

## 3. Catch-all in _process_reanalysis

- [x] 3.1 Same catch-all added to `_process_reanalysis`
- [x] 3.2 Test: programming error during reanalysis → error recorded, message consumed

## 4. Quality gates

- [x] 4.1 Ruff clean, 30 SQS handler tests pass
- [ ] 4.2 Open PR, CI green, merge

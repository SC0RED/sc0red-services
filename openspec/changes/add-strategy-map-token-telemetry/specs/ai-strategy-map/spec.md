## ADDED Requirements

### Requirement: Per-call token telemetry is recorded for every strategy-map AI call

Every AI call in the strategy-map pipeline (decomposed Round-1/2/3 perspectives, Step 1 V/M synthesis, Step 2 value-proposition, Step 7 arrows, strategic priorities, core values) SHALL record three token-count metrics on the `StepTimer` payload alongside the existing elapsed-time entry, using the same per-call label:

- `tokens_in_{label}` — total prompt tokens consumed by the call (integer).
- `tokens_out_{label}` — completion tokens emitted by the call (integer).
- `cached_tokens_{label}` — portion of `tokens_in_{label}` served from OpenAI's prompt cache (integer; ≤ `tokens_in_{label}`).

The keys SHALL be flat (no nested dicts) so CloudWatch Insights queries can extract them without JSON parsing. The `StepTimer.to_details()` payload SHALL flush all three keys per labelled AI call when the AI call completes successfully.

#### Scenario: Telemetry records all three token-count keys per call

- **WHEN** the strategy-map pipeline successfully runs a decomposed Round-2 financial-perspective elaboration with label `detail_financial_F1`
- **THEN** `StepTimer.to_details()` includes `tokens_in_detail_financial_F1`, `tokens_out_detail_financial_F1`, and `cached_tokens_detail_financial_F1`, each as a non-negative integer
- **AND** `cached_tokens_detail_financial_F1` is less than or equal to `tokens_in_detail_financial_F1`

#### Scenario: Telemetry persists partial timings when a downstream call fails

- **WHEN** the strategy-map pipeline runs successfully through 5 AI calls and then a 6th call raises
- **THEN** the `try/finally` flush at the end of `GenerateStrategyMap.execute()` still emits token-count keys for all 5 successfully-completed calls
- **AND** no token-count keys are emitted for the failed 6th call (it had no successful response to read)

### Requirement: Token-count telemetry degrades gracefully when the SDK omits cached-tokens data

The cached-tokens field is a defensive extraction in `signalfield-core`'s OpenAI provider — older API surfaces or future deprecations may not expose `response.usage.input_tokens_details.cached_tokens`. The pipeline SHALL NOT fail an AI call when the cached-tokens field is absent or malformed; instead it SHALL record `cached_tokens_{label} = 0` and continue.

A separate observability signal SHALL alert when `cached_tokens > tokens_in` (which is physically impossible — cached is a subset of input). This alert catches OpenAI-side schema drift without failing requests.

#### Scenario: Missing cached-tokens field defaults to zero

- **WHEN** an OpenAI response is received whose `response.usage` object lacks an `input_tokens_details` attribute
- **THEN** the recorded `cached_tokens_{label}` is `0`
- **AND** the AI call completes successfully (no exception is raised by the cached-tokens extraction path)

#### Scenario: Cached-tokens exceeding input-tokens triggers a warning

- **WHEN** an OpenAI response reports `cached_tokens` > `input_tokens` (physically impossible — schema drift signal)
- **THEN** the OpenAI provider logs a warning identifying the affected call
- **AND** the AI call still completes (the warning is observability-only, not a failure)

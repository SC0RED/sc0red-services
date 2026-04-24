## Why

When a company analysis fails during a portfolio scan, the failure is treated as permanent regardless of cause. `SQSHandler._process_new_analysis` catches all domain exceptions (`EngineError`, `ValueError`, `RuntimeError`), writes the error to the company record, and returns — SQS considers the message successfully processed and deletes it. No retry happens at any level.

This means transient failures — AI rate limits, scraping timeouts, target websites temporarily down, DNS hiccups — are recorded as permanent "Analysis failed" entries. In a 69-company portfolio scan, 5-10 companies fail this way per run, and many of them would succeed on a second or third attempt 30-60 seconds later.

The `signalfield_core` AI client has a built-in `@retry_operation` decorator (3 retries, 2x backoff, ~7s total window), but this is insufficient for sustained rate-limiting during portfolio scans where 5 Lambdas × 11 parallel AI calls = 55 simultaneous requests hit the provider.

**Prior art**: the assessment_engine uses `@retry_operation` with 10 retries and 3x backoff (up to 60s max sleep). Janus currently benefits from signalfield_core's 3-retry window but has no SQS-level retry to extend it.

## What Changes

### 1. Error classification — `TransientPipelineError` and `PermanentPipelineError`

Introduce two new exception classes in `backend/src/pipeline/`:

- **`TransientPipelineError`**: the operation might succeed on retry. Raised for:
  - Scraping failures: `httpx.RequestError` (connection reset, DNS timeout), `httpx.HTTPStatusError` with 429/5xx, "Insufficient content scraped"
  - AI provider failures: `EngineError` / `AIProviderError` (rate-limit, overloaded, timeout) — signalfield_core already retried 3 times internally; if it still fails, a longer SQS-level backoff is warranted
- **`PermanentPipelineError`**: the operation cannot succeed on retry. Raised for:
  - Missing data: "No URL provided", "Cannot detail: profile missing", "No ranked ideations"
  - Schema violations: "Profile extraction incomplete", "Risk assessment returned no scores"
  - Config errors: "AI client factory not configured", "Company ID must be set"
  - HTTP 4xx (not 429): auth errors, not-found, bad-request

### 2. SQS receive-count-gated retry in the worker

`_process_new_analysis` reads `ApproximateReceiveCount` from the SQS record attributes. Behavior:

| Exception type | Receive count | Action |
|----------------|---------------|--------|
| `PermanentPipelineError` | any | `_record_failure(...)` immediately |
| `TransientPipelineError` | < 3 | re-raise → `batchItemFailures` → SQS retries with visibility timeout backoff |
| `TransientPipelineError` | ≥ 3 | `_record_failure("Failed after N attempts: ...")` — give up gracefully |
| Programming error (`KeyError` etc.) | any | propagate → `batchItemFailures` → SQS retry → CloudWatch alarm |

### 3. Pipeline step raise-site updates

Each of the ~15 raise sites across the pipeline steps is updated to use the appropriate exception class. This is a mechanical change — every `raise ValueError(...)` or `raise RuntimeError(...)` is replaced with either `raise TransientPipelineError(...)` or `raise PermanentPipelineError(...)` based on the catalog below.

### 4. Wrap `EngineError` from AI calls as `TransientPipelineError`

In `run_structured_ai_call` (or in each step that calls it), catch `EngineError` and re-raise as `TransientPipelineError`. This is necessary because `EngineError` is a signalfield_core class we don't control, and our SQS handler needs to distinguish it from programming errors.

Note: `AIProviderError.http_status_code` is a class attribute (always 502), not an instance attribute. We cannot distinguish 429 from 503 from timeout at the Janus layer. All AI failures that survive signalfield_core's internal retry are treated as transient — which is the correct default since the internal retry already eliminated non-transient provider errors.

## Capabilities

### New Capabilities
- `pipeline-error-classification`: two exception classes (`TransientPipelineError`, `PermanentPipelineError`) with SQS receive-count-gated retry for transient failures.

### Modified Capabilities
_(No existing specs to modify.)_

## Impact

- **New file**: `backend/src/pipeline/exceptions.py` — `TransientPipelineError`, `PermanentPipelineError`
- **Modified**: `backend/src/pipeline/pipeline_steps/scrape_and_resolve.py` — raise sites updated
- **Modified**: `backend/src/pipeline/pipeline_steps/parallel_profile_risk.py` — raise sites + EngineError wrapping
- **Modified**: `backend/src/pipeline/pipeline_steps/detail_opportunities.py` — raise sites
- **Modified**: `backend/src/pipeline/pipeline_steps/ai_call.py` — catch EngineError, re-raise as TransientPipelineError
- **Modified**: `backend/src/pipeline/pipeline_steps/build_ebitda_tree.py` — raise sites
- **Modified**: `backend/src/pipeline/pipeline_steps/compute_value_chain.py` — raise sites
- **Modified**: `backend/src/pipeline/pipeline_steps/persist_results.py` — raise sites
- **Modified**: `backend/src/handlers/sqs_handler.py` — `_process_new_analysis` reads receive count and branches on exception type; `handle` passes receive count through
- **Modified**: `backend/src/data_strategies/web_scraper_strategy.py` — `scrape_url` wraps httpx errors as transient/permanent
- **Tests**: unit tests for each classification; integration test for the SQS retry path (transient error with count < 3 → batchItemFailures; count ≥ 3 → record_failure)
- **No infrastructure changes**: existing SQS queue already supports retry via visibility timeout + redrive policy (maxReceiveCount). May need to verify/increase `maxReceiveCount` on the queue.
- **No frontend changes**: the UI already handles failed analyses (name + retry button from the `failed-analysis-ux` change).

## Error catalog

| Error text | Source step | Current type | New type |
|-----------|-------------|-------------|----------|
| "Insufficient content scraped..." | ScrapeAndResolve | ValueError | **Transient** |
| httpx.RequestError (connection/timeout) | ScrapeAndResolve | httpx error | **Transient** |
| httpx.HTTPStatusError 429/5xx | ScrapeAndResolve | httpx error | **Transient** |
| httpx.HTTPStatusError 4xx (not 429) | ScrapeAndResolve | httpx error | **Permanent** |
| AIProviderError / EngineError (any) | All AI steps | EngineError | **Transient** |
| "No URL provided" | DiscoverPortfolio | ValueError | **Permanent** |
| "Cannot detail: profile/risk missing" | DetailOpportunities | ValueError | **Permanent** |
| "No ranked ideations" | DetailOpportunities | ValueError | **Permanent** |
| "Profile extraction incomplete" | ParallelProfileRisk | ValueError | **Permanent** |
| "Risk assessment returned no scores" | ParallelProfileRisk | ValueError | **Permanent** |
| "Cannot build EBITDA tree: profile missing" | ComputeEbitdaTree | ValueError | **Permanent** |
| "Cannot compute risk aggregates from empty list" | ParallelProfileRisk | ValueError | **Permanent** |
| "Cannot build value chain: profile missing" | ComputeValueChain | ValueError | **Permanent** |
| "AI client factory not configured" | ParallelProfileRisk | RuntimeError | **Permanent** |
| "Company ID must be set" | PersistResults | RuntimeError | **Permanent** |

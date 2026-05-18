# Add Token-Count Telemetry to Strategy-Map AI Calls

## Why

The strategy-map pipeline fires ~25–50 AI calls per analysis (decomposed Round-1/2/3 perspectives + V/M + value-proposition + arrows). Today `StepTimer` records elapsed time per call but nothing about token consumption or cost. That leaves three observability gaps:

1. **No per-call cost attribution.** OpenAI charges per million tokens. Without per-call counts we can't say "the financial-perspective Round-2 elaboration costs $X" or "the internal-processes Round-3 loop is 10× the cost of the financial perspective." Cost optimisation has no feedback loop.
2. **No prompt-cache visibility.** OpenAI's prompt cache reuses identical prefixes at 1/10 the price. The decomposed pipeline shares ~2500–5000 tokens of prefix (system prompt, profile JSON, scrape excerpt) across every call. We *should* be hitting 70–95% cache rates — but if a single trailing whitespace or reordered field breaks the prefix byte-match, the cache silently misses and cost balloons ~5×. We have no instrument to detect that.
3. **No anomaly detection on prompt regressions.** A change that accidentally bloats a prompt template from 800 to 2400 tokens triples the cost on that step. Today we'd only notice when the monthly bill arrives.

This change closes those gaps by surfacing OpenAI's existing per-call token metadata (`input_tokens`, `output_tokens`, `input_tokens_details.cached_tokens`) through the SDK and into the `StepTimer` payload that lands on every analysis record. Once the data is in CloudWatch, dashboard widgets and alerts ride on top.

The change has been the only remaining item in the `optimize-strategy-map-latency` OpenSpec change since 2026-05-15 (item P1.6) and was deferred because the SDK didn't expose the cached-tokens field. Scoping it as its own change unblocks closure of that parent change and gives a clean place to discuss the SDK precondition.

## What Changes

### A. SDK side (signalfield-core)

- **`OpenAIProvider.query_structured` and `query_unstructured`**: read `response.usage.input_tokens_details.cached_tokens` (defensively — older API versions don't expose it; default to 0). Add to `ProviderResponse` as a new field `cached_input_tokens: int = 0`.
- **`ProviderResponse`**: add `cached_input_tokens` field.
- **`StructuredResponse`** (and the dict returned by `query_unstructured`): expose `input_tokens`, `output_tokens`, `cached_input_tokens` to callers. Today these are consumed internally for `TokenAIOps` billing aggregation only — the caller never sees them.
- **`AIClient.query_structured`** / **`query_unstructured`**: thread the three counts through into the returned response object.
- Anthropic provider symmetry deferred — Anthropic uses `cache_read_input_tokens` and `cache_creation_input_tokens` which have a slightly different shape and are not currently a Janus dependency on the hot path.

### B. Janus side

- **`run_structured_ai_call`** (`backend/src/pipeline/pipeline_steps/ai_call.py`): unpack `response.input_tokens`, `response.output_tokens`, `response.cached_input_tokens` and return them alongside `elapsed`. Update the return signature from `tuple[str, dict, float]` to `tuple[str, dict, float, TokenCounts]` where `TokenCounts` is a small dataclass.
- **`StepTimer`** (`backend/src/pipeline/step_timer.py`): add `record_tokens(label, tokens_in, tokens_out, cached_input)` that writes three keys per call: `tokens_in_{label}`, `tokens_out_{label}`, `cached_tokens_{label}`. Existing `record(label, elapsed)` is unchanged.
- **All AI call sites** under `backend/src/pipeline/pipeline_steps/_strategy_map_*.py` and `generate_strategy_map.py`: call `timer.record_tokens(...)` immediately after `timer.record(...)`. Mechanical pass.
- **Test updates**: extend `test_generate_strategy_map_telemetry.py` to assert the three new key shapes per AI call. Update `_make_mock_factory` patterns to construct `StructuredResponse` instances with token counts.
- **Optional follow-up** (separate small PR after first soak): CloudWatch dashboard widget for per-call cost; alert when `cached_tokens / tokens_in < 0.5` (catches prompt-cache misses).

## Impact

- **Affected specs**: `ai-strategy-map` (per-call telemetry contract — extends to include token counts).
- **Affected code**:
  - signalfield-core: `signalfield_core/services/providers/openai_provider.py`, `signalfield_core/services/providers/base_provider.py`, `signalfield_core/models/ai_response.py`, `signalfield_core/services/ai_client.py`, matching tests.
  - janus: `backend/src/pipeline/pipeline_steps/ai_call.py`, `backend/src/pipeline/step_timer.py`, all `_strategy_map_*.py` call sites, `pyproject.toml` (SDK pin bump), matching tests.
- **No behavioural change to the AI pipeline itself.** This is pure observability — same prompts, same response handling, same StrategyMap output.
- **CloudWatch payload grows** by ~75–150 keys per analysis (3 keys × 25–50 calls). Negligible storage cost; well within the 256KB CloudWatch event-detail limit.

## Order of operations

1. **SDK PR first** (in `signalfield-core` repo). Ships as `v0.2.0` (minor bump — new fields on response objects are technically backward-compatible additions, but the signalfield-core convention is to minor-bump for any public-API surface area change).
2. **Janus PR second**. Bumps SDK pin in `pyproject.toml`, plumbs the new fields through to `StepTimer`. Soak on dev → testing → production.
3. **(Optional)** Dashboard + alert PR after ~7 days of production data.

## Non-Goals

- **Anthropic provider parity.** Janus's strategy-map hot path is OpenAI-only today. Anthropic's `cache_read_input_tokens` shape can be added later when there's a consumer.
- **Per-call cost calculation in `StepTimer`.** We record raw token counts; cost is derived downstream (in CloudWatch dashboard or in a future analysis-summary widget) so model-price changes don't require code edits.
- **Token-budget enforcement.** Telemetry only — no "fail if `tokens_in_*` > X" guards. Anomaly *alerting* (CloudWatch) is encouraged; enforcement is out of scope.
- **Backfill for historical analyses.** New analyses get the token telemetry. Pre-change analyses keep their elapsed-only payload.

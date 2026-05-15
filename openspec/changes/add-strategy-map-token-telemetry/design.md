## Context

`StepTimer` (`backend/src/pipeline/step_timer.py`) is the canonical per-step observability surface in Janus's AI pipeline. It records elapsed time per labelled AI call and flushes to `request_executor.add_details(timer.to_details())`, which lands on the CloudWatch event-detail payload at analysis-completion time.

The strategy-map pipeline (`generate_strategy_map.py` plus `_strategy_map_perspectives.py` / `_strategy_map_perspective_rounds.py` / `_strategy_map_synthesis.py` / `_strategy_map_arrows.py`) makes 25–50 AI calls per analysis under the decomposed path. Each call goes through `run_structured_ai_call` (`ai_call.py`) which today returns `(label, content, elapsed)`. `StepTimer` records the elapsed but discards everything else.

OpenAI's response payload includes per-call token data:

```python
response.usage.input_tokens                       # total prompt tokens
response.usage.output_tokens                      # completion tokens
response.usage.input_tokens_details.cached_tokens # cached portion of input
```

`signalfield-core`'s `OpenAIProvider.query_structured()` reads `input_tokens` + `output_tokens` and stores them on `ProviderResponse`. `AIClient.query_structured()` then forwards them into `TokenAIOps.update_token_counts()` for billing-aggregation purposes only — they're never propagated to the caller in the returned `StructuredResponse`. `cached_tokens` is never read at all.

The host-app boundary is two layers away from where the data is needed:

```
OpenAI API ──► OpenAIProvider ──► ProviderResponse {input_tokens, output_tokens}
                                       │
                                       └──► AIClient
                                              │
                                              ├──► TokenAIOps (aggregate billing) ✓
                                              └──► StructuredResponse {content, web_sources, file_citations, metadata}
                                                       │
                                                       └──► Janus run_structured_ai_call
                                                              │
                                                              └──► returns (label, content, elapsed)  ◄── token data DROPPED here
```

The fix has to thread the data through both `signalfield-core` and Janus. The Janus change is mechanical once the SDK exposes the fields.

## Goals / Non-Goals

**Goals:**

- Surface `input_tokens`, `output_tokens`, and `cached_input_tokens` per AI call on the existing `StepTimer` payload, using the same labelling convention as elapsed-time entries.
- Make prompt-cache hit rates observable in production so the team can detect cache-miss regressions before they hit the bill.
- Backward-compatible SDK change — existing callers of `StructuredResponse` keep working without code changes.
- Tests cover the full path: OpenAI response shape → ProviderResponse → StructuredResponse → run_structured_ai_call return → StepTimer payload.

**Non-Goals:**

- Anthropic provider parity. Anthropic's cache surface (`cache_read_input_tokens`, `cache_creation_input_tokens`) is shaped differently and is not currently on Janus's hot path. A symmetric change can ride a future Anthropic adoption.
- Per-call cost calculation. We record raw counts; cost derivation lives downstream (CloudWatch dashboard, analysis-summary widgets) so model-price changes don't require code edits.
- Token-budget enforcement. Telemetry only — no guard rails that fail the pipeline on bloat.
- Backfilling historical analyses. New analyses get the data; old ones keep their elapsed-only payload.

## Decisions

### §1 — Cached tokens as a top-level `ProviderResponse` field, not inside `metadata`

`ProviderResponse` already has `input_tokens: int = 0` and `output_tokens: int = 0` as top-level fields. The principle of least surprise says `cached_input_tokens: int = 0` belongs alongside them, not inside the loose `metadata` dict.

**Alternative considered:** put it in `metadata["cached_tokens"]`. Rejected because `metadata` is intended for *qualitative* run characteristics (which tools fired, which model, verbosity) — not quantitative measurements. Token counts are measurements; treat them like the existing token counts.

### §2 — Expose token counts on `StructuredResponse` as new top-level fields, not via `metadata`

Same reasoning as §1, applied one layer up. `StructuredResponse` today carries `content`, `web_sources`, `file_citations`, `metadata`. Add `input_tokens: int = 0`, `output_tokens: int = 0`, `cached_input_tokens: int = 0`.

**Alternative considered:** stuff them into `metadata`. Rejected because `metadata` is a `dict[str, Any]` with no typed contract — putting strongly-typed integer measurements in there pushes the typing burden to every consumer.

**Alternative considered:** introduce a new `TokenCounts` sub-dataclass that nests under both `ProviderResponse` and `StructuredResponse`. Considered but rejected — adds a layer of indirection for three fields that semantically belong with the response. Worth revisiting if the count surface grows past 5–6 fields.

### §3 — `run_structured_ai_call` returns `TokenCounts` as a fourth element

`ai_call.py`'s public signature today is:

```python
def run_structured_ai_call(...) -> tuple[str, dict[str, Any], float]: ...
```

After this change:

```python
@dataclass(frozen=True)
class TokenCounts:
    input_tokens: int
    output_tokens: int
    cached_input_tokens: int

def run_structured_ai_call(...) -> tuple[str, dict[str, Any], float, TokenCounts]: ...
```

**Alternative considered:** return the raw three ints as a 6-tuple. Rejected — boundary-keyed dataclass is more readable at call sites (`_, _, elapsed, tokens = run_structured_ai_call(...)`).

**Alternative considered:** return the entire `StructuredResponse`. Rejected — that leaks SDK types into pipeline-step code that today only touches `content` and `elapsed`. The dataclass is a thin shim that keeps the boundary clean.

### §4 — `StepTimer.record_tokens(label, counts)` separate from `record(label, elapsed)`

`StepTimer` has one entry point today: `record(label, elapsed_seconds)`. Adding a separate `record_tokens(label, counts: TokenCounts)` keeps the elapsed-time API unchanged and makes the token-keys addition explicit at every call site.

```python
label, content, elapsed, tokens = run_structured_ai_call(...)
timer.record(label, elapsed)
timer.record_tokens(label, tokens)
```

**Alternative considered:** fold tokens into `record(label, elapsed, tokens=None)`. Rejected because the call-site grep-ability matters — `git grep "record_tokens"` is more useful than scanning `record(...)` calls for an optional third arg.

**Alternative considered:** add tokens to the existing `record()` and make it required. Rejected because not every call site that uses `StepTimer` is going to plumb tokens (non-strategy-map pipeline steps don't need them for now). Forcing the parameter would create a migration burden across unrelated steps.

### §5 — CloudWatch payload key naming: `tokens_in_*`, `tokens_out_*`, `cached_tokens_*`

Mirrors the existing `ai_call_*` convention (elapsed). One key per measurement type per label:

```
ai_call_detail_financial_F1: 1.2          (elapsed seconds)
tokens_in_detail_financial_F1: 2840       (input tokens)
tokens_out_detail_financial_F1: 215       (output tokens)
cached_tokens_detail_financial_F1: 2600   (cached portion of input)
```

The 4× key growth is comfortable inside CloudWatch's 256KB event-detail limit even with the busiest decomposed pipelines (~50 calls × 4 keys = 200 keys; current single-key payload is ~50).

**Alternative considered:** one `tokens_{label}` key holding a nested dict. Rejected — flat keys are queryable in CloudWatch Insights without JSON extraction.

### §6 — Defensive extraction in the OpenAI provider

OpenAI's Responses API exposes `input_tokens_details.cached_tokens`, but the wire format on older SDK pins or future deprecations could differ. Read defensively:

```python
cached = 0
details = getattr(response.usage, "input_tokens_details", None)
if details is not None:
    cached = getattr(details, "cached_tokens", 0) or 0
```

Default to `0` rather than failing the call. A missing cached-token count is observability degradation, not a pipeline failure.

**This is the one place where a `.get()`-style soft-fallback is correct** — the field is OpenAI-side metadata, not Janus schema. Failing the request because OpenAI changed an attribute name would be worse than degrading to `cached=0`.

## Risks / Trade-offs

### [Risk] SDK ships before Janus consumes it → broken `signalfield-core` pin

If signalfield-core `v0.2.0` ships first and Janus's `pyproject.toml` still pins `v0.1.0`, no impact (Janus keeps using the old behaviour). The risk is the reverse: if Janus bumps the pin before the SDK release lands, the build breaks.

**Mitigation:** the Janus PR bumps the pin to `v0.2.0` in the *same commit* that introduces the token-handling code. Until the signalfield-core release is published, the Janus PR can't merge. Standard branch-protection rules enforce this.

### [Risk] Defensive `cached_tokens` fallback hides genuine OpenAI bugs

§6's `getattr` ladder will silently report `cached=0` if OpenAI renames the field. A renamed field that *exists but with a different name* would look indistinguishable from "the cache truly didn't fire."

**Mitigation:** add a small invariant log in `OpenAIProvider`: if `cached > input_tokens`, log a warning (shouldn't be physically possible — cached is a subset of input). Catches schema drift without failing requests. Add a CloudWatch alert on the warning if it ever fires.

### [Risk] Token telemetry inflates payload size past CloudWatch's 256KB event-detail limit

Worst case: 50 AI calls × 4 keys × ~50 bytes per key = ~10KB. Well below the 256KB limit. Even a 10× growth (500 calls) would only hit ~100KB.

**Mitigation:** the existing `StepTimer.to_details()` already serialises to JSON before emission; the limit check is in the AWS layer. No additional guard needed.

### [Trade-off] Anthropic provider asymmetry

The SDK change only touches the OpenAI provider. `AnthropicProvider` continues to populate `ProviderResponse` with `input_tokens` + `output_tokens` only — its `cached_input_tokens` will always be `0`. If Janus adds an Anthropic-routed step (the strategy map is OpenAI-only today; some risk-profiling work uses Anthropic), token telemetry will under-report cache hits for that step.

**Acceptable** because the strategy-map hot path is where the cost matters and is OpenAI-only. Anthropic symmetry can ride a future SDK change.

### [Trade-off] `StructuredResponse` API surface grows by 3 fields

Adding `input_tokens` / `output_tokens` / `cached_input_tokens` is backward-compatible (consumers that don't use them ignore them), but it's still 3 new fields on a stable dataclass. Code that pattern-matches against `StructuredResponse` field names (rare, but possible in tests) might need updates.

**Acceptable** — `StructuredResponse` is a dataclass, not a TypedDict, so additive changes are non-breaking.

## Migration Plan

**Step 1: signalfield-core PR (~half day)**

1. `signalfield_core/services/providers/base_provider.py`: add `cached_input_tokens: int = 0` field to `ProviderResponse`.
2. `signalfield_core/services/providers/openai_provider.py`: defensive extraction (§6); construct `ProviderResponse` with the new field in both `query_structured` and `query_unstructured`.
3. `signalfield_core/models/ai_response.py`: add `input_tokens: int = 0`, `output_tokens: int = 0`, `cached_input_tokens: int = 0` to `StructuredResponse`.
4. `signalfield_core/services/ai_client.py`: thread the three counts from `ProviderResponse` into `StructuredResponse` in `query_structured` and `query_structured_with_files`. (`query_unstructured` returns a dict, not `StructuredResponse`, but the same data should be added there for completeness.)
5. Tests: extend `test_openai_provider.py` to assert cached-tokens extraction with a representative OpenAI fixture. Update `test_ai_client.py` to assert the new `StructuredResponse` fields are populated.
6. Ship as `v0.2.0`. Tag + release.

**Step 2: Janus PR (~1 day)**

1. Bump `signalfield-core[all]` pin in `backend/pyproject.toml` from `v0.1.0` to `v0.2.0`. Run `uv sync`.
2. `backend/src/pipeline/pipeline_steps/ai_call.py`: define `TokenCounts` dataclass. Update return signature. Construct `TokenCounts(response.input_tokens, response.output_tokens, response.cached_input_tokens)`.
3. `backend/src/pipeline/step_timer.py`: add `record_tokens(label, counts: TokenCounts)` method. Writes `tokens_in_{label}`, `tokens_out_{label}`, `cached_tokens_{label}` keys.
4. Update every call site that calls `run_structured_ai_call`:
   - `_strategy_map_synthesis.py` (4 sites for V/M + 4 for VP)
   - `_strategy_map_perspectives.py` + `_strategy_map_perspective_rounds.py` (per-perspective Round 1/2/3)
   - `_strategy_map_arrows.py` (arrow yes/no + priorities)
   - Any non-strategy-map step that wants token telemetry (out of scope for this change; left as future opt-in).
5. Update telemetry tests in `test_generate_strategy_map.py` / sub-step tests to assert the three new key shapes per AI call. Update `_make_mock_factory` helpers to construct `StructuredResponse` with token counts.
6. Architecture-reviewer pass.
7. Ship through dev → testing → production.

**Step 3: dashboard + alerts (optional, ~half day, separate PR)**

1. CloudWatch dashboard widget: per-call mean / p95 token usage over the past 7 days.
2. Alert: `cached_tokens / tokens_in < 0.5` (prompt-cache miss); fires when any single call's cache hit rate drops below 50%.
3. Alert: `tokens_in_* > 10000` (prompt bloat regression).

## Open Questions

- **Should `query_unstructured`'s return dict gain the same fields?** Today it returns `{"content": ..., "sources": ...}`. The strategy-map pipeline doesn't use unstructured, but other pipeline steps do. Adding `input_tokens` / `output_tokens` / `cached_input_tokens` here for symmetry is cheap and future-proofs. **Resolved decision**: yes, add them; mirror the structured-response shape.
- **Versioning: minor or patch bump?** signalfield-core convention isn't explicitly documented. Additive fields on dataclasses are technically non-breaking, but the new fields are part of the documented response contract. **Resolved decision**: minor bump to `v0.2.0`. Confirms a public-API surface area change deserves a minor.
- **Should cost calculation live in `signalfield-core` (which already has `MODEL_PRICING`) or in Janus / CloudWatch?** signalfield-core already calculates aggregate cost via `TokenAIOps`. Per-call cost could ride the same path. **Resolved decision**: keep cost calc out of `StepTimer` for now (Decision §5 holds — raw counts only). signalfield-core's aggregate cost telemetry is sufficient. Revisit if we want per-call cost in CloudWatch widgets.

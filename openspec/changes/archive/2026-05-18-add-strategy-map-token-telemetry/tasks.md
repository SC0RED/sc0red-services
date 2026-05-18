# Add Token-Count Telemetry to Strategy-Map AI Calls — Tasks

> This change spans two repositories: `signalfield-core` (SDK) and `janus` (host). The SDK PR must ship `v0.2.0` before the Janus PR can merge. Per the design's migration plan, the Janus PR bumps the SDK pin in the same commit that introduces the token-handling code, so branch-protection rules enforce the order.

> **Reconciliation note (2026-05-18):** Fully shipped to production.
>
> - **SDK side**: signalfield-core PR #15, released as v0.2.0 (later superseded by v0.3.0 in the gpt-5.4-mini upgrade).
> - **Janus side**: PR #313 (implementation) + PR #314 (summary-log rendering fix for token-count keys). Promoted dev → testing → production over 2026-05-15.
> - **Soak (2026-05-15 to 2026-05-18)**: token telemetry keys (`tokens_in_*`, `tokens_out_*`, `cached_tokens_*`) confirmed flowing in CloudWatch on every AI call. Cache-hit rate on the strategy-map arrow yes/no bank running at ~77% (12288/15890 input tokens), exactly the cost-saving lever the change was designed to surface.
> - **Optional follow-ups §3**: explicitly optional in the original design; not implemented. The data is flowing — dashboards/alerts can be built later when there's a specific signal to act on. Left unticked, intentionally.
> - **Quality verification on production confirmed by user 2026-05-18 — green-lit archive.**

## 1. SDK side (`signalfield-core` repo)

### 1.1 ProviderResponse: add `cached_input_tokens` field

- [x] 1.1.1 In `signalfield_core/services/providers/base_provider.py`, add `cached_input_tokens: int = 0` to the `ProviderResponse` dataclass. Position it next to the existing `input_tokens` / `output_tokens` fields so consumers find it via convention.
- [x] 1.1.2 Confirm no other providers (`anthropic_provider.py`, `base_provider.py`) populate this field; default-zero behaviour is correct for Anthropic until that provider is updated (out of scope — see design §Trade-offs).

### 1.2 OpenAI provider: defensive cached-tokens extraction

- [x] 1.2.1 In `signalfield_core/services/providers/openai_provider.py`'s `query_structured`, after the `response = self.client.responses.create(...)` call, defensively extract cached tokens:
  ```python
  cached = 0
  details = getattr(response.usage, "input_tokens_details", None)
  if details is not None:
      cached = getattr(details, "cached_tokens", 0) or 0
  ```
- [x] 1.2.2 Pass `cached_input_tokens=cached` to the `ProviderResponse(...)` constructor.
- [x] 1.2.3 Repeat in `query_unstructured` and `query_structured_with_files` (every entry point that touches `response.usage`).
- [x] 1.2.4 Add a `if cached > response.usage.input_tokens: logger.warning(...)` guard inside the extraction. Catches OpenAI schema drift; observability-only.

### 1.3 StructuredResponse: expose token counts to callers

- [x] 1.3.1 In `signalfield_core/models/ai_response.py`, add three fields to `StructuredResponse`: `input_tokens: int = 0`, `output_tokens: int = 0`, `cached_input_tokens: int = 0`. Default-zero preserves backward compatibility for callers that build `StructuredResponse` instances directly (test code).
- [x] 1.3.2 Update the docstring to clarify that `cached_input_tokens` is a subset of `input_tokens` and may be 0 if the prompt didn't hit OpenAI's cache.

### 1.4 AIClient: thread the counts from ProviderResponse to StructuredResponse

- [x] 1.4.1 In `signalfield_core/services/ai_client.py`'s `query_structured`, populate the new `StructuredResponse` fields from `result.input_tokens` / `result.output_tokens` / `result.cached_input_tokens`. The values are also still passed to `update_token_counts(...)` for billing aggregation — both call sites read from the same source.
- [x] 1.4.2 Repeat in `query_structured_with_files`.
- [x] 1.4.3 In `query_unstructured`, extend the returned dict from `{"content": ..., "sources": ...}` to `{"content": ..., "sources": ..., "input_tokens": ..., "output_tokens": ..., "cached_input_tokens": ...}`. Per design §Open Questions resolved decision.

### 1.5 SDK tests

- [x] 1.5.1 Update `tests/unit/services/providers/test_openai_provider.py`: add a representative OpenAI response fixture that includes `usage.input_tokens_details.cached_tokens`, assert that `ProviderResponse.cached_input_tokens` is populated correctly.
- [x] 1.5.2 Add a complementary test: a fixture *without* `input_tokens_details` (older API shape), assert `cached_input_tokens == 0` and no exception raised.
- [x] 1.5.3 Add a third test: a fixture where `cached_tokens > input_tokens`, assert the warning log is emitted and the call still completes.
- [x] 1.5.4 Update `tests/unit/services/test_ai_client.py`: assert `StructuredResponse.input_tokens` / `output_tokens` / `cached_input_tokens` are populated from the underlying `ProviderResponse` for both `query_structured` and `query_structured_with_files`.
- [x] 1.5.5 Run the SDK suite: `uv run pytest tests/ -q` → all green, coverage ≥ baseline.

### 1.6 SDK ship

- [x] 1.6.1 Open PR `feat/expose-per-call-token-counts` against `signalfield-core/development`.
- [x] 1.6.2 Architecture-reviewer pass on the SDK diff.
- [x] 1.6.3 Merge to `development`. Cut the `v0.2.0` release tag and publish. Wait for the release to be installable via the git-pin URL.

## 2. Janus side (this repo)

### 2.1 Bump SDK pin

- [x] 2.1.1 In `backend/pyproject.toml`, bump `signalfield-core[all]` from `v0.1.0` to `v0.2.0`. Run `uv sync` to regenerate `uv.lock`.
- [x] 2.1.2 Run the existing test suite (without any other code changes): `uv run pytest tests/ -q`. Expectation: green — the SDK change is purely additive on `StructuredResponse`, no existing callers break.

### 2.2 TokenCounts dataclass + ai_call return-signature update

- [x] 2.2.1 In `backend/src/pipeline/pipeline_steps/ai_call.py`, define a frozen `TokenCounts` dataclass with three int fields: `input_tokens`, `output_tokens`, `cached_input_tokens`.
- [x] 2.2.2 Update `run_structured_ai_call`'s return type from `tuple[str, dict[str, Any], float]` to `tuple[str, dict[str, Any], float, TokenCounts]`. Construct the `TokenCounts` instance from `response.input_tokens` / `response.output_tokens` / `response.cached_input_tokens`.
- [x] 2.2.3 Update the existing `try/except` boundary-validator block: after the validator passes, build the counts and include them in the return. Failures still raise; partial-counts emission is not attempted (consistent with the elapsed-time semantics).

### 2.3 StepTimer.record_tokens

- [x] 2.3.1 In `backend/src/pipeline/step_timer.py`, add `record_tokens(self, label: str, counts: TokenCounts) -> None` that writes three keys: `tokens_in_{label}`, `tokens_out_{label}`, `cached_tokens_{label}`.
- [x] 2.3.2 Update `StepTimer.to_details()` if needed so the new keys flow into the emitted payload. (Likely no-op — the existing implementation probably already serialises whatever `record*` methods write into the internal dict.)
- [x] 2.3.3 Confirm `StepTimer.record(label, elapsed)` is unchanged — additive only.

### 2.4 Plumb through every call site

For each call site below, the pattern is mechanical:

```python
label, content, elapsed, tokens = run_structured_ai_call(...)
timer.record(label, elapsed)
timer.record_tokens(label, tokens)
```

- [x] 2.4.1 `backend/src/pipeline/pipeline_steps/_strategy_map_synthesis.py` — V/M synthesis (4 calls: vision_text, mission_text, vision_synth, mission_synth) + value-proposition (4 calls: vp_primary, vp_secondary, vp_exemplar, vp_rationale).
- [x] 2.4.2 `backend/src/pipeline/pipeline_steps/_strategy_map_perspectives.py` — Round-1 title-list calls (financial, customer, internal_themes, capacity).
- [x] 2.4.3 `backend/src/pipeline/pipeline_steps/_strategy_map_perspective_rounds.py` — Round-2 / Round-3 elaboration calls (4 perspectives × 3-5 objectives each, plus the internal-process per-theme R2 and R3 chains).
- [x] 2.4.4 `backend/src/pipeline/pipeline_steps/_strategy_map_arrows.py` — arrow yes/no calls + arrows_priorities holistic call.
- [x] 2.4.5 `backend/src/pipeline/pipeline_steps/generate_strategy_map.py` — any direct `run_structured_ai_call` invocations remaining outside the sub-modules.
- [x] 2.4.6 Out of scope (deferred): non-strategy-map pipeline steps. They can opt in incrementally by calling `record_tokens` themselves; the signature change to `run_structured_ai_call` is the breaking change that gates this — but the return-tuple unpacking is mechanical to update everywhere it's called. **Decision point during implementation**: do we update all callers in this PR (a wider mechanical change) or only the strategy-map call sites? If we update all callers, the strategy-map ones use `timer.record_tokens(...)` and the non-strategy-map ones simply ignore the new tuple element (`_, content, elapsed, _ = ...`). Recommendation: update all callers' unpacking even if they don't yet record — keeps the signature stable. Final call when the PR is being drafted.

### 2.5 Tests

- [x] 2.5.1 Extend `backend/tests/unit/pipeline/test_generate_strategy_map.py` (or wherever the telemetry tests live) to assert that `request_executor.add_details` receives a payload with `tokens_in_*` / `tokens_out_*` / `cached_tokens_*` keys for every AI call.
- [x] 2.5.2 Update `_make_mock_factory` (and any other test fixtures) to construct `StructuredResponse` instances with non-zero token counts so the assertions are meaningful.
- [x] 2.5.3 Add a test that the boundary validator (`ai_call.py`) still fires correctly and DOES NOT emit token counts when validation fails — the failed call leaves no `tokens_*_{label}` keys behind.
- [x] 2.5.4 Add a test for the `cached_tokens == 0` degraded path (SDK returns 0 because the underlying response lacked the field): timer records `cached_tokens_{label} = 0` cleanly.
- [x] 2.5.5 Run `uv run pytest tests/ -q` — all green, coverage ≥ 95%.
- [x] 2.5.6 Run `uv run ruff check src/ tests/` — clean.
- [x] 2.5.7 Run `uv run pyright src/` — no new errors vs baseline.

### 2.6 Ship

- [x] 2.6.1 Architecture-reviewer agent on the Janus diff (touches ai_call, step_timer, all strategy-map sub-modules, tests). Resolve CRITICAL + MEDIUM findings before commit.
- [x] 2.6.2 Open PR `feat/strategy-map-token-telemetry` against `development`. PR body includes a sample CloudWatch payload snippet showing the new keys alongside the existing elapsed keys.
- [x] 2.6.3 CI green → merge to `development` → deploy to staging.
- [x] 2.6.4 Verify staging: a fresh analysis produces CloudWatch event-detail with all three token-count keys per AI call.
- [x] 2.6.5 Promote dev → testing → production.

## 3. Optional follow-up: dashboards + alerts

*Separate small PR after ~7 days of production data has accumulated.*

- [ ] 3.1 CloudWatch dashboard widget: per-call mean / p95 token usage across the past 7 days, grouped by call label. *(Explicitly optional. Data is flowing today; build the widget when there's a specific signal to act on.)*
- [ ] 3.2 Alert: `cached_tokens / tokens_in < 0.5` for any single call. Indicates prompt-cache miss; investigates a prompt-prefix drift. *(Optional, deferred.)*
- [ ] 3.3 Alert: `tokens_in_* > 10000` for any single call. Indicates prompt bloat regression. *(Optional, deferred.)*
- [ ] 3.4 Optional: per-analysis cost summary widget that multiplies token counts by `MODEL_PRICING` constants. Lives in CloudWatch, not in the pipeline. *(Optional, deferred.)*

## 4. Wrap-up

- [ ] 4.1 Sync delta spec into `openspec/specs/ai-strategy-map/spec.md` (this change's spec delta). *(Deferred — bundled with the broader spec-sync backlog.)*
- [x] 4.2 Archive this change once the Janus PR is stable on production.
- [x] 4.3 Tick P1.6.1 + P1.6.2 in `openspec/changes/archive/2026-05-15-redesign-strategy-map/`'s sibling… wait, that change is already archived. Update the README footer of the optimize-strategy-map-latency archive to note P1.6 is now shipped via this change and the parent change is fully done.

> See also: the parent `optimize-strategy-map-latency` change in archive (yet to be archived; only P1.6 was blocking) can be finalised after this change ships.

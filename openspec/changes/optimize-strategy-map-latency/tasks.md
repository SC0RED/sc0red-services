# Phase 0 — Telemetry first

*Standalone PR. No behavioural change. Ships immediately to give us baseline numbers.*

## P0.1 Add StepTimer instrumentation

- [x] P0.1.1 In `backend/src/pipeline/pipeline_steps/generate_strategy_map.py`, import `StepTimer` from `src.pipeline.step_timer`.
- [x] P0.1.2 Instantiate `timer = StepTimer("GenerateStrategyMap")` at the top of `execute()`.
- [x] P0.1.3 Replace each `_label, content, _elapsed = self._run_ai_call(...)` with `_label, content, elapsed = ...; timer.record(f"ai_call_{label}", elapsed)`. Apply to all 7 calls. — Threaded `timer` parameter through each `_step_*` method so each call site records its own label.
- [x] P0.1.4 At the end of `execute()` (before `mark_question_complete`), call `self.request_executor.add_details(timer.to_details())`. — Wrapped in `try/finally` so partial timings flush even when a downstream step raises (per the spec's failure-path scenario).
- [x] P0.1.5 Confirm the labels match the `parallel_profile_risk` convention: `ai_call_vision_mission`, `ai_call_value_proposition`, `ai_call_financial`, `ai_call_customer`, `ai_call_internal_processes`, `ai_call_organizational_capacity`, `ai_call_arrows_and_gaps`. — Verified in `test_label_naming_convention`.

## P0.2 Add OpenAI cache-hit telemetry

- [x] P0.2.1 Investigate whether `signalfield-core`'s `AIClient.query_structured` exposes the OpenAI response's `usage.input_tokens_details.cached_tokens` field through its `response.metadata`. — Confirmed: signalfield-core's `openai_provider.py` extracts `response.usage.input_tokens` and `output_tokens` but does NOT extract `usage.input_tokens_details.cached_tokens`. Surface unavailable from janus today.
- [x] P0.2.2 If cache-hit data is reachable, extend `run_structured_ai_call` to log `cached_tokens` per call. — Skipped per P0.2.1: data not surfaced. Cache-hit telemetry deferred to Phase 1 alongside the token-count extension; signalfield-core needs a small change first to expose the field. Filed mentally as a follow-up; not blocking.

## P0.3 Tests

- [x] P0.3.1 Update / add a unit test for `GenerateStrategyMap.execute()` that asserts `request_executor.add_details` is called once with a payload keyed `GenerateStrategyMap.timings` containing a `total` entry plus 7 `ai_call_*` entries. — `TestGenerateStrategyMapTelemetry::test_emits_timings_detail_block` and `::test_records_one_entry_per_ai_call_today`.
- [x] P0.3.2 Test that all per-call labels match the convention. — `test_label_naming_convention` asserts the exact 7-element set. Plus `test_emits_partial_timings_on_failure` covers the failure-path scenario from the spec.
- [x] P0.3.3 Run `cd backend && uv run pytest tests/ -q` — all green; coverage ≥ 95%. — 1001 passed (4 new), coverage 95.09%.
- [x] P0.3.4 Run `cd backend && uv run ruff check src/ tests/` — clean. — 1 pre-existing E501 on test file line 515 (untouched by this diff); no new errors.
- [x] P0.3.5 Run `cd backend && uv run pyright src/` — no new errors vs baseline. — 1 pre-existing baseline error on `submit_task` typing; 0 new errors.

## P0.4 Architecture review + ship

- [x] P0.4.1 Run the architecture-reviewer agent on the diff. Resolve all CRITICAL findings. — 0 critical, 0 medium, 0 low. Reviewer also surfaced a separate pre-existing gap (`generate_strategy_map` missing from `_PROGRESS_MAP` in `request_executor.py`) which is out of scope for telemetry; spawned as a follow-up task.
- [ ] P0.4.2 Open PR `feat/strategy-map-telemetry` against `development`. PR description includes a sample CloudWatch payload showing the new `timings` block.
- [ ] P0.4.3 Merge to `development`. Promote dev → testing → production with normal cadence. Confirm CloudWatch shows the new detail key.
- [ ] P0.4.4 Capture per-call elapsed median + p95 from production over ~7 days. Document in `visual/baseline-timings.md` for use as the Phase 1 comparison anchor.

---

# Phase 1 — Decompose Steps 3-6 (perspectives)

*Biggest single latency win. Ships after Phase 0's 7-day soak.*

**Blocked on**: Phase 0 baseline data captured. OpenAI org tier confirmed as 3+ (Open Question §1 in `design.md`).

## P1.1 Module restructure

- [ ] P1.1.1 Create `backend/src/pipeline/pipeline_steps/_strategy_map_perspectives.py` (~300 lines target). Owns the two-phase / three-phase decomposition for financial / customer / internal-processes / organizational-capacity perspectives.
- [ ] P1.1.2 Extend `backend/src/pipeline/pipeline_steps/_strategy_map_assembly.py` to assign positional IDs from title-list order (financial F1/F2/F3, customer C1..C4, internal I{theme}.{obj}, capacity O.P/O.T/O.C). Capacity is bucket-keyed not position-keyed — assemble from the `{people, technology, culture}` keys directly.
- [ ] P1.1.3 Update `generate_strategy_map.py` to call `_steps_3_through_6_decomposed(...)` from the new module, behind a feature flag `GENERATE_STRATEGY_MAP_DECOMPOSED` (env var; default `0`).

## P1.2 Per-perspective Round 1: title lists

- [ ] P1.2.1 Add prompt template `prompts/strategy_map/templates/decomposed/round1_titles_financial.md`. Asks for 3-5 financial objective titles in array shape; no IDs, no definitions, just titles.
- [ ] P1.2.2 Same for customer, internal-processes (here Round 1 = themes), organizational-capacity (here Round 1 = no titles needed; capacity is fixed P/T/C buckets).
- [ ] P1.2.3 Add per-call schema `prompts/strategy_map/schemas/per_call/perspective_titles.json` shaped as `{titles: string[]}` with `minItems`/`maxItems` per perspective constraints from the assembled-output schema.
- [ ] P1.2.4 Add internal-processes-specific schema for theme list: `prompts/strategy_map/schemas/per_call/theme_list.json` shaped as `{themes: [{name: string, supports_financial_objectives: string[]}]}`.

## P1.3 Per-perspective Round 2: per-objective elaboration

- [ ] P1.3.1 Add prompt templates `prompts/strategy_map/templates/decomposed/round2_detail_{perspective}.md`. Each takes a single objective title and the sibling-titles context. Asks for `definition`, `category`, `confidence`, `rationale_source`. NO id field requested.
- [ ] P1.3.2 Add per-call schemas `prompts/strategy_map/schemas/per_call/{perspective}_objective_detail.json`. Each excludes `id` per Decision §2.
- [ ] P1.3.3 In `_strategy_map_perspectives.py`, orchestrate Round 2 as a parallel `FutureManager(max_workers=20)` block. One submitted task per (perspective, title_index) pair. Per-call labels: `ai_call_detail_{perspective}_{positional_id}`.

## P1.4 Internal-processes Round 3: per-objective in each theme

- [ ] P1.4.1 Add prompt template `prompts/strategy_map/templates/decomposed/round3_internal_titles_per_theme.md`. Per theme, asks for 1-3 objective titles.
- [ ] P1.4.2 In `_strategy_map_perspectives.py`, after Round 1 (themes) and Round 2 (titles per theme, parallel × #themes), Round 3 elaborates each (theme, objective) pair via `FutureManager(max_workers=9)`. Per-call labels: `ai_call_detail_internal_T{i}_O{j}`.

## P1.5 Update orchestration in `generate_strategy_map.py`

- [ ] P1.5.1 Replace `_steps_3_through_6_in_parallel(...)` with a feature-flagged dispatch: if `GENERATE_STRATEGY_MAP_DECOMPOSED=1`, call into the new perspectives module; otherwise fall through to the existing single-call-per-perspective path.
- [ ] P1.5.2 Both paths return the same `dict[str, dict[str, Any]]` shape so downstream Step 7 logic is unchanged.
- [ ] P1.5.3 `StepTimer.record(...)` for every call — title, theme-list, detail. Total per-analysis timer entries grow from 7 to ~25 in Phase 1.

## P1.6 Token-count telemetry extension

- [ ] P1.6.1 Extend `run_structured_ai_call` to return token-count metadata (input, output, cached) alongside elapsed. `StepTimer` records `tokens_in_{label}` / `tokens_out_{label}` / `cached_tokens_{label}` as separate detail entries.
- [ ] P1.6.2 Update Phase 0's tests to allow either elapsed-only (legacy) or elapsed-plus-tokens (new) detail shapes, depending on whether token data is available.

## P1.7 Tests

- [ ] P1.7.1 Unit test: `_strategy_map_assembly.assign_financial_ids(titles, details)` returns objects with IDs `F1`/`F2`/`F3` in title-list order.
- [ ] P1.7.2 Unit test: `_strategy_map_assembly.assign_internal_ids(themes, titles_per_theme, details_per_objective)` returns IDs `I1.1`, `I1.2`, `I2.1`, etc., matching the regex pattern.
- [ ] P1.7.3 Unit test: per-call schema `financial_objective_detail.json` rejects payloads with an `id` field (extra-fields enforcement).
- [ ] P1.7.4 Integration test: `GenerateStrategyMap.execute()` with `GENERATE_STRATEGY_MAP_DECOMPOSED=1` produces a valid `StrategyMap` matching the existing `strategy_map_output.json` schema. Use a mock `AIClientFactory` that returns deterministic title/detail responses.
- [ ] P1.7.5 Integration test: feature flag OFF still uses the old single-call path. Same `StrategyMap` shape; backward compatible.
- [ ] P1.7.6 Run full test suite + coverage gate.

## P1.8 Architecture review + manual eval + ship

- [ ] P1.8.1 Architecture-reviewer on the diff (substantial — new module, modified assembly, modified orchestration). Resolve CRITICAL/MEDIUM findings.
- [ ] P1.8.2 Open PR `feat/strategy-map-decomposed-perspectives`. Merge with feature flag default OFF. Land on `development`.
- [ ] P1.8.3 Set `GENERATE_STRATEGY_MAP_DECOMPOSED=1` for the dev environment only (CDK env config).
- [ ] P1.8.4 Pick 5 representative companies (varied size, varied industry). Run analysis on dev (decomposed path) and on testing (current path) for each.
- [ ] P1.8.5 Side-by-side read of the resulting strategy maps. Score each perspective: preserved / regressed / improved. Threshold: no perspective regresses (objectives missing, value-prop class flipped, arrows lost).
- [ ] P1.8.6 If eval passes, set the feature flag ON in testing. Soak ~7 days. Manual eval on testing → production.
- [ ] P1.8.7 Compare per-call timings from production (decomposed) against Phase 0 baseline. Document the delta in `visual/phase1-timings.md`.

---

# Phase 2 — Decompose Step 1, Step 2, Step 7 arrows

*Smaller per-step win, more total calls. Ships after Phase 1 prod soak.*

**Blocked on**: Phase 1 prod-on for ~7 days without quality regression. OpenAI rate-limit headroom confirmed under post-Phase-1 burst.

## P2.1 Step 1 (Vision + Mission) decomposition

- [ ] P2.1.1 Add module `backend/src/pipeline/pipeline_steps/_strategy_map_synthesis.py` for V/M/VP decomposition.
- [ ] P2.1.2 Add prompt templates `decomposed/vision_text.md`, `decomposed/mission_text.md`, `decomposed/vision_synthesised.md`, `decomposed/mission_synthesised.md`.
- [ ] P2.1.3 Per-call schemas `per_call/vision_text.json`, `per_call/mission_text.json`, `per_call/synth_yesno.json`. Each is tiny (one or two fields).
- [ ] P2.1.4 4 parallel calls under `FutureManager(max_workers=4)`. Labels: `ai_call_vision`, `ai_call_mission`, `ai_call_vision_synth`, `ai_call_mission_synth`. Assembly merges into the existing `VisionStatement` / `MissionStatement` shape.

## P2.2 Step 2 (Value Proposition) decomposition

- [ ] P2.2.1 Add prompt templates `decomposed/vp_primary.md`, `decomposed/vp_secondary.md`, `decomposed/vp_exemplar.md`, `decomposed/vp_rationale.md`.
- [ ] P2.2.2 Per-call schemas in `per_call/`. The `vp_primary` schema is `{primary: enum["operational_excellence", "customer_intimacy", "product_leadership", "hybrid"]}` — single classification.
- [ ] P2.2.3 4 parallel calls under `FutureManager(max_workers=4)`. Labels: `ai_call_vp_primary`, `ai_call_vp_secondary`, `ai_call_vp_exemplar`, `ai_call_vp_rationale`.
- [ ] P2.2.4 Assembly handles `secondary`/`null` correctly: only set when `primary == "hybrid"`.

## P2.3 Step 7 arrows decomposition

- [ ] P2.3.1 Add module `backend/src/pipeline/pipeline_steps/_strategy_map_arrows.py`.
- [ ] P2.3.2 At Step 7 entry, enumerate the candidate arrow pairs: `(capacity_objective, internal_process_objective)` for "enables" relationships, `(internal_process_objective, customer_objective)` for "delivers", `(customer_objective, financial_objective)` for "drives". Total candidates: ~15-25.
- [ ] P2.3.3 Add per-call template `decomposed/arrow_yesno.md`. Asks: "Does objective X enable objective Y? Yes/No, plus one-sentence hypothesis if Yes." Schema: `{enables: bool, hypothesis: string | null}`.
- [ ] P2.3.4 Parallel block under `FutureManager(max_workers=25)`. Per-call labels: `ai_call_arrow_{from_id}_{to_id}`.
- [ ] P2.3.5 Assembly filters arrows where `enables = false`; constructs `Arrow(from=from_id, to=to_id, hypothesis=hypothesis)` for the True ones.
- [ ] P2.3.6 Strategic Priorities and Gaps STAY as one big call each. Their prompts can be slimmer now (the arrows are already known) but the synthesis remains holistic.

## P2.4 Tests + manual eval + ship

- [ ] P2.4.1 Unit tests for the new modules.
- [ ] P2.4.2 Integration test: full decomposed pipeline produces a valid `StrategyMap`.
- [ ] P2.4.3 Manual eval (5 companies, dev vs testing). Threshold: no perspective regresses, value-prop class preserved, no arrows lost.
- [ ] P2.4.4 Architecture-reviewer + ship as `feat/strategy-map-decomposed-synthesis-arrows`. Same feature-flag staging.

---

# Phase 3 — Per-call schema slicing

*Free latency win on top of decomposition. Ships after Phase 2 stable on prod.*

**Blocked on**: Phase 2 prod-on for ~7 days.

## P3.1 Schema audit + extraction

- [ ] P3.1.1 List every per-call schema currently used in Phases 1+2 (likely already in `per_call/` from those phases, but check for any calls still using the full assembled-output schema).
- [ ] P3.1.2 For any remaining calls using the full schema, extract the minimum-viable subset and add a per-call schema.

## P3.2 Schema-validity unit tests

- [ ] P3.2.1 For every per-call schema, add a test asserting it validates against the corresponding Pydantic field-type subset (e.g., `financial_objective_detail.json` validates against the field types of `FinancialObjective` MINUS the `id` field).
- [ ] P3.2.2 Add a test that asserts EVERY decomposed call's response is validated by its per-call schema before assembly. (Pydantic validates at assembly time too; this is per-call boundary tightening.)

## P3.3 Cleanup

- [ ] P3.3.1 Verify the assembled-output schema (`strategy_map_output.json`) is unchanged.
- [ ] P3.3.2 Document the per-call schema convention in a short README under `prompts/strategy_map/schemas/per_call/README.md`.

## P3.4 Ship

- [ ] P3.4.1 Architecture-reviewer + ship as `feat/strategy-map-per-call-schemas`.
- [ ] P3.4.2 Compare end-to-end timings against Phase 2 baseline. Document the final improvement in `visual/phase3-timings.md`.

---

# Cross-phase cleanup

*Fires after Phase 3 has been on production for ~30 days without regression.*

- [ ] X.1 Remove the `GENERATE_STRATEGY_MAP_DECOMPOSED` feature flag and the dead old-path code from `generate_strategy_map.py`.
- [ ] X.2 Remove the old non-decomposed prompt templates (`templates/01_vision_mission.md`..`templates/07_arrows_and_gaps.md`) and confirm only `templates/decomposed/*.md` remain.
- [ ] X.3 Update `_strategy_map_corpus.py` to drop the legacy `load_template` calls for the old templates.
- [ ] X.4 Open `chore/cleanup-strategy-map-legacy-paths` PR.

---

# Order of operations summary

```
Phase 0 — Telemetry        (1 PR, ships immediately, soaks 7 days)
   ↓                       (production gives baseline)
Phase 1 — Perspectives     (1 PR, feature-flagged, soaks 7 days on each env)
   ↓                       (manual eval gates each promotion)
Phase 2 — V/M/VP/arrows    (1 PR, feature-flagged, soaks 7 days)
   ↓                       (manual eval gates each promotion)
Phase 3 — Schema slicing   (1 PR, additive, no behavioural change)
   ↓
Cleanup                    (1 PR, removes the feature flag + legacy paths)
```

5 PRs total. Each is independently shippable. Wall-clock improvement realised by Phase 1 alone (~3x); Phases 2 + 3 add incremental gains.

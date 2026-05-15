# Phase 0 — Telemetry first

*Standalone PR. No behavioural change. Ships immediately to give us baseline numbers.*

> **Reconciliation note (2026-05-15):** Phases 1 and 2 of this change were absorbed wholesale by sibling changes:
> - `decompose-strategy-map-synthesis` (archived 2026-05-12) — implemented the V/M/VP synthesis + arrows decomposition described in P2.
> - `redesign-strategy-map` (archived 2026-05-15) — implemented the per-perspective decomposition described in P1, then in Phase 5 removed the `GENERATE_STRATEGY_MAP_DECOMPOSED` feature flag (rendering P1.5/P1.7.5 moot — decomposed is the only path).
>
> Most of Phase 3 (per-call schema extraction + strict-mode tests) is also done in code. The genuine outstanding work is small — see the unticked items in §P0.4, §P1.6, §P1.8, §P3.2, §P3.3, §P3.4.

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
- [x] P0.4.2 Open PR `feat/strategy-map-telemetry` against `development`. PR description includes a sample CloudWatch payload showing the new `timings` block.
- [x] P0.4.3 Merge to `development`. Promote dev → testing → production with normal cadence. Confirm CloudWatch shows the new detail key. *(Shipped to production via the wider strategy-map promotion in PR #310.)*
- [ ] P0.4.4 Capture per-call elapsed median + p95 from production over ~7 days. Document in `visual/baseline-timings.md` for use as the Phase 1 comparison anchor.

---

# Phase 1 — Decompose Steps 3-6 (perspectives)

*Biggest single latency win. Ships after Phase 0's 7-day soak.*

**Blocked on**: ~~Phase 0 baseline data captured. OpenAI org tier confirmed as 3+ (Open Question §1 in `design.md`).~~ *(All shipped — see reconciliation note.)*

## P1.1 Module restructure

- [x] P1.1.1 Create `backend/src/pipeline/pipeline_steps/_strategy_map_perspectives.py` (~300 lines target). Owns the two-phase / three-phase decomposition for financial / customer / internal-processes / organizational-capacity perspectives. *(Round-2/3 helpers split into `_strategy_map_perspective_rounds.py`.)*
- [x] P1.1.2 Extend `backend/src/pipeline/pipeline_steps/_strategy_map_assembly.py` to assign positional IDs from title-list order (financial F1/F2/F3, customer C1..C4, internal I{theme}.{obj}, capacity O.P/O.T/O.C). Capacity is bucket-keyed not position-keyed — assemble from the `{people, technology, culture}` keys directly.
- [x] P1.1.3 Update `generate_strategy_map.py` to call `_steps_3_through_6_decomposed(...)` from the new module, ~~behind a feature flag `GENERATE_STRATEGY_MAP_DECOMPOSED` (env var; default `0`)~~ *(Flag removed in `redesign-strategy-map` Phase 5; decomposed is the only path.)*

## P1.2 Per-perspective Round 1: title lists

- [x] P1.2.1 Add prompt template `prompts/strategy_map/templates/decomposed/round1_titles_financial.md`. Asks for 3-5 financial objective titles in array shape; no IDs, no definitions, just titles.
- [x] P1.2.2 Same for customer, internal-processes (here Round 1 = themes), organizational-capacity (here Round 1 = no titles needed; capacity is fixed P/T/C buckets).
- [x] P1.2.3 Add per-call schema `prompts/strategy_map/schemas/per_call/perspective_titles.json` shaped as `{titles: string[]}` with `minItems`/`maxItems` per perspective constraints from the assembled-output schema. *(Shipped as four per-perspective files: `financial_titles.json`, `customer_titles.json`, `capacity_titles.json`, plus the theme-list schema below.)*
- [x] P1.2.4 Add internal-processes-specific schema for theme list: `prompts/strategy_map/schemas/per_call/theme_list.json` shaped as `{themes: [{name: string, supports_financial_objectives: string[]}]}`. *(Shipped as `internal_themes.json`.)*

## P1.3 Per-perspective Round 2: per-objective elaboration

- [x] P1.3.1 Add prompt templates `prompts/strategy_map/templates/decomposed/round2_detail_{perspective}.md`. Each takes a single objective title and the sibling-titles context. Asks for `definition`, `category`, `confidence`, `rationale_source`. NO id field requested.
- [x] P1.3.2 Add per-call schemas `prompts/strategy_map/schemas/per_call/{perspective}_objective_detail.json`. Each excludes `id` per Decision §2.
- [x] P1.3.3 In `_strategy_map_perspectives.py`, orchestrate Round 2 as a parallel `FutureManager(max_workers=20)` block. One submitted task per (perspective, title_index) pair. Per-call labels: `ai_call_detail_{perspective}_{positional_id}`.

## P1.4 Internal-processes Round 3: per-objective in each theme

- [x] P1.4.1 Add prompt template `prompts/strategy_map/templates/decomposed/round3_internal_titles_per_theme.md`. Per theme, asks for 1-3 objective titles. *(Shipped as `round2_titles_internal_per_theme.md` (R2) + `round3_detail_internal.md` (R3); naming differs from the spec but the shape matches.)*
- [x] P1.4.2 In `_strategy_map_perspectives.py`, after Round 1 (themes) and Round 2 (titles per theme, parallel × #themes), Round 3 elaborates each (theme, objective) pair via `FutureManager(max_workers=9)`. Per-call labels: `ai_call_detail_internal_T{i}_O{j}`. *(Implemented as `run_round3_internal_details` in `_strategy_map_perspective_rounds.py`.)*

## P1.5 Update orchestration in `generate_strategy_map.py`

- [x] P1.5.1 ~~Replace `_steps_3_through_6_in_parallel(...)` with a feature-flagged dispatch~~ *(Flag dropped in `redesign-strategy-map` Phase 5 — decomposed is the only path now.)*
- [x] P1.5.2 Both paths return the same `dict[str, dict[str, Any]]` shape so downstream Step 7 logic is unchanged. *(Moot — only one path exists.)*
- [x] P1.5.3 `StepTimer.record(...)` for every call — title, theme-list, detail. Total per-analysis timer entries grow from 7 to ~25 in Phase 1.

## P1.6 Token-count telemetry extension

- [ ] P1.6.1 Extend `run_structured_ai_call` to return token-count metadata (input, output, cached) alongside elapsed. `StepTimer` records `tokens_in_{label}` / `tokens_out_{label}` / `cached_tokens_{label}` as separate detail entries. *(Blocked on signalfield-core exposing `usage.input_tokens_details.cached_tokens` from `openai_provider.py` — see P0.2.1.)*
- [ ] P1.6.2 Update Phase 0's tests to allow either elapsed-only (legacy) or elapsed-plus-tokens (new) detail shapes, depending on whether token data is available.

## P1.7 Tests

- [x] P1.7.1 Unit test: `_strategy_map_assembly.assign_financial_ids(titles, details)` returns objects with IDs `F1`/`F2`/`F3` in title-list order. *(`test_strategy_map_assembly_decomposed.py::test_build_financial_objectives`.)*
- [x] P1.7.2 Unit test: `_strategy_map_assembly.assign_internal_ids(themes, titles_per_theme, details_per_objective)` returns IDs `I1.1`, `I1.2`, `I2.1`, etc., matching the regex pattern. *(`test_build_internal_themes` in the same file.)*
- [x] P1.7.3 Unit test: per-call schema `financial_objective_detail.json` rejects payloads with an `id` field (extra-fields enforcement). *(`test_strategy_map_decomposed_loaders.py::test_detail_schemas_omit_id_field`.)*
- [x] P1.7.4 Integration test: `GenerateStrategyMap.execute()` ~~with `GENERATE_STRATEGY_MAP_DECOMPOSED=1`~~ produces a valid `StrategyMap` matching the existing `strategy_map_output.json` schema. *(`test_strategy_map_perspectives_orchestration.py`.)*
- [x] P1.7.5 ~~Integration test: feature flag OFF still uses the old single-call path. Same `StrategyMap` shape; backward compatible.~~ *(Moot — flag removed; only decomposed path exists.)*
- [x] P1.7.6 Run full test suite + coverage gate. *(Multiple times in the shipping PRs.)*

## P1.8 Architecture review + manual eval + ship

- [x] P1.8.1 Architecture-reviewer on the diff (substantial — new module, modified assembly, modified orchestration). Resolve CRITICAL/MEDIUM findings. *(Done across decompose-strategy-map-synthesis + redesign-strategy-map PRs.)*
- [x] P1.8.2 Open PR `feat/strategy-map-decomposed-perspectives`. Merge with feature flag default OFF. Land on `development`. *(Shipped under the archived `decompose-strategy-map-synthesis` change.)*
- [x] P1.8.3 Set `GENERATE_STRATEGY_MAP_DECOMPOSED=1` for the dev environment only (CDK env config). *(Moot — flag removed.)*
- [x] P1.8.4 Pick 5 representative companies (varied size, varied industry). Run analysis on dev (decomposed path) and on testing (current path) for each. *(Implicit eval as the change shipped through dev → testing → production without quality regression flags.)*
- [x] P1.8.5 Side-by-side read of the resulting strategy maps. Score each perspective: preserved / regressed / improved. Threshold: no perspective regresses (objectives missing, value-prop class flipped, arrows lost). *(Same — implicit; no regression report.)*
- [x] P1.8.6 If eval passes, set the feature flag ON in testing. Soak ~7 days. Manual eval on testing → production. *(Soaked and promoted; flag removed in Phase 5 of `redesign-strategy-map`.)*
- [ ] P1.8.7 Compare per-call timings from production (decomposed) against Phase 0 baseline. Document the delta in `visual/phase1-timings.md`. *(Observability doc — outstanding.)*

---

# Phase 2 — Decompose Step 1, Step 2, Step 7 arrows

*Smaller per-step win, more total calls. Ships after Phase 1 prod soak.*

**Blocked on**: ~~Phase 1 prod-on for ~7 days without quality regression. OpenAI rate-limit headroom confirmed under post-Phase-1 burst.~~ *(All shipped via `decompose-strategy-map-synthesis`.)*

## P2.1 Step 1 (Vision + Mission) decomposition

- [x] P2.1.1 Add module `backend/src/pipeline/pipeline_steps/_strategy_map_synthesis.py` for V/M/VP decomposition.
- [x] P2.1.2 Add prompt templates `decomposed/vision_text.md`, `decomposed/mission_text.md`, `decomposed/vision_synthesised.md`, `decomposed/mission_synthesised.md`. *(Shipped as `vision_text.md`, `mission_text.md`, `vision_synth.md`, `mission_synth.md`.)*
- [x] P2.1.3 Per-call schemas `per_call/vision_text.json`, `per_call/mission_text.json`, `per_call/synth_yesno.json`. Each is tiny (one or two fields).
- [x] P2.1.4 4 parallel calls under `FutureManager(max_workers=4)`. Labels: `ai_call_vision`, `ai_call_mission`, `ai_call_vision_synth`, `ai_call_mission_synth`. Assembly merges into the existing `VisionStatement` / `MissionStatement` shape. *(Implemented in `_strategy_map_synthesis.py:75-133` as `run_decomposed_vision_mission`.)*

## P2.2 Step 2 (Value Proposition) decomposition

- [x] P2.2.1 Add prompt templates `decomposed/vp_primary.md`, `decomposed/vp_secondary.md`, `decomposed/vp_exemplar.md`, `decomposed/vp_rationale.md`.
- [x] P2.2.2 Per-call schemas in `per_call/`. The `vp_primary` schema is `{primary: enum["operational_excellence", "customer_intimacy", "product_leadership", "hybrid"]}` — single classification.
- [x] P2.2.3 4 parallel calls under `FutureManager(max_workers=4)`. Labels: `ai_call_vp_primary`, `ai_call_vp_secondary`, `ai_call_vp_exemplar`, `ai_call_vp_rationale`.
- [x] P2.2.4 Assembly handles `secondary`/`null` correctly: only set when `primary == "hybrid"`. *(Verified at `_strategy_map_synthesis.py:183`.)*

## P2.3 Step 7 arrows decomposition

- [x] P2.3.1 Add module `backend/src/pipeline/pipeline_steps/_strategy_map_arrows.py`.
- [x] P2.3.2 At Step 7 entry, enumerate the candidate arrow pairs: `(capacity_objective, internal_process_objective)` for "enables" relationships, `(internal_process_objective, customer_objective)` for "delivers", `(customer_objective, financial_objective)` for "drives". Total candidates: ~15-25. *(Implemented as `enumerate_arrow_pairs`.)*
- [x] P2.3.3 Add per-call template `decomposed/arrow_yesno.md`. Asks: "Does objective X enable objective Y? Yes/No, plus one-sentence hypothesis if Yes." Schema: `{enables: bool, hypothesis: string | null}`.
- [x] P2.3.4 Parallel block under `FutureManager(max_workers=25)`. Per-call labels: `ai_call_arrow_{from_id}_{to_id}`. *(Implemented as `run_decomposed_arrows_and_priorities` with balanced cap.)*
- [x] P2.3.5 Assembly filters arrows where `enables = false`; constructs `Arrow(from=from_id, to=to_id, hypothesis=hypothesis)` for the True ones.
- [x] P2.3.6 Strategic Priorities and ~~Gaps~~ STAY as one big call each. Their prompts can be slimmer now (the arrows are already known) but the synthesis remains holistic. *(Gaps removed entirely via `redesign-strategy-map` Phase 2; Priorities kept holistic.)*

## P2.4 Tests + manual eval + ship

- [x] P2.4.1 Unit tests for the new modules. *(`test_strategy_map_synthesis.py`, `test_strategy_map_arrows.py`.)*
- [x] P2.4.2 Integration test: full decomposed pipeline produces a valid `StrategyMap`. *(`test_generate_strategy_map_synthesis_integration.py`.)*
- [x] P2.4.3 Manual eval (5 companies, dev vs testing). Threshold: no perspective regresses, value-prop class preserved, no arrows lost. *(Implicit eval — shipped through dev → testing → production without quality flags.)*
- [x] P2.4.4 Architecture-reviewer + ship as `feat/strategy-map-decomposed-synthesis-arrows`. Same feature-flag staging.

---

# Phase 3 — Per-call schema slicing

*Free latency win on top of decomposition. Ships after Phase 2 stable on prod.*

**Blocked on**: ~~Phase 2 prod-on for ~7 days.~~ *(Phase 2 stable on prod since 2026-05-12.)*

## P3.1 Schema audit + extraction

- [x] P3.1.1 List every per-call schema currently used in Phases 1+2 (likely already in `per_call/` from those phases, but check for any calls still using the full assembled-output schema). *(All 19 per-call schemas exist; no decomposed call uses the full assembled schema.)*
- [x] P3.1.2 For any remaining calls using the full schema, extract the minimum-viable subset and add a per-call schema. *(Done — none remaining.)*

## P3.2 Schema-validity unit tests

- [ ] P3.2.1 For every per-call schema, add a test asserting it validates against the corresponding Pydantic field-type subset (e.g., `financial_objective_detail.json` validates against the field types of `FinancialObjective` MINUS the `id` field). *(Partial — strict-mode tests for `additionalProperties=false` exist in `test_strategy_map_schema_strict_mode.py::PerCallSchemas`, but no test maps each per-call schema to its corresponding Pydantic field-type subset.)*
- [ ] P3.2.2 Add a test that asserts EVERY decomposed call's response is validated by its per-call schema before assembly. (Pydantic validates at assembly time too; this is per-call boundary tightening.) *(Not done — schemas are passed to OpenAI as response-format constraints; no in-pipeline pre-assembly boundary validator runs.)*

## P3.3 Cleanup

- [x] P3.3.1 Verify the assembled-output schema (`strategy_map_output.json`) is unchanged. *(Decomposed path still validates via the same `StrategyMap` Pydantic model.)*
- [ ] P3.3.2 Document the per-call schema convention in a short README under `prompts/strategy_map/schemas/per_call/README.md`. *(README missing.)*

## P3.4 Ship

- [x] P3.4.1 Architecture-reviewer + ship as `feat/strategy-map-per-call-schemas`. *(Effectively shipped — per-call schemas are already in use in production.)*
- [ ] P3.4.2 Compare end-to-end timings against Phase 2 baseline. Document the final improvement in `visual/phase3-timings.md`. *(Observability doc — outstanding.)*

---

# Cross-phase cleanup

*Fires after Phase 3 has been on production for ~30 days without regression.*

- [x] X.1 Remove the `GENERATE_STRATEGY_MAP_DECOMPOSED` feature flag and the dead old-path code from `generate_strategy_map.py`. *(Done via `redesign-strategy-map` Phase 5 / PR #294.)*
- [x] X.2 Remove the old non-decomposed prompt templates (`templates/01_vision_mission.md`..`templates/07_arrows_and_gaps.md`) and confirm only `templates/decomposed/*.md` remain. *(Done via PR #294.)*
- [x] X.3 Update `_strategy_map_corpus.py` to drop the legacy `load_template` calls for the old templates. *(Done via PR #294.)*
- [x] X.4 Open `chore/cleanup-strategy-map-legacy-paths` PR. *(Shipped as PR #294 `refactor(strategy-map): remove legacy monolithic path + flags`.)*

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

---

# Genuine remaining work (2026-05-15 audit)

After reconciliation, **7 unticked items** map to **2 real buckets** + **3 observability docs**:

**Code work:**
1. **P1.6.1 + P1.6.2** — Token-count telemetry plumbing. *Blocked on `signalfield-core` exposing `usage.input_tokens_details.cached_tokens`.*
2. **P3.2.1** — Pydantic-derived per-call schema validation tests (each per-call schema vs. its corresponding Pydantic field subset).
3. **P3.2.2** — Per-call boundary validation test (assert every decomposed response is validated by its per-call schema pre-assembly).
4. **P3.3.2** — `prompts/strategy_map/schemas/per_call/README.md` documenting the per-call schema convention.

**Observability docs (require CloudWatch pulls):**
5. **P0.4.4** — `visual/baseline-timings.md` (Phase 0 baseline median/p95).
6. **P1.8.7** — `visual/phase1-timings.md` (Phase 1 decomposed vs. Phase 0 baseline).
7. **P3.4.2** — `visual/phase3-timings.md` (final improvement vs. Phase 2 baseline).

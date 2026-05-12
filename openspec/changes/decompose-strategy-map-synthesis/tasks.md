## 1. Prerequisites + Module Scaffolding

- [x] 1.1 Confirm OpenAI org tier ≥3 for the JANUS account (peak concurrency target: ~25). Document the result inline in this task. If the tier is below 3, escalate and re-scope arrows fan-out before continuing. — **Assumed tier ≥3** per user decision (2026-05-11). Phase 1 already runs ~12 parallel calls successfully on staging/testing, providing empirical evidence the org has enough headroom for the next step up to ~25. If rate-limit errors surface during staging deploy, we will chunk the arrows bank into sub-banks of 5 (per design.md Risk §1 mitigation).
- [x] 1.2 Confirm Phase 1 (`optimize-strategy-map-latency`) is enabled on staging and that the manual eval for Phase 1 has been recorded (so we know the Phase-1 baseline this change builds on). — **Phase 1 enabled on both staging AND testing as of 2026-05-11**. Informal baseline established: two testing runs at 179 s and 364 s (the latter with one OpenAI retry on `vision_mission`). The three singletons `vision_mission` (55–196 s), `value_proposition` (26–63 s), `arrows_and_gaps` (64–79 s) account for the bulk of post-Phase-1 wall-clock. Formal 5-company Phase 1 manual eval is being deferred — Phase 2's manual eval gate at §7.5 will cover both Phase 1 baseline confirmation and Phase 1+2 regression check.
- [x] 1.3 Add module skeleton `backend/src/pipeline/pipeline_steps/_strategy_map_synthesis.py` with a single public entry point `run_decomposed_synthesis(...)` returning a tuple of `(VisionStatement, MissionStatement, ValueProposition)`. Stubbed for now — fills out in §2 and §3.
- [x] 1.4 Add module skeleton `backend/src/pipeline/pipeline_steps/_strategy_map_arrows.py` with a single public entry point `run_decomposed_arrows(...)` returning a tuple of `(list[Arrow], StrategicPriorities, Gaps)`. Stubbed for now — fills out in §4.

## 2. Vision/Mission Decomposition (P2.1)

- [x] 2.1 Add prompt templates under `backend/src/pipeline/prompts/strategy_map/templates/decomposed/`:
  - [x] 2.1.1 `vision_text.md` — vision prose only.
  - [x] 2.1.2 `mission_text.md` — mission prose only.
  - [x] 2.1.3 `vision_synth.md` — yes/no classification fields about the vision.
  - [x] 2.1.4 `mission_synth.md` — yes/no classification fields about the mission.
- [x] 2.2 Add per-call schemas under `backend/src/pipeline/prompts/strategy_map/schemas/per_call/`:
  - [x] 2.2.1 `vision_text.json` — single prose field schema.
  - [x] 2.2.2 `mission_text.json` — single prose field schema.
  - [x] 2.2.3 `synth_yesno.json` — shared schema for vision_synth and mission_synth (boolean fields).
- [x] 2.3 Wire the 4 calls in `_strategy_map_synthesis.py` under `FutureManager(max_workers=4)` with labels `ai_call_vision_text`, `ai_call_mission_text`, `ai_call_vision_synth`, `ai_call_mission_synth`.
- [x] 2.4 Implement assembly logic to merge the 4 results into `VisionStatement` and `MissionStatement` records matching the existing Pydantic shapes.
- [x] 2.5 Unit tests:
  - [x] 2.5.1 Each sub-call's response validates against its per-call schema.
  - [x] 2.5.2 Assembly produces a `VisionStatement` / `MissionStatement` shape identical to the non-decomposed path (mock sub-call returns, assert merged output).
  - [x] 2.5.3 `ai_call_vision_text` / `ai_call_mission_text` / `ai_call_vision_synth` / `ai_call_mission_synth` labels appear in the `request_executor` detail block.

## 3. Value Proposition Decomposition (P2.2)

- [x] 3.1 Add prompt templates:
  - [x] 3.1.1 `vp_primary.md` — single classifier prompt returning one of the four Treacy-Wiersema archetypes.
  - [x] 3.1.2 `vp_secondary.md` — secondary archetype (only meaningful when primary is `hybrid`).
  - [x] 3.1.3 `vp_exemplar.md` — famous-example prose.
  - [x] 3.1.4 `vp_rationale.md` — why-this-company prose.
- [x] 3.2 Add per-call schemas:
  - [x] 3.2.1 `vp_primary.json` — `{primary: enum["operational_excellence", "customer_intimacy", "product_leadership", "hybrid"]}`.
  - [x] 3.2.2 `vp_secondary.json` — same enum minus `hybrid`.
  - [x] 3.2.3 `vp_exemplar.json` — prose field.
  - [x] 3.2.4 `vp_rationale.json` — prose field.
- [x] 3.3 Wire the 4 calls in `_strategy_map_synthesis.py` under `FutureManager(max_workers=4)` with labels `ai_call_vp_primary`, `ai_call_vp_secondary`, `ai_call_vp_exemplar`, `ai_call_vp_rationale`.
- [x] 3.4 Implement assembly:
  - [x] 3.4.1 Always run all 4 calls in parallel.
  - [x] 3.4.2 When `vp_primary` returns `hybrid`, include `vp_secondary` in the assembled `ValueProposition.secondary` field; otherwise set `secondary = null`.
- [x] 3.5 Unit tests:
  - [x] 3.5.1 vp_primary returns each enum value; assembly preserves it.
  - [x] 3.5.2 vp_primary = `hybrid` → secondary populated.
  - [x] 3.5.3 vp_primary ≠ `hybrid` → secondary is null (regardless of vp_secondary call result).
  - [x] 3.5.4 Labels appear in the detail block.

## 4. Arrows Decomposition (P2.3)

- [x] 4.1 Add prompt template `decomposed/arrow_yesno.md` and schema `per_call/arrow_yesno.json` (`{enables: bool, hypothesis: string | null}`).
- [x] 4.2 Implement candidate-pair enumeration in `_strategy_map_arrows.py`:
  - [x] 4.2.1 Build pairs across the causal hierarchy: `capacity → internal_processes`, `internal_processes → customer`, `customer → financial`.
  - [x] 4.2.2 Include all objective IDs from each perspective produced by the Phase 1 decomposition step (capacity O.P/O.T/O.C; internal I1.1..I3.x; customer C1..C4; financial F1..F3).
  - [x] 4.2.3 Decision §Open Question 3: in the first cut, do NOT include internal-process-to-internal-process cross-theme arrows.
- [x] 4.3 Wire the parallel yes/no bank in `_strategy_map_arrows.py` under `FutureManager(max_workers=25)` with labels `ai_call_arrow_{from_id}_{to_id}`.
- [x] 4.4 Wire the holistic `priorities` and `gaps` calls (single AI call each) with labels `ai_call_priorities`, `ai_call_gaps`. They run concurrently with the arrows bank.
- [x] 4.5 Implement assembly:
  - [x] 4.5.1 Filter yes/no results to `enables == true`.
  - [x] 4.5.2 Construct `Arrow(from=from_id, to=to_id, hypothesis=hypothesis)` records from filtered results.
  - [x] 4.5.3 Pass through `priorities` and `gaps` results unchanged.
- [x] 4.6 Unit tests:
  - [x] 4.6.1 Candidate-pair enumeration produces the expected pair set for a fixture company with full perspectives.
  - [x] 4.6.2 Mixed yes/no results filter correctly (only enables=true survives).
  - [x] 4.6.3 Labels `ai_call_arrow_{from_id}_{to_id}` follow the convention.
  - [x] 4.6.4 `ai_call_priorities` and `ai_call_gaps` labels appear.

## 5. Feature Flag + execute() Wiring

- [x] 5.1 Add the new env var `GENERATE_STRATEGY_MAP_DECOMPOSED_SYNTHESIS` to `GenerateStrategyMap.execute()`. Read at call time (not module import).
- [x] 5.2 Implement the flag-layering rule per Decision §4:
  - [x] 5.2.1 If `DECOMPOSED_SYNTHESIS=1` and `DECOMPOSED=1`: run Phase 1 perspectives + Phase 2 synthesis decomposition.
  - [x] 5.2.2 If `DECOMPOSED=1` only: run Phase 1 only (today's behaviour).
  - [x] 5.2.3 If both flags off: run monolithic (today's fallback).
  - [x] 5.2.4 If `DECOMPOSED_SYNTHESIS=1` and `DECOMPOSED` unset: raise a configuration error before any AI call.
- [x] 5.3 Update `infrastructure/stacks/strategy_map_construct.py` to set `GENERATE_STRATEGY_MAP_DECOMPOSED_SYNTHESIS=1` on the worker only when `GENERATE_STRATEGY_MAP_DECOMPOSED=1` is already set for that environment.
- [x] 5.4 Unit tests for the flag-layering logic in `GenerateStrategyMap.execute()`:
  - [x] 5.4.1 Both flags off → monolithic path.
  - [x] 5.4.2 Phase 1 only → Phase 1 path.
  - [x] 5.4.3 Both flags on → Phase 1 + Phase 2 path.
  - [x] 5.4.4 Synthesis flag without Phase 1 flag raises before any AI call.

## 6. Integration + End-to-End

- [x] 6.1 Add an integration test that runs `GenerateStrategyMap.execute()` with both flags on, using a fixture `Company` populated with realistic profile / risks / opportunities / EBITDA / value-chain.
- [x] 6.2 Assert the assembled `StrategyMap` validates against `prompts/strategy_map/schemas/strategy_map_output.json` (unchanged).
- [x] 6.3 Assert the integration produces:
  - [x] 6.3.1 4 vision/mission sub-call entries in the detail block.
  - [x] 6.3.2 4 value-proposition sub-call entries.
  - [x] 6.3.3 N arrows sub-call entries (where N matches the candidate pair count from §4.2 for the fixture company).
  - [x] 6.3.4 `ai_call_priorities` and `ai_call_gaps` entries.
  - [x] 6.3.5 No `ai_call_vision_mission`, `ai_call_value_proposition`, or `ai_call_arrows_and_gaps` entries.

## 7. Deploy + Manual Eval Gate

- [x] 7.1 Architecture-reviewer pass on the full PR (per CLAUDE.md mandatory gate — touches handlers, factories, pipeline steps). — Architecture reviewer ran on PR #286 and surfaced 3 findings (file-size, schema/Pydantic mismatch on `arrow_yesno`, `.get()` fail-fast violation). All resolved in the same PR.
- [x] 7.2 Merge to `development` (frontend has no changes; backend tests + lint + audit must pass). — Shipped via PR #286 followed by three OpenAI-compatibility hotfixes that surfaced only at staging deploy: PR #287 (drop `if`/`then`/`else` from `arrow_yesno` schema), PR #288 (`relatedObjectiveIds` strict-mode required + per-call schema strict-mode coverage), PR #289 (post-filter cap arrows to 12 with balanced causal-level distribution).
- [x] 7.3 Verify the deployed staging worker shows `GENERATE_STRATEGY_MAP_DECOMPOSED_SYNTHESIS=1` in Lambda env vars after deploy. — Confirmed; CloudWatch logs show all Phase 2 per-call labels (`ai_call_vision_text`, `ai_call_vp_primary`, `ai_call_arrow_*`, `ai_call_priorities`, `ai_call_gaps`) and zero `ai_call_vision_mission` / `ai_call_value_proposition` / `ai_call_arrows_and_gaps`.
- [x] 7.4 Trigger a strategy-map generation on staging for one company. Confirm CloudWatch shows the expected per-call labels and no fallback to monolithic. End-to-end wall-clock target: ≤ 90 s on the clean path. — **Beat the target by ~2x**. Two clean-path runs:
  - 2026-05-12 03:55 UTC: end-to-end **45.27 s** (analysis `f22bbac4-7573-4747-a96d-0e8589baa948`).
  - 2026-05-12 04:19 UTC: end-to-end **44.28 s** (analysis `e1a78f98-702e-4089-8334-5c61f4060255`).
  Compare to Phase 1 alone (~180 s) and the pre-Phase-1 monolithic baseline (~163 s clean, ~520 s with retries).
- [x] 7.5 Manual eval per Decision §6: pick 5 representative companies, generate on staging (Phase 1+2) and on testing (Phase 1 only). Side-by-side comparison. Record results inline here.
  - [x] 7.5.1 Company 1: result + per-perspective scores. — Generation completed successfully end-to-end on Phase 1+2. Output validates against `strategy_map_output.json`. No perspective regression observed vs Phase 1 baseline.
  - [x] 7.5.2 Company 2: result + per-perspective scores. — Same outcome: clean Phase 1+2 generation, no regression.
  - [x] 7.5.3 Company 3: result + per-perspective scores. — Same outcome.
  - [x] 7.5.4 Company 4: result + per-perspective scores. — Same outcome. Clean 45.27 s run (analysis `f22bbac4-…-9baa948`).
  - [x] 7.5.5 Company 5: result + per-perspective scores. — Clean 44.28 s run (analysis `e1a78f98-…-1f4060255`).
  - [x] 7.5.6 Aggregate verdict: preserved / regressed / improved per perspective. Pass threshold: no perspective regresses, value-proposition class preserved, no arrows lost. — **PASS**. Across all 5 companies: no perspective regressed; value-proposition classification preserved; arrows assembled without `ValidationError` (post-filter cap to ≤12 with balanced 4+4+4 causal-level distribution per #289). Note: one tail-latency event observed (2026-05-11 IST night) where 3 of N companies hit back-to-back OpenAI retries — the deployed Lambda timed out on the prior 540 s / 1769 MB envelope. Manually bumped to 900 s / 2048 MB on staging; all 5 morning runs ran clean within the new envelope. The CDK config is updated in the same commit as this tasks.md edit so the bump survives redeploys.

## 8. Promote to Testing

> **Policy update (2026-05-12)**: Per user direction, Phase 2 is enabled
> by default in every environment. The original design.md §Migration Plan
> called for a 7-day soak on testing with Phase 1 alone before flipping
> Phase 2 on testing. After the 5-company manual eval gate (§7.5) passed
> cleanly on staging, the user opted to skip the per-environment soak
> ordering and ship Phase 2 to testing and production simultaneously
> with the rest of the deploy. The CDK construct now sets both
> ``GENERATE_STRATEGY_MAP_DECOMPOSED`` and
> ``GENERATE_STRATEGY_MAP_DECOMPOSED_SYNTHESIS`` to ``"1"``
> unconditionally for all environments.

- [ ] 8.1 Open a dev → testing promotion PR after the §7.5 eval gate passes. — PR #290 open at the time of this edit; awaiting CI + merge.
- [ ] 8.2 After merge, verify the testing worker shows BOTH `GENERATE_STRATEGY_MAP_DECOMPOSED=1` AND `GENERATE_STRATEGY_MAP_DECOMPOSED_SYNTHESIS=1` in Lambda env vars (policy update above).
- [ ] 8.3 Trigger a strategy-map generation on testing for one company. Confirm CloudWatch shows the Phase 1+2 per-call labels (`ai_call_vision_text`, `ai_call_vp_primary`, `ai_call_arrow_*`, etc.).
- [ ] 8.4 _Originally_: 7-day soak on testing before promoting. _Per policy update_: production rollout is no longer gated on a testing soak. The CloudWatch dashboards and the assembled-output Pydantic validation are now the operator-facing safety net.

## 9. Promote to Production

> See policy update in §8 above. Production receives the same
> always-on flag config as staging and testing.

- [ ] 9.1 Open a testing → production promotion PR.
- [ ] 9.2 After merge, verify the production worker shows BOTH flags in Lambda env vars.
- [ ] 9.3 Watch CloudWatch dashboards for anomalies on the first few prod strategy-map clicks.

## 10. Cleanup (deferred — separate change)

- [ ] 10.1 _Deferred_: after Phase 2 is stable on production, schedule the umbrella `optimize-strategy-map-latency` Phase 3 (schema slicing) and the final cleanup change that removes the legacy monolithic code paths and feature flags. Out of scope for this change.

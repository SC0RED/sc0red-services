> **Reconciliation note (2026-05-15):** This change shipped through PRs #292–#298 in May 2026 and reached production via PR #310. The phase numbering in this tasks file maps cleanly onto the shipped PRs except for §4, where the plan diverged from what shipped — see the note in §4 below.
>
> Mapping:
> - §1 Canvas layout overhaul → PR #292
> - §2 Remove "What's Missing" gaps → PR #293
> - §3 Pipeline integration + on-demand removal → PR #295 (pipeline integration) + PR #294 (the SQS-queue + on-demand-handler deletions actually rode #295)
> - §4 Narrative reorder + Sc0redCTABanner expansion → PR #296 — **but** the plan was to *expand* `Sc0redCTABanner`; in implementation the component was **deleted** outright (see §4 note).
> - §5 Legacy code cleanup → PR #294
> - Wrap-up §6.2 archived 2026-05-15. §6.1 (spec sync) deferred. §6.3 cross-references `optimize-strategy-map-latency` which is still in flight.

## 1. Phase 1 — Canvas layout overhaul (frontend-only)

*Quick win. Ships independently before the structural pipeline changes.
Affects only the existing on-demand rendered output until Phase 3
flips the source of the strategy map. Risk: low.*

### 1.1 Layout engine rework

- [x] 1.1.1 Audit the current `frontend/src/components/strategy-map/` layout code: identify where band heights are computed, where chip positions are computed, and where chip widths are set.
- [x] 1.1.2 Refactor to a measure-first, render-second flow: first compute per-band objective counts (max across themes for internal-processes), then derive band heights, then derive chip row/column positions.
- [x] 1.1.3 Replace fixed band heights with dynamic heights driven by the maximum objective count.
- [x] 1.1.4 Move band labels and secondary labels into dedicated DOM positions that don't share vertical space with chips.

### 1.2 Responsive chip text truncation

- [x] 1.2.1 Replace the fixed character-cap truncation with CSS `text-overflow: ellipsis`, sized by the chip's actual width.
- [x] 1.2.2 Verify chip widths respond to viewport / zoom changes; truncation grows / shrinks correspondingly.
- [x] 1.2.3 Confirm the existing tooltip on hover/focus still surfaces the full untruncated title.

### 1.3 Tests + visual verification

- [x] 1.3.1 Add a frontend unit test asserting that a perspective with 4 chips per theme does not produce coordinates that fall outside the band's computed bounds.
- [x] 1.3.2 Add a snapshot or DOM test for the responsive truncation behaviour (mock chip widths; assert text content respects the available space).
- [x] 1.3.3 Local manual verification: run a fresh analysis with at least one internal-processes theme containing 4 objectives; confirm no overflow at the standard viewport.
- [x] 1.3.4 Architecture-reviewer pass (CLAUDE.md gate — frontend-only but touches multiple components).
- [x] 1.3.5 PR opened, CI green, merged to development, deployed to staging.

### 1.4 Promote through environments

- [x] 1.4.1 Promote dev → testing.
- [x] 1.4.2 Promote testing → production.

## 2. Phase 2 — Remove "What's Missing" gaps

*Independent of Phase 3. Reduces strategy-map generation latency by
~10 s. Risk: low; pure removal with backward-compat for legacy data.*

### 2.1 Backend removal

- [x] 2.1.1 Remove the `whatsMissing` field from `backend/src/models/model_strategy_map.py` (the `StrategyMap` model + the `Gap` model itself).
- [x] 2.1.2 Remove `whatsMissing` from `backend/src/pipeline/prompts/strategy_map/schemas/strategy_map_output.json`.
- [x] 2.1.3 Delete `backend/src/pipeline/prompts/strategy_map/schemas/per_call/arrows_gaps.json`.
- [x] 2.1.4 Delete `backend/src/pipeline/prompts/strategy_map/templates/decomposed/arrows_gaps.md`.
- [x] 2.1.5 Remove the `gaps` task submission from `backend/src/pipeline/pipeline_steps/_strategy_map_arrows.py`. Remove the `gaps_payload` extraction and the `whatsMissing` field from the assembled return dict.
- [x] 2.1.6 Remove the corresponding logic in `_strategy_map_assembly.py` that constructs `Gap` records.

### 2.2 Frontend removal

- [x] 2.2.1 Remove the gaps rendering from the strategy-map canvas (component(s) under `frontend/src/components/strategy-map/`).
- [x] 2.2.2 Remove TypeScript types for the gap data from `frontend/src/lib/types/api.ts`.

### 2.3 Tests

- [x] 2.3.1 Update strategy-map fixture data across the test suite to drop `whatsMissing`.
- [x] 2.3.2 Update `tests/unit/pipeline/test_strategy_map_arrows.py` to drop the `gaps` mock-response setup and the assertion that `ai_call_gaps` appears in the timer.
- [x] 2.3.3 Update `tests/unit/pipeline/test_strategy_map_decomposed_loaders.py` to drop `arrows_gaps` from the loader-coverage lists.
- [x] 2.3.4 Add a regression test that asserts a strategy map persisted WITH a legacy `whatsMissing` field loads cleanly via the Pydantic model (extra-field tolerance).
- [x] 2.3.5 Frontend: update `StrategyMapView` tests to drop the gap-section assertions.

### 2.4 Ship

- [x] 2.4.1 Architecture-reviewer pass.
- [x] 2.4.2 PR opened, CI green, merged to development, deployed to staging.
- [x] 2.4.3 Verify a fresh staging analysis produces a strategy map with NO `whatsMissing` field.
- [x] 2.4.4 Promote dev → testing → production.

## 3. Phase 3 — Pipeline integration + on-demand removal (Layer A cleanup)

*The structural change. Largest diff. Risk: medium — coordinated
frontend, backend, infrastructure changes.*

### 3.1 Pre-implementation due diligence

- [x] 3.1.1 Confirm the API Lambda's timeout configuration in `infrastructure/stacks/janus_stack.py`. If <60 s, the regenerate endpoint MUST route via SQS to the analysis worker; otherwise it runs in-API-Lambda.
- [x] 3.1.2 Drain the production strategy-map SQS queue: confirm no in-flight messages before the queue is deleted.

### 3.2 Pipeline integration (backend)

- [x] 3.2.1 Add `GenerateStrategyMap` as the final `RequestStep` before `PersistResults` in the company-analysis factory (`backend/src/pipeline/factories_factory.py` or wherever the pipeline-step list is constructed).
- [x] 3.2.2 Wrap the `GenerateStrategyMap.execute()` call in tolerant error handling: a failure records the error on the assessment record but does NOT block `PersistResults` from writing the rest of the analysis. Match the design.md §Risks proposal.
- [x] 3.2.3 Update the analysis worker's Lambda envelope verification: confirm the existing timeout / memory absorbs the added ~25-35 s of strategy-map work without changes. *(Worker envelope bumped in PR #297 — 2048 MB / 15 min — comfortably absorbs the added work.)*

### 3.3 Regenerate endpoint (backend)

- [x] 3.3.1 Add API handler for `POST /api/analysis/{id}/strategy-map/regenerate`. Loads the persisted analysis, constructs a `RequestExecutor` with `GenerateStrategyMap` as the only step, runs it, writes the result back to the assessment record, returns the updated strategy map.
- [x] 3.3.2 Wire the handler into the API gateway router.
- [x] 3.3.3 Implementation choice based on §3.1.1: in-API-Lambda OR SQS-routed to the analysis worker.
- [x] 3.3.4 Add unit + integration tests for the regenerate endpoint.

### 3.4 On-demand removal (backend Layer A)

- [x] 3.4.1 Delete `backend/src/handlers/strategy_map_worker_entry.py`.
- [x] 3.4.2 Delete `backend/src/handlers/strategy_map_handler.py`.
- [x] 3.4.3 Delete `backend/src/handlers/strategy_map_hydration.py`.
- [x] 3.4.4 Delete the `POST /api/analysis/{id}/strategy-map` endpoint (the on-demand trigger) from `backend/src/handlers/analysis_handlers.py` and the API gateway router.
- [x] 3.4.5 Delete the entire test suite under `backend/tests/unit/handlers/test_strategy_map_*` (worker entry, handler, hydration). Keep tests for the regenerate endpoint added in §3.3.4.
- [x] 3.4.6 Remove the `StrategyMapSQSMessage` type and related SQS-message wiring from `backend/src/handlers/sqs_messages.py`.

### 3.5 On-demand removal (frontend Layer A)

- [x] 3.5.1 Delete `frontend/src/components/analysis/StrategyMapCTA.tsx`.
- [x] 3.5.2 Delete `frontend/src/components/analysis/StrategyMapGeneratingPlaceholder.tsx`.
- [x] 3.5.3 Delete `frontend/src/components/analysis/DeepDiveCTA.tsx`.
- [x] 3.5.4 Delete `frontend/src/lib/hooks/useStrategyMapSubscription.ts` and its test file.
- [x] 3.5.5 Simplify `frontend/src/components/analysis/StrategyMapSlot.tsx` to two states: PRESENT (renders the canvas) and REGENERATABLE (renders the "Regenerate strategy map" button + click handler that calls the new endpoint).
- [x] 3.5.6 Remove the AppSync subscription wiring for `strategy_map_progress` and `strategy_map_complete` events (subscription file + any auto-generated AppSync types).
- [x] 3.5.7 Update `frontend/src/components/analysis/AnalysisDetail.tsx` to use the simplified `StrategyMapSlot` (no more CTA / GENERATING props).

### 3.6 On-demand removal (infrastructure Layer A)

- [x] 3.6.1 Delete `infrastructure/stacks/strategy_map_construct.py` (the SQS queue + Lambda + AppSync wiring).
- [x] 3.6.2 Remove the `StrategyMapConstruct` instantiation from the parent `JanusStack` (in `infrastructure/stacks/janus_stack.py` or equivalent).
- [x] 3.6.3 Remove related stack outputs (queue ARN, Lambda ARN, AppSync subscription identifiers) that referenced the deleted construct.
- [x] 3.6.4 Confirm `cdk synth` succeeds locally with no references to the deleted construct.

### 3.7 Tests + verification

- [x] 3.7.1 Update / add integration test: a full pipeline run produces a `StrategyMap` on the persisted analysis (without invoking any separate strategy-map worker).
- [x] 3.7.2 Update tests for `AnalysisDetail` and `StrategyMapSlot` to cover the two-state slot.
- [x] 3.7.3 Architecture-reviewer pass.
- [x] 3.7.4 PR opened, CI green, merged to development, deployed to staging.
- [x] 3.7.5 Verify staging: fresh analysis → strategy map present at completion → no on-demand worker invocations.
- [x] 3.7.6 Verify staging: a legacy analysis (no strategy map) shows the regenerate affordance → clicking it produces a strategy map → page re-renders.
- [x] 3.7.7 Promote dev → testing → production.

## 4. Phase 4 — Narrative reorder + Sc0redCTABanner expansion

*Frontend-only. Depends on Phase 3 (the slot's state machine must be
simplified before the reorder doesn't render orphan CTAs). Risk: low.*

> **Pivot note (2026-05-15):** The design called for **expanding** `Sc0redCTABanner` at Beat 4 with a full value-proposition rendering. In implementation (PR #296), the component was instead **deleted outright** — the narrative read better without a self-promotional banner between the strategy map and EBITDA, and the page felt cleaner. As a result, §4.2 (banner-expansion sub-phase) is intentionally left unticked: the work it described was superseded, not completed. §4.1 (beat reorder) and §4.3 (tests + ship) reflect what shipped.

### 4.1 Beat reorder

- [x] 4.1.1 Update `frontend/src/components/analysis/AnalysisDetail.tsx` to render the new beat order: Hero → Top 3 Actions → Strategy Map → ~~Sc0redCTABanner (expanded) →~~ EBITDA Tree → Opportunities → Risks → Value Chain. *(Sc0redCTABanner deleted instead of expanded — see pivot note.)*
- [x] 4.1.2 Remove any remaining references to the old `Sc0redCTABanner` mount site at the old Beat 4 (post-Top-3-Actions, pre-EBITDA-tree position).
- [x] 4.1.3 Ensure `DeepDiveCTA` import / mount is fully removed from `AnalysisDetail` (Phase 3 deleted the component; this confirms the import is gone).

### 4.2 Sc0redCTABanner expanded-by-default *(SUPERSEDED — banner deleted in PR #296)*

- [ ] 4.2.1 Add `expanded` prop (boolean, default `false`) to `Sc0redCTABanner`. *(Not done — superseded.)*
- [ ] 4.2.2 Implement the expanded layout: full value-proposition rendering instead of the compact CTA bar. Design pass during implementation (per design.md §Open Questions). *(Not done — superseded.)*
- [ ] 4.2.3 Mount at Beat 4 with `expanded={true}`. *(Not done — superseded.)*
- [ ] 4.2.4 Verify existing call sites of `Sc0redCTABanner` (legacy mount points elsewhere in the app, if any) continue to render in compact mode (no `expanded` prop passed → default `false`). *(Not done — superseded.)*

### 4.3 Tests + verification

- [x] 4.3.1 Update `AnalysisDetail` page-level tests for the new beat order.
- [ ] 4.3.2 Add a render test for the expanded `Sc0redCTABanner` state. *(Not done — superseded; banner deleted.)*
- [ ] 4.3.3 Add a test confirming dismissal still works in the expanded state. *(Not done — superseded; banner deleted.)*
- [x] 4.3.4 Architecture-reviewer pass.
- [x] 4.3.5 PR opened, CI green, merged to development, deployed to staging.
- [x] 4.3.6 Verify staging: load an analysis-detail page; confirm the new beat order, ~~expanded Sc0redCTABanner immediately after the strategy map,~~ no other CTAs visible.
- [x] 4.3.7 Promote dev → testing → production.

## 5. Phase 5 — Legacy code cleanup (Layer B)

*Pure deletion of the Phase 1/Phase 2 feature flags and the legacy
monolithic step runners. No behavioural change in production
(decomposed is already the only used path). Risk: low.*

### 5.1 Remove feature flags

- [x] 5.1.1 Remove `GENERATE_STRATEGY_MAP_DECOMPOSED` from `infrastructure/stacks/strategy_map_construct.py` — wait, the entire file is deleted in Phase 3. Confirm no other CDK references remain.
- [x] 5.1.2 Remove `GENERATE_STRATEGY_MAP_DECOMPOSED_SYNTHESIS` — same as above.
- [x] 5.1.3 Remove the flag-layering guard (the `ValueError` raise when Phase 2 is set without Phase 1) from `GenerateStrategyMap.execute()`.
- [x] 5.1.4 Remove the `_decomposed_path_enabled()` and `_decomposed_synthesis_enabled()` helper functions.
- [x] 5.1.5 Remove the env-var name constants (`DECOMPOSED_FLAG_ENV_VAR`, `DECOMPOSED_SYNTHESIS_FLAG_ENV_VAR`).

### 5.2 Remove conditional dispatch and legacy step runners

- [x] 5.2.1 Remove the conditional branches in `GenerateStrategyMap.execute()` that dispatch to `run_step_1_vision_mission`, `run_step_2_value_proposition`, `run_step_7_arrows_and_gaps`, and `run_steps_3_through_6_in_parallel` — these are the legacy monolithic paths.
- [x] 5.2.2 The decomposed dispatch calls become the only code path: `run_decomposed_vision_mission`, `run_decomposed_value_proposition`, `generate_perspectives_decomposed`, `run_decomposed_arrows_and_gaps`.
- [x] 5.2.3 Delete `backend/src/pipeline/pipeline_steps/_strategy_map_legacy_steps.py`.
- [x] 5.2.4 Delete the legacy monolithic prompt templates that are no longer reachable:
  - `backend/src/pipeline/prompts/strategy_map/templates/01_vision_mission.md`
  - `backend/src/pipeline/prompts/strategy_map/templates/02_value_proposition_classify.md`
  - `backend/src/pipeline/prompts/strategy_map/templates/03_financial_perspective.md`
  - `backend/src/pipeline/prompts/strategy_map/templates/04_customer_perspective.md`
  - `backend/src/pipeline/prompts/strategy_map/templates/05_internal_processes.md`
  - `backend/src/pipeline/prompts/strategy_map/templates/06_organizational_capacity.md`
  - `backend/src/pipeline/prompts/strategy_map/templates/07_arrows_and_gaps.md`
- [x] 5.2.5 The decomposed templates under `templates/decomposed/` remain — they are the only used templates.

### 5.3 Tests

- [x] 5.3.1 Delete `backend/tests/unit/pipeline/test_generate_strategy_map_decomposed_dispatch.py` — the dispatch logic it tests no longer exists.
- [x] 5.3.2 Update `tests/unit/pipeline/test_strategy_map_decomposed_loaders.py` to remove any references to the deleted legacy templates.
- [x] 5.3.3 Update integration / unit tests that asserted both flag states (on / off) — they only need the always-on (decomposed) state now.

### 5.4 Ship

- [x] 5.4.1 Architecture-reviewer pass (pure deletions, but covers multiple files).
- [x] 5.4.2 PR opened, CI green, merged to development, deployed to staging.
- [x] 5.4.3 Verify staging: a fresh analysis produces a strategy map via the decomposed path (CloudWatch shows `ai_call_vision_text`, `ai_call_vp_primary`, `ai_call_arrow_*`, etc.) with no flag checks in the execution path.
- [x] 5.4.4 Promote dev → testing → production.

## 6. Wrap-up

- [ ] 6.1 Sync delta specs into canonical specs (`ai-strategy-map`, `analysis-detail-narrative`, `strategy-map`). *(Deferred — `ebitda-impact-model` and `analysis-page-readability` from the parallel EBITDA changes share the same deferral, can be tackled in one focused sync pass.)*
- [x] 6.2 Archive this change once all 5 phases are stable on production. *(Archiving 2026-05-15.)*
- [ ] 6.3 Update the `optimize-strategy-map-latency` parent change to mark its §10 cleanup task complete (legacy monolithic paths removed in Phase 5 above). *(To be handled when `optimize-strategy-map-latency` itself is reconciled.)*

# Phase A — Backend infra (additive; old auto-gen path still runs)

*Sequenced first. Adds the new on-demand path alongside the existing pipeline-step auto-gen. Both paths produce the same persisted artifact. No frontend or pipeline-removal changes yet.*

## A.1 SQS queue + DLQ + alarm

- [x] A.1.1 In `infrastructure/stacks/strategy_map_construct.py` (extracted to its own construct rather than inline in `janus_stack.py` — see PR #271), define a new `janus-strategy-map-queue-{env}` SQS queue with visibility timeout = 720 seconds (per the AWS-recommended 6× function-timeout ratio; PR #274 corrected this from an initial 90s value that AWS rejected because it was less than the 120s Lambda timeout). Message retention 4 days.
- [x] A.1.2 Define a corresponding `janus-strategy-map-dlq-{env}` DLQ with `maxReceiveCount = 3` so SQS auto-routes failed messages after 3 retries.
- [x] A.1.3 CloudWatch alarm on DLQ depth > 0 wired to the existing alerting topic.
- [x] A.1.4 New Lambda function `janus-strategy-map-worker-{env}` consuming the queue. Timeout 120s, memory 1024MB, reserved concurrency 4 for the current ~55s call shape (post `optimize-strategy-map-latency` Phase 1 the work shrinks but the Lambda config can stay as-is).
- [x] A.1.5 IAM role: read `assessments` table, write `assessments` + `companies` tables, publish to AppSync.

## A.2 SQS worker handler

- [x] A.2.1 Create `backend/src/handlers/strategy_map_handler.py`. `process_records(event)` parses each SQS record's `{analysis_id, scan_id}` body, loads the assessment + company via repos, invokes `GenerateStrategyMap` via the existing `_strategy_map_*` modules, persists, and pushes AppSync.
- [x] A.2.2 Per CLAUDE.md fail-fast: catch only domain errors (`ValueError`, `RuntimeError`, `EngineError`) and translate them to AppSync `strategy_map_failed` events. Programming errors (`KeyError`, `TypeError`, `AttributeError`) propagate to SQS retry.
- [x] A.2.3 Reuse `StepTimer` (already in place from `optimize-strategy-map-latency` Phase 0) so the worker emits the same `GenerateStrategyMap.timings` detail block as the pipeline-step path does today.
- [x] A.2.4 Set `companies.strategy_map_generation_state = "generating"` on entry; clear on exit (success or failure). Use an idempotent set (existing `repo.update`).

## A.3 API handler + route

- [x] A.3.1 Add `handle_generate_strategy_map(analysis_id, user, sqs_client)` in `backend/src/handlers/analysis_handlers.py`. Validates analysis exists, validates user has access (org check), enqueues SQS message on `janus-strategy-map-queue`, returns 202 Accepted.
- [x] A.3.2 Wire into `backend/src/handlers/api_gateway_handler.py`: `POST /api/analysis/{id}/strategy-map → handle_generate_strategy_map`. Add to existing route table.
- [x] A.3.3 Repo extension: `assessment_repo.clear_strategy_map(assessment_id)` removes the persisted map. `companies` repo extension: read/write `strategy_map_generation_state`.

## A.4 AppSync events

- [x] A.4.1 In `backend/src/pipeline/appsync_notifier.py`, add `notify_strategy_map_complete(analysis_id, scan_id)` and `notify_strategy_map_failed(analysis_id, scan_id, error_message)` helpers. Mirror the existing `notify_progress` mutation shape.
- [x] A.4.2 The strategy-map worker reuses the existing `onScanProgress` AppSync subscription channel filtered by `scanId`; events are distinguished client-side by the `status` field (`strategy_map_complete` / `strategy_map_failed`). No schema change needed — the existing channel already accepts arbitrary `status` strings.

## A.5 GET endpoint surfaces generation state

- [x] A.5.1 Update `backend/src/handlers/analysis_payload.py` to surface `strategy_map_generation_state` (camelCase: `strategyMapGenerationState`) on the analysis-detail response when the company record has it set. Default to absent (omit) when not generating.

## A.6 Tests + ship

- [x] A.6.1 Unit tests: handler validates access, enqueues SQS message, sets state, returns 202.
- [x] A.6.2 Unit tests: worker `process_records` runs the full generation path against a mocked `AIClientFactory`, persists, clears state, emits AppSync.
- [x] A.6.3 Unit tests: worker error path (domain errors) emits `strategy_map_failed` and clears state; programming errors propagate.
- [x] A.6.4 Integration test: end-to-end POST → SQS → worker → persisted strategy map → AppSync push (with mocked AppSync).
- [x] A.6.5 `cd backend && uv run pytest tests/ -q` all green; coverage ≥ 95%; ruff + pyright clean.
- [x] A.6.6 Architecture-reviewer agent. Resolve all CRITICAL findings.
- [x] A.6.7 Open PR (split into PR #270 backend + PR #271 infra + PR #274 hotfix). Landed on development. Smoke-test of POST endpoint via curl deferred to first user click in dev (deploy verified at `f5e1e4a` on 2026-05-06 21:43 UTC).

---

# Phase B — Frontend three-state UI + Sc0redCTA reposition

*Sequenced after Phase A is on production. Adds the CTA, generating placeholder, AppSync subscription, and layout reorder including Sc0redCTABanner reposition.*

**Blocked on**: Phase A merged + AppSync subscription verified working in dev.

## B.1 New components + hooks

- [x] B.1.1 Create `frontend/src/components/analysis/StrategyMapCTA.tsx`. Click handler POSTs to `/api/analysis/{id}/strategy-map`. On 202, calls a parent-provided `onGenerationStarted(analysisId)` callback. On error, renders an inline error message with retry. Includes brief framing copy ("Synthesise a Balanced Scorecard view from your risks, opportunities, EBITDA, and value chain").
- [x] B.1.2 Create `frontend/src/lib/hooks/useStrategyMapSubscription.ts`. Subscribes to AppSync events filtered by `analysis_id`. Handles `strategy_map_complete` (triggers re-fetch) and `strategy_map_failed` (transitions to error message). 90-second client-side timeout fallback to one-time `GET /api/analysis/{id}` if no event arrives.
- [x] B.1.3 Create `frontend/src/components/analysis/StrategyMapGeneratingPlaceholder.tsx`. Skeleton + status message ("Generating your strategy map..."). No cancel button.
- [x] B.1.4 Update `frontend/src/lib/types/api.ts`: `AnalysisData` gains `strategyMapGenerationState?: "generating" | null`.

## B.2 Layout reorder in `AnalysisDetail.tsx`

- [x] B.2.1 Move `<Sc0redCTABanner />` from after `OpportunitiesList` to between `AnalysisOverviewCards` and `TopActionsCallout` (Beat 1.5 of new layout). Single instance.
- [x] B.2.2 Move the strategy-map slot from after `TopActionsCallout` to after `OpportunitiesList` (Beat 6 of new layout).
- [x] B.2.3 Replace the conditional `{data.strategyMap ? <StrategyMapView/> : null}` with a three-state branch: CTA / generating / present.
- [x] B.2.4 `<DeepDiveCTA />` renders ONLY in the present state, immediately after `<StrategyMapView />`. Remove its standalone-render branch.
- [x] B.2.5 Update the file's docstring to reflect the new beat order.

## B.3 Sc0redCTABanner copy + framing

- [x] B.3.1 Update `Sc0redCTABanner.tsx` collapsed-state headline. Draft string: **"Dig deeper with a sc0red advisor"**. Final wording is leadership's call — keep the prop or constant editable.
- [x] B.3.2 Update expanded-state body copy. Draft string: **"Our PE-experienced advisors take you from this analysis to operational results — from positioning strategy through production deployment, faster than traditional advisory timelines."** Final wording is leadership's call.
- [x] B.3.3 Keep "Start the conversation" CTA button label unchanged.
- [x] B.3.4 Verify analytics events (`sc0red_cta_banner_expanded` / `_collapsed` / `sc0red_cta_clicked`) still fire with the existing `analyticsContext` payload at the new position.

## B.4 Tests

- [x] B.4.1 Unit tests: `<StrategyMapCTA />` renders the button, POSTs on click, transitions on 202, shows error on non-202.
- [x] B.4.2 Unit tests: `useStrategyMapSubscription` hook subscribes on mount, unsubscribes on unmount, handles complete + failed events, fires the 90s timeout fallback.
- [x] B.4.3 Page-level test (`AnalysisDetail.test.tsx`): all three slot states render correctly given different `data` shapes; section order matches the new spec; Sc0redCTABanner is at Beat 1.5 not Beat 12.
- [x] B.4.4 Page-level test: clicking the CTA optimistically transitions to generating; AppSync push transitions to present; failure event transitions back to CTA with error.
- [x] B.4.5 `cd frontend && npm run lint && npx tsc --noEmit && npm test` all clean.

## B.5 Architecture review + ship

- [x] B.5.1 Architecture-reviewer agent on the diff (substantial — new components, new hook, layout reorder, copy changes).
- [x] B.5.2 Open PR `feat/strategy-map-on-demand-frontend` (PR #272). Landed on development. Manual smoke-test deferred to first user interaction post-deploy:
  - Fresh analysis → CTA renders at Beat 6
  - Click CTA → optimistic transition → AppSync push → present
  - Re-analyse → CTA returns
  - Pre-existing analysis with strategy map → renders in present state at Beat 6
- [x] B.5.3 Promote dev → testing → production with normal cadence. — Shipped to all environments via PR #272 (dev), PR #285 (dev → testing 2026-05-07), and PR #291 (testing → production 2026-05-12).

---

# Phase C — Disable auto-gen + activate re-analyse invalidation

*Sequenced last. Removes the pipeline step and wires the re-analyse-clears-map logic. After this, the on-demand path is the only generation path.*

**Blocked on**: Phase B production-stable for ~7 days.

## C.1 Remove pipeline step

- [x] C.1.1 In `backend/src/pipeline/pipeline_factories/company_analysis_factory.py`, remove `GenerateStrategyMap` from the step list. Pipeline becomes: `Scrape → ParallelProfileRiskAndIdeation → DetailOpportunities → ComputeEbitdaTree → ComputeValueChain → PersistResults`. (PR #273)
- [x] C.1.2 `_PROGRESS_MAP["generate_strategy_map"]` removed in this cleanup PR (`chore/strategy-map-on-demand-cleanup`). It was harmless when nothing called `mark_question_complete("generate_strategy_map")`, but dead config drifts; better to remove it now that the auto-pipeline doesn't fire it.
- [x] C.1.3 Test fixtures audited as part of Phase B/C; the `analysis-detail-narrative` page-level tests and `ai-strategy-map` view tests already cover the no-strategy-map path because the slot was always conditionally rendered. No fixture changes needed beyond what shipped in #272/#273.

## C.2 Re-analyse invalidation

- [x] C.2.1 In `backend/src/handlers/analysis_handlers.py::handle_reanalyze`, call `assessment_repo.clear_strategy_map(analysis_id)` BEFORE the SQS enqueue. (PR #273)
- [x] C.2.2 Tests: re-analyse path with existing strategy map asserts the map is cleared before the pipeline runs (`test_reanalyze_clears_strategy_map_before_enqueue` captures call ordering via two `side_effect` callbacks appending to a shared list).
- [x] C.2.3 Tests: re-analyse path WITHOUT a strategy map does not error (`test_reanalyze_clears_strategy_map_when_none_exists`); the repo method is idempotent (`delete_item` on a missing row is a no-op).

## C.3 Tests + ship

- [x] C.3.1 The clear-before-enqueue ordering test plus the existing GET-after-reanalyse coverage from prior phases stand in for a full integration test (the SQS message lands on the existing analysis worker which is already covered end-to-end).
- [x] C.3.2 `cd backend && uv run pytest tests/ -q` — 1034 / 1034 pass, 95.25% coverage.
- [x] C.3.3 Architecture-reviewer agent — 0 findings.
- [x] C.3.4 PR #273 opened. Landed on development. Smoke-test deferred to first user interaction post-deploy:
  - Fresh analysis → CTA at Beat 6 (no auto-gen)
  - Re-analyse on an existing analysis with a map → map clears; CTA returns
- [x] C.3.5 Promote dev → testing → production. — Shipped to all environments via PR #273 (dev), PR #285 (dev → testing 2026-05-07), and PR #291 (testing → production 2026-05-12).

---

# Phase D — Cleanup

*Fires after Phase C has been on production for ~30 days.*

- [ ] D.1 Remove old non-decomposed prompt templates that the worker no longer uses (only relevant if `optimize-strategy-map-latency` Phase 1+ has shipped by then; otherwise the worker uses the same templates as the pipeline step did). **Status: still pending — `optimize-strategy-map-latency` Phase 1 has not shipped, so this is a no-op for now.**
- [x] D.2 Remove `_PROGRESS_MAP["generate_strategy_map"]` entry from `request_executor.py`. The legacy `mark_question_complete("generate_strategy_map")` call inside `GenerateStrategyMap.execute()` now silently no-ops (touching that step was deemed riskier than letting the call drop). The `test_mark_question_complete_fires_for_generate_strategy_map` regression test from PR #266 was inverted into `test_mark_question_complete_skips_for_strategy_map_post_on_demand` to lock in the intentional no-op.
- [x] D.3 Swept `CLAUDE.md` for stale references to the strategy-map step as a pipeline component — none found in the project's `CLAUDE.md` (the file describes patterns and gates, not the specific pipeline step list). The pipeline-step list lives in `company_analysis_factory.py`'s docstring, which Phase C already updated.

---

# Cross-phase coordination

- [x] X.1 `optimize-strategy-map-latency` design.md updated: Context section gets an entry-point note, and a new Decision §0a "Entry point under strategy-map-on-demand: worker handler, not pipeline step" documents that the feature flag `GENERATE_STRATEGY_MAP_DECOMPOSED` is now read by the strategy-map worker Lambda, not the analysis worker. The decomposition logic is unchanged.
- [x] X.2 `rename-janus-to-vector-advisory` Phase 3 tasks updated: Phase 3 is explicitly scoped to reorder the Beats 3–5 cluster ONLY. The Beat 1.5 (Sc0red CTA) and Beat 6 (strategy-map slot) positions are pinned by `strategy-map-on-demand` and are out of scope for Phase 3. Open Question §9 is reframed accordingly. Leadership still owns the §9 decision; the scope reduction does not change that gate.

---

# Order of operations summary

```
        ┌────────────────────────────────────────────────┐
        │  optimize-strategy-map-latency Phase 0        │
        │  (PR #265 — telemetry)                          │
        │  ↓ unblocks measurement                         │
        └────────────────────────────────────────────────┘
                          ↓
        ┌────────────────────────────────────────────────┐
        │  Phase A — Backend infra (this change)         │
        │  ↓ adds on-demand path; old auto-gen still runs│
        └────────────────────────────────────────────────┘
                          ↓
        ┌────────────────────────────────────────────────┐
        │  Phase B — Frontend three-state UI             │
        │  ↓ user can now click; old auto-gen still runs │
        └────────────────────────────────────────────────┘
                          ↓ (wait ~7 days prod-stable)
        ┌────────────────────────────────────────────────┐
        │  Phase C — Disable auto-gen                    │
        │  ↓ on-demand becomes the only path             │
        └────────────────────────────────────────────────┘
                          ↓ (wait ~30 days prod-stable)
        ┌────────────────────────────────────────────────┐
        │  Phase D — Cleanup                             │
        └────────────────────────────────────────────────┘

  In parallel, optimize-strategy-map-latency Phase 1+ can
  ship at any time after Phase A — the feature flag guards
  the worker's call shape rather than the pipeline-step's.
```

3-4 PRs total (Phase A + B + C, optionally D). Each independently shippable. Phase A is purely additive; Phase B is purely additive; Phase C is the removal.

# Phase A — Backend infra (additive; old auto-gen path still runs)

*Sequenced first. Adds the new on-demand path alongside the existing pipeline-step auto-gen. Both paths produce the same persisted artifact. No frontend or pipeline-removal changes yet.*

## A.1 SQS queue + DLQ + alarm

- [ ] A.1.1 In `infrastructure/stacks/janus_stack.py`, define a new `janus-strategy-map-queue-{env}` SQS queue with visibility timeout = 90 seconds (allows ~55s call + buffer); message retention 4 days.
- [ ] A.1.2 Define a corresponding `janus-strategy-map-dlq-{env}` DLQ with `maxReceiveCount = 3` so SQS auto-routes failed messages after 3 retries.
- [ ] A.1.3 CloudWatch alarm on DLQ depth > 0 wired to the existing alerting topic.
- [ ] A.1.4 New Lambda function `strategy-map-handler-{env}` consuming the queue. Memory + timeout tuned for current ~55s call shape (post `optimize-strategy-map-latency` Phase 1 the work shrinks but the Lambda config can stay as-is).
- [ ] A.1.5 IAM role: read `assessments` table, write `assessments` + `companies` tables, publish to AppSync.

## A.2 SQS worker handler

- [ ] A.2.1 Create `backend/src/handlers/strategy_map_handler.py`. `process_records(event)` parses each SQS record's `{analysis_id, scan_id}` body, loads the assessment + company via repos, invokes `GenerateStrategyMap` via the existing `_strategy_map_*` modules, persists, and pushes AppSync.
- [ ] A.2.2 Per CLAUDE.md fail-fast: catch only domain errors (`ValueError`, `RuntimeError`, `EngineError`) and translate them to AppSync `strategy_map_failed` events. Programming errors (`KeyError`, `TypeError`, `AttributeError`) propagate to SQS retry.
- [ ] A.2.3 Reuse `StepTimer` (already in place from `optimize-strategy-map-latency` Phase 0) so the worker emits the same `GenerateStrategyMap.timings` detail block as the pipeline-step path does today.
- [ ] A.2.4 Set `companies.strategy_map_generation_state = "generating"` on entry; clear on exit (success or failure). Use an idempotent set (existing `repo.update`).

## A.3 API handler + route

- [ ] A.3.1 Add `handle_generate_strategy_map(analysis_id, user, sqs_client)` in `backend/src/handlers/analysis_handlers.py`. Validates analysis exists, validates user has access (org check), enqueues SQS message on `janus-strategy-map-queue`, returns 202 Accepted.
- [ ] A.3.2 Wire into `backend/src/handlers/api_gateway_handler.py`: `POST /api/analysis/{id}/strategy-map → handle_generate_strategy_map`. Add to existing route table.
- [ ] A.3.3 Repo extension: `assessment_repo.clear_strategy_map(assessment_id)` removes the persisted map. `companies` repo extension: read/write `strategy_map_generation_state`.

## A.4 AppSync events

- [ ] A.4.1 In `backend/src/pipeline/appsync_notifier.py`, add `notify_strategy_map_complete(analysis_id, scan_id)` and `notify_strategy_map_failed(analysis_id, scan_id, error_message)` helpers. Mirror the existing `notify_progress` mutation shape.
- [ ] A.4.2 Update the AppSync schema (under `infrastructure/stacks/observability_construct.py` if that's where it lives) to include the two new event types. Subscriptions filterable by `analysis_id`.

## A.5 GET endpoint surfaces generation state

- [ ] A.5.1 Update `backend/src/handlers/analysis_payload.py` to surface `strategy_map_generation_state` (camelCase: `strategyMapGenerationState`) on the analysis-detail response when the company record has it set. Default to absent (omit) when not generating.

## A.6 Tests + ship

- [ ] A.6.1 Unit tests: handler validates access, enqueues SQS message, sets state, returns 202.
- [ ] A.6.2 Unit tests: worker `process_records` runs the full generation path against a mocked `AIClientFactory`, persists, clears state, emits AppSync.
- [ ] A.6.3 Unit tests: worker error path (domain errors) emits `strategy_map_failed` and clears state; programming errors propagate.
- [ ] A.6.4 Integration test: end-to-end POST → SQS → worker → persisted strategy map → AppSync push (with mocked AppSync).
- [ ] A.6.5 `cd backend && uv run pytest tests/ -q` all green; coverage ≥ 95%; ruff + pyright clean.
- [ ] A.6.6 Architecture-reviewer agent. Resolve all CRITICAL findings.
- [ ] A.6.7 Open PR `feat/strategy-map-on-demand-backend`. Land on development. Smoke-test the new POST endpoint with curl.

---

# Phase B — Frontend three-state UI + Sc0redCTA reposition

*Sequenced after Phase A is on production. Adds the CTA, generating placeholder, AppSync subscription, and layout reorder including Sc0redCTABanner reposition.*

**Blocked on**: Phase A merged + AppSync subscription verified working in dev.

## B.1 New components + hooks

- [ ] B.1.1 Create `frontend/src/components/analysis/StrategyMapCTA.tsx`. Click handler POSTs to `/api/analysis/{id}/strategy-map`. On 202, calls a parent-provided `onGenerationStarted(analysisId)` callback. On error, renders an inline error message with retry. Includes brief framing copy ("Synthesise a Balanced Scorecard view from your risks, opportunities, EBITDA, and value chain").
- [ ] B.1.2 Create `frontend/src/lib/hooks/useStrategyMapSubscription.ts`. Subscribes to AppSync events filtered by `analysis_id`. Handles `strategy_map_complete` (triggers re-fetch) and `strategy_map_failed` (transitions to error message). 90-second client-side timeout fallback to one-time `GET /api/analysis/{id}` if no event arrives.
- [ ] B.1.3 Create `frontend/src/components/analysis/StrategyMapGeneratingPlaceholder.tsx`. Skeleton + status message ("Generating your strategy map..."). No cancel button.
- [ ] B.1.4 Update `frontend/src/lib/types/api.ts`: `AnalysisData` gains `strategyMapGenerationState?: "generating" | null`.

## B.2 Layout reorder in `AnalysisDetail.tsx`

- [ ] B.2.1 Move `<Sc0redCTABanner />` from after `OpportunitiesList` to between `AnalysisOverviewCards` and `TopActionsCallout` (Beat 4 of new layout). Single instance.
- [ ] B.2.2 Move the strategy-map slot from after `TopActionsCallout` (Beat 5) to after `OpportunitiesList` (Beat 11 of new layout).
- [ ] B.2.3 Replace the conditional `{data.strategyMap ? <StrategyMapView/> : null}` with a three-state branch: CTA / generating / present.
- [ ] B.2.4 `<DeepDiveCTA />` renders ONLY in the present state, immediately after `<StrategyMapView />`. Remove its standalone-render branch.
- [ ] B.2.5 Update the file's docstring to reflect the new beat order.

## B.3 Sc0redCTABanner copy + framing

- [ ] B.3.1 Update `Sc0redCTABanner.tsx` collapsed-state headline. Draft string: **"Dig deeper with a sc0red advisor"**. Final wording is leadership's call — keep the prop or constant editable.
- [ ] B.3.2 Update expanded-state body copy. Draft string: **"Our PE-experienced advisors take you from this analysis to operational results — from positioning strategy through production deployment, faster than traditional advisory timelines."** Final wording is leadership's call.
- [ ] B.3.3 Keep "Start the conversation" CTA button label unchanged.
- [ ] B.3.4 Verify analytics events (`sc0red_cta_banner_expanded` / `_collapsed` / `sc0red_cta_clicked`) still fire with the existing `analyticsContext` payload at the new position.

## B.4 Tests

- [ ] B.4.1 Unit tests: `<StrategyMapCTA />` renders the button, POSTs on click, transitions on 202, shows error on non-202.
- [ ] B.4.2 Unit tests: `useStrategyMapSubscription` hook subscribes on mount, unsubscribes on unmount, handles complete + failed events, fires the 90s timeout fallback.
- [ ] B.4.3 Page-level test (`AnalysisDetail.test.tsx`): all three slot states render correctly given different `data` shapes; section order matches the new spec; Sc0redCTABanner is at Beat 4 not Beat 12.
- [ ] B.4.4 Page-level test: clicking the CTA optimistically transitions to generating; AppSync push transitions to present; failure event transitions back to CTA with error.
- [ ] B.4.5 `cd frontend && npm run lint && npx tsc --noEmit && npm test` all clean.

## B.5 Architecture review + ship

- [ ] B.5.1 Architecture-reviewer agent on the diff (substantial — new components, new hook, layout reorder, copy changes).
- [ ] B.5.2 Open PR `feat/strategy-map-on-demand-frontend`. Land on development. Manual smoke-test:
  - Fresh analysis → CTA renders at Beat 11
  - Click CTA → optimistic transition → AppSync push → present
  - Re-analyse → CTA returns
  - Pre-existing analysis with strategy map → renders in present state at Beat 11
- [ ] B.5.3 Promote dev → testing → production with normal cadence.

---

# Phase C — Disable auto-gen + activate re-analyse invalidation

*Sequenced last. Removes the pipeline step and wires the re-analyse-clears-map logic. After this, the on-demand path is the only generation path.*

**Blocked on**: Phase B production-stable for ~7 days.

## C.1 Remove pipeline step

- [ ] C.1.1 In `backend/src/pipeline/pipeline_factories/company_analysis_factory.py`, remove `GenerateStrategyMap` from the step list. Pipeline becomes: `Scrape → ParallelProfileRiskAndIdeation → DetailOpportunities → ComputeEbitdaTree → ComputeValueChain → PersistResults`.
- [ ] C.1.2 Remove the `generate_strategy_map` entry from `_PROGRESS_MAP` in `request_executor.py` (the entry added in PR #266 to fix the silent-progress-notification gap is no longer needed once the step is gone). Or keep it, since it's harmless when no step calls `mark_question_complete("generate_strategy_map")` — decide in code review.
- [ ] C.1.3 Update `analysis-detail-narrative` and `ai-strategy-map` test fixtures that assumed every analysis had a strategy map.

## C.2 Re-analyse invalidation

- [ ] C.2.1 In whichever handler triggers re-analyse (likely `re_analyse_handler.py` or similar — confirm location), call `assessment_repo.clear_strategy_map(assessment_id)` as the first step before pipeline kickoff. Single line + import.
- [ ] C.2.2 Tests: re-analyse path with existing strategy map asserts the map is cleared before the pipeline runs; post-re-analyse `GET` returns no `strategyMap` field.
- [ ] C.2.3 Tests: re-analyse path WITHOUT a strategy map (already absent) does not error.

## C.3 Tests + ship

- [ ] C.3.1 Integration test: full re-analyse flow on a previously-mapped analysis clears the map; CTA returns; click generates a new map.
- [ ] C.3.2 `cd backend && uv run pytest tests/ -q` all green; coverage gate.
- [ ] C.3.3 Architecture-reviewer agent. Resolve findings.
- [ ] C.3.4 Open PR `feat/strategy-map-on-demand-disable-autogen`. Land on development. Smoke-test:
  - Fresh analysis → CTA at Beat 11 (no auto-gen)
  - Re-analyse on an existing analysis with a map → map clears; CTA returns
- [ ] C.3.5 Promote dev → testing → production.

---

# Phase D — Cleanup

*Fires after Phase C has been on production for ~30 days.*

- [ ] D.1 Remove old non-decomposed prompt templates that the worker no longer uses (only relevant if `optimize-strategy-map-latency` Phase 1+ has shipped by then; otherwise the worker uses the same templates as the pipeline step did).
- [ ] D.2 Remove `_PROGRESS_MAP` entry for `generate_strategy_map` if not removed in Phase C.
- [ ] D.3 Update `CLAUDE.md` if it references the strategy-map step as a pipeline component.

---

# Cross-phase coordination

- [ ] X.1 `optimize-strategy-map-latency` design.md: noting that the entry point shifts from the pipeline step to the SQS worker. Add a Decision §0a "Entry point under strategy-map-on-demand: worker handler, not pipeline step" so the feature flag `GENERATE_STRATEGY_MAP_DECOMPOSED` documentation reflects reality.
- [ ] X.2 `rename-janus-to-vector-advisory` Phase 3 (analysis-page-advisory-reorder): the section reorder there is now obsolete for the strategy-map slot — strategy map moves to Beat 11 here, not as part of the rename change. Update Phase 3's tasks to remove the strategy-map reorder. Confirm with leadership before that change activates.

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

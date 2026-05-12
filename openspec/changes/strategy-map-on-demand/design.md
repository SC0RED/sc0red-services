## Context

The strategy map was originally specified as a pipeline output. The canonical `ai-strategy-map` spec says the company analysis pipeline SHALL produce a `StrategyMap` artifact for every analysed company. That requirement was implemented in `GenerateStrategyMap` (a `RequestStep` between `ComputeValueChain` and `PersistResults`) which has been running in production since the strategy-map feature shipped.

Several signals say this default is wrong:

- The strategy-map step is the dominant component of analysis-pipeline latency (~55s of ~90s wall-clock). Re-analyse loops feel slow because every re-analyse regenerates the map even when the user is just refreshing the diagnosis after a document upload.
- Cost-per-analysis includes the map regardless of whether anyone reads it — $0.37 of AI input for what is effectively page wallpaper for users who don't engage with strategy frameworks.
- The map is rendered as Beat 3 (top of page) which is heavy framing on a page where Beats 4-6 (risks, opportunities) are the practical diagnosis. Users who just want the diagnosis scroll past the map.
- We have zero engagement signal. Auto-generation gives no read on how often the map is actually consulted.

The fix is to flip the strategy map from pipeline output to on-demand artifact: generated only when a user clicks a CTA after seeing the diagnosis. This proposal scopes that flip plus a small adjacent change — repositioning `Sc0redCTABanner` from the bottom of the page to the top, with reframed copy that fits its new position.

The strategy-map generation call itself is unchanged: same inputs (profile + risks + opportunities + EBITDA + value chain + scraped content + uploaded docs + Vector white-paper system prompt + exemplars), same output shape, same Pydantic validation. Only the trigger and timing change.

This change interacts with two in-flight changes:

- **`optimize-strategy-map-latency`**: Phase 0 telemetry (PR #265) is unaffected — `StepTimer` still works in the worker invocation path. Phase 1+ decomposition lands in the worker code path; the feature flag `GENERATE_STRATEGY_MAP_DECOMPOSED` guards the worker's call shape, not the pipeline step.
- **`rename-janus-to-vector-advisory`** (Phase 3 reorder): the original reorder plan was drafted before this change. Phase 3 of that change should reference this one — the strategy-map slot moves to Beat 6 (here), not as part of the rename's section reshuffle.

## Goals / Non-Goals

**Goals:**

- Remove `GenerateStrategyMap` from the analysis pipeline; generation is API + SQS-worker-triggered.
- Drop base-pipeline latency from ~90s to ~35s by removing the strategy-map step.
- Render the strategy-map slot at Beat 6 of the analysis page (after risks + opportunities). The slot has three states: CTA (no map), generating (worker in flight), present (map persisted).
- Persist generation state on the company record so frontend cold-load and refresh-during-generation render the right UI.
- On any re-analyse, invalidate the persisted strategy map. The CTA returns; users explicitly opt back in for a fresh map against the new diagnosis.
- Push completion events via the existing AppSync infrastructure so generating-state UI updates in real time without polling.
- Reposition `Sc0redCTABanner` to Beat 1.5 (top of page, after identity beat) with reframed copy. Final strings are leadership's call; codify the placement and framing direction.
- Match existing async-pipeline patterns: dedicated SQS queue + worker + AppSync completion event, mirroring portfolio-discovery / portfolio-validation patterns already in production.

**Non-Goals:**

- Changing the strategy-map content shape, schema, or generation algorithm.
- Optimising the strategy-map call's latency — that's `optimize-strategy-map-latency`'s scope.
- Adding new analytics events beyond the AppSync completion push (existing `sc0red_cta_*` events stay).
- Building a queue / job dashboard for strategy-map jobs in flight (overkill for this feature; existing CloudWatch + SQS metrics cover ops).
- Generating strategy maps from the PDF export side. PDF includes whatever's persisted; no on-demand generation from Puppeteer.
- Migrating existing test-data analyses' strategy maps. Existing maps stay visible in the new layout; users explicitly regenerate via re-analyse if they want a fresh one.
- Per-call progress UI inside the generating state. The placeholder is a single skeleton + status message until the AppSync `strategy_map_complete` event arrives. (`optimize-strategy-map-latency` Phase 0 telemetry will surface per-call timings to CloudWatch but not to the frontend in v1.)

## Decisions

### 1. Async via SQS + AppSync (not synchronous API)

**Decision**: The on-demand generation runs asynchronously. The API handler enqueues an SQS message and returns 202 Accepted immediately. A dedicated SQS worker Lambda runs the generation and pushes completion via AppSync.

**Why:**

| Reason | Detail |
|---|---|
| API Gateway hard timeout | API Gateway terminates connections at 29s. Today's strategy-map call is ~55s. Sync would timeout. After `optimize-strategy-map-latency` Phase 1 (~17s) sync becomes feasible, but we don't want this change blocked on that. |
| Pattern reuse | The codebase already has dedicated SQS workers + AppSync completion pushes for portfolio discovery / validation (`discover_portfolio` / `validate_portfolio` flow in `_PROGRESS_MAP`). This is the established async pattern; we're not inventing a new mechanism. |
| Refresh / nav-away semantics | Async makes mid-generation refresh trivial: backend completes independently; frontend either sees the result on the next GET or the AppSync completion push. Sync makes this awkward — request abort might or might not stop the work. |
| Multi-user consistency | If user A clicks "generate" and user B opens the same analysis 5s later, B should see the generating state too. Async + AppSync makes this natural; sync makes it a per-session implementation problem. |

**Alternatives considered:**

| Option | Why rejected |
|---|---|
| Synchronous API call (Option A from explore) | API Gateway timeout. Awkward refresh / nav-away semantics. Doesn't reuse existing async pattern. |
| Hybrid (sync with async fallback if > 25s) | Most complex; the failure modes multiply. Rarely the right call. |

**Trade-off**: more moving parts (handler + worker + AppSync event + new state field). Mitigated by the pattern already being in the codebase — the worker structure mirrors `sqs_handler.py`'s portfolio-discovery worker; the AppSync notify mirrors `notify_progress`.

### 2. Dedicated `janus-strategy-map-queue` (not piggy-back on existing analysis queue)

**Decision**: Create a dedicated SQS queue + DLQ for strategy-map jobs in `infrastructure/stacks/janus_stack.py`. The worker Lambda is also new (not an extension of the existing analysis worker).

**Why:**

| Reason | Detail |
|---|---|
| Independent scaling | Strategy-map jobs are bounded (one per click) and expensive (~55s of Lambda time today). Mixing them with the high-volume analysis queue means SQS visibility timeouts have to be tuned for the slowest job, hurting throughput on shorter analyses. |
| Independent monitoring | Per-queue CloudWatch metrics give clean observability — SQS depth, age of oldest message, DLQ size — for the strategy-map workload specifically. Mixing into the analysis queue means digging through metric filters to isolate strategy-map jobs. |
| Isolated failures | If the strategy-map worker crashes (e.g., OpenAI rate limit, schema regression), it doesn't affect the analysis pipeline. The analysis queue keeps draining; only strategy-map jobs queue up. |

**Alternatives considered:**

- **Piggy-back on `janus-analysis-queue`** with a message-type discriminator. Rejected: harder to monitor, harder to scale independently, blast-radius coupling.
- **No queue — Step Functions or EventBridge async invoke**: heavier infra than what's needed for "fire-and-forget worker." SQS is the established pattern.

**Trade-off**: a small CDK delta — one queue, one DLQ, one event-source mapping, one alarm on DLQ depth. Acceptable cost for the operational clarity.

### 3. Generation state lives on the company record (not the assessment record)

**Decision**: Add `strategy_map_generation_state` (`"generating"` or absent) to the `companies` DynamoDB record, not the `assessments` record. The frontend reads this on `GET /api/analysis/{id}` to choose CTA vs progress vs present.

**Why:**

- The frontend always loads the latest assessment via `analysis_payload.py`, which already reads from the company record for top-level analysis state (`pipeline_progress`, `pipeline_label`, etc.). One more field there is consistent.
- The assessment record already carries the persisted strategy map (`assessment_repo.save_strategy_map(...)`). Mixing in-flight state with persisted output on the same record creates ambiguity: "is `strategyMap = null` because no map yet, or because generation is in progress?"
- Company-level state is the natural home for "this analysis has a generation in flight" because the analysis is the unit users interact with.

**Trade-off**: the company record gains a transient field. Acceptable — `pipeline_progress` already plays this role for the analysis pipeline.

### 4. Re-analyse invalidates unconditionally (not "only with new docs")

**Decision**: ANY re-analyse — with or without document upload — clears the persisted strategy map. The CTA returns. User explicitly clicks to regenerate against the new diagnosis.

**Why**: re-analyse can update scraped content, profile, risks, opportunities, EBITDA, and value chain even without a document upload (e.g., a re-scrape after the company website changed). All of those feed the strategy-map generation. Tying invalidation only to "with new docs" makes the rule fragile and the resulting map stale relative to the diagnosis it visually accompanies.

The simpler rule — "any re-analyse invalidates" — matches the on-demand mental model: the strategy map is a synthesis of the diagnosis at a moment in time. When the diagnosis changes, the synthesis is stale.

**Alternatives considered:**

- **Only invalidate on doc upload** (the user's initial phrasing). Rejected: brittle, surfaces incorrect maps when re-scrape changes the diagnosis without a doc upload.
- **Auto-regenerate on re-analyse**: violates pure on-demand. Defeats the cost / engagement-signal goals.

### 5. Three-state frontend slot

**Decision**: The strategy-map slot at Beat 6 renders one of three states based on the response from `GET /api/analysis/{id}`:

| State | Condition | UI |
|---|---|---|
| **Absent** | `strategyMap` field is `null` AND `strategyMapGenerationState` is not `"generating"` | `<StrategyMapCTA />` — "Generate strategy map" button + brief framing copy |
| **Generating** | `strategyMapGenerationState === "generating"` | Skeleton placeholder + status message ("Generating your strategy map...") + AppSync subscription is live |
| **Present** | `strategyMap` field is populated | `<StrategyMapView />` + `<DeepDiveCTA />` (DeepDiveCTA only renders here, paired with the map) |

State transitions:

```
absent ──click "Generate"──▶ generating ──AppSync push──▶ present
   ▲                              │                          │
   │                              │ (worker error)           │
   └──────────────────────────────┘                          │
                                                             │
   ◀──re-analyse fires──────────────────────────────────────┘
```

On worker error, the worker writes the error to CloudWatch, clears the `generation_state` field on the company record (so the CTA returns), and pushes an AppSync `strategy_map_failed` event. Frontend renders a small "Generation failed — try again" message above the CTA on receipt of the failure event.

### 6. AppSync event shape

**Decision**: Two new event types, mirroring the existing `pipeline_progress` shape:

```
strategy_map_complete  { analysis_id, scan_id }
strategy_map_failed    { analysis_id, scan_id, error_message }
```

Frontend hook `useStrategyMapSubscription(analysisId)` filters AppSync events on `analysis_id` and re-fetches the analysis on `complete`. On `failed`, it shows the failure message + transitions back to absent.

The events do NOT carry the strategy map content itself — frontend re-fetches the full analysis after receiving `complete` to get the persisted map. This avoids a second source-of-truth issue (DynamoDB vs AppSync push payload) and keeps AppSync payloads small.

**Alternatives considered:**

- **Push the full strategy map content via AppSync**. Rejected: makes AppSync the strategy-map delivery channel, which it isn't. AppSync is a notification mechanism; DynamoDB is the persistence layer.

### 7. `Sc0redCTABanner` reposition + reframe

**Decision**: Move `Sc0redCTABanner` from "after `OpportunitiesList`" to "after `AnalysisOverviewCards`, before `TopActionsCallout`" (Beat 1.5). Update collapsed headline to "Dig deeper with a sc0red advisor" and the expanded body to remove "these opportunities" framing.

**Why**: at the bottom of the page (after opportunities), the banner can reasonably reference "these opportunities" because the user has just read them. At the top of the page, "these opportunities" is forward-referencing — the user hasn't seen them yet — and reads as an unfamiliar pronoun. The banner needs an analysis-level framing ("for a human eye on this analysis, contact sc0red") rather than an opportunity-level framing.

**Position rationale**: Beat 1.5 (after identity, before synthesis) gives the user just enough context to know what they're being offered help with. Earlier (above identity) is too aggressive — feels like clickbait. Later (after risks / opportunities) means a returning user has to scroll past most of the page to find the CTA.

**Final copy strings** are leadership's call; the proposal codifies the position and framing direction. The `tasks.md` carries draft strings that stay editable until launch.

**Trade-off**: existing analytics events (`sc0red_cta_banner_expanded` / `_collapsed` / `sc0red_cta_clicked`) keep firing identically. The `analytics_context` payload still carries `opportunityCount` and `activeLeverFilter` — at the new top position those values are typed but represent state from later in the page. Acceptable: the events are about banner interaction, not opportunity context; the lever-filter context is informational, not semantic.

### 8. Sc0redCTABanner repositioned, the OLD position is removed entirely

**Decision**: After this change, `Sc0redCTABanner` lives only at Beat 1.5. The post-OpportunitiesList instance is removed. There is one banner per page.

**Why**: showing the banner twice is louder than one good placement. Bottom-of-page placement made sense when the banner referenced "these opportunities"; at the new framing, putting it twice is just redundant.

## Risks / Trade-offs

- **[Risk]** Existing analyses have a strategy map auto-generated by the old pipeline. Frontend renders these via the present-state path. If a user happens to re-analyse one of these, the strategy map is invalidated and the CTA returns — they may be confused that "the map disappeared."
  → **Mitigation**: `<StrategyMapCTA />` copy explicitly says "Your previous strategy map was based on an earlier analysis. Generate a fresh one to reflect the latest data." Test data is the only affected population today (no production users).

- **[Risk]** SQS worker takes longer than the current timeout, retries via DLQ, and produces a duplicate strategy map.
  → **Mitigation**: `assessment_repo.save_strategy_map(...)` is idempotent — saves overwrite, never append. Duplicate processing produces the same result; the second AppSync `strategy_map_complete` event is a no-op for a frontend already showing the result.

- **[Risk]** AppSync push is fire-and-forget and may drop during network blips. User stays in generating state forever.
  → **Mitigation**: frontend cold-load and refresh both fetch `GET /api/analysis/{id}` which returns the current `strategy_map_generation_state` and the persisted map (if complete). A user can manually refresh if they think generation has hung. Add a 90-second client-side timeout in the subscription hook that triggers a one-time GET fallback.

- **[Risk]** Re-analyse invalidates the strategy map, but the user expected to keep it (e.g., re-analysed only to update a notes field).
  → **Mitigation**: re-analyse always implies "the diagnosis may have changed." If the user expected stability, that's a UX expectations bug — but on-demand semantics say the map is a synthesis of the diagnosis at a point in time. Document this in `<StrategyMapCTA />` copy: "Re-analysing invalidates the strategy map; click Generate to create one from the updated diagnosis."

- **[Risk]** OpenAI errors / rate limits in the worker fail every retry; user keeps clicking "Generate" with no progress.
  → **Mitigation**: handler returns 202 even if the worker is going to fail; SQS DLQ captures messages after 3 retries. CloudWatch alarm on DLQ depth fires for ops. Frontend's failure-state UI says "Generation failed — try again or contact support." After 3 failed CTA clicks, frontend disables the button for 60 seconds (rate-limit-aware UX).

- **[Risk]** The current `strategyMap` state lives in `AnalysisData` and many tests assume it's always populated for analyses with `data.strategyMap` truthy. Removing the auto-gen pipeline step means new analyses always start with `strategyMap = null`.
  → **Mitigation**: existing test fixtures stay valid (they explicitly set strategy maps where needed). New tests for absent / generating states. The page-level test `test_AnalysisDetail.tsx` already conditionalizes on `strategyMap`; adding two more conditional branches is mechanical.

- **[Risk]** `Sc0redCTABanner` moves up in the page layout but its collapsed-default state means users may not notice it. Engagement may drop relative to bottom-of-page positioning.
  → **Mitigation**: top-of-page positioning has better visibility but lower context; bottom has worse visibility but higher context. Net effect is uncertain. Track click-through rate via existing `sc0red_cta_clicked` event for ~30 days post-launch; revisit if measurably worse.

- **[Risk]** The `optimize-strategy-map-latency` change's Phase 1+ feature flag (`GENERATE_STRATEGY_MAP_DECOMPOSED`) was scoped against the pipeline-step entry point. After this change, the flag guards the worker's call shape instead.
  → **Mitigation**: minor change to `optimize-strategy-map-latency` design.md noting the entry point shift. The flag mechanic stays the same.

- **[Risk]** PDF export removes the strategy-map page when no map is persisted, but readers comparing two PDFs of the same analysis (one before/after generation) may be confused why the page disappeared.
  → **Mitigation**: PDF generation always reflects the current persisted state. Cover page or methodology footer mentions "strategy map present: yes / no" so the difference is explicit. Or: this is rare enough to ignore; PDF exports are point-in-time snapshots.

## Migration Plan

```
Step 1 — Backend infra (Phase A)
  • Add janus-strategy-map-queue + DLQ + alarm in CDK.
  • Add strategy_map_handler.py SQS worker.
  • Add handle_generate_strategy_map handler + route.
  • Add notify_strategy_map_complete in appsync_notifier.py.
  • Extend assessment_repository (clear_strategy_map).
  • Extend analysis_payload to surface strategy_map_generation_state.
  • Pipeline factory NOT yet modified — auto-gen still runs; new path is
    additive. Both paths produce the same persisted artifact.
  • Tests: handler + worker unit; integration via a mocked AI factory.
  • Land on development. Soak.

Step 2 — Frontend three-state UI (Phase B)
  • Add StrategyMapCTA component.
  • Add useStrategyMapSubscription hook (subscribes to AppSync).
  • Update AnalysisDetail.tsx layout: strategy-map slot moves to Beat 6;
    the auto-generated map (from old path) still renders in the new slot
    location since the data shape is unchanged. CTA shows for any
    re-analysed analysis once the auto-gen path is disabled in Step 3.
  • Sc0redCTABanner reposition + copy update.
  • Tests: three-state render, subscription, layout reorder.
  • Land on development. Soak.

Step 3 — Disable auto-gen + activate invalidation (Phase C)
  • REMOVE GenerateStrategyMap from CompanyAnalysisFactory.
  • Re-analyse handler calls clear_strategy_map(...) before pipeline runs.
  • Tests: re-analyse flow asserts the old map clears + CTA returns.
  • Land on development. Soak.

Step 4 — Promote dev → testing → production
  • Each environment gets its own soak + manual smoke test.
  • Manual verification: a freshly-analysed company shows the CTA at
    Beat 6; clicking generates a map; re-analysing clears it.

Step 5 — Cleanup (after ~30 days production stable)
  • If rollback hasn't been needed, the old auto-gen code path is gone
    (Step 3 removed it). No cleanup PR needed unless test fixtures
    referencing the auto-gen path stayed too long.
```

**Rollback strategy per step**:

- Step 1: revert the backend infra PR. New API + worker disappear; old auto-gen still runs unchanged.
- Step 2: revert the frontend PR. Layout reverts; old strategy-map-at-Beat-3 returns.
- Step 3: revert the auto-gen-removal PR. Pipeline regenerates the step; CTAs may briefly show on analyses that ran during the disable window, but next re-analyse populates them.
- Step 4: per environment, revert the promotion PR.

## Open Questions

- **Sc0redCTABanner final copy strings**: leadership / product to confirm. Drafts in `tasks.md`.
- **Failure-state copy on worker errors**: `<StrategyMapCTA />` shows what when generation fails? Drafts in tasks.md; final copy is a small product call.
- **Client-side timeout in subscription hook**: 90 seconds proposed; could be 60 or 120. Tune based on Phase 0 telemetry baseline once it lands.
- **Should the GET endpoint surface the failure reason, or only the state?** Proposal: surface a generic `"failed"` state on the company record, not the underlying error. The error is in CloudWatch; users get a re-try button. Confirm.
- **Should we preserve the option to manually trigger generation from an admin UI?** Out of scope for this change but worth flagging — operationally useful when debugging a customer's failed generation.

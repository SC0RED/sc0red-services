## Why

Today the strategy map is auto-generated as part of every analysis pipeline run. Every analyse / re-analyse pays ~55s of latency and ~$0.37 of AI cost for a strategy map regardless of whether anyone reads it. This is wrong on three axes:

1. **Latency**: the strategy-map call dominates the analysis-pipeline wall-clock (~55s of ~90s). Re-analysing a company to see updated risks/opportunities means waiting a minute for a strategy map you might not need.
2. **Cost**: every analysis costs the strategy map even when no user views it. Currently we have no signal on engagement; this is wallpaper.
3. **Information density**: rendered at the top of the analysis page (Beat 3), the strategy map is heavy framing on a page that already has identity + top actions. Users who just want risks + opportunities have to scroll past it.

The fix is to flip the strategy map from a pipeline output to an on-demand artifact. Generation runs only when a user explicitly clicks "Generate strategy map" after seeing the diagnosis (risks + opportunities). This:

- Drops base-pipeline latency from ~90s → ~35s (removing the strategy-map step entirely).
- Charges AI cost only for users who actually want the map — engagement signal becomes measurable.
- Keeps the page narrative focused on the diagnosis; the map becomes a deeper-dive affordance below the opportunities.

A second smaller change rides along: the `Sc0redCTABanner` is repositioned from the bottom of the page (after opportunities) to the top of the page (after the identity beat), with reframed copy. The current copy ("sc0red can help you capture these opportunities") is opportunity-centric and only makes sense at the bottom; at the top we need an analysis-centric framing ("Dig deeper with a sc0red advisor"). This rides along because both changes touch the page layout in `AnalysisDetail.tsx` and bundling avoids two close-succession layout PRs.

## What Changes

### Strategy map: pipeline output → on-demand artifact

- **REMOVE** `GenerateStrategyMap` from `CompanyAnalysisFactory`'s pipeline. Pipeline becomes: `Scrape → ParallelProfileRiskAndIdeation → DetailOpportunities → ComputeEbitdaTree → ComputeValueChain → PersistResults`. Strategy map no longer auto-generated.
- **ADD** new API route: `POST /api/analysis/{id}/strategy-map`. The handler validates the analysis exists + user has access, sets `strategy_map_generation_state = "generating"` on the company record, enqueues an SQS message on the new `janus-strategy-map-queue`, and returns 202 Accepted immediately.
- **ADD** new SQS worker `strategy_map_handler.py` that consumes the queue. Worker invokes `GenerateStrategyMap` (or its decomposed equivalent post-`optimize-strategy-map-latency` Phase 1+) against the analysis context, persists the result via `assessment_repo.save_strategy_map(...)`, sets state to `complete` (clears the field), and pushes an AppSync `strategy_map_complete` event.
- **ADD** new dedicated SQS queue `janus-strategy-map-queue` (per-environment) with its own dead-letter queue, defined in `infrastructure/stacks/janus_stack.py`.
- **ADD** AppSync subscription event `strategy_map_complete` (alongside the existing `pipeline_progress`). Frontend subscribes by `analysis_id` and renders the result on receipt.
- **MODIFY** re-analyse handler — when an analysis is re-analysed (any re-analyse, with or without document upload), the persisted strategy map SHALL be removed from the assessment record so the on-demand CTA returns. The map is invalidated by re-analyse because the underlying diagnosis (risks, opportunities, EBITDA, value chain) may have changed.
- **MODIFY** PDF export — when an analysis has no persisted strategy map, the PDF omits the section cleanly. No placeholder, no on-demand-from-PDF.

### Inputs to the on-demand call

The on-demand worker uses the **same input shape as today's pipeline-step**: scraped content + `CompanyProfile` + `RiskAssessment` + `OpportunityResult` + `EbitdaTreeResult` + `ValueChainResult` + uploaded document text + the Vector white-paper system prompt + Mobil/Wawa exemplars. No web search (already not doing it). The user's mental framing is "synthesise the diagnosis"; functionally that means everything the pipeline produced.

### Frontend layout reorder

```
Beat 1 (IDENTITY):
   Header → ExecutiveStrap → OverviewCards
                ↓
Beat 1.5 (NEW POSITION for Sc0redCTABanner):
   Sc0redCTABanner (collapsed, headline "Dig deeper with a sc0red advisor")
                ↓
Beat 2 (SYNTHESIS):
   TopActionsCallout
                ↓
Beat 3 (MONEY):
   EbitdaSection → ValueChainDiagram (paired)
                ↓
Beat 4 (RISK):
   RiskBreakdown
                ↓
Beat 5 (OPPORTUNITIES):
   ValueLever → OpportunitiesList
                ↓
Beat 6 (NEW STRATEGY MAP SLOT — on-demand):
   IF strategy_map_generation_state = "generating":
     → progress placeholder + "Generating your strategy map..."
   ELIF data.strategyMap is present:
     → StrategyMapView → DeepDiveCTA
   ELSE:
     → StrategyMapCTA "Generate strategy map" (button)
                ↓
Beat 7 (IMPROVE):
   DocumentUpload
```

The previous Beat 3 position for `StrategyMapView` (top of page) is removed. The previous Beat 5/7 position for `Sc0redCTABanner` (after opportunities) is removed.

`DeepDiveCTA` only renders when the strategy map is present (per Q4=(a)). When the map is absent or generating, the deep-dive CTA is suppressed — it pairs with the rendered map.

### Sc0redCTABanner copy + position change

| | Today | After this change |
|---|---|---|
| **Position** | Bottom of page, after OpportunitiesList | Beat 1.5, after AnalysisOverviewCards |
| **Collapsed headline** | "sc0red can help you capture these opportunities" | "Dig deeper with a sc0red advisor" |
| **Expanded body** | "Our AI specialists implement opportunities like these end-to-end..." | "Our PE-experienced advisors take you from this analysis to operational results — from positioning strategy through production deployment, faster than traditional advisory timelines." |
| **CTA button** | "Start the conversation" | "Start the conversation" (unchanged) |

Final copy is leadership's call; the proposal codifies the *placement* and *framing direction*. Concrete strings live in `tasks.md` and stay editable until launch.

### What's NOT changing

- The strategy-map content shape (`StrategyMap` Pydantic model, `strategy_map_output.json` schema, all Vector house-style content requirements).
- The strategy-map generation algorithm (still 7 calls today, decomposed in `optimize-strategy-map-latency` later).
- AWS resource names elsewhere (Lambda, DynamoDB table, IAM roles all unchanged).
- The frontend's existing `StrategyMapView`, `DeepDiveCTA`, `WhatsMissingPanel` components — they continue to render the same way when the map is present.
- The `Sc0redCTABanner`'s analytics events (`sc0red_cta_banner_expanded` / `_collapsed` / `sc0red_cta_clicked`) and the `keepalive: true` emit semantics.

## Capabilities

### New Capabilities

None. The on-demand flow is a re-shape of the existing `ai-strategy-map` capability.

### Modified Capabilities

- **`ai-strategy-map`** — major change. Removes "pipeline produces strategy map for every analysed company" requirement. Adds requirements for on-demand generation via API + SQS worker + AppSync completion event, persistence shape (`strategy_map_generation_state` field), and re-analyse invalidation.
- **`analysis-detail-narrative`** — updates the section-ordering scenarios. Strategy map moves from Beat 3 to Beat 6, with three states (CTA, generating, present). Sc0redCTABanner moves from after-opportunities to Beat 1.5. DeepDiveCTA renders only when the strategy map is present.
- **`polished-pdf-export`** — clarifies the strategy-map-section-conditional behaviour. When no map is persisted, the section is omitted cleanly.

## Impact

- **Backend** (~10 files):
  - `infrastructure/stacks/janus_stack.py` — new `janus-strategy-map-queue` + DLQ + SQS event-source mapping for the worker Lambda.
  - `backend/src/handlers/analysis_handlers.py` — new `handle_generate_strategy_map(analysis_id, user)` handler; routed via `api_gateway_handler.py`.
  - `backend/src/handlers/strategy_map_handler.py` — NEW SQS worker; `process_records(event)` orchestrates the generation.
  - `backend/src/pipeline/pipeline_factories/company_analysis_factory.py` — REMOVE `GenerateStrategyMap` from the step list.
  - `backend/src/pipeline/pipeline_steps/generate_strategy_map.py` — kept (moved into the SQS worker invocation path); no `RequestStep` integration changes today.
  - `backend/src/repositories/dynamodb/assessment_repository.py` — extend `save_strategy_map` to also write `strategy_map_generation_state`; new `clear_strategy_map(assessment_id)` for re-analyse invalidation.
  - `backend/src/repositories/dynamodb/company_repository.py` — extend to track `strategy_map_generation_state` field at the company record level (frontend reads this to choose CTA vs progress vs present).
  - `backend/src/pipeline/sqs_handler.py` (or equivalent) — re-analyse path calls `clear_strategy_map(...)` before the pipeline starts.
  - `backend/src/pipeline/appsync_notifier.py` — new `notify_strategy_map_complete(analysis_id)` helper.
  - `backend/src/handlers/analysis_payload.py` — surface `strategy_map_generation_state` on the GET response so the frontend renders the right state on cold load.
- **Frontend** (~5 files):
  - `frontend/src/components/analysis/StrategyMapCTA.tsx` — NEW component; click handler POSTs `/api/analysis/{id}/strategy-map`.
  - `frontend/src/app/(authenticated)/analysis/[analysisId]/AnalysisDetail.tsx` — repositioned Sc0redCTABanner, repositioned strategy-map slot with three-state rendering.
  - `frontend/src/components/Sc0redCTABanner.tsx` — copy changes (headline + body); analytics events unchanged.
  - `frontend/src/lib/hooks/useStrategyMapSubscription.ts` — NEW hook subscribing to AppSync `strategy_map_complete` for the active `analysisId`. Falls back to polling on reconnect.
  - `frontend/src/lib/types/api.ts` — `AnalysisData` gains `strategyMapGenerationState?: "generating" | null`.
- **Tests**: unit + integration coverage for the new handler, the worker, the AppSync emission, the re-analyse invalidation; frontend unit + RTL coverage for the three-state render and the AppSync subscription path.
- **Infrastructure**: new SQS queue + DLQ + alarm; new Lambda function for the worker. CDK delta is small.
- **Cost**: per-analysis cost decreases (no auto-gen). Per-strategy-map cost unchanged. Engagement-driven cost shape — 100% of analyses pay $0 for strategy map; X% of users click and pay full price.
- **Performance**: base pipeline drops from ~90s to ~35s. Strategy-map call latency unchanged from today's ~55s (drops to ~17s after `optimize-strategy-map-latency` Phase 1).
- **Out of scope**: in-flight changes (`optimize-strategy-map-latency`, `rename-janus-to-vector-advisory`) — design.md notes the integration points but keeps their scopes intact. The Sc0redCTABanner reposition is intentionally bundled here; final copy strings stay editable until launch and are leadership's call.

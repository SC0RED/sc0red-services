## Why

The strategy-map feature shipped to production yesterday in two waves
(`strategy-map-on-demand` + `decompose-strategy-map-synthesis`), but
production usage surfaced five issues that together amount to a
narrative-redesign:

1. **Discoverability**: the on-demand "click to generate" CTA at Beat 6
   buries the most valuable artifact the analysis produces. Users
   shouldn't have to opt in to see their company's strategy map.
2. **Redundant content**: the `whatsMissing` (gaps) section duplicates
   or contradicts the risks section. K&N's gap concept is distinct in
   theory but the AI implementation conflates them in practice.
3. **Layout quality**: the 2D React Flow canvas has chips overflowing
   their perspective bands when a theme has 4 objectives. Text
   truncates with `...` regardless of available chip width. The
   rendering looks unprofessional.
4. **CTA redundancy**: `DeepDiveCTA` (below the strategy map) and
   `Sc0redCTABanner` (at Beat 4) cover the same intent with different
   copy. Two CTAs compete for the same conversion event.
5. **Legacy code burden**: the on-demand SQS+Lambda+API+frontend-CTA
   plumbing is the obvious dead weight. There's also older cruft —
   the decomposition feature flags (`GENERATE_STRATEGY_MAP_DECOMPOSED`,
   `GENERATE_STRATEGY_MAP_DECOMPOSED_SYNTHESIS`) and the legacy
   monolithic step-runners that have been kept as a fallback during
   Phase 2's rollout. Now's the moment to clear all of it.

The on-demand architecture was the right call when strategy map was
still experimental and we needed failure isolation. Now that Phase 1+2
have soaked through manual eval and a clean production deploy, the
artifact has earned a permanent always-on slot in the analysis
narrative.

## What Changes

This is a single coherent product shift implemented as a phased rollout.
The phases are independently shippable PRs tracked under one change.

- **Pipeline integration**: `GenerateStrategyMap` moves back into the
  analysis pipeline as the last step before `PersistResults`. Adds
  ~35 s to every scan (less after the §2 cleanup below). Removes the
  dedicated on-demand SQS queue, Lambda, API endpoint, and frontend
  CTA component.
- **Narrative reorder**: strategy map renders at Beat 3 of the
  analysis-detail page (immediately after the Top 3 Immediate Actions
  in Beat 2). `Sc0redCTABanner` "Want a deeper analysis?" moves to
  Beat 4 (immediately after the strategy map) and renders **expanded
  by default**. `DeepDiveCTA` is removed. EBITDA tree, opportunities,
  risks, and value chain follow at Beat 5+.
- **What's Missing removal**: hard-removed from generation, schema,
  and UI. `GenerateStrategyMap` drops the `ai_call_gaps` call. The
  `StrategyMap.whatsMissing` field is removed from the Pydantic model
  and the output JSON schema. Frontend stops rendering the section.
  Cleanup saves ~10 s of generation latency on top of the pipeline
  integration.
- **Layout overhaul**: the 2D canvas layout is reworked so chips never
  overflow their perspective bands. Band heights scale dynamically
  with the maximum objective count across themes; chip widths and
  text truncation are responsive to available space. Professional
  UI/UX bar — not a band-height tweak.
- **Backfill UX for old analyses**: analyses persisted before this
  change have no strategy map. Show a "Regenerate strategy map"
  affordance on the analysis-detail page for those. The user is
  currently the only production consumer, so an inline regenerate
  button is sufficient (no bulk-backfill script needed).
- **Legacy code cleanup**:
  - Remove the on-demand worker (`strategy_map_worker_entry.py`,
    `strategy_map_handler.py`, `strategy_map_hydration.py`).
  - Remove the CDK construct for the dedicated SQS queue and Lambda.
  - Remove the API endpoint `POST /api/analysis/{id}/strategy-map`.
  - Remove frontend components: `StrategyMapCTA`,
    `StrategyMapGeneratingPlaceholder`, `useStrategyMapSubscription`,
    `DeepDiveCTA`. Remove the AppSync subscription wiring for
    strategy-map progress events.
  - Remove the `GENERATE_STRATEGY_MAP_DECOMPOSED` and
    `GENERATE_STRATEGY_MAP_DECOMPOSED_SYNTHESIS` feature flags from
    the CDK construct and from `GenerateStrategyMap.execute()`.
  - Delete `_strategy_map_legacy_steps.py` and the conditional
    dispatch in `execute()` — the decomposed path is the only path.

## Capabilities

### New Capabilities

_None_ — every change here modifies existing capabilities. No new
user-facing capability is being introduced.

### Modified Capabilities

- `ai-strategy-map`: strategy map generated in-pipeline (not
  on-demand). `whatsMissing` removed from the generated artifact.
  Feature flags and legacy monolithic fallback paths removed; the
  decomposed call shape is the only generation path.
- `analysis-detail-narrative`: strategy map relocates from Beat 6 to
  Beat 3. `Sc0redCTABanner` moves to Beat 4 with expanded-by-default
  behaviour. `DeepDiveCTA` removed. Old-analysis regenerate affordance
  added.
- `strategy-map`: 2D React Flow canvas layout reworked — dynamic band
  heights, responsive chip widths, no chip-band overflow,
  professional rendering quality. `whatsMissing` rendering removed.

## Impact

- **Backend pipeline**:
  - `factories/janus_factories_factory.py` (or the equivalent factory
    in `pipeline/factories_factory.py`): re-add `GenerateStrategyMap`
    as a `RequestStep` in the company analysis pipeline.
  - `pipeline_steps/generate_strategy_map.py`: remove flag-gating;
    always-decomposed. Remove the dispatch to `_strategy_map_legacy_steps`.
    Drop the `gaps` call from the Step 7 fan-out.
  - `pipeline_steps/_strategy_map_arrows.py`: stop submitting the
    `gaps` task; remove `arrows_gaps` schema/template references.
  - `pipeline_steps/_strategy_map_legacy_steps.py`: delete.
  - Pydantic models (`model_strategy_map.py`): drop the `whatsMissing`
    field and the `Gap` model.
  - Output schema (`prompts/strategy_map/schemas/strategy_map_output.json`):
    drop `whatsMissing`.
  - Per-call schema (`prompts/strategy_map/schemas/per_call/arrows_gaps.json`):
    delete.
  - Prompt template (`prompts/strategy_map/templates/decomposed/arrows_gaps.md`):
    delete.
- **Backend handlers (deletions)**:
  - `handlers/strategy_map_worker_entry.py`: delete.
  - `handlers/strategy_map_handler.py`: delete.
  - `handlers/strategy_map_hydration.py`: delete.
  - API endpoint `POST /api/analysis/{id}/strategy-map`: delete from
    `handlers/analysis_handlers.py` and the API gateway router.
  - The "regenerate strategy map" affordance for old analyses needs
    a small new endpoint (e.g., `POST /api/analysis/{id}/strategy-map/regenerate`)
    that triggers an in-pipeline rerun. This is the ONE piece of API
    surface that survives — it's not the on-demand worker pattern,
    it's a targeted "re-run just this step on a persisted analysis."
- **Infrastructure (CDK)**:
  - Delete `infrastructure/stacks/strategy_map_construct.py` (the
    entire dedicated SQS + Lambda + AppSync wiring construct).
  - Remove the construct's instantiation from the parent stack.
  - The strategy-map regenerate endpoint runs through the existing
    API Lambda + analysis worker (same path as a normal scan
    re-trigger).
- **Frontend**:
  - `components/analysis/AnalysisDetail.tsx`: reorder Beats — strategy
    map at Beat 3, `Sc0redCTABanner` at Beat 4 expanded-by-default,
    everything else shifts down.
  - `components/analysis/StrategyMapSlot.tsx`: simplify — drop the
    GENERATING and ABSENT-with-CTA states. Two states only:
    PRESENT (render the map) or ABSENT-LEGACY (show the regenerate
    affordance for old analyses).
  - Delete: `StrategyMapCTA.tsx`, `StrategyMapGeneratingPlaceholder.tsx`,
    `lib/hooks/useStrategyMapSubscription.ts`, `DeepDiveCTA.tsx`.
  - Remove AppSync subscription wiring for `strategy_map_progress`
    and `strategy_map_complete` events.
  - `components/strategy-map/`: rework the 2D React Flow canvas
    layout. Dynamic band heights, responsive chip text truncation,
    overflow prevention. Drop the `whatsMissing` section from the
    canvas.
  - `Sc0redCTABanner.tsx`: add an `expanded` prop that defaults to
    `false` for legacy callers but is `true` at the Beat 4 mount
    site.
- **Tests**:
  - Backend: update `tests/unit/handlers/test_analysis_handlers.py`
    for the removed and added endpoints. Update pipeline tests for
    the re-integrated `GenerateStrategyMap` step. Delete the entire
    `tests/unit/handlers/test_strategy_map_handler.py` and
    `tests/unit/handlers/test_strategy_map_hydration.py`. Update
    strategy-map fixture data to drop `whatsMissing`.
  - Frontend: update `AnalysisDetail` tests for the new beat order.
    Delete `StrategyMapCTA.test.tsx`,
    `StrategyMapGeneratingPlaceholder.test.tsx`,
    `useStrategyMapSubscription.test.tsx`. Update `StrategyMapSlot`
    tests for the simplified state machine. Add tests for the
    canvas layout fixes (overflow prevention, responsive chip widths).
- **Migration**:
  - Persisted analyses with `whatsMissing` data continue to load
    (the field is dropped from new generations but legacy persisted
    data may still include it — Pydantic should ignore extra fields).
  - Persisted analyses WITHOUT a strategy map render the regenerate
    affordance.
- **Performance**:
  - Per-scan latency: +35 s (strategy-map step at the end of the
    analysis pipeline) MINUS the ~10 s savings from dropping gaps =
    ~+25 s net. Acceptable given the strategy-map artifact is now
    delivered with the analysis instead of requiring a separate user
    click + wait.
  - Lambda cost: NET REDUCTION — eliminates the dedicated
    strategy-map-worker Lambda (reserved concurrency 4, memory
    2048 MB, timeout 900 s). The analysis worker absorbs the work
    within its existing envelope.

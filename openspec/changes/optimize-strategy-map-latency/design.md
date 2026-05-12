## Context

> **Entry-point note (2026-05-07):** When this proposal was first drafted,
> `GenerateStrategyMap` ran as a step in the auto-pipeline. Since
> `strategy-map-on-demand` shipped (Phase A: PR #270/#271/#274; Phase B:
> #272; Phase C: #273), the auto-pipeline no longer includes the step —
> the strategy map is generated on demand by the dedicated
> `janus-strategy-map-worker-{env}` Lambda triggered from
> `POST /api/analysis/{id}/strategy-map`. The worker still invokes the
> SAME `GenerateStrategyMap.execute()` method via a single-step
> `JanusRequestExecutor` (see `backend/src/handlers/strategy_map_handler.py`),
> so every decomposition decision below applies unchanged. The
> measurement target shifts: instead of "pipeline duration includes
> strategy map at the end," the worker is timed on its own. See
> Decision §0a below.

The `GenerateStrategyMap` step (`backend/src/pipeline/pipeline_steps/generate_strategy_map.py`, 269 lines) is the slowest single AI step in the company analysis flow. It produces a `StrategyMap` artifact via 7 sequential rounds of AI calls (the middle round fans out to 4 parallel calls), with a wall-clock of ~50–60 seconds per generation. This is the dominant component of user-perceived latency on the re-analyse loop AND on every on-demand "Generate strategy map" click.

Other AI-heavy pipeline steps (`parallel_profile_risk`, `detail_opportunities`, `ideate_opportunities`, `assess_risk`) were optimised in earlier work and now follow a consistent pattern: many tiny parallel calls under one `FutureManager` block, with `StepTimer.record(label, elapsed)` for each call and a single `request_executor.add_details(timer.to_details())` emission to CloudWatch. Strategy-map generation predates that pattern and is now an outlier — it does not use `StepTimer` at all (per-call elapsed times are returned but discarded).

The `assessment_engine` codebase (sister product) demonstrates that decomposing big AI prompts into many tiny yes-or-one-line questions answered in parallel reduces wall-clock latency by 3–5x, because output-token streaming time dominates structured-response latency on OpenAI's models. Strategy-map generation is a natural fit: most of its calls have a fan-out shape (5 financial objectives, 4 customer objectives, ~10 themed internal-process objectives, N pair-wise arrows) where decomposition yields proportional latency reduction.

OpenAI's automatic prompt cache (50% off cached prefix on identical system prompt across calls within ~5 min) compounds with decomposition: the strategy-map system prompt is 14.5K tokens, well above the 1024-token caching threshold. Sending 50 parallel calls within a ~17-second window keeps every call but the first inside the cache.

Constraints:

- The output must remain a valid `StrategyMap` per the existing `strategy_map_output.json` schema. Pydantic validation in `_strategy_map_assembly.py` is the gating contract.
- The `ai-strategy-map` canonical-spec requirements about content (Vector house style, Customer perspective in customer voice, Internal Processes themed, Organizational Capacity = People/Technology/Culture, value-prop classification) MUST be preserved. The decomposition changes call shapes, not output behaviour.
- Per CLAUDE.md mandatory patterns: stay on `RequestStep`, every AI call goes through `run_structured_ai_call`, parallel work goes through `FutureManager`, prompts loaded from external files.
- File-size limit: 400 lines max for backend Python files. Decomposition will balloon `generate_strategy_map.py` if all logic stays there — design splits across focused sub-modules.

Stakeholders: end users (latency complaints), engineering (this proposal), product (output quality must hold).

## Goals / Non-Goals

**Goals:**

- Cut strategy-map wall-clock latency from ~55s to ~17s (~3.2x faster) by decomposing big AI calls into many tiny parallel ones plus exploiting OpenAI's automatic prompt cache.
- Add per-AI-call timing telemetry matching the pattern in `parallel_profile_risk` / `detail_opportunities` so production gives us measurement-grade visibility on every call's elapsed time.
- Preserve the assembled `StrategyMap` output shape — same schema, same content quality, same Vector house style.
- Match existing rate-limiting / retry behaviour by reusing `FutureManager` (which other steps already use under load).
- Stage the rollout: telemetry first (baseline), then decomposition (perspectives → synthesis → schemas), each phase shippable independently.

**Non-Goals:**

- Changing the assembled `StrategyMap` schema or any field's semantic.
- Changing the on-page or PDF rendering of the strategy map.
- Changing the underlying AI model (still OpenAI; choice is environmental).
- Optimising other AI-heavy pipeline steps (already done).
- Pipeline-level caching ("skip strategy-map regen if `CompanyProfile` unchanged") — separate change.
- Building an automated quality eval set — manual side-by-side comparison is the chosen verification.
- Cost optimisation. Cost is accepted to roughly 3x in exchange for the latency win.

## Decisions

### 0a. Entry point under strategy-map-on-demand: worker handler, not pipeline step

**Decision**: All decomposition work targets `GenerateStrategyMap.execute()` (and the supporting `_strategy_map_*` modules). The auto-pipeline no longer invokes this step directly — `strategy-map-on-demand` Phase C removed it from `CompanyAnalysisFactory.get_pipeline()`. The new call site is `backend/src/handlers/strategy_map_handler.py`, which builds a single-step `JanusRequestExecutor` and runs the step in isolation.

**What changes for this proposal:**

| Concern | Before strategy-map-on-demand | After |
|---|---|---|
| Where the step runs | Inline in `CompanyAnalysisFactory` after `ComputeValueChain` | Inside `StrategyMapSQSHandler._generate_and_persist` |
| Lambda timeout budget | Shared with the analysis worker (540s) | Dedicated 120s on `janus-strategy-map-worker` |
| AppSync progress channel | `notify_progress` events with `pipeline_progress` | `strategy_map_complete` / `strategy_map_failed` on the same `onScanProgress` channel |
| Trigger | Implicit (every analysis) | Explicit (user click) |

**Implications for decomposition phases:**

- The 120s worker timeout is comfortable for the current ~55s shape and the post-Phase-1 ~17s target. No timeout headroom risk.
- Per-call telemetry (`StepTimer.record(...)` then `request_executor.add_details(...)`) still works unchanged inside `GenerateStrategyMap` — the worker's executor receives the same details payload and writes it to CloudWatch.
- The feature flag `GENERATE_STRATEGY_MAP_DECOMPOSED` (Decision §6) is read by `GenerateStrategyMap.execute()`; it's an env var on the `janus-strategy-map-worker-{env}` Lambda after this change, NOT on the analysis worker. Update the rollout checklist accordingly.
- The "first-call uncached, rest cached" cache-utilization argument (Decision §1, §3) is unchanged — calls still happen within a single execution, so the OpenAI prompt cache window applies the same way.

**Why call this out:** the rollout checklist in `tasks.md` originally read "deploy to analysis worker, flip flag, watch CloudWatch." Without this note, an engineer reading the design after Phase C ships would set the env var on the wrong Lambda.

### 1. Two-phase decomposition pattern for perspectives

**Decision**: For each perspective (financial, customer, internal-processes, organizational-capacity), decompose generation into:

- **Round 1**: a single AI call returning the LIST of objective titles for that perspective. The model holds the full perspective in working memory at this point — coherence (no overlap, right count) is enforced naturally.
- **Round 2**: parallel AI calls (one per title) elaborating each title's content (`definition`, `category`, `confidence`, `rationale_source`). Each call sees the other titles as context to differentiate from but does NOT see other elaborations in flight.

Internal Processes is the three-round case: Round 1 = theme list, Round 2 = per-theme objective titles (parallel × ~3), Round 3 = per-objective elaboration (parallel × ~9).

**Why two-phase rather than fully fan-out**: Round 1 enforces coherence — the AI generates the title list once, holding the full perspective in mind. If we asked "give me one financial objective" in 5 parallel calls with no shared context, they'd all return overlapping defaults. Two-phase keeps coherence at the title level, where it matters, and parallelizes elaboration, where each title is independent.

**Why pass siblings as context to elaboration calls**: each elaboration call sees the other titles in its prompt so it can write the definition to differentiate. Without this, two parallel elaborations of titles that *sound* similar might produce overlapping definitions.

**Alternatives considered:**

| Option | Why rejected |
|---|---|
| Keep current single-call-per-perspective | Doesn't address the latency root cause (output streaming time). |
| Fully fan out — N parallel calls each generating one objective | Loses coherence. Without shared awareness of "what other objectives exist," the AI duplicates or overlaps. |
| Generate everything in one mega-call across all 4 perspectives | Reverses the existing parallelism win. Output is bounded by the slowest call, which is the whole map at once. Slower, not faster. |

### 2. Assembly assigns positional IDs; per-call schemas exclude the `id` field

**Decision**: The IDs in the strategy-map schema (`F1`/`F2`/`F3` for financial objectives, `C1`..`C4` for customer, `I{theme}.{obj}` for internal processes, `O.P`/`O.T`/`O.C` for capacity, `G1`..`G9` for gaps) are positional anchors — they encode order, not identity. With decomposition, parallel detail calls cannot independently know their position. Asking each call to invent its own ID is asking for collisions or schema-regex failures.

Instead, `_strategy_map_assembly.py` (already the validation chokepoint) assigns IDs deterministically by walking the title list:

```python
financial_titles = [...]  # from Round 1
financial_details = [...]  # from Round 2 (same order as titles)
financial_objectives = [
    FinancialObjective(id=f"F{i+1}", title=title, **detail)
    for i, (title, detail) in enumerate(zip(titles, details))
]
```

Per-call schemas for elaboration calls exclude `id` entirely. The "elaborate-one-objective" schema is `{definition, category, confidence, rationale_source}` — no regex constraint, no position-in-list signal needed.

For arrows: each yes/no call's prompt encodes the pair (`"Does objective C2 enable F1?"`). The response schema is `{enables: bool, hypothesis: str}` — no IDs. Assembly constructs the `Arrow(from="C2", to="F1", hypothesis=...)` from the prompt context, not the response.

**Why this is a strict improvement over today**: today's prompts hand-instruct the AI to fill `id: F1` in order, with the schema regex enforcing it. The AI is being asked to do what the assembly should do — that's wasted reasoning. Removing `id` from per-call output:

- Eliminates a class of failure modes (`id: F4` in a 3-objective list, duplicate IDs across parallel calls).
- Simplifies the schema for each call by ~80%.
- Makes assembly the single source of truth for structural shape.

**Alternatives considered:**

| Option | Why rejected |
|---|---|
| Pass index-in-list to each elaboration call's prompt; AI echoes the ID | Adds prompt complexity. AI compliance with "say `F2` here" is imperfect. We'd still need schema-regex validation. The bug surface stays. |
| Have parallel elaboration calls write to a shared dict keyed by title; assembly synthesises IDs from key order | Same outcome as the chosen approach but more code. |

### 3. Telemetry pattern matches existing AI-heavy steps

**Decision**: Use `StepTimer` from `src/pipeline/step_timer.py` exactly the way `parallel_profile_risk` and `detail_opportunities` do:

```python
timer = StepTimer("GenerateStrategyMap")

with FutureManager(name="GenerateStrategyMap", max_workers=N) as manager:
    for label, prompt, schema in tasks:
        manager.submit_task(self._run_ai_call, prompt, schema, system_prompt, label)
    results = manager.wait_for_all_and_collect_results()

for label, data, elapsed in results:
    timer.record(f"ai_call_{label}", elapsed)

self.request_executor.add_details(timer.to_details())
```

Per-call labels follow the existing convention:

- Phase 0 labels (one per current call): `ai_call_vision_mission`, `ai_call_value_proposition`, `ai_call_financial`, `ai_call_customer`, `ai_call_internal_processes`, `ai_call_organizational_capacity`, `ai_call_arrows_and_gaps`.
- Phase 1+ labels (per decomposed call): `ai_call_titles_financial`, `ai_call_detail_financial_F1`, `ai_call_titles_customer`, `ai_call_detail_customer_C1`, etc. Internal-processes uses three-level: `ai_call_themes`, `ai_call_titles_internal_T1`, `ai_call_detail_internal_T1_O1`.
- Phase 2 labels: `ai_call_vision`, `ai_call_mission`, `ai_call_vision_synth`, `ai_call_mission_synth`, `ai_call_vp_primary`, `ai_call_vp_secondary`, `ai_call_vp_exemplar`, `ai_call_vp_rationale`, `ai_call_arrow_F1_C1`, `ai_call_arrow_F1_C2`, ...

CloudWatch landing format identical to existing steps:

```json
{
  "GenerateStrategyMap.timings": {
    "ai_call_titles_financial": 1.8,
    "ai_call_detail_financial_F1": 1.4,
    "ai_call_detail_financial_F2": 1.6,
    "ai_call_arrow_F1_C1": 0.9,
    ...
    "total": 17.2
  }
}
```

This is testable end-to-end via existing CloudWatch dashboards. No new observability infrastructure.

### 4. FutureManager max_workers tuned per phase

**Decision**: Each phase's `FutureManager` block sizes its `max_workers` to its parallelism pattern:

| Phase | Block | Concurrent calls | max_workers |
|---|---|---|---|
| Phase 1 | Perspectives Round 1 (titles) | 4 | 4 |
| Phase 1 | Perspectives Round 2 (details) | ~20 | 20 |
| Phase 1 | Internal-Processes Round 3 | ~9 | 9 |
| Phase 2 | V/M tiny | 4 | 4 |
| Phase 2 | VP tiny | 4 | 4 |
| Phase 2 | Arrows | ~25 | 25 |
| Phase 3 | (unchanged) | n/a | n/a |

The largest single block is the arrow generation (~25 pair-wise calls). This stays well under OpenAI tier-3+ rate limits but worth confirming the org's tier when Phase 2 lands. If we hit limits, throttling lives in `FutureManager` (the existing pattern), not in the orchestration code.

### 5. Per-call JSON schemas under `prompts/strategy_map/schemas/per_call/`

**Decision**: Phase 3 splits the monolithic `strategy_map_output.json` into per-call schemas:

```
prompts/strategy_map/schemas/
├── strategy_map_output.json        ← unchanged; assembled-output schema
└── per_call/
    ├── perspective_titles.json     ← {titles: string[]}
    ├── financial_objective_detail.json
    ├── customer_objective_detail.json
    ├── internal_objective_detail.json
    ├── capacity_objective_detail.json
    ├── theme_list.json              ← {themes: [{name, supports_financial_objectives}]}
    ├── vision_text.json             ← {statement: string}
    ├── mission_text.json            ← {statement: string}
    ├── synth_yesno.json             ← {synthesised: bool}
    ├── vp_primary.json              ← {primary: enum}
    ├── vp_secondary.json            ← {secondary: enum | null}
    ├── arrow_yesno.json             ← {enables: bool, hypothesis: string}
    ├── strategic_priorities.json    ← {priorities: [{name, result}]}
    └── gaps.json                    ← {gaps: [{title, description, deepDiveFraming}]}
```

Each per-call schema is the smallest possible structure for that call. Loaded lazily via the existing `load_schema(name)` helper in `_strategy_map_corpus.py`, extended to support the `per_call/` subdirectory.

**Why slice instead of share**: today's full schema is ~10.6K tokens. Sent on every call regardless of which fields are populated. With ~50 decomposed calls, that's ~500K wasted input tokens of schema duplication. Slicing eliminates this overhead and makes Pydantic validation tighter at the per-call boundary (a "definition" call returning a `category` field would be rejected, not silently ignored).

### 6. Manual eval via dev-vs-testing side-by-side comparison

**Decision**: No automated quality eval; instead, after each phase ships to dev:

1. Pick 5 representative companies (varied size, varied industry).
2. Run the same analysis on dev (new code) and testing (current code).
3. Read the two strategy maps side by side.
4. Score qualitatively per perspective: preserved / regressed / improved.

**Threshold to ship to testing**: no perspective regresses (objectives missing, value-prop class flipped, arrows lost). Wording differences are fine. The check is "does a PE analyst reading both find the new one better, equal, or worse?"

**Why this is acceptable**: building an automated eval set is a multi-week effort with no current input. The user explicitly chose manual verification. 5 companies × ~2 min side-by-side read = ~15 min per phase verification, low overhead.

**Trade-off**: not regression-proof against rare edge cases. Mitigation: keep the old call-shape code in the codebase (commented out behind a feature flag during the rollout window) so we can A/B compare specific surfaces if quality issues surface in production.

### 7. Phase ordering and sequencing

**Decision**: Phases ship in order, but each is independently shippable:

```
Phase 0  Telemetry only (no behavioural change). Ships immediately.
   ↓                                       Production gives us baseline.
Phase 1  Decompose perspectives. Biggest single latency win.
   ↓                                       Ships when manual eval passes.
Phase 2  Decompose V/M, VP, arrows. Smaller win, more calls.
   ↓                                       Ships when manual eval passes.
Phase 3  Per-call schema slicing. Free latency on top.
                                          Ships independently of decomposition state.
```

Phase 3 can run in parallel with Phases 1 / 2 if the engineer has bandwidth, since the schema-slice change is mostly orthogonal. But the simpler default is sequential.

**Rollback strategy**: each phase = one PR. `git revert` on a phase PR returns to the previous phase's behaviour. Phase 0 is purely additive (emits new CloudWatch details); reverting doesn't lose data, just timing visibility.

## Risks / Trade-offs

- **[Phase 1 Risk]** Two-phase decomposition loses cross-objective coherence vs single-call generation. Two objectives within a perspective end up overlapping or duplicating concepts.
  → **Mitigation**: Round 1 generates titles holistically (model sees all 5 in working memory). Round 2 elaboration calls receive the sibling titles as context to differentiate from. Manual eval threshold catches regressions.

- **[Phase 1 Risk]** AI returns Round 1 title list with wrong count (4 instead of 3 financials) or duplicate titles.
  → **Mitigation**: Round 1's per-call schema enforces array length (`minItems: 3, maxItems: 5` for financial; `minItems: 3, maxItems: 4` for customer; etc.). Pydantic validation at assembly time catches deduplication failures.

- **[Phase 2 Risk]** Arrow generation as ~25 pair-wise yes/no calls produces nonsensical "enabling" relationships because each call is too narrow to see the bigger picture.
  → **Mitigation**: each arrow call's prompt includes the FULL list of perspective objectives as context, just asks "does X enable Y?" specifically. Tested against eval companies — quality threshold is "the arrows make strategic sense to a PE reader."

- **[Phase 2 Risk]** Strategic-priorities and gaps are kept as holistic single calls. Their inputs (the full set of objectives + arrows) becomes large; output streaming time stays slow on these.
  → **Mitigation**: accepted. These two calls are inherently synthesizing — any decomposition loses what makes them valuable. They stay big; the latency win comes from the surrounding decomposition.

- **[Phase 3 Risk]** Per-call schema slicing introduces drift if the assembled-output schema (`strategy_map_output.json`) changes but a per-call schema isn't updated to match.
  → **Mitigation**: per-call schemas are derived from the same Pydantic models that build the assembled output. Add a unit test asserting per-call schemas validate against the corresponding Pydantic field types.

- **[Cross-phase Risk]** OpenAI rate limits bite under burst (peak hours, multiple concurrent users re-analysing). Per-analysis call count goes from 7 to ~50; 100 analyses × peak = many calls/min.
  → **Mitigation**: `FutureManager(max_workers=...)` is the existing throttle mechanism — same pattern other steps use. If rate limits become real, the `max_workers` cap is the per-step lever. Org tier confirmed before Phase 1 lands.

- **[Cross-phase Risk]** Cost increases ~3x per analysis. Accepted in the proposal but worth surfacing post-Phase-1 to confirm it stays in expected range.
  → **Mitigation**: Phase 0's telemetry includes per-call elapsed but NOT per-call token count. Phase 1's StepTimer extension can include token counts (from OpenAI response metadata) to make cost trackable too.

- **[Cross-phase Risk]** Manual eval is not regression-proof. A subtle quality change could land without the eval catching it.
  → **Mitigation**: keep the un-decomposed call-shape code paths reachable behind a feature flag for at least 30 days post-Phase-1 launch so we can compare specific surfaces if production surfaces an issue.

- **[Cross-phase Risk]** The strategy-map system prompt is 14.5K tokens. With ~50 decomposed calls all sharing it, one cache miss per analysis is ~14K wasted tokens. If production keeps the cache warm (analyses arriving < 5 min apart), the overhead per analysis is minimal. If analyses are sparse (one every 10 min), every analysis pays the cache-miss tax once.
  → **Mitigation**: monitor cache-hit telemetry once Phase 1 lands. If sparse-analysis pattern dominates, consider a "warm-up" call at pipeline start to populate the cache before the parallel block. Probably unnecessary; flagged for review.

## Migration Plan

```
Step 1 — Phase 0 Telemetry PR
  • Add StepTimer to generate_strategy_map.py.
  • Replace the discarded `_elapsed` values with timer.record(label, elapsed).
  • Single emit at end via request_executor.add_details(...).
  • Land on development. Promote to testing → production with normal cadence.
  • Soak on production for ~7 days. Capture per-call elapsed median + p95.

Step 2 — Phase 1 Perspectives PR
  • Add _strategy_map_perspectives.py with two-phase orchestration.
  • _strategy_map_assembly.py extended to assign positional IDs.
  • Old single-call paths kept under a feature flag (env var
    GENERATE_STRATEGY_MAP_DECOMPOSED=1 enables the new path; default off
    in testing+prod for the soak window).
  • Set the env var on `janus-strategy-map-worker-{env}` Lambda — NOT the
    analysis worker. Per Decision §0a, `GenerateStrategyMap.execute()`
    only runs inside the strategy-map worker after the
    `strategy-map-on-demand` change.
  • Land on development with flag ON for dev environment only.
  • Manual eval: 5 companies × dev (new) vs testing (current).
  • If eval passes, flip flag ON for testing. Soak. If pass, flip ON for prod.

Step 3 — Phase 2 V/M/VP/Arrows PR
  • Same staging pattern: feature-flagged new-call paths, dev-first rollout,
    manual eval, sequential promotion.

Step 4 — Phase 3 Per-call schemas PR
  • Schema slicing applies to all decomposed calls from Phase 1+2.
  • Lands as one PR after Phase 2 has been on prod for ~7 days.

Step 5 — Cleanup
  • After ~30 days of decomposed-path stability, remove the feature flag and
    delete the old single-call code paths. Final code shape lives in
    prompts/strategy_map/templates/decomposed/ and per_call/ schemas.
```

**Rollback strategy per step**:

- Step 1: revert telemetry PR. Loses observability; no other impact.
- Steps 2–4: flip the feature flag back to OFF. Old single-call paths reactivate. Latency reverts to ~55s.
- Step 5: this is the final cleanup; revert is `git revert` of the cleanup PR (restores feature flag + old paths).

## Open Questions

- **OpenAI org tier**: confirm tier 3+ for the production org before Phase 1 lands. The decomposed call count (~50/analysis) needs ~5K RPM headroom under burst; tier 3 gives 30K RPM, ample.
- **Cache-hit measurement**: OpenAI's `responses` API exposes cached-token count in `usage.input_tokens_details.cached_tokens`. Plumb this through `StepTimer` in Phase 0 so we measure cache hit rate from the start.
- **Existing analyses' strategy maps**: this change does not regenerate maps for already-analysed companies. New analyses get the new path; old analyses keep their old strategy map. Confirm with product that this is the right behaviour (it is — re-analyse explicitly regenerates).
- **Token-count telemetry**: out of scope for Phase 0 (just elapsed). Worth adding in Phase 1 alongside the decomposition orchestration so we can track cost-per-analysis trend.

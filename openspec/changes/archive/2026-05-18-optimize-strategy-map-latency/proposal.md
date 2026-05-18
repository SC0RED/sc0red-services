## Why

The strategy-map generation step (`GenerateStrategyMap`) makes 7 AI calls per analysis and currently runs ~50–60 seconds wall-clock. That's the dominant latency component of the analysis pipeline post-streaming-enabled — users feel it directly on every re-analyse loop. Latency complaints are the trigger; cost is acceptable as a secondary concern.

Two specific shapes drive the latency today:

1. **Output-token streaming time dominates.** Each of the 7 calls produces a structured response of 500–2000 tokens. At ~50–100 tokens/sec OpenAI throughput, big responses cost 10–20 seconds of streaming each, even when the model has nothing left to "think" about.
2. **Sequential gating between phases.** Step 1 (Vision/Mission) → Step 2 (Value Proposition) → Steps 3–6 (perspectives, parallel) → Step 7 (Arrows/Gaps). Four sequential AI rounds; the parallel block in the middle helps but doesn't break the gating.

The optimisation pattern proven in `sc0red/assessment_engine` (decompose big prompts into many tiny yes-or-one-line questions answered in parallel) maps cleanly onto strategy-map generation: most calls have a fan-out shape (5 financial objectives, 4 customer objectives, ~10 themed internal-process objectives, N pair-wise arrows) where decomposition gives back proportional latency. Combined with OpenAI's automatic prompt caching (50% off cached prefix on identical system prompt across calls within ~5 min) and the existing `StepTimer` + `FutureManager` patterns from `parallel_profile_risk` / `detail_opportunities`, the wall-clock projection is **~55s → ~17s (~3.2x faster)**.

A telemetry gap blocks measurement: today's `GenerateStrategyMap` does NOT use `StepTimer` (other AI-heavy steps do). Per-call elapsed values are returned by `_run_ai_call` but discarded. Phase 0 closes that gap as a standalone PR so production gives us baseline numbers before architectural change.

## What Changes

The change ships in four phases. Each is independently reviewable and shippable.

### Phase 0 — Telemetry first
Add `StepTimer` to `generate_strategy_map.py`. Record each of the 7 existing calls' elapsed time under labels matching the pattern in `parallel_profile_risk` (`ai_call_vision_mission`, `ai_call_value_proposition`, `ai_call_financial`, `ai_call_customer`, `ai_call_internal_processes`, `ai_call_organizational_capacity`, `ai_call_arrows_and_gaps`). Emit via `request_executor.add_details(timer.to_details())`. **No behavioural change.** Gives a week of real production timings to anchor the optimisation claims.

### Phase 1 — Decompose Steps 3–6 (perspectives) — biggest single win
Two-phase pattern per perspective:

- **Round 1** (parallel × 4): "Generate the 3–5 OBJECTIVE TITLES for the {perspective} perspective."
- **Round 2** (parallel × ~20): per title, "Elaborate this objective: definition, category, confidence, rationale_source."

For Internal Processes specifically, Round 1 generates the theme list, Round 2 generates the per-theme objective titles, and Round 3 elaborates each objective. Three rounds total, all internally parallel.

`_strategy_map_assembly.py` assigns IDs deterministically from list position (F1/F2/F3, C1..C4, I{theme}.{obj}, etc.) — see Decision §2.

### Phase 2 — Decompose Steps 1, 2, and Step 7 arrows
- Step 1: 4 tiny parallel calls (`vision_text`, `mission_text`, `vision_synthesised?`, `mission_synthesised?`).
- Step 2: 4 tiny parallel calls (`primary_vp_class`, `secondary_vp_class?`, `exemplar_company`, `rationale`).
- Step 7 arrows: N pair-wise yes/no calls in parallel ("Does objective X enable objective Y? Y/N + 1-sentence hypothesis"). Strategic priorities and gaps STAY as one synthesizing call each — they require holistic reasoning across the full map.

### Phase 3 — Per-call JSON schema slicing
Today every call ships the full ~10.6K `strategy_map_output.json` schema. With decomposition, each tiny call only populates a few fields. Slice the schema per call (e.g., a "elaborate-one-objective" schema with just `{definition, category, confidence, rationale_source}` — no `id` field per Decision §2). Reduces per-call input by ~10K tokens × ~50 calls = ~500K tokens of schema duplication. Mostly free latency win on prefill once decomposition lands.

## Capabilities

### New Capabilities

None. The optimisation does not introduce a new user-visible capability.

### Modified Capabilities

- `ai-strategy-map`: adds a new requirement for per-AI-call timing telemetry on the strategy-map step (matching the pattern other AI-heavy pipeline steps already use). Existing requirements about strategy-map content, schema validity, and persistence are unchanged — the optimisation produces an identical output shape.

## Impact

- **Backend** (Phase 0: 1 file; Phases 1–3: ~5 files): `generate_strategy_map.py` orchestration, new `_strategy_map_perspectives.py` / `_strategy_map_synthesis.py` / `_strategy_map_arrows.py` sub-modules, expanded `_strategy_map_assembly.py` (now responsible for ID assignment), per-call schema slicing.
- **Backend tests**: new unit tests covering ID-assignment-by-position, per-call schema validation, decomposed orchestration; existing strategy-map integration tests continue to pass against the same `StrategyMap` output.
- **Backend prompts** (Phase 1+): per-step user-prompt templates expand from 7 to ~15–20 per-call templates under `prompts/strategy_map/templates/decomposed/`. Existing 7 stay in place for fallback during rollout.
- **Backend schema**: `prompts/strategy_map/schemas/strategy_map_output.json` is unchanged (it's the **assembled output** schema, not per-call). New per-call schemas live under `prompts/strategy_map/schemas/per_call/` (Phase 3).
- **Infrastructure**: no changes. Same Lambda, same DynamoDB, same SQS, same model.
- **Cost**: estimated ~3x increase per analysis (~$0.37 → ~$1.26) — accepted as the trade for ~3.2x faster latency.
- **Eval**: no held-out eval set exists; quality verification is manual side-by-side comparison of dev (new) vs testing (current) on 5 representative companies. Threshold to ship: no perspective regresses (objectives missing, value-prop class flipped, arrows lost). Wording differences acceptable.
- **Out of scope**: optimising `parallel_profile_risk` / `detail_opportunities` / other AI-heavy steps — those were optimised previously and follow the patterns this change adopts. Pipeline-step caching ("skip strategy-map regen if `CompanyProfile` unchanged") is a separate concern for a future change.

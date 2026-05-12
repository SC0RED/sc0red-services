## Why

Phase 1 of `optimize-strategy-map-latency` decomposed the four perspective
generations into ~30 parallel sub-calls and brought end-to-end strategy-map
generation from ~520 s to ~180 s wall-clock on testing. Three singletons
remain undecomposed and now dominate the total: `vision_mission` (≈55 s),
`value_proposition` (≈26 s), and `arrows_and_gaps` (≈64 s). Together they
account for ~80 % of post-Phase-1 wall-clock. Decomposing them into smaller
parallel calls — using the same pattern Phase 1 proved out — should bring
end-to-end generation to ~70 s on the clean path while preserving the
assembled `StrategyMap` shape.

The latency win matters because strategy-map generation is now an on-demand
user-clicked flow; every additional second is a second the user watches
the placeholder spin.

## What Changes

- Decompose `vision_mission` (1 call → 4 parallel sub-calls): two text
  generations (vision prose, mission prose) plus two synth/yes-no
  classifications (e.g. "is the vision growth-oriented vs steady-state").
- Decompose `value_proposition` (1 call → 4 parallel sub-calls):
  `vp_primary` (single-classifier yes/no over the four Treacy-Wiersema
  archetypes), `vp_secondary`, `vp_exemplar`, `vp_rationale`.
- Decompose `arrows_and_gaps` (1 call → ~15–25 yes/no arrow calls running
  in parallel + 1 holistic `priorities` call + 1 holistic `gaps` call):
  each arrow call asks "Does objective X enable objective Y? Yes/No,
  plus one-sentence hypothesis if Yes."
- Add a new feature flag `GENERATE_STRATEGY_MAP_DECOMPOSED_SYNTHESIS=1`
  gating the new behaviour, layered on top of the existing
  `GENERATE_STRATEGY_MAP_DECOMPOSED` flag from Phase 1.
- Stable label conventions for every new call so existing per-AI-call
  telemetry from PR #265 captures them: `ai_call_vision_text`,
  `ai_call_mission_text`, `ai_call_vision_synth`, `ai_call_mission_synth`,
  `ai_call_vp_primary`, `ai_call_vp_secondary`, `ai_call_vp_exemplar`,
  `ai_call_vp_rationale`, `ai_call_arrow_{from_id}_{to_id}`,
  `ai_call_priorities`, `ai_call_gaps`.
- Assembly modules (`_strategy_map_synthesis.py`, `_strategy_map_arrows.py`)
  merge sub-call results back into the existing `VisionStatement`,
  `MissionStatement`, `ValueProposition`, and arrows-list shapes — the
  assembled-output JSON schema (`strategy_map_output.json`) does NOT
  change.

## Capabilities

### New Capabilities

_None_ — this change does not introduce a new user-facing capability; it
refines the implementation of an existing one.

### Modified Capabilities

- `ai-strategy-map`: extends the existing decomposed call-shape
  requirements (added in `optimize-strategy-map-latency`) to cover the
  three remaining synthesis singletons. Output shape unchanged;
  per-call labels and decomposition rules added.

## Impact

- **Backend pipeline**:
  - New modules `backend/src/pipeline/pipeline_steps/_strategy_map_synthesis.py`
    and `backend/src/pipeline/pipeline_steps/_strategy_map_arrows.py`.
  - `GenerateStrategyMap.execute()` switches synthesis singletons on the
    new feature flag (additive — keeps existing decomposed-perspective
    path).
  - New prompt templates under `backend/src/pipeline/prompts/strategy_map/templates/decomposed/`
    (`vision_text.md`, `mission_text.md`, `vision_synth.md`, `mission_synth.md`,
    `vp_primary.md`, `vp_secondary.md`, `vp_exemplar.md`, `vp_rationale.md`,
    `arrow_yesno.md`).
  - New per-call schemas under `backend/src/pipeline/prompts/strategy_map/schemas/per_call/`
    (`vision_text.json`, `mission_text.json`, `synth_yesno.json`,
    `vp_primary.json`, `vp_secondary.json`, `vp_exemplar.json`,
    `vp_rationale.json`, `arrow_yesno.json`).
- **Infrastructure**:
  - `strategy_map_construct.py` sets the new env var on the strategy-map
    worker only on environments where Phase 1 (`GENERATE_STRATEGY_MAP_DECOMPOSED=1`)
    is already enabled.
- **Concurrency**:
  - Peak parallel OpenAI requests per user-click goes from ~12 (Phase 1
    internal-detail bank) to ~25 (arrows yes/no bank). The change is
    blocked on confirming OpenAI org-tier headroom.
- **Cost**:
  - Total token count increases (~3x estimated) because each sub-call
    repeats portions of the system prompt. Mitigated partly by OpenAI
    prompt-prefix cache hits across the parallel sub-calls.
- **Frontend**: unchanged. Assembled `StrategyMap` JSON shape is identical.
- **Tests**: new unit tests for the synthesis and arrows assembly modules
  plus an integration test asserting the full decomposed pipeline produces
  a valid `StrategyMap`.
- **Quality gate**: same manual eval pattern as Phase 1 — 5 representative
  companies, side-by-side dev vs testing, no perspective regresses, value-
  proposition class preserved, no arrows lost.

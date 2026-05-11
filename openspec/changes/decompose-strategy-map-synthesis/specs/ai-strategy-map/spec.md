## ADDED Requirements

### Requirement: Strategy-map step decomposes vision/mission synthesis when the synthesis-decomposition flag is enabled

When the environment variable `GENERATE_STRATEGY_MAP_DECOMPOSED_SYNTHESIS=1` is set on the strategy-map worker (and the Phase 1 `GENERATE_STRATEGY_MAP_DECOMPOSED=1` is also set), `GenerateStrategyMap.execute()` SHALL split the single `vision_mission` AI call into four parallel sub-calls. The sub-calls SHALL run under a `FutureManager` with `max_workers=4` and SHALL produce, after assembly, the same `VisionStatement` and `MissionStatement` shapes that the non-decomposed path produces.

The four sub-calls and their labels:

- `ai_call_vision_text` — generates the vision prose only.
- `ai_call_mission_text` — generates the mission prose only.
- `ai_call_vision_synth` — yes/no classification fields about the vision (e.g. growth-oriented vs steady-state).
- `ai_call_mission_synth` — yes/no classification fields about the mission.

Each sub-call SHALL use its own prompt template under `prompts/strategy_map/templates/decomposed/` and its own per-call schema under `prompts/strategy_map/schemas/per_call/`. Assembly logic in `_strategy_map_synthesis.py` SHALL merge the four sub-call results into the assembled `VisionStatement` and `MissionStatement` records expected by the downstream `StrategyMap` schema.

#### Scenario: Vision/mission decomposed sub-calls fire in parallel

- **WHEN** `GenerateStrategyMap.execute()` runs with both decomposition flags set
- **THEN** the CloudWatch detail block for `GenerateStrategyMap.timings` contains entries for `ai_call_vision_text`, `ai_call_mission_text`, `ai_call_vision_synth`, and `ai_call_mission_synth`
- **AND** no entry labelled `ai_call_vision_mission` appears
- **AND** the four entries' start timestamps fall within ~100 ms of each other

#### Scenario: Vision/mission assembled output is identical to non-decomposed path

- **WHEN** a strategy map is generated with synthesis decomposition enabled
- **THEN** the persisted `StrategyMap` artifact contains `visionStatement` and `missionStatement` fields with the same shape and field types as a strategy map generated with synthesis decomposition disabled
- **AND** validation against `strategy_map_output.json` passes

### Requirement: Strategy-map step decomposes value-proposition synthesis when the synthesis-decomposition flag is enabled

When the environment variable `GENERATE_STRATEGY_MAP_DECOMPOSED_SYNTHESIS=1` is set, `GenerateStrategyMap.execute()` SHALL split the single `value_proposition` AI call into four parallel sub-calls running under `FutureManager(max_workers=4)`:

- `ai_call_vp_primary` — single classifier returning one enum value from `{operational_excellence, customer_intimacy, product_leadership, hybrid}`.
- `ai_call_vp_secondary` — only meaningful when `vp_primary` is `hybrid`; otherwise discarded during assembly.
- `ai_call_vp_exemplar` — short prose: company-X-is-a-famous-example.
- `ai_call_vp_rationale` — short prose: why-this-company-maps-here.

Assembly logic in `_strategy_map_synthesis.py` SHALL build the final `ValueProposition` record honouring `vp_primary` (only set `secondary` when `primary == hybrid`).

#### Scenario: Value-proposition decomposed sub-calls fire in parallel

- **WHEN** `GenerateStrategyMap.execute()` runs with both decomposition flags set
- **THEN** the CloudWatch detail block contains entries for `ai_call_vp_primary`, `ai_call_vp_secondary`, `ai_call_vp_exemplar`, `ai_call_vp_rationale`
- **AND** no entry labelled `ai_call_value_proposition` appears

#### Scenario: vp_primary classification drives secondary inclusion

- **WHEN** `vp_primary` returns `hybrid`
- **THEN** the assembled `ValueProposition.secondary` field is set from the `vp_secondary` sub-call result
- **AND** when `vp_primary` returns any other value, the assembled `ValueProposition.secondary` field is `null`

### Requirement: Strategy-map step decomposes arrow generation into per-pair yes/no calls when the synthesis-decomposition flag is enabled

When `GENERATE_STRATEGY_MAP_DECOMPOSED_SYNTHESIS=1` is set, `GenerateStrategyMap.execute()` SHALL replace the monolithic `arrows_and_gaps` call with:

- A parallel bank of yes/no AI calls — one per candidate arrow pair drawn from the four-perspective causal hierarchy — running under `FutureManager(max_workers=25)`. Each call asks "Does objective X enable objective Y? Yes/No, plus one-sentence hypothesis if Yes." Per-call schema: `{enables: bool, hypothesis: string | null}`. Labels follow `ai_call_arrow_{from_id}_{to_id}` (matching the convention established by the parent change).
- One holistic `ai_call_priorities` call producing the strategic-priorities section.
- One holistic `ai_call_gaps` call producing the strategic-gaps section.

The arrows yes/no bank, `priorities`, and `gaps` SHALL all run concurrently (no inter-dependency). Assembly logic in `_strategy_map_arrows.py` SHALL:

1. Enumerate candidate pairs across the causal hierarchy (`capacity → internal_processes`, `internal_processes → customer`, `customer → financial`).
2. Filter the yes/no results to those where `enables == true`.
3. Construct `Arrow(from=from_id, to=to_id, hypothesis=hypothesis)` records from the filtered results.

#### Scenario: Arrows yes/no bank fires in parallel with priorities and gaps

- **WHEN** `GenerateStrategyMap.execute()` runs with synthesis decomposition enabled and the candidate-pair enumeration returns N pairs
- **THEN** the CloudWatch detail block contains exactly N entries labelled `ai_call_arrow_{from_id}_{to_id}`
- **AND** the detail block contains entries labelled `ai_call_priorities` and `ai_call_gaps`
- **AND** no entry labelled `ai_call_arrows_and_gaps` appears

#### Scenario: Only enables-true pairs become arrows in the assembled output

- **WHEN** a yes/no sub-call returns `{enables: false}`
- **THEN** the assembled `StrategyMap.arrows` list does NOT contain an `Arrow` for that pair
- **AND** when a yes/no sub-call returns `{enables: true, hypothesis: "<text>"}`
- **THEN** the assembled `StrategyMap.arrows` list contains an `Arrow` for that pair with the returned hypothesis

#### Scenario: Holistic priorities and gaps remain unaffected by arrow decomposition

- **WHEN** synthesis decomposition is enabled
- **THEN** the assembled `StrategyMap.strategicPriorities` is produced by a single AI call (no decomposition)
- **AND** the assembled `StrategyMap.gaps` is produced by a single AI call (no decomposition)

### Requirement: The synthesis-decomposition flag requires the Phase 1 decomposition flag

The feature-flag layering for strategy-map decomposition SHALL be: `GENERATE_STRATEGY_MAP_DECOMPOSED_SYNTHESIS=1` is only honoured when `GENERATE_STRATEGY_MAP_DECOMPOSED=1` is also set. If the synthesis flag is set without the Phase 1 flag, `GenerateStrategyMap.execute()` SHALL raise a configuration error before any AI call is made.

#### Scenario: Synthesis flag without Phase 1 flag fails fast

- **WHEN** `GENERATE_STRATEGY_MAP_DECOMPOSED_SYNTHESIS=1` is set and `GENERATE_STRATEGY_MAP_DECOMPOSED` is unset (or `0`)
- **THEN** `GenerateStrategyMap.execute()` raises a configuration error
- **AND** no AI calls are made

#### Scenario: Both flags off falls back to monolithic call shape

- **WHEN** both flags are unset
- **THEN** `GenerateStrategyMap.execute()` runs today's 7-call monolithic call shape
- **AND** no error is raised

### Requirement: Decomposed synthesis call shape preserves the assembled StrategyMap output schema

When synthesis decomposition is enabled, the assembled `StrategyMap` JSON output SHALL validate against the existing `prompts/strategy_map/schemas/strategy_map_output.json` schema with no additions or removals. All field types, IDs, and structural constraints (e.g., regex patterns for objective IDs) SHALL be identical to those produced by the non-decomposed call shape.

#### Scenario: Decomposed-synthesis output validates against the unchanged output schema

- **WHEN** a strategy map is generated with synthesis decomposition enabled
- **THEN** the persisted `StrategyMap` JSON validates against `prompts/strategy_map/schemas/strategy_map_output.json` without modifications to that schema file

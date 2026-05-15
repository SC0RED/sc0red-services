## MODIFIED Requirements

### Requirement: Strategy maps are generated as part of the analysis pipeline (not on-demand)

The strategy map SHALL be generated automatically as the last step of the company analysis pipeline before `PersistResults`, using the existing `GenerateStrategyMap` `RequestStep`. The strategy map MUST be persisted on the assessment record alongside other analysis output (risk scores, opportunities, EBITDA tree, value chain) and MUST be returned by `GET /api/analysis/{id}` as a `strategyMap` field on the response. Strategy-map generation MUST NOT require a separate user action (CTA click, API trigger, or other opt-in step) for analyses created after this change ships.

A new endpoint `POST /api/analysis/{id}/strategy-map/regenerate` SHALL exist to regenerate the strategy map for an existing persisted analysis that does not have one (e.g., analyses created before this change). This endpoint is the ONLY surviving API surface from the prior on-demand pattern; the previously-existing `POST /api/analysis/{id}/strategy-map` (on-demand-trigger) endpoint is removed.

#### Scenario: New analysis produces a strategy map in the same scan

- **WHEN** a single company analysis runs end-to-end
- **THEN** the persisted assessment record contains a populated `strategyMap` field by the time `PersistResults` completes
- **AND** the API response from `GET /api/analysis/{id}` includes the `strategyMap` field
- **AND** no separate strategy-map worker Lambda or SQS queue is invoked
- **AND** no user action is required to surface the strategy map

#### Scenario: Re-analysis regenerates the strategy map

- **WHEN** a user re-analyses a company (e.g. after uploading a document)
- **THEN** the pipeline regenerates the strategy map using the updated inputs as part of the same scan
- **AND** the previous strategy map is replaced on the assessment record

#### Scenario: Old analyses can regenerate their strategy map on demand

- **WHEN** an analysis predates this change and has no `strategyMap` field
- **AND** a user clicks the "Regenerate strategy map" affordance on the analysis-detail page
- **THEN** the API receives a `POST /api/analysis/{id}/strategy-map/regenerate` request
- **AND** the server runs `GenerateStrategyMap` against the persisted analysis inputs
- **AND** the assessment record is updated with the new strategy map
- **AND** the analysis-detail page re-renders showing the strategy map

#### Scenario: Strategy-map step failure does not block the rest of the analysis

- **WHEN** `GenerateStrategyMap` raises during the pipeline scan
- **THEN** the failure is recorded on the assessment record but does NOT prevent `PersistResults` from writing the rest of the analysis output
- **AND** the analysis-detail page renders the "Regenerate strategy map" affordance in place of the strategy map

### Requirement: Strategy map omits the "What's Missing" gaps section

The generated `StrategyMap` artifact SHALL NOT contain a `whatsMissing` (gaps) field. The Pydantic model, the JSON output schema, the prompt template, and the AI call for generating gaps are all removed.

#### Scenario: New strategy maps have no whatsMissing field

- **WHEN** a strategy map is generated end-to-end
- **THEN** the persisted `StrategyMap` JSON has no `whatsMissing` key
- **AND** the CloudWatch detail block for `GenerateStrategyMap.timings` has no `ai_call_gaps` entry

#### Scenario: Legacy strategy maps with whatsMissing data continue to load

- **WHEN** an analysis persisted before this change contains a `whatsMissing` field on its strategy map
- **THEN** the API returns the strategy-map record without error (Pydantic ignores the extra field)
- **AND** the frontend renders the strategy map without the gaps section

### Requirement: Strategy-map generation uses the decomposed call shape unconditionally

The `GenerateStrategyMap.execute()` method SHALL always run the decomposed call shape (Round-1 perspective titles → Round-2 details → Round-3 internal-detail elaboration → arrows yes/no bank + holistic priorities, per the `optimize-strategy-map-latency` and `decompose-strategy-map-synthesis` changes). The previously-existing `GENERATE_STRATEGY_MAP_DECOMPOSED` and `GENERATE_STRATEGY_MAP_DECOMPOSED_SYNTHESIS` environment-variable feature flags are removed. The legacy monolithic step runners (`_strategy_map_legacy_steps.py`) are deleted.

#### Scenario: No feature flags gate the call shape

- **WHEN** any strategy map is generated
- **THEN** the decomposed call shape is used
- **AND** no environment-variable check gates the path
- **AND** the codebase contains no monolithic legacy step runners (`_strategy_map_legacy_steps.py` is absent)

## REMOVED Requirements

### Requirement: Strategy-map generation has its own dedicated SQS queue + worker Lambda

**Reason**: Strategy-map generation is now part of the analysis pipeline (see the modified requirement above). The dedicated SQS queue, worker Lambda, AppSync wiring, and `infrastructure/stacks/strategy_map_construct.py` are deleted.

**Migration**: any in-flight messages in the dedicated SQS queue at the time of cutover MUST be drained before the queue is deleted. The new pipeline integration does not consume from that queue.

### Requirement: Strategy-map generation pushes completion events via AppSync

**Reason**: AppSync push events were necessary when strategy-map generation ran asynchronously in a separate worker after the analysis-detail page had loaded. With pipeline integration, the strategy map is present in the analysis response by the time the analysis-detail page loads; no push is needed.

**Migration**: the AppSync `strategy_map_progress` and `strategy_map_complete` event types and their subscription handlers are removed.

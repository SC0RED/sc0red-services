## ADDED Requirements

### Requirement: Strategy-map step emits per-AI-call timing telemetry

The `GenerateStrategyMap` pipeline step SHALL record wall-clock elapsed time for every AI call it makes and SHALL emit those timings to CloudWatch via `request_executor.add_details(...)` using the same `StepTimer` pattern that other AI-heavy pipeline steps (`ParallelProfileRiskAndIdeation`, `DetailOpportunities`) already follow. The emitted detail block SHALL be keyed `GenerateStrategyMap.timings` and SHALL include one entry per AI call labelled `ai_call_{descriptor}` plus a `total` entry covering the step's full wall-clock duration.

This requirement applies to every call shape — both today's 7 sequential-and-parallel calls and any future decomposed call layout introduced by `optimize-strategy-map-latency`. The label naming convention SHALL be stable enough to drive CloudWatch dashboards: per-stage labels follow `ai_call_titles_{perspective}` / `ai_call_detail_{perspective}_{id}` / `ai_call_arrow_{from_id}_{to_id}` for decomposed calls, and one-word descriptors (`ai_call_vision_mission`, `ai_call_value_proposition`, etc.) for any non-decomposed calls.

#### Scenario: Per-call timings appear in CloudWatch

- **WHEN** a strategy map is generated for any company
- **THEN** the pipeline run's CloudWatch detail payload contains a `GenerateStrategyMap.timings` object
- **AND** the object has one entry per AI call the step made
- **AND** the object includes a `total` entry covering the step's overall wall-clock

#### Scenario: Failed calls still report timing

- **WHEN** an AI call within `GenerateStrategyMap` raises an exception
- **THEN** the step propagates the exception (no swallowing) AND the partial `timings` block is still emitted via `request_executor.add_details(...)` for the calls that completed
- **AND** the failed call's elapsed time is recorded if measurable, omitted otherwise

#### Scenario: Decomposed calls follow the labelling convention

- **WHEN** the strategy-map step is running with the decomposed call shape (post-`optimize-strategy-map-latency` Phase 1+)
- **THEN** the perspective-titles calls are labelled `ai_call_titles_{perspective}` (e.g., `ai_call_titles_financial`)
- **AND** the per-objective elaboration calls are labelled `ai_call_detail_{perspective}_{id}` (e.g., `ai_call_detail_financial_F1`)
- **AND** the arrow yes/no calls are labelled `ai_call_arrow_{from_id}_{to_id}` (e.g., `ai_call_arrow_C2_F1`)

### Requirement: Strategy-map step uses positional ID assignment in assembly

When the strategy-map step is running with the decomposed call shape, per-call AI responses SHALL NOT be required to include the `id` field for any objective, theme, or gap. The assembly module (`_strategy_map_assembly.py`) SHALL assign IDs deterministically from list position, matching the regex patterns enforced by `strategy_map_output.json`:

- Financial objectives: `F1`, `F2`, `F3` by list order.
- Customer objectives: `C1`..`C4` by list order.
- Internal-process themes: indexed `1`..`3` by list order; objectives within a theme indexed `1`..`9` by list order; assembled IDs follow `I{theme_index}.{objective_index}`.
- Capacity objectives: `O.P` (people), `O.T` (technology), `O.C` (culture) — the bucket determines the ID, not the list position.
- Gaps: `G1`..`G9` by list order.

The non-decomposed call shape (today's behaviour) MAY continue to emit IDs from the AI response — this requirement does not retroactively change existing call shapes.

#### Scenario: Decomposed financial-perspective elaboration calls return content without IDs

- **WHEN** a parallel elaboration call for a financial objective returns
- **THEN** the response contains `definition`, `category`, `confidence`, and `rationale_source` fields
- **AND** the response does NOT contain an `id` field

#### Scenario: Assembly assigns IDs by list position

- **WHEN** `_strategy_map_assembly.py` constructs a `FinancialPerspective` from a title list and a parallel-elaboration result list
- **THEN** the resulting `FinancialObjective` instances have IDs `F1`, `F2`, `F3` in the same order as the title list
- **AND** the IDs match the regex `^F[123]$` enforced by `strategy_map_output.json`

#### Scenario: Internal-process theme IDs follow positional encoding

- **WHEN** `_strategy_map_assembly.py` constructs an `InternalProcessesPerspective` from a theme list, per-theme title lists, and per-objective elaboration results
- **THEN** the first theme's first objective has ID `I1.1`, second objective `I1.2`, etc.
- **AND** the second theme's first objective has ID `I2.1`, etc.
- **AND** every assembled ID matches the regex `^I[1-3]\.[1-9]$` enforced by `strategy_map_output.json`

## ADDED Requirements

### Requirement: AI call sites declare precision tier matching their quality bar

Every AI call site SHALL pass an explicit `precision: Precision` value matching the quality requirements of the workload. The codebase SHALL support two precision tiers backed by distinct models:

- `Precision.STANDARD` — bulk parallel calls + short structured outputs where latency and cost dominate; backed by a small/fast model (`gpt-5.4-mini` as of 2026-05).
- `Precision.ADVANCED` — calls where output specificity, audit-trail quality, or nuanced reasoning dominate; backed by the full-precision model (`gpt-5.1` as of 2026-05).

The default for `ai_call.run_structured_ai_call` SHALL be `Precision.STANDARD`. Call sites with a higher quality bar SHALL pass `precision=Precision.ADVANCED` explicitly at the call site, not via global config.

#### Scenario: Bulk parallel strategy-map calls use STANDARD precision

- **WHEN** the strategy-map decomposed path fires its arrow-yes/no bank, objective-detail elaborations, perspective titles, vision/mission/value-proposition synthesis, or holistic priorities calls
- **THEN** every one of those calls uses `Precision.STANDARD`
- **AND** the resolved model name in `OPENAI_MODEL_MAP[Precision.STANDARD.value]` is the configured mini variant
- **AND** the per-call telemetry payload records the actual model used in `metadata.model`

#### Scenario: Higher-quality call sites can opt out via Precision.ADVANCED

- **WHEN** a pipeline step's quality benchmark documents a regression on the STANDARD model for that step's output
- **THEN** the step SHALL pass `precision=Precision.ADVANCED` to `ai_client_factory.get_client(...)` at its call site
- **AND** the override applies only to that call site, leaving other call sites on STANDARD
- **AND** the step's commit log / OpenSpec change documents the benchmark finding that justified the override

#### Scenario: Schema compliance is validated on every call regardless of model

- **WHEN** a structured AI call completes with a model emitting a response
- **THEN** `ai_call.run_structured_ai_call` runs `jsonschema.validate(response.content, schema)` (already shipped in 2026-05-15)
- **AND** validation failure raises `jsonschema.ValidationError` regardless of which model produced the response
- **AND** the retry layer above handles the retry on validation errors

### Requirement: Model upgrades are gated on a published benchmark

Any change to the model string in `signalfield-core`'s `OPENAI_MODEL_MAP` SHALL be preceded by a benchmark run that produces a markdown comparison report. The report SHALL include:

- Aggregate metrics: average latency, total cost, schema compliance rate, error count for both baseline and candidate.
- Per-prompt comparison: cost, latency, token counts, schema compliance, and a human-tagged quality verdict (✅ equivalent / 🟡 acceptable / 🔴 regression).
- A recommendation: ✅ ship / 🔴 don't ship / 🟡 ship with per-call-site overrides.

The report SHALL be committed to `backend/scripts/benchmark/results/` alongside the raw JSON outputs from both runs.

#### Scenario: Model change without published benchmark is blocked

- **WHEN** a PR proposes updating `OPENAI_MODEL_MAP[Precision.STANDARD.value]` in `signalfield-core`
- **AND** the PR description does NOT link to a benchmark comparison report
- **THEN** the change SHALL be requested to add the benchmark output before merge
- **AND** the architecture-reviewer agent SHALL flag this as a CRITICAL finding

#### Scenario: Benchmark with regression on specific call site informs per-site override

- **WHEN** a benchmark run flags a 🔴 regression on the `detail` schema (DetailOpportunities) but not on strategy-map schemas
- **THEN** the model upgrade still proceeds, but `DetailOpportunities._run_ai_call` is updated to pass `precision=Precision.ADVANCED`
- **AND** the OpenSpec change's commit log captures the 🔴 finding and the per-site override

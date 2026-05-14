# ai-strategy-map Specification

## Purpose

Backend pipeline generation of a Balanced Scorecard strategy map artifact, with Vector Advisory house-style content, customer value-proposition classification, confidence markers, "What's Missing?" gaps, and analysis-page rendering with deep-dive CTA.

## Requirements

### Requirement: Strategy maps are generated on-demand via a dedicated API + worker, not as part of the analysis pipeline

The company analysis pipeline SHALL NOT include a `GenerateStrategyMap` step. Instead, strategy maps are generated on-demand: a user clicks a CTA on the analysis page, the frontend POSTs to `POST /api/analysis/{id}/strategy-map`, the API handler enqueues an SQS message on the dedicated `janus-strategy-map-queue`, the worker Lambda consumes the message and runs the generation against the existing analysis data, and the worker persists the result + pushes a completion event via AppSync.

The on-demand worker SHALL consume the same input shape as the previous pipeline-step did: scraped content + `CompanyProfile` + `RiskAssessment` + `OpportunityResult` + `EbitdaTreeResult` + `ValueChainResult` + uploaded document text + the Vector white-paper system prompt + Mobil/Wawa exemplars. The strategy-map generation algorithm itself is unchanged — only the trigger and timing change.

The strategy map SHALL be persisted on the assessment record (`assessment_repo.save_strategy_map(...)`) and SHALL be returned by `GET /api/analysis/{id}` as a `strategyMap` field on the response when present, omitted when absent.

A `strategy_map_generation_state` field on the COMPANY record (not the assessment record) SHALL track in-flight generation: present with value `"generating"` while the worker is processing, absent otherwise. The frontend reads this on `GET /api/analysis/{id}` to render the appropriate UI state on cold load and on refresh during generation.

#### Scenario: Newly analysed company has no strategy map until generation is requested

- **WHEN** a fresh company analysis completes
- **THEN** the persisted assessment record does NOT contain a `strategyMap` field
- **AND** the API response from `GET /api/analysis/{id}` omits the `strategyMap` field
- **AND** the frontend renders the strategy-map slot in CTA state ("Generate strategy map" button)

#### Scenario: User clicks "Generate strategy map"

- **WHEN** the frontend POSTs to `/api/analysis/{id}/strategy-map`
- **THEN** the handler validates the analysis exists + the user has access (org check), sets `strategy_map_generation_state = "generating"` on the company record, enqueues an SQS message on `janus-strategy-map-queue` carrying `{analysis_id, scan_id}`, and returns 202 Accepted immediately
- **AND** subsequent `GET /api/analysis/{id}` responses surface the `"generating"` state until the worker completes

#### Scenario: Worker completes generation

- **WHEN** the strategy-map worker Lambda finishes generation successfully
- **THEN** the worker persists the strategy map via `assessment_repo.save_strategy_map(...)`, clears `strategy_map_generation_state` from the company record, and pushes an AppSync `strategy_map_complete` event keyed by `analysis_id`
- **AND** subsequent `GET /api/analysis/{id}` responses include the `strategyMap` field
- **AND** the frontend, on receipt of the AppSync event OR via natural cold-load, transitions to the present state and renders `StrategyMapView`

#### Scenario: Worker fails generation

- **WHEN** the strategy-map worker Lambda fails to generate (e.g., AI client error, schema validation failure)
- **THEN** the worker logs the error to CloudWatch, clears `strategy_map_generation_state` from the company record, and pushes an AppSync `strategy_map_failed` event with a generic error message
- **AND** the frontend transitions back to CTA state with a "Generation failed — try again" message above the button
- **AND** the SQS message is retried up to 3 times before landing in the DLQ (CloudWatch alarm fires for ops)

### Requirement: Re-analysing a company invalidates the persisted strategy map

When a re-analyse is triggered on a company (with or without document upload), the re-analyse handler SHALL clear the persisted strategy map from the assessment record before the analysis pipeline starts. The strategy map is invalidated unconditionally on every re-analyse — re-analyse can update scraped content, profile, risks, opportunities, EBITDA, and value chain even without a document upload, all of which feed the strategy-map generation. Tying invalidation only to "with new docs" would surface stale strategy maps relative to a refreshed diagnosis.

The frontend SHALL render the CTA state after re-analyse completes; users explicitly re-generate by clicking "Generate strategy map" against the new diagnosis.

#### Scenario: Re-analyse without document upload clears the map

- **WHEN** a user clicks Re-analyse on an analysis that has a persisted strategy map (no documents uploaded in the same action)
- **THEN** the persisted strategy map is cleared from the assessment record before the pipeline runs
- **AND** the post-re-analyse `GET /api/analysis/{id}` response omits the `strategyMap` field
- **AND** the frontend renders the strategy-map slot in CTA state

#### Scenario: Re-analyse with document upload also clears the map

- **WHEN** a user uploads a new document and clicks Re-analyse
- **THEN** the persisted strategy map is cleared from the assessment record before the pipeline runs (same as the no-document case)

### Requirement: Existing strategy maps remain visible until invalidated

Strategy maps generated by the legacy pipeline-step path (before this change) SHALL continue to render on the analysis page after this change ships. They are not retroactively cleared. They are invalidated only when a re-analyse fires (per the re-analyse-invalidation requirement).

#### Scenario: Pre-change analysis still shows its auto-generated map

- **WHEN** an analysis whose strategy map was auto-generated before this change is loaded
- **THEN** `GET /api/analysis/{id}` returns the strategy map as before
- **AND** the frontend renders `StrategyMapView` in the present state at Beat 6

### Requirement: Strategy-map generation pushes completion events via AppSync

The strategy-map worker Lambda SHALL push completion events via the existing AppSync infrastructure on the same event channel used for pipeline progress (`appsync_notifier`). Two event types:

- `strategy_map_complete` payload: `{analysis_id, scan_id}`. Fired on successful generation.
- `strategy_map_failed` payload: `{analysis_id, scan_id, error_message}`. Fired on worker error after retries.

The events do NOT carry the strategy-map content — frontend re-fetches via `GET /api/analysis/{id}` on receipt of `strategy_map_complete`. This keeps the persistence layer (DynamoDB) as the single source of truth and keeps AppSync payloads small.

The frontend hook `useStrategyMapSubscription(analysisId)` SHALL filter AppSync events on `analysis_id` and trigger a re-fetch on `complete` or transition to failure UI on `failed`. The hook SHALL implement a 90-second client-side timeout that triggers a one-time fallback `GET /api/analysis/{id}` if no AppSync event arrives — guarding against dropped subscriptions.

#### Scenario: Frontend renders the result via AppSync push

- **WHEN** the frontend is in generating state, subscribed to AppSync, and the worker pushes `strategy_map_complete`
- **THEN** the hook triggers a `GET /api/analysis/{id}` fetch
- **AND** the response carries the persisted strategy map
- **AND** the slot transitions to the present state without a manual refresh

#### Scenario: AppSync push is dropped; client-side fallback fires

- **WHEN** the frontend is in generating state for 90+ seconds without an AppSync event
- **THEN** the subscription hook fires a one-time fallback `GET /api/analysis/{id}`
- **AND** if the response carries the map (worker completed, AppSync dropped), the slot transitions to present
- **AND** if the response still shows generating state, the slot continues to wait for AppSync without further fallbacks

### Requirement: Strategy-map generation has its own dedicated SQS queue + worker Lambda

The infrastructure SHALL provide a dedicated `janus-strategy-map-queue` SQS queue + DLQ + CloudWatch alarm on DLQ depth (per environment), defined in `infrastructure/stacks/janus_stack.py`. The queue is consumed by a dedicated `strategy_map_handler` Lambda whose only job is to run strategy-map generation jobs.

The queue is dedicated (not piggy-backed on the existing `janus-analysis-queue`) for three reasons documented in `design.md` Decision §2: independent scaling, independent monitoring, isolated failure blast radius.

#### Scenario: Worker drains the dedicated queue

- **WHEN** an SQS message lands on `janus-strategy-map-queue`
- **THEN** only the `strategy_map_handler` Lambda processes it
- **AND** the analysis-pipeline worker Lambda is unaffected (no shared visibility timeout, no shared concurrency budget)

#### Scenario: DLQ depth alarm fires on persistent failures

- **WHEN** strategy-map generation fails 3 times for the same SQS message and lands in the DLQ
- **THEN** the CloudWatch alarm on DLQ depth fires for ops
- **AND** the front-end already showed the user a "Generation failed — try again" message via the AppSync `strategy_map_failed` event

### Requirement: Strategy map content uses Vector Advisory house style

Generated strategy maps SHALL follow the Vector Advisory house style derived from the leader's calibration corpus. Specifically:

- The Customer perspective objectives SHALL be written as first-person customer-voice quotes (e.g. *"Wawa is my preferred destination for on-the-go breakfast..."*), not corporate-voice imperatives.
- The Internal Processes perspective objectives SHALL be organised into 2-3 named themes that connect to the Financial perspective's revenue or productivity strategies.
- The Organizational Capacity perspective SHALL contain exactly three objectives, one each for **People**, **Technology**, and **Culture** — the third bucket is Culture (per Kaplan & Norton canonical) rather than Financial Management.
- Objective definitions SHALL be 50-150 words written in "We will…" first-person plural voice.
- Each pair of perspectives in the visual layout SHALL have an associated narrative connector phrase (e.g. *"Enables us to deliver"* between Capacity and Internal Processes).
- A core values strip SHALL appear as a foundation row beneath the Organizational Capacity perspective.

#### Scenario: Customer perspective renders quoted customer voice

- **WHEN** a strategy map is generated for any company
- **THEN** every Customer-perspective objective's title is a first-person quote
- **AND** the objective definition continues in first-person customer voice

#### Scenario: Internal Processes are themed, not flat

- **WHEN** a strategy map is generated for any company with at least 4 internal-process objectives
- **THEN** the objectives are grouped into 2-3 named themes
- **AND** each theme name is a verb-led phrase (e.g. "Grow Through Foodservice", "Expand Profitably")

#### Scenario: Organizational Capacity has the three-bucket structure

- **WHEN** a strategy map is generated for any company
- **THEN** the Organizational Capacity perspective contains exactly three objectives
- **AND** they are bucketed as People, Technology, Culture (one each)

### Requirement: Customer Value Proposition is classified explicitly

Every generated strategy map SHALL include an explicit classification of the company's primary Customer Value Proposition as one of `operational_excellence`, `customer_intimacy`, `product_leadership`, or `hybrid`. When `hybrid` is chosen, the schema SHALL also include a `secondary` field naming the second proposition and a `rationale` field explaining why neither single proposition fits.

The classification SHALL be derived from the scraped company content, opportunity strategic categories, and value chain emphasis — using the framework definitions from `guides/kaplan_norton_framework.md`.

#### Scenario: Single-strategy company classifies cleanly

- **WHEN** a company's public positioning aligns clearly with one of the three propositions
- **THEN** the strategy map's `valueProposition.primary` is set to that proposition
- **AND** `valueProposition.secondary` is omitted

#### Scenario: Hybrid company surfaces the dual classification

- **WHEN** a company's public positioning shows two strong propositions (e.g. customer intimacy + operational excellence)
- **THEN** `valueProposition.primary` is `hybrid`
- **AND** `valueProposition.secondary` names the second proposition
- **AND** `valueProposition.rationale` is a one-sentence justification

### Requirement: Every objective carries a confidence marker

Every generated objective SHALL be tagged with one of three confidence levels:

- `HIGH` — directly inferred from concrete public data (e.g. financial objective derived from EBITDA tree)
- `MEDIUM` — typical of similar companies in this industry, pattern-matched but not directly observed
- `LOW` — inferred from absence; reasonable but unverified

Confidence markers SHALL be visible to the user as small visual chips on each objective card in the rendered output.

#### Scenario: Financial-perspective objectives derived from EBITDA carry HIGH confidence

- **WHEN** the strategy map's Financial perspective objectives are generated from a populated EBITDA tree
- **THEN** at least one objective is tagged HIGH confidence
- **AND** the rendered card displays the HIGH chip

#### Scenario: Cultural objectives carry LOW confidence by default

- **WHEN** the Organizational Capacity perspective's Culture objective is generated for a company without explicit public values content
- **THEN** the objective is tagged LOW confidence
- **AND** it appears as a candidate gap in the "What's Missing?" panel

### Requirement: Strategy map does NOT include measures, targets, or initiatives

The v1 strategy map output SHALL contain Vision, Mission, Strategic Priorities, the four perspectives' Objectives + Definitions, Causal Arrows, "What's Missing?" gaps, and Core Values. The output SHALL NOT include Measures, Targets, or Initiatives — those are deferred to a deep-dive engagement and their visible absence is the conversion hook.

#### Scenario: Generated map omits scorecard columns

- **WHEN** any strategy map is generated
- **THEN** the schema does not include `measures`, `targets`, or `initiatives` fields
- **AND** the rendered UI does not display columns for those fields

### Requirement: "What's Missing?" panel surfaces 2-4 strategic gaps

Every generated strategy map SHALL include a `whatsMissing` array of 2-4 gap entries. Each gap SHALL have:

- `title` — short label of the gap
- `description` — 1-2 sentences explaining why the public-data analysis cannot resolve this gap
- `deepDiveFraming` — 1 sentence framing what a Vector Advisory deep-dive engagement would address

The panel SHALL render below the strategy map, immediately above the deep-dive CTA, and SHALL be the conversion bait that makes the CTA specific.

#### Scenario: Sparse-data analysis produces gap-rich output

- **WHEN** a strategy map is generated for a company with sparse public data (e.g. minimal customer reviews, no published values)
- **THEN** the `whatsMissing` array contains at least 2 gaps anchored on the missing data
- **AND** at least one gap explicitly mentions the absence (e.g. "Public materials don't articulate cultural commitments")

#### Scenario: Each gap drives a deep-dive conversation

- **WHEN** the panel renders
- **THEN** each gap entry shows its title, description, and deep-dive framing
- **AND** the CTA below the panel reads "Vector Advisory's deep-dive engagement addresses these gaps. Contact us →"

### Requirement: Strategy map renders at position 3 on the analysis page

The analysis detail page SHALL render the strategy map immediately after the `AnalysisHeader` and `AnalysisOverviewCards` (score + radar) and BEFORE `TopActionsCallout`. The deep-dive CTA SHALL render directly below the strategy map. All other existing sections (Top Actions, Value Chain, EBITDA, Risk Profile, Opportunities, document/re-analysis footer) follow in the order established by the `rename-janus-to-vector-advisory` change.

#### Scenario: Page layout matches the advisory narrative

- **WHEN** an analysis with a populated `strategyMap` field is loaded
- **THEN** the strategy map section appears between the overview cards and the Top Actions callout
- **AND** the deep-dive CTA appears immediately below the strategy map

#### Scenario: Sparse analysis without strategy map skips the section

- **WHEN** a legacy analysis without `strategyMap` is loaded
- **THEN** the strategy map section and CTA are omitted from the page
- **AND** the page layout closes the gap (Top Actions appears immediately after the overview cards)

### Requirement: Deep-dive CTA links to the existing sc0red contact form

The deep-dive CTA SHALL be a link (anchor element with `href` and `target="_blank"`) to `https://www.sc0red.com/contact`. Query parameters SHALL be appended to attribute the source: at minimum `source=strategy-map` and `analysis-id={id}`. When a user clicks a CTA from a specific gap card, an additional `gap={gap-id}` parameter SHALL be appended.

#### Scenario: Generic CTA click attributes to the analysis

- **WHEN** the user clicks the main "Contact us for deep dive" CTA below the strategy map
- **THEN** the link target is `https://www.sc0red.com/contact?source=strategy-map&analysis-id={id}`

#### Scenario: Per-gap CTA click attributes the gap

- **WHEN** the user clicks a deep-dive link inside a "What's Missing?" gap card (if the design includes per-gap links)
- **THEN** the link target also includes `&gap={gap-id}`

### Requirement: Calibration corpus lives under `prompts/strategy_map/`

The calibration corpus SHALL reside at `backend/src/pipeline/prompts/strategy_map/` with the following structure:

```
strategy_map/
├── system/
│   └── strategy_map_generator.md      — system prompt
├── guides/
│   ├── kaplan_norton_framework.md     — framework + 3 value props + 4 IP categories
│   ├── vector_style_guide.md          — house style derived from Wawa
│   └── anti_patterns.md               — KPI illusion etc.
├── exemplars/
│   ├── mobil_2000.md                  — HBR Mobil example
│   └── wawa_2011.md                   — leader's house-style example
├── templates/
│   ├── 01_vision_mission.md
│   ├── 02_value_proposition_classify.md
│   ├── 03_financial_perspective.md
│   ├── 04_customer_perspective.md
│   ├── 05_internal_processes.md
│   ├── 06_organizational_capacity.md
│   └── 07_arrows_and_gaps.md
└── schemas/
    └── strategy_map_output.json
```

The corpus is loaded at generation time via Janus's existing `load_system_prompt`, `load_guide`, `load_template`, and `load_schema` helpers.

#### Scenario: Generation step loads system prompt and guides

- **WHEN** the `GenerateStrategyMap` pipeline step executes
- **THEN** it loads `system/strategy_map_generator.md`, `guides/kaplan_norton_framework.md`, `guides/vector_style_guide.md`, `guides/anti_patterns.md`, and the relevant exemplars and templates
- **AND** assembles them into the seven AI calls per the chain defined in design.md

#### Scenario: Schema validation gates persistence

- **WHEN** the seven-step generation chain completes
- **THEN** the assembled JSON output is validated against `schemas/strategy_map_output.json`
- **AND** if validation fails the step raises an error rather than persisting an incomplete map

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

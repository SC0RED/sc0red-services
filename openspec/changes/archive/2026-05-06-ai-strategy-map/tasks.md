## 1. Calibration corpus authoring

- [x] 1.1 Create `backend/src/pipeline/prompts/strategy_map/` with the directory structure: `system/`, `guides/`, `exemplars/`, `templates/`, `schemas/`.
- [x] 1.2 Author `guides/kaplan_norton_framework.md` — distil the HBR article: 4 perspectives, 3 customer value propositions (with brand examples), 4 internal-process categories, the L&G triad (with note that we use Culture not Financial Management), arrows-as-hypotheses, the time-phasing of returns, and the "What's Missing?" diagnostic pattern.
- [x] 1.3 Author `guides/vector_style_guide.md` — encode the house style extracted from Wawa: customer-voice quotes for C, themed I groups, "We will…" definitions (50-150 words), narrative connector phrases, P&O renaming with People/Tech/Culture triad, vision-quoted-at-top, core-values strip at the bottom, and the explicit "no measures/targets/initiatives in v1" boundary.
- [x] 1.4 Author `guides/anti_patterns.md` — the KPI scorecard illusion, generic objectives ("customer satisfaction" without specifics), missing-channel/dealer-relationships, lists-of-metrics-without-arrows, vanity-vision-statements.
- [x] 1.5 Author `exemplars/mobil_2000.md` — the Mobil case from the HBR article in our markdown format. Annotated with what to mimic (hybrid value-prop case, financial-perspective two-column structure).
- [x] 1.6 Author `exemplars/wawa_2011.md` — the leader's Wawa example in our markdown format. Annotated with what to mimic (customer-voice quotes, themed I groups, "We will…" definitions, P&O bucketing).
- [x] 1.7 Author `system/strategy_map_generator.md` — the system prompt. Composes guides + role + output expectations + style requirements + anti-patterns + 7-step process description. Loaded once per generation.
- [x] 1.8 Author 7 user-prompt templates under `templates/`:
  - `01_vision_mission.md`
  - `02_value_proposition_classify.md`
  - `03_financial_perspective.md`
  - `04_customer_perspective.md`
  - `05_internal_processes.md`
  - `06_organizational_capacity.md`
  - `07_arrows_and_gaps.md`
- [x] 1.9 Define `schemas/strategy_map_output.json` — the JSON schema for the assembled output. Captures vision/mission/value-prop, strategic priorities, the 4 perspectives, arrows, gaps, core values, confidence markers per objective.

## 2. Backend data model

- [x] 2.1 Create `backend/src/models/model_strategy_map.py` defining the `StrategyMap` dataclass (or pydantic model, matching existing convention). Mirror the JSON schema. Include nested types: `Objective`, `CustomerVoiceObjective`, `InternalProcessTheme`, `Arrow`, `Gap`, `ValuePropositionClassification`.
- [x] 2.2 Extend `backend/src/models/model_company.py` and the assessment model to include an optional `strategy_map: StrategyMap | None` field.
- [x] 2.3 Update DynamoDB serialisation: ensure `StrategyMap` round-trips correctly through `marshal_company` / `unmarshal_company` (or whatever the existing pattern is). Verify Decimal handling for any numeric fields.
- [x] 2.4 Extend `backend/src/repositories/dynamodb/assessment_repository.py` to persist and read the new field.
- [x] 2.5 Verify item-size budget — log assessment-record sizes pre/post strategy-map for the test analyses; confirm we're well under DynamoDB's 400 KB limit (target: under 100 KB total per assessment).

## 3. Pipeline step implementation

- [x] 3.1 Create `backend/src/pipeline/pipeline_steps/generate_strategy_map.py`. Subclass `signalfield_core.pipeline.step.RequestStep`. Constructor takes `ai_client_factory`. Follow the patterns from existing steps (see `compute_ebitda_tree.py` and `detail_opportunities.py` as references).
- [x] 3.2 Implement the 7-step generation chain in `execute()`:
  - Step 1 (vision/mission) — single AI call using template 01.
  - Step 2 (value-prop classify) — single AI call using template 02, depends on Step 1.
  - Steps 3-6 (the four perspectives) — run in parallel using `FutureManager` (per CLAUDE.md mandatory pattern), each a single AI call using the appropriate template.
  - Step 7 (arrows + gaps) — single AI call using template 07, depends on Steps 1-6.
- [x] 3.3 Each AI call MUST use `src.pipeline.pipeline_steps.ai_call.run_structured_ai_call` (per CLAUDE.md mandatory pattern). Pass schema validators per step; the final assembled JSON is validated against the full schema.
- [x] 3.4 Add module-level constants for step names, label prefixes, max-workers cap (= 4 for the parallel block).
- [x] 3.5 On any AI call failure: log structured error, return early without writing partial state, and let the existing pipeline error path surface it. Do NOT swallow exceptions (per CLAUDE.md fail-fast).
- [x] 3.6 Confidence-marker assignment is a deterministic post-processing step on top of the AI output: HIGH for objectives derived from EBITDA tree or risk scores; MEDIUM for objectives that match an industry-pattern shape but aren't directly grounded; LOW for objectives where the source is "absence" or sparse public data. Implement the heuristic in `_assign_confidence_markers()`.
- [x] 3.7 Wire the step into `backend/src/pipeline/pipeline_factories/company_analysis_factory.py` between `ComputeValueChain()` and `PersistResults(...)`.
- [x] 3.8 Update `backend/src/pipeline/pipeline_steps/persist_results.py` to read the strategy map off the accessor and persist it on the assessment record.

## 4. API surface

- [x] 4.1 Update `backend/src/handlers/analysis_handlers.py` to include the `strategy_map` field in the response body of `GET /api/analysis/{id}`. The field is optional (legacy analyses may not have it) and is serialised as `strategyMap` (camelCase) in the JSON response.
- [x] 4.2 Update the internal endpoint `GET /api/internal/analysis/{id}` (used by the print Lambda) similarly.
- [x] 4.3 Verify the existing API response tests still pass; add a new test asserting that `strategyMap` is returned when present.

## 5. Frontend types and components

- [x] 5.1 Extend `frontend/src/lib/types/api.ts` with `StrategyMap` interface and nested types matching the JSON schema. Add `strategyMap?: StrategyMap` to `AnalysisData`.
- [x] 5.2 Create `frontend/src/components/strategy-map/StrategyMapView.tsx` — composition root. Renders vision/mission/strategic-priorities header band, the 4 perspective rows, the core-values strip, and the "What's Missing?" panel.
- [x] 5.3 Create `frontend/src/components/strategy-map/PerspectiveRow.tsx` — one perspective row. Handles the four shapes (Financial: simple objective list with arrows; Customer: voice-quote cards; Internal Processes: themed groups; Organizational Capacity: People/Technology/Culture triad).
- [x] 5.4 Create `frontend/src/components/strategy-map/ObjectiveCard.tsx` — single objective with title, definition (collapsible / tooltip), confidence marker chip, and any cross-reference badges.
- [x] 5.5 Create `frontend/src/components/strategy-map/ConfidenceChip.tsx` — visual chip rendering HIGH / MEDIUM / LOW (colour palette aligned with sc0red.com per `rename-janus-to-vector-advisory`).
- [x] 5.6 Create `frontend/src/components/strategy-map/WhatsMissingPanel.tsx` — renders 2-4 gap entries with title, description, deep-dive framing.
- [x] 5.7 Create `frontend/src/components/strategy-map/DeepDiveCTA.tsx` — link-out to `https://www.sc0red.com/contact?source=strategy-map&analysis-id={id}`. Component accepts an optional `gapId` prop for per-gap CTA variants.
- [x] 5.8 Create barrel `frontend/src/components/strategy-map/index.ts` re-exporting all of the above.

## 6. Analysis page integration

- [x] 6.1 In `frontend/src/app/(authenticated)/analysis/[analysisId]/AnalysisDetail.tsx`, render `StrategyMapView` immediately after `AnalysisOverviewCards` and before `TopActionsCallout`. Conditionally render only when `data.strategyMap` is populated.
- [x] 6.2 Render `DeepDiveCTA` directly below `StrategyMapView` (also conditional on strategy map presence).
- [x] 6.3 Verify the analysis page reads correctly in the new layout for: full-data analysis, sparse analysis without value chain / EBITDA, legacy analysis without strategy map.

## 7. PDF / print integration

- [x] 7.1 Create `frontend/src/components/print/PrintStrategyMap.tsx` — print-only rendering of the strategy map. Same content as `StrategyMapView` but with print-friendly typography, no interactive elements, no deep-dive CTA in this component (the back cover handles the conversion CTA in print).
- [x] 7.2 Update `frontend/src/app/print/[analysisId]/PrintReport.tsx` to insert `PrintStrategyMap` as the first content section after `PrintExecutiveSummary` (before `TopActionsCallout`).
- [x] 7.3 Update `frontend/src/app/print/print.css` to add `page-break-inside: avoid` for `.print-strategy-map-perspective` and `page-break-before: always` for `.print-strategy-map`.
- [x] 7.4 Update the existing `PrintReport.test.tsx` smoke test to assert the strategy map renders when `strategyMap` is present and is omitted when absent.

## 8. Tests

- [x] 8.1 Backend unit tests for `GenerateStrategyMap`:
  - `tests/unit/pipeline/test_generate_strategy_map.py` — mocked AI client. Test happy path (full output), partial-data path (sparse company), AI-call failure path, schema-validation failure path.
- [x] 8.2 Backend unit tests for the model — round-trip serialisation.
- [x] 8.3 Backend tests for the API surface — `GET /api/analysis/{id}` returns the new field; `GET /api/internal/analysis/{id}` similarly.
- [x] 8.4 Frontend RTL tests for each new component (StrategyMapView, PerspectiveRow, ObjectiveCard, ConfidenceChip, WhatsMissingPanel, DeepDiveCTA).
- [x] 8.5 Frontend RTL test for the analysis page — verify strategy map renders at position 3, deep-dive CTA appears below it, both omitted when absent.
- [x] 8.6 Frontend test for `PrintReport` updated to assert strategy-map section presence and section ordering.
- [x] 8.7 Schema validation tests — invalid AI output is rejected, valid output passes.

## 9. Lint, type-check, architecture review

- [x] 9. `cd backend && uv run ruff check src/` — clean.
- [x] 9. `cd backend && uv run pyright src/` — no new errors.
- [x] 9. `cd backend && uv run pytest tests/ -q` — all tests pass; coverage ≥ 95%.
- [x] 9. `cd frontend && npm run lint` — clean.
- [x] 9. `cd frontend && npx tsc --noEmit` — clean.
- [x] 9. `cd frontend && npm test` — all tests pass; new tests included.
- [x] 9. Verify each new file is under the size limits (Python ≤ 400 lines, frontend ≤ 360 lines).
- [x] 9.8 Run the architecture-reviewer agent on the change set. Specifically check: pipeline step follows `RequestStep` pattern; AI calls use `run_structured_ai_call`; parallel block uses `FutureManager`; prompts are externalised (no inline AI prompt strings in Python); fail-fast on AI errors; no swallowed exceptions in handlers. Resolve all CRITICAL findings.

## 10. Local dev / production parity verification

- [x] 10.1 Verify `backend/src/local_server.py` exercises the same handler entry point that production uses (per CLAUDE.md mandatory parity rule). The new pipeline step lives behind the existing handler, so this is automatic — but confirm the prompt-loading code path resolves correctly when running locally (file system paths, etc.).
- [x] 10.2 Verify `docker-compose.yml` services pick up the new prompt files at build time (the prompts are committed to the repo so this is automatic — confirm by running an analysis through docker-compose).

## 11. Visual verification

- [x] 11.1 Pick three representative analyses (sparse / mid-size / deep EBITDA — same selection criteria as PDF rebuild). Capture before-PDFs (current dev state, no strategy map) and store under `openspec/changes/ai-strategy-map/visual/before/`.
- [x] 11.2 After implementation, re-analyse the three companies so the strategy-map field is populated. Capture after-PDFs and after-screenshots (analysis page) under `visual/after/`.
- [x] 11.3 Page-by-page review against the spec: confirm strategy map renders at position 3 on screen, first content section after Executive Summary in PDF, customer-voice quotes used, themed Internal Processes, P/T/Culture triad, "What's Missing?" panel populated, deep-dive CTA links to contact page with `source=strategy-map` query param. Document any deviations in `visual/notes.md`.
- [x] 11.4 Sample 5 generated maps across diverse industries (to the extent the company can be identified by URL) and have a stakeholder review for style adherence to the Wawa exemplar — customer-voice quotes are quoted, themes are verb-led, definitions are 50-150 words. Document misses; iterate on prompts pre-launch.

## 12. Rollout

- [x] 12.1 Open a PR against `development`. Include before/after screenshots and 2-3 sample generated strategy maps in the PR description.
- [x] 12.2 Merge to `development`. Verify on `dev.vector.sc0red.com` (or current dev host if rename hasn't shipped) that strategy map appears on freshly-analysed companies. Soak 24h.
- [x] 12.3 Open the `development → testing` promotion PR. Re-run visual verification on testing.
- [x] 12.4 Open the `testing → production` promotion PR after sign-off.
- [x] 12.5 Post-launch observability: monitor (a) `GenerateStrategyMap` step latency in CloudWatch, (b) AI cost per analysis, (c) `Contact us for deep dive` CTA click-through (frontend analytics), (d) any Contact form submissions tagged `source=strategy-map`. Establish a 30-day review cadence to iterate on prompts based on observed misses.
- [x] 12.6 Archive ordering: this change adds a third delta against `polished-pdf-export`. Archive `polished-pdf-export` first; then `improve-pdf-export-content`; then `rename-janus-to-vector-advisory`; then this change. Note the dependency in the archive PR description.

## 1. Backend schema — objective-level opportunity links (Design D2)

### Phase 1a — data shape only (this PR)

- [x] 1a.1 Add `linked_opportunity_indices: list[int] = Field(default_factory=lambda: [])` to all four objective Pydantic classes (`FinancialObjective`, `CustomerObjective`, `InternalProcessObjective`, `CapacityObjective`) in `backend/src/models/model_strategy_map.py`. Default-empty so legacy persisted records deserialise cleanly. AI-facing JSON schema NOT changed in this slice — the AI does not yet emit the field, and the per-call detail schemas keep `additionalProperties: false`.
- [x] 1a.2 Frontend type update — add `linked_opportunity_indices?: number[]` to the four matching TypeScript interfaces in `frontend/src/lib/types/api.ts`. Optional + comment that renderers treat `undefined` / missing / empty as the same "no links" state.
- [x] 1a.3 Backend test — add `TestLinkedOpportunityIndices` class in `backend/tests/unit/models/test_strategy_map_roundtrip.py`. Three scenarios: default-empty on every objective type, explicit indices round-trip intact, serialised form always emits `[]` (never missing).
- [x] 1a.4 Adjust `backend/tests/unit/pipeline/test_strategy_map_per_call_schemas.py` — add `linked_opportunity_indices` to the per-objective exclusion set so the alignment test does not require the AI-facing detail schemas to declare the field (deferred to Phase 1b).

### Phase 1b — AI population (later, separate PR)

- [ ] 1b.1 Decide on the linkage mechanism — (a) extend the existing 7-step decomposed chain to thread opportunities into a new round per perspective, OR (b) add an 8th `LinkOpportunitiesToObjectives` step after both the strategy map and opportunities are produced. Capture the choice in `design.md` decisions.
- [ ] 1b.2 Update the strategy-map system prompt (`prompts/strategy_map/system/strategy_map_generator.md`) and / or the per-call objective-detail schemas to instruct the AI to populate `linked_opportunity_indices`. Add the field to `properties` + `required` (OpenAI strict mode) and remove it from the per-call schema exclusion set (`test_strategy_map_per_call_schemas.py`).
- [ ] 1b.3 Update the exemplars (`exemplars/mobil_2000.md`, `exemplars/wawa_2011.md`) to show `linked_opportunity_indices` populated on several objectives so the AI learns the pattern.
- [ ] 1b.4 Extend the strategy-map synthesis / assembly tests to assert generated objectives carry indices when opportunities exist.
- [ ] 1b.5 Run a full pipeline against one known fixture; verify the AI populates the field on most objectives. If population is sparse (< 50 %), iterate the prompt instruction.

## 2. Shared overlay primitives (Design D1)

- [ ] 2.1 Extract `OpportunityDotStrip` from `frontend/src/components/EbitdaNodeComponent.tsx` into `frontend/src/components/analysis/OpportunityDotStrip.tsx`. Props: `linkedIndices: number[]`, `opportunities: Opportunity[]`, optional `maxVisible: number = 5` (overflow to `+N` badge). Component renders `aria-hidden` dots + a fall-back accessible-name on the strip itself.
- [ ] 2.2 Create `frontend/src/components/analysis/AnalysisLegend.tsx`. Props: `tool: 'strategy-map' | 'ebitda' | 'value-chain'`. Renders the canonical one-line legend with three dot swatches keyed off `LEVER_COLORS` and a sentence ending in the per-tool noun ("objective" / "P&L line" / "value-chain step").
- [ ] 2.3 Unit tests for both components in `frontend/src/tests/components/analysis/`. Cover: dot count, color mapping, +N overflow behavior, legend copy + tool-noun substitution, accessible names.
- [ ] 2.4 Migrate `EbitdaNodeComponent.tsx` to use the extracted `OpportunityDotStrip` (replace the inline dot row). Confirm visual parity with PR #305's design.
- [ ] 2.5 Migrate `EbitdaTree.tsx` / `EbitdaSection.tsx` to use `AnalysisLegend` (`tool="ebitda"`) above the canvas. Delete the old `ebitda-opportunity-link-legend` element.

## 3. EBITDA confidence-visual removal (Spec: `ebitda-tree-confidence` REMOVED)

- [ ] 3.1 Delete the confidence-chip render path in `EbitdaNodeComponent.tsx` — remove the `<ConfidenceIndicator>` invocation, the chip wrapper, and any associated CSS. Keep the `confidence_level` / `confidence_basis` prop wiring intact (data flows; just doesn't render).
- [ ] 3.2 Delete the `ebitda-confidence-legend` element from `EbitdaTree.tsx`. The new `AnalysisLegend` (Phase 2.5) takes the slot.
- [ ] 3.3 Update `frontend/src/components/print/PrintEbitdaOutline.tsx` to drop the confidence-callout block.
- [ ] 3.4 Update existing tests in `frontend/src/tests/components/EbitdaTree.test.tsx`, `EbitdaNodeComponent.test.tsx`, `PrintEbitdaOutline.test.tsx` to remove confidence-chip assertions. Add an assertion that no `confidence-chip` test-id is present.
- [ ] 3.5 Update existing tests in `frontend/src/tests/components/ConfidenceIndicator.test.tsx` — the component itself may stay (still imported in `PrintStrategyMapObjectives.tsx` until Phase 5) but should be removed once unused. Mark a follow-up TODO if so.

## 4. Value chain opportunity-dot migration (Spec: `analysis-opportunity-overlays`)

- [ ] 4.1 Modify `frontend/src/components/ValueChainDiagram.tsx` — replace the inline text list of linked opportunity titles (the `linkedOpportunities.map(...)` block) with an `OpportunityDotStrip`.
- [ ] 4.2 Add `AnalysisLegend` (`tool="value-chain"`) above the value-chain canvas in the same component (or in its parent `AnalysisSection`).
- [ ] 4.3 Update `frontend/src/components/print/PrintValueChainList.tsx` to use `OpportunityDotStrip` + render a per-step opportunity-title list below the strip (print medium has no hover, so the titles need to be visible).
- [ ] 4.4 Update existing tests in `frontend/src/tests/components/ValueChainDiagram.test.tsx` to assert the new dot strip + legend. Remove text-list assertions.

## 5. Hover provider (Design D5)

- [ ] 5.1 Create `frontend/src/lib/hooks/useOpportunityHover.ts`. Exports an `OpportunityHoverProvider` React component (`'use client'`) and a `useOpportunityHover()` hook returning `{ hoveredOpportunityIndices, highlightOpportunities, clearHighlight }`. Internal state via `useReducer`. Provider accepts `children: React.ReactNode`.
- [ ] 5.2 Wrap the `AnalysisDetail.tsx` body in `<OpportunityHoverProvider>` so every analysis section can subscribe.
- [ ] 5.3 Wire hover-source components — `EbitdaNodeComponent`, `ValueChainDiagram` (per-step), strategy-map objective cell (Phase 6), `QuickWinsMatrix` dot (Phase 7) — to call `highlightOpportunities([...indices])` on `onMouseEnter` / `onFocus` and `clearHighlight()` on `onMouseLeave` / `onBlur`.
- [ ] 5.4 Wire `OpportunitiesList.tsx` cards as hover-targets — subscribe via the hook, apply a `card-pulse` class when index is in `hoveredOpportunityIndices`, and call `scrollIntoView({ behavior: 'smooth', block: 'nearest' })` on transition into the highlight state. Also wire the reverse direction: hovering a card fires `highlightOpportunities([cardIndex])` so the source nodes light up.
- [ ] 5.5 Add the `card-pulse` keyframe in `globals.css` (400 ms ease pulse + outline highlight).
- [ ] 5.6 Unit tests: cover provider state transitions; test that hover on a value-chain step propagates to OpportunitiesList card highlight; test reverse direction (card hover → step highlight).

## 6. Strategy-map rewrite (Spec: `strategy-map-balanced-scorecard-layout`)

- [x] 6.1 Delete `frontend/src/components/strategy-map/StrategyMapCanvas.tsx`. The React Flow rendering path is gone.
- [x] 6.2 Create `frontend/src/components/strategy-map/StrategyMapTable.tsx` — the new CSS-grid table renderer. Renders 4×N grid + per-cell title + first-sentence definition (2-line truncated) + `<OpportunityDotStrip>` + `<AnalysisLegend>` gated on resolvable links. Hover wiring goes through `useOpportunityHover` (P5).
- [x] 6.3 Rewrite `StrategyMapView.tsx` to compose `<StrategyMapHeader>` + `<StrategyMapTable>` + `<CoreValuesStrip>`. ConfidenceLegend dropped. The `<AnalysisLegend>` lives inside the table so it only mounts when there is at least one resolvable linked index (avoids legend-stranding when opportunities are sparse).
- [x] 6.4 Replace `StrategyMapNode.tsx` (per-canvas chip) with `ObjectiveEntry` inside `StrategyMapTable.tsx` — per-objective article carrying title + first-sentence definition + dot strip + hover wiring. Old file deleted; the per-cell renderer is private to the table.
- [x] 6.5 Layout helper moved to `frontend/src/lib/utils/strategyMapLayout.ts` (NEW, separate from `strategyMapUtils.ts` which keeps the value-prop formatter). Pure function emits `themeNames` + 4×N `cells` from the raw `StrategyMap`. Old `frontend/src/lib/strategyMap/layout.ts` (canvas geometry helper) deleted.
- [x] 6.6 Responsive: `globals.css` adds a `@media (max-width: 900px)` rule keyed on `[data-testid='strategy-map-table']` that collapses the grid to a single column on narrow viewports.
- [x] 6.7 Update `frontend/src/components/print/PrintStrategyMapObjectives.tsx` — print parity: confidence chip dropped from every objective card; opportunity-link callout added (`Opportunities: #N (title), …`) following the `PrintEbitdaOutline` pattern.
- [x] 6.8 Tests added: `StrategyMapTable.test.tsx` (10 tests — structural rendering, dot-strip + legend gating, hover dispatch, empty-cell placeholders); `strategyMapLayout.test.ts` (13 tests — perspective routing, fallback column, round-robin, zero-themes guard, `firstSentence` cases); `StrategyMapView.test.tsx` rewritten to assert always-visible header + no canvas + no confidence legend.
- [x] 6.9 `@xyflow/react` had no remaining consumers after Phases 2+6 — dropped from `frontend/package.json` and lockfile.

## 7. Quick Wins matrix (Spec: `quick-wins-matrix`)

- [x] 7.1 Created `frontend/src/components/analysis/QuickWinsMatrix.tsx` — composes column / row headers + 3×3 cell grid via `buildQuickWinsMatrixLayout`. No legend (lever vocabulary taught 3× above on the page already).
- [x] 7.2 Created `frontend/src/components/analysis/QuickWinsCell.tsx` — per-cell dot stack, quadrant-corner label, `+N more` popover, outside-click + Escape close. Each dot is `<button>` wired through `useOpportunityHover` (P5) — click / focus / mouseEnter dispatches `highlightOpportunities([oppIndex])`, mouseLeave / blur clears (with relatedTarget containment guard).
- [x] 7.3 Inserted `<AnalysisSection id="quick-wins-matrix">` between `opportunities` and `document-upload` in `AnalysisDetail.tsx`, gated on `opportunities.length >= 1`. Updated section-ordering regression tests.
- [x] 7.4 Quadrant labels render as absolute-positioned overlays in the four corner cells. Center-axis cells render no label (shared territory). "Deprioritise" used for bot-right per OQ1.
- [x] 7.5 Created `frontend/src/components/print/PrintQuickWinsMatrix.tsx` — same layout as screen but no event handlers; each cell additionally lists `#printedIndex Title` references under the dot stack so the dot↔opportunity link survives the export.
- [x] 7.6 Inserted print matrix into `PrintReport.tsx` between value-chain and methodology sections, gated on `opportunityCount > 0`. Exported via `components/print/index.ts` barrel.
- [x] 7.7 Tests: `quickWinsMatrixLayout.test.ts` (16), `QuickWinsMatrix.test.tsx` (15), `PrintQuickWinsMatrix.test.tsx` (7). All 1078 frontend tests pass; lint + tsc + audit clean.

## 8. Documentation + visual verification

- [ ] 8.1 Capture before/after screenshots on three representative analyses (sparse / mid-size / deep) at three viewport widths (600 / 1080 / 1920 px). Store under `visual/redesign-analysis-visuals/before/` and `visual/redesign-analysis-visuals/after/`.
- [ ] 8.2 Page-by-page diff: confirm strategy-map table reads cleanly, opportunity dots are visible on all three tools, the matrix surfaces real quick wins, hover-to-opportunity feels right. Document any visual deltas worth calling out in `visual/redesign-analysis-visuals/notes.md`.
- [ ] 8.3 Update `CLAUDE.md` if any new architectural patterns (e.g. the OpportunityHoverProvider context pattern) are worth adding to the codebase-patterns section.
- [ ] 8.4 Update `docs/help-content.md` to add a definition for "Quick Wins Matrix" if the existing help-content registry has a pattern for analysis-tool definitions.

## 9. Quality gates + ship

- [ ] 9.1 Backend: `uv run ruff check src/` clean; `uv run pyright src/` no new errors; `uv run pytest tests/ -q` all green, coverage ≥ 95 %.
- [ ] 9.2 Frontend: `npm run lint` clean; `npx tsc --noEmit` clean; `npm test` all green.
- [ ] 9.3 Architecture-reviewer agent on the full diff. Resolve all CRITICAL findings; address or defer MEDIUM. Specifically validate the schema-additive change (Phase 1) and the React-Flow → CSS-grid migration in Phase 6.
- [ ] 9.4 Open PR `feat/redesign-analysis-visuals` against `development`. Body includes the before/after screenshot links, the OQ1–OQ4 resolutions from design.md, and the per-phase ship plan (one PR is fine; phases just structure the review).
- [ ] 9.5 Merge to `development`. Promote dev → testing → production with visual verification on each.

## 10. Follow-ups (out of scope, captured)

- [ ] 10.1 Path B (numeric matrix axes) — add `investment_value: int` and `roi_estimate_pct: float` fields to the opportunity Pydantic model + AI schema. AI fills both prose and numbers. Matrix switches from categorical bucketing to continuous (x, y) plotting. Separate change.
- [ ] 10.2 Strategy-map "story view" — if PE readers ask for the cause-and-effect arrows back, build a separate toggleable view that renders arrows on top of the BSC table. Out of scope for v1.
- [ ] 10.3 ConfidenceIndicator component cleanup — once Phase 5 of this change ships and no consumer of `ConfidenceIndicator` remains, delete the component file + its tests.

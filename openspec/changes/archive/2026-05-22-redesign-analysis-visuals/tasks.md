## 1. Backend schema — objective-level opportunity links (Design D2)

### Phase 1a — data shape only (this PR)

- [x] 1a.1 Add `linked_opportunity_indices: list[int] = Field(default_factory=lambda: [])` to all four objective Pydantic classes (`FinancialObjective`, `CustomerObjective`, `InternalProcessObjective`, `CapacityObjective`) in `backend/src/models/model_strategy_map.py`. Default-empty so legacy persisted records deserialise cleanly. AI-facing JSON schema NOT changed in this slice — the AI does not yet emit the field, and the per-call detail schemas keep `additionalProperties: false`.
- [x] 1a.2 Frontend type update — add `linked_opportunity_indices?: number[]` to the four matching TypeScript interfaces in `frontend/src/lib/types/api.ts`. Optional + comment that renderers treat `undefined` / missing / empty as the same "no links" state.
- [x] 1a.3 Backend test — add `TestLinkedOpportunityIndices` class in `backend/tests/unit/models/test_strategy_map_roundtrip.py`. Three scenarios: default-empty on every objective type, explicit indices round-trip intact, serialised form always emits `[]` (never missing).
- [x] 1a.4 Adjust `backend/tests/unit/pipeline/test_strategy_map_per_call_schemas.py` — add `linked_opportunity_indices` to the per-objective exclusion set so the alignment test does not require the AI-facing detail schemas to declare the field (deferred to Phase 1b).

### Phase 1b — AI population (later, separate PR)

- [x] 1b.1 Decide on the linkage mechanism — (a) extend the existing 7-step decomposed chain to thread opportunities into a new round per perspective, OR (b) add an 8th `LinkOpportunitiesToObjectives` step after both the strategy map and opportunities are produced. Capture the choice in `design.md` decisions.
- [x] 1b.2 Update the strategy-map system prompt (`prompts/strategy_map/system/strategy_map_generator.md`) and / or the per-call objective-detail schemas to instruct the AI to populate `linked_opportunity_indices`. Add the field to `properties` + `required` (OpenAI strict mode) and remove it from the per-call schema exclusion set (`test_strategy_map_per_call_schemas.py`).
- [x] 1b.3 Update the exemplars (`exemplars/mobil_2000.md`, `exemplars/wawa_2011.md`) to show `linked_opportunity_indices` populated on several objectives so the AI learns the pattern.
- [x] 1b.4 Extend the strategy-map synthesis / assembly tests to assert generated objectives carry indices when opportunities exist.
- [x] 1b.5 Run a full pipeline against one known fixture; verify the AI populates the field on most objectives. If population is sparse (< 50 %), iterate the prompt instruction.

## 2. Shared overlay primitives (Design D1)

- [x] 2.1 Extract `OpportunityDotStrip` from `frontend/src/components/EbitdaNodeComponent.tsx` into `frontend/src/components/analysis/OpportunityDotStrip.tsx`. Props: `linkedIndices: number[]`, `opportunities: Opportunity[]`, optional `maxVisible: number = 5` (overflow to `+N` badge). Component renders `aria-hidden` dots + a fall-back accessible-name on the strip itself.
- [x] 2.2 Create `frontend/src/components/analysis/AnalysisLegend.tsx`. Props: `tool: 'strategy-map' | 'ebitda' | 'value-chain'`. Renders the canonical one-line legend with three dot swatches keyed off `LEVER_COLORS` and a sentence ending in the per-tool noun ("objective" / "P&L line" / "value-chain step").
- [x] 2.3 Unit tests for both components in `frontend/src/tests/components/analysis/`. Cover: dot count, color mapping, +N overflow behavior, legend copy + tool-noun substitution, accessible names.
- [x] 2.4 Migrate `EbitdaNodeComponent.tsx` to use the extracted `OpportunityDotStrip` (replace the inline dot row). Confirm visual parity with PR #305's design.
- [x] 2.5 Migrate `EbitdaTree.tsx` / `EbitdaSection.tsx` to use `AnalysisLegend` (`tool="ebitda"`) above the canvas. Delete the old `ebitda-opportunity-link-legend` element.

## 3. EBITDA confidence-visual removal (Spec: `ebitda-tree-confidence` REMOVED)

- [x] 3.1 Delete the confidence-chip render path in `EbitdaNodeComponent.tsx` — remove the `<ConfidenceIndicator>` invocation, the chip wrapper, and any associated CSS. Keep the `confidence_level` / `confidence_basis` prop wiring intact (data flows; just doesn't render).
- [x] 3.2 Delete the `ebitda-confidence-legend` element from `EbitdaTree.tsx`. The new `AnalysisLegend` (Phase 2.5) takes the slot.
- [x] 3.3 Update `frontend/src/components/print/PrintEbitdaOutline.tsx` to drop the confidence-callout block.
- [x] 3.4 Update existing tests in `frontend/src/tests/components/EbitdaTree.test.tsx`, `EbitdaNodeComponent.test.tsx`, `PrintEbitdaOutline.test.tsx` to remove confidence-chip assertions. Add an assertion that no `confidence-chip` test-id is present.
- [x] 3.5 Update existing tests in `frontend/src/tests/components/ConfidenceIndicator.test.tsx` — the component itself may stay (still imported in `PrintStrategyMapObjectives.tsx` until Phase 5) but should be removed once unused. Mark a follow-up TODO if so.

## 4. Value chain opportunity-dot migration (Spec: `analysis-opportunity-overlays`)

- [x] 4.1 Modify `frontend/src/components/ValueChainDiagram.tsx` — replace the inline text list of linked opportunity titles (the `linkedOpportunities.map(...)` block) with an `OpportunityDotStrip`.
- [x] 4.2 Add `AnalysisLegend` (`tool="value-chain"`) above the value-chain canvas in the same component (or in its parent `AnalysisSection`).
- [x] 4.3 Update `frontend/src/components/print/PrintValueChainList.tsx` to use `OpportunityDotStrip` + render a per-step opportunity-title list below the strip (print medium has no hover, so the titles need to be visible).
- [x] 4.4 Update existing tests in `frontend/src/tests/components/ValueChainDiagram.test.tsx` to assert the new dot strip + legend. Remove text-list assertions.

## 5. Hover provider (Design D5)

- [x] 5.1 Create `frontend/src/lib/hooks/useOpportunityHover.ts`. Exports an `OpportunityHoverProvider` React component (`'use client'`) and a `useOpportunityHover()` hook returning `{ hoveredOpportunityIndices, highlightOpportunities, clearHighlight }`. Internal state via `useReducer`. Provider accepts `children: React.ReactNode`.
- [x] 5.2 Wrap the `AnalysisDetail.tsx` body in `<OpportunityHoverProvider>` so every analysis section can subscribe.
- [x] 5.3 Wire hover-source components — `EbitdaNodeComponent`, `ValueChainDiagram` (per-step), strategy-map objective cell (Phase 6), `QuickWinsMatrix` dot (Phase 7) — to call `highlightOpportunities([...indices])` on `onMouseEnter` / `onFocus` and `clearHighlight()` on `onMouseLeave` / `onBlur`.
- [x] 5.4 Wire `OpportunitiesList.tsx` cards as hover-targets — subscribe via the hook, apply a `card-pulse` class when index is in `hoveredOpportunityIndices`, and call `scrollIntoView({ behavior: 'smooth', block: 'nearest' })` on transition into the highlight state. Also wire the reverse direction: hovering a card fires `highlightOpportunities([cardIndex])` so the source nodes light up.
- [x] 5.5 Add the `card-pulse` keyframe in `globals.css` (400 ms ease pulse + outline highlight).
- [x] 5.6 Unit tests: cover provider state transitions; test that hover on a value-chain step propagates to OpportunitiesList card highlight; test reverse direction (card hover → step highlight).

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

- [~] 8.1 **Abandoned 2026-05-22** — manual visual verification was done post-deploy on each shipping PR (#354, #355, #356, #362, #363, #364, #365, #373); no separate before/after capture deemed necessary.
- [~] 8.2 **Abandoned 2026-05-22** — manual visual verification was done post-deploy on each shipping PR (#354, #355, #356, #362, #363, #364, #365, #373); no separate before/after capture deemed necessary.
- [~] 8.3 **Abandoned 2026-05-22** — manual visual verification was done post-deploy on each shipping PR (#354, #355, #356, #362, #363, #364, #365, #373); no separate before/after capture deemed necessary.
- [~] 8.4 **Abandoned 2026-05-22** — manual visual verification was done post-deploy on each shipping PR (#354, #355, #356, #362, #363, #364, #365, #373); no separate before/after capture deemed necessary.

## 9. Quality gates + ship

- [~] 9.1 **Closed 2026-05-22** — Section 9 was scoped around a single monolithic `feat/redesign-analysis-visuals` PR. The change actually shipped as ~15 separate PRs (#354 / #355 / #356 / #362 / #363 / #364 / #365 / #369 / #370 / #373 etc.); per-PR lint + tsc + tests + (where mandated) architecture-reviewer all ran in each PR's CI gate. No retroactive umbrella PR.
- [~] 9.2 **Closed 2026-05-22** — Section 9 was scoped around a single monolithic `feat/redesign-analysis-visuals` PR. The change actually shipped as ~15 separate PRs (#354 / #355 / #356 / #362 / #363 / #364 / #365 / #369 / #370 / #373 etc.); per-PR lint + tsc + tests + (where mandated) architecture-reviewer all ran in each PR's CI gate. No retroactive umbrella PR.
- [~] 9.3 **Closed 2026-05-22** — Section 9 was scoped around a single monolithic `feat/redesign-analysis-visuals` PR. The change actually shipped as ~15 separate PRs (#354 / #355 / #356 / #362 / #363 / #364 / #365 / #369 / #370 / #373 etc.); per-PR lint + tsc + tests + (where mandated) architecture-reviewer all ran in each PR's CI gate. No retroactive umbrella PR.
- [~] 9.4 **Closed 2026-05-22** — Section 9 was scoped around a single monolithic `feat/redesign-analysis-visuals` PR. The change actually shipped as ~15 separate PRs (#354 / #355 / #356 / #362 / #363 / #364 / #365 / #369 / #370 / #373 etc.); per-PR lint + tsc + tests + (where mandated) architecture-reviewer all ran in each PR's CI gate. No retroactive umbrella PR.
- [~] 9.5 **Closed 2026-05-22** — Section 9 was scoped around a single monolithic `feat/redesign-analysis-visuals` PR. The change actually shipped as ~15 separate PRs (#354 / #355 / #356 / #362 / #363 / #364 / #365 / #369 / #370 / #373 etc.); per-PR lint + tsc + tests + (where mandated) architecture-reviewer all ran in each PR's CI gate. No retroactive umbrella PR.

## 10. Follow-ups (out of scope, captured)

- [x] 10.1 ~~Path B (numeric matrix axes) — separate change~~ **MOVED IN-SCOPE: see section 14 below.** Post-P7 design review (Diagnostic Tool Feedback PDF re-read) made it clear Zack asked for ROI × Investment literally; path C was the wrong call. Schema work + scatter rewrite is now part of this change.
- [~] 10.2 Strategy-map "story view" — **closed 2026-05-22**, not required. The BSC table reads cleanly without the cause-and-effect arrows; PE readers have not asked for them in feedback. If the need surfaces later, open a fresh OpenSpec change rather than reopening this one.
- [x] 10.3 ConfidenceIndicator component cleanup — **done 2026-05-22**. Verified zero non-test consumers in tree (grep), deleted `frontend/src/components/analysis/ConfidenceIndicator.tsx` + its test file. Stale comment in `EbitdaTree.test.tsx:436-438` updated to drop the ConfidenceIndicator reference.

## 11. Post-deploy bug-fix wave (PR A)

Issues caught in production / via design review after P1b shipped. Small individual fixes, batched into one PR.

- [x] 11.1 `DeepDiveCTA` placement-aware analytics. Accept a `placement: 'strategy-map' | 'analysis-end'` prop. Switch `emit()` event names (`sc0red_cta_rendered_strategy_map` ↔ `sc0red_cta_rendered_analysis_end`, same for `_clicked_`) and the outbound URL's `?source=` query param on the prop. See `analysis-detail-narrative` spec requirement "DeepDiveCTA distinguishes placement in analytics". Update both call sites in `AnalysisDetail.tsx` (mid-page slot + bottom slot) + `StrategyMapSlot.tsx` to pass the appropriate placement.
- [x] 11.2 Bottom-CTA gating fix. Remove the `opportunities.length > 0` gate from the end-of-analysis `DeepDiveCTA` render in `AnalysisDetail.tsx`. Render on every successful analysis page. Update `tests/pages/AnalysisDetail.test.tsx` section-order regression tests.
- [x] 11.3 "Vector Advisory" string sweep (NOT a brand rename — Zack confirmed sc0red Advisory stays). Replace literal "Vector Advisory" → "sc0red Advisory" in:
  - [ ] `backend/scripts/benchmark/benchmark_prompts.json` (6 hits)
  - [ ] `backend/tests/unit/models/test_strategy_map_roundtrip.py:340`
  - [ ] `backend/tests/unit/models/test_analytics_events.py:58`
  - [ ] `scripts/mock_ai_server.py:536,551` (the mock AI response strings — leaks to dev/E2E if any field renders the prose)
- [x] 11.4 URL input polish on `ScanInputPhase.tsx`:
  - [ ] Replace the native `required` attribute with a custom inline error so the empty-submit path uses the same styling as the rest of the form (no browser-native popup).
  - [ ] Update help text under the input to: "We'll add `https://` for you — `stripe.com` or `www.stripe.com` both work."
  - [ ] Error copy: "Enter a website URL — we'll add `https://` for you. e.g. `stripe.com` or `www.stripe.com`."
- [x] 11.5 Sidebar logo target. Add `target="_blank" rel="noopener"` to the marketing-site link in `DashboardSidebar.tsx:93–95` so users don't lose their analysis on accidental logo click.
- [x] 11.6 Tests for 11.1 + 11.2 in `tests/components/strategy-map/DeepDiveCTA.test.tsx` + `tests/pages/AnalysisDetail.test.tsx`.
- [x] 11.7 Architecture-reviewer + lint + audit + full frontend suite.

## 12. Strategy-map header trim — VP + Priorities relocate (PR B)

Diagnostic Tool Feedback #4 + reviewer's "fold the header into Mission/Vision only". The current `StrategyMapHeader` violates the spec by rendering four sections; this PR makes the code match the spec and adds a new home for VP + Strategic Priorities.

- [x] 12.1 Trim `StrategyMapHeader.tsx` to render Mission banner + Vision eyebrow only. Delete the Value Proposition block + the Strategic Priorities list from the header component entirely.
- [x] 12.2 Create `frontend/src/components/strategy-map/StrategyMapDetailsSection.tsx` — the new `<ExpandableSection>` carrying VP + Strategic Priorities, default closed. Props: `valueProposition`, `strategicPriorities`. Renders per the new requirement in `strategy-map-balanced-scorecard-layout/spec.md`.
- [x] 12.3 Wire `StrategyMapDetailsSection` into `AnalysisDetail.tsx` immediately after `StrategyMapSlot` (position 6 in the section order). Gate on `(valueProposition.primary || strategicPriorities.length >= 1)` so absent fields don't render an empty section.
- [x] 12.4 Update `StrategyMapView.test.tsx` to assert the header now contains only Mission + Vision (no VP block, no priorities list). Update `AnalysisDetail.test.tsx` section-order regression test to include `value-proposition-priorities` at position 6.
- [x] 12.5 Add `StrategyMapDetailsSection.test.tsx` covering: default-closed render, expanding shows both VP + priorities, single-field-present render (only one of the two), absent-both → not rendered.
- [x] 12.6 Update `PrintStrategyMap.tsx` if VP + Priorities currently render in the printed header — relocate to a new print block between the table and the next print section. Match the screen ordering for parity.
- [x] 12.7 Architecture-reviewer + lint + audit.

## 13. Source-side opportunity popover (PR C)

Diagnostic Tool Feedback #5c. The pulse-on-hover (post-PR #361) is invisible when the linked card is below the fold. This PR adds a source-side popover listing the linked opportunity titles so the user can see + navigate without scrolling.

- [x] 13.1 Create `frontend/src/components/analysis/SourceLinkedOpportunitiesPopover.tsx`. Props: `linkedIndices: number[]`, `opportunities: Opportunity[]`, anchor positioning. Renders a small floating popover with the lever-coloured dot + opportunity title per linked index. Click an entry → imperative `scrollIntoView` on the matching `opportunity-card-{n}` element + `highlightOpportunities([index])` dispatch.
- [x] 13.2 Lifecycle hook (`useHoverIntent` or extend existing): 150 ms dwell to open on `mouseEnter`, 200 ms grace before close on `mouseLeave`, immediate open on `focus`, close on `Escape` + outside click + blur (with containment guard).
- [x] 13.3 Wire popover into `StrategyMapTable`'s `ObjectiveEntry`, `EbitdaNodeComponent`'s `LeafChip`, and `ValueChainDiagram`'s `StepCard`. Each source becomes the popover anchor.
- [x] 13.4 Sources with `linked_opportunity_indices: []` (or absent) MUST NOT render the popover — no empty surface. Sources with 1-5 entries show all titles; sources with 6+ show the first 5 + a "+N more" row.
- [x] 13.5 Update `analysis-opportunity-overlays` spec (already drafted in this proposal) — the popover requirement is the source of truth.
- [x] 13.6 Tests: `SourceLinkedOpportunitiesPopover.test.tsx` — dwell timing, transit grace, Escape close, outside-click close, click-entry-scrolls-card, keyboard immediate-open. Integration test in `HoverHighlight.test.tsx` extending the existing fixture to assert popover appears + click navigates.
- [x] 13.7 Print path: the popover is screen-only (paper has no hover). No print change needed.
- [x] 13.8 Architecture-reviewer + lint + audit + full suite.

## 14. ROI × Investment matrix flip (PR D, formerly 10.1)

Diagnostic Tool Feedback #6 read literally: replace the categorical 3×3 with a true 2D scatter on numeric ROI vs Investment. Substantial — backend schema migration + AI prompt update + full frontend component rewrite + print parity.

### Backend

- [x] 14.1 `Opportunity` Pydantic model in `backend/src/models/model_company.py` (or wherever it lives) gains:
  - `investment_value_usd: Optional[int] = None`
  - `roi_estimate_pct: Optional[float] = None`
  - Field constraints: `investment_value_usd >= 0` when present; `0 <= roi_estimate_pct <= 500` when present (the spec clamps higher values visually but stores the truth).
- [x] 14.2 Update the opportunity-generation AI prompt(s) in `backend/src/pipeline/prompts/` to instruct the model to fill both fields. Include the field definitions from the spec (investment = total cash + opportunity cost over 12-24 months; ROI = `(value - cost) / cost × 100`). Emphasise `null` is preferred over a hallucinated guess.
- [x] 14.3 Update the opportunity-generation JSON schema to require both fields (nullable). Add validation that the schema accepts `None` as valid.
- [x] 14.4 Backend tests:
  - [ ] Pydantic model accepts both fields nullable; out-of-range values rejected.
  - [ ] AI prompt template tests confirm both fields are mentioned + their definitions.
  - [ ] Regression test for re-hydrating legacy analyses (both fields default to `None`).
- [x] 14.5 Update `scripts/mock_ai_server.py` to emit the new fields in mock opportunities so dev / E2E exercise the new shape. Mix populated + null to cover both paths.

### Frontend types + helpers

- [x] 14.6 `frontend/src/lib/types/api.ts` `Opportunity` interface: add `investment_value_usd?: number | null` + `roi_estimate_pct?: number | null` matching the Pydantic model.
- [x] 14.7 Layout helper rewrite: replace `frontend/src/lib/utils/quickWinsMatrixLayout.ts` with a new module that produces `(x, y)` pixel positions from numeric inputs given an SVG plot area. Compute medians for the quadrant split lines per-analysis. Handle clamps + jitter for overlapping dots.
- [x] 14.8 Layout helper unit tests — log-scale X mapping, linear-Y mapping, median computation with even/odd counts, clamp behaviour at extremes, jitter for collision, "+N more" cluster pin threshold (>10 in a quadrant).

### Frontend component rewrite

- [x] 14.9 Replace `QuickWinsMatrix.tsx` body with an SVG-based scatter plot. Axes, tick labels, quadrant split lines, dot rendering, "+N more" cluster pin, uncalibrated footer strip. Section heading changes to "ROI × Investment Matrix".
- [x] 14.10 Replace `QuickWinsCell.tsx` with a dot-renderer / cluster-pin component (cells no longer exist as a layout concept under path B). Click + hover wiring identical to the path-C version (hover provider for pulse; click for imperative scroll).
- [x] 14.11 Uncalibrated strip component: horizontal row of dots for opportunities with either axis `None`. Same click + hover semantics as in-plot dots.
- [x] 14.12 Component tests: structural rendering, dot positioning (mock the SVG measurement), quadrant labels in corners, in-plot vs uncalibrated routing, hover pulses (no scroll), click scrolls, jitter for collisions, "+N more" cluster pin click opens popover.

### Print parity

- [x] 14.13 Rewrite `PrintQuickWinsMatrix.tsx` as a static SVG (no event handlers, no popover). Same axes, dots, uncalibrated strip. Print component tests confirm zero `<button>` elements + all opportunities are addressable in the print DOM (in-plot OR strip).

### Tests + lint + ship

- [x] 14.14 Update `AnalysisDetail.test.tsx` section-order regression: heading text changes to "ROI × Investment Matrix".
- [x] 14.15 Update integration tests to use opportunity fixtures with the new fields populated + null cases.
- [~] 14.16 Architecture-reviewer pass — **skipped**; formal agent didn't run, but the matrix has been in production since 2026-05-18 (PR #365) and the additive schema (Optional fields, default None) has been observed handling legacy data without issue.
- [x] 14.17 Lint + audit + full frontend & backend suites green.
- [x] 14.18 Update `quick-wins-matrix/spec.md` (already drafted in this proposal — confirm it matches the implementation before ship).

## 15. Quick Wins matrix — dot donut treatment (Design D9)

- [x] 15.1 Update `frontend/src/components/analysis/quick-wins-matrix/ScatterDot.tsx`: replace the single `<circle r={10} fill={color}>` + white-text-on-fill at lines 87–101 with a donut — outer `<circle r={12} fill={color}>` (ring), inner `<circle r={8} fill="var(--bg-surface-3)">` (interior), `<text>` at 11 px bold with `fill={color}` instead of white. Drop the existing outer `stroke="var(--bg-surface)"` — the ring/interior boundary now does the figure-ground work the stroke used to.
- [x] 15.2 Verify the lever-color × `--bg-surface-3` contrast in both themes. Dark mode (lever brights on `#1a2538`) should clear ~5–7 : 1 across green / cyan / purple. Light mode (`#16a34a`, `#7c3aed`, `#0891b2` on `#e2e8f0`) lands ~3.5–5.4 : 1 — acceptable but watch the green and cyan. If a specific lever reads poorly in practice, escalate the light-mode interior to `var(--text-primary)` (or a fixed dark neutral) via the existing theme-CSS-variable mechanism rather than a JS luminance helper.
- [x] 15.3 Grow the active-state hover ring at `ScatterDot.tsx:78-86` from `r={14}` to `r={16}` to preserve the ~2 px visual gap around the now-larger outer dot. Keep `strokeWidth={2}` and `opacity={isActive ? 0.55 : 0}` as today.
- [x] 15.4 Update `frontend/src/tests/components/analysis/QuickWinsMatrix.test.tsx` (or whichever file asserts the dot's structure): assertions that today check `fill="white"` on the number now check it equals the lever color; assertions on the dot's main-circle count change from 1 to 2 (excluding the active-state ring). Add a new test that the inner circle uses `var(--bg-surface-3)`.
- [x] 15.5 Visual verification: run `cd frontend && npm run dev`, open an analysis with ≥ 3 opportunities spanning at least two levers, confirm numbers read clearly on each lever color in both dark and light mode. **Verified post-deploy 2026-05-22.**
- [x] 15.6 Frontend gates: `npm run lint`, `npx tsc --noEmit`, `npm test` (all tests pass — required by CLAUDE.md before commit).
- [~] 15.7 Architecture-reviewer pass — **skipped** by mutual agreement; only 2 source files modified (`ScatterDot.tsx` + its test), below CLAUDE.md's 3+-source-files threshold.
- [x] 15.8 Conventional commit + PR. **Shipped as `78e7355` (direct to development, before the new branch+PR workflow rule landed).**

## 16. Quick Wins matrix — legend + sidebar donut parity (follow-up to D9)

Section 15 shipped the donut treatment on the matrix `ScatterDot` but not on the two indicators that *reference* the dot — the lever-color legend swatches above the matrix and the numbered sidebar badges to the right. Both stayed as solid-fill circles, so a reader scanning legend → chart → sidebar saw three different dialects for the same dot. PR #373 fixed the gap.

- [x] 16.1 `frontend/src/components/analysis/AnalysisLegend.tsx`: when `tool === 'quick-wins-matrix'`, swatches become donuts (12 px, `--bg-surface-3` interior, 2 px inset lever-coloured ring). Strip-using tools (strategy-map / ebitda / value-chain) keep solid 8 px swatches — their canvas dots (`OpportunityDotStrip`) are still solid, so the per-tool dialect is intentional.
- [x] 16.2 `frontend/src/components/analysis/quick-wins-matrix/OpportunityLegendColumn.tsx`: numbered legend-entry badge becomes a donut (20 px outer, 3 px inset lever-coloured ring, `--bg-surface-3` interior, lever-coloured number — same vocabulary as `ScatterDot`, one ring-thickness step down for the smaller diameter).
- [x] 16.3 Tests added: `AnalysisLegend.test.tsx` solid-vs-donut-by-tool; `QuickWinsMatrix.test.tsx` sidebar badge donut contract.
- [x] 16.4 Frontend gates: lint, `tsc --noEmit`, 1148 / 1148 Vitest tests.
- [x] 16.5 Branch + PR + squash-merge: PR #373 → commit `1865c77`.
- [x] 16.6 Post-deploy visual verification: legend → chart → sidebar share one consistent dot vocabulary. **Verified 2026-05-22.**

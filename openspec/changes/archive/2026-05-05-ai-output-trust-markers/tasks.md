## 1. ConfidenceIndicator component

- [x] 1.1 Create `frontend/src/components/analysis/ConfidenceIndicator.tsx`. Props: `{ confidence: ConfidenceMarker; size?: 'small' | 'default' }`. Renders 3 dots — filled count = the confidence level (HIGH=3, MEDIUM=2, LOW=1), hollow count = 3 minus filled. Single neutral color (`--text-secondary` for filled, `--border` for hollow). NO use of `--risk-*` palette. `aria-label="Confidence: {level}"` on the wrapper; dots are `aria-hidden`. `size="small"` produces ~6px dots for chip headers; `size="default"` produces ~10px dots for tooltip bodies. Component under 100 lines.
- [x] 1.2 Tooltip-on-hover preserves the existing long-form rationale text per `CONFIDENCE_PALETTE` in the legacy `ConfidenceChip.tsx` (HIGH = "Directly inferred from concrete public data", MEDIUM = "Typical of similar companies in this industry; pattern-matched but not directly observed", LOW = "Inferred from absence; reasonable but unverified — deep-dive candidate"). Use the native `title` attribute on the wrapper, matching the existing pattern. The default variant carries the tooltip; the small variant skips it (header context is less inviting for hover).
- [x] 1.3 Create `frontend/src/tests/components/analysis/ConfidenceIndicator.test.tsx`. Cases: HIGH renders 3 filled, MEDIUM renders 2+1, LOW renders 1+2; accessible name matches the level for each; `size="small"` renders smaller dots than `size="default"` (assert via inline width style or computed dimensions); the rendered DOM does NOT include any of the `--risk-*` CSS variable names anywhere (regression guard for the Audit-5 collision); icon dots are `aria-hidden`.

## 2. ProvenanceMarker component

- [x] 2.1 Create `frontend/src/components/analysis/ProvenanceMarker.tsx`. Props: `{ kind: 'inferred'; label?: string }`. Renders a small inline-flex element with a sparkle/star inline SVG icon + an uppercase-tracking-tertiary label. Default label for `kind="inferred"` is "Inferred". `aria-label="AI-inferred"` on the wrapper; the icon is `aria-hidden`. Component under 80 lines. CSS classes `provenance-marker` and `provenance-marker-icon` defined in `globals.css` so the styling is centralised.
- [x] 2.2 Add CSS rules to `globals.css`: `.provenance-marker` (inline-flex, gap, font-size, weight, letter-spacing, uppercase, tertiary color) and `.provenance-marker-icon` (small dimensions, accent-blue currentColor fill).
- [x] 2.3 Create `frontend/src/tests/components/analysis/ProvenanceMarker.test.tsx`. Cases: renders the icon + label for `kind="inferred"`; accessible name conveys "AI-inferred"; icon carries `aria-hidden="true"`; `label` prop overrides the default text; rendered text is in uppercase via the CSS class (assert classlist contains `provenance-marker`).

## 3. Migrate StrategyMapNode to ConfidenceIndicator

- [x] 3.1 In `frontend/src/components/strategy-map/StrategyMapNode.tsx`, remove the `CONFIDENCE_DOT` map and the standalone 8-px dot at line ~157 (the chip header's separate confidence dot). Replace with a `<ConfidenceIndicator confidence={data.confidence} size="small" />` rendered in the same header position.
- [x] 3.2 In the tooltip body at line ~289, replace `<ConfidenceChip confidence={data.confidence} />` with `<ConfidenceIndicator confidence={data.confidence} />` (default size).
- [x] 3.3 Remove the `ConfidenceChip` import from this file.

## 4. Delete legacy ConfidenceChip

- [x] 4.1 Search the codebase for all `ConfidenceChip` references via grep. Verify zero production consumers remain (test references will reference the legacy component name in old tests; those should be updated, not preserved).
- [x] 4.2 Delete `frontend/src/components/strategy-map/ConfidenceChip.tsx`
- [x] 4.3 Remove the `ConfidenceChip` export from `frontend/src/components/strategy-map/index.ts`

## 5. Migrate StrategyMapHeader provenance markers

- [x] 5.1 In `frontend/src/components/strategy-map/StrategyMapHeader.tsx`, replace the inline-styled `<span>(synthesised)</span>` next to Vision (line ~70-84) with `<ProvenanceMarker kind="inferred" />`
- [x] 5.2 Replace the Mission summary's inline `${mission.synthesised ? ' (synthesised)' : ''}` template (line ~88) — the mission label is currently a string concatenation. Refactor: pass a `label` ReactNode that includes the marker as a separate element when `synthesised: true`, OR move the marker rendering up to the page level. Pick the cleaner approach during implementation.
- [x] 5.3 Verify both Vision and Mission `synthesised: false` paths still render cleanly with no marker.

## 6. Migrate CoreValuesStrip provenance marker

- [x] 6.1 In `frontend/src/components/strategy-map/StrategyMapView.tsx`, replace the inline `'Live our values' + (synthesised ? ' (inferred)' : '') + ':'` template (line ~84) with a layout that renders the static text + a `<ProvenanceMarker kind="inferred" />` when `synthesised: true`.

## 7. Migrate print path

- [x] 7.1 In `frontend/src/components/print/PrintStrategyMap.tsx`, replace the three inline `(synthesised)` / `(inferred)` parentheticals (lines ~109, ~113, ~218) with `ProvenanceMarker`. The component renders cleanly in print (no browser-only APIs).
- [x] 7.2 Verify `frontend/src/components/print/PrintStrategyMapObjectives.tsx` does NOT use `ConfidenceChip` — if it does, migrate to `ConfidenceIndicator`. If the print path renders confidence differently from screen (e.g. text + numeric), leave it alone and note in the design as "print confidence rendering deliberately separate."

## 8. Update existing tests

- [x] 8.1 In `StrategyMapNode.test.tsx` (or whichever test file asserts on `ConfidenceChip` text): update assertions that queried `getByText('HIGH' | 'MEDIUM' | 'LOW')` to instead query `getByLabelText(/Confidence: (high|medium|low)/i)`.
- [x] 8.2 If `StrategyMapHeader.test.tsx` exists and asserts on inline `(synthesised)` text, update to query `getByLabelText('AI-inferred')` or the equivalent.
- [x] 8.3 Add a regression test that asserts no `ConfidenceChip` element appears in the rendered DOM at the AnalysisDetail page level (defensive — catches accidental re-introduction).

## 9. Verification

- [x] 9.1 `cd frontend && npm run lint` — fix any errors
- [x] 9.2 `cd frontend && npx tsc --noEmit` — no type errors
- [x] 9.3 `cd frontend && npm test` — all tests pass
- [x] 9.4 Confirm post-migration line counts: `ConfidenceIndicator.tsx` < 100 lines, `ProvenanceMarker.tsx` < 80 lines, `StrategyMapNode.tsx` line count unchanged or smaller (CONFIDENCE_DOT removal saves ~6 lines).
- [ ] 9.5 (deferred — manual) Visually verify on local dev or after deploy: load an analysis with a strategy map; confirm dot scales render at the right counts (HIGH = ●●●, MEDIUM = ●●○, LOW = ●○○); confirm provenance markers replace the parentheticals on Vision/Mission/CoreValues and look like styled markers (icon + uppercase label) rather than parenthetical text; confirm the print preview also renders correctly.
- [ ] 9.6 (deferred — manual) Screen-reader spot-check: navigate the strategy-map chips with VoiceOver/NVDA — should hear "Confidence: high" (or similar) when focusing chips with confidence data; should hear "AI-inferred" when focusing a section with `synthesised: true`.

## 10. Architecture review + commit + PR

- [x] 10.1 Run the `architecture-reviewer` agent over the diff. Focus areas: (a) does ConfidenceIndicator's neutral palette truly avoid the risk-tier collision, (b) is the size variant API the right shape (or should it be just one size with caller-side scaling), (c) is the print path migration clean, (d) is `ConfidenceChip` deletion safe (zero remaining consumers), (e) does ProvenanceMarker correctly handle the screen + print contexts in one component.
- [x] 10.2 Commit with conventional-commit message: `feat(analysis): add AI confidence + provenance markers (decouple from risk-tier palette)`
- [x] 10.3 Open PR against `development`. Body should reference UX review Audits 5 + 7, explicitly call out that backend extension to opportunities/EBITDA/value-chain is a separate proposal, list the manual visual + screen-reader verification gates, and reference the established BA/UX-review track of work.

## 1. AnalysisSection component (foundation)

- [x] 1.1 Create `frontend/src/components/analysis/AnalysisSection.tsx` per design D1: props `{ id, title?, lead?, children }`. No state, no hooks, no side effects. Title rendered as `<h2 className="section-header">`; lead rendered as `<p>` in secondary-text style; testid always present
- [x] 1.2 Create `frontend/src/tests/components/analysis/AnalysisSection.test.tsx` covering: testid-only render, string title, ReactNode title with adornment, title + lead, no-title-no-lead, every prop produces the expected DOM shape
- [x] 1.3 Verify with isolated tests: `cd frontend && npm test -- src/tests/components/analysis/AnalysisSection.test.tsx --run`

## 2. AnalysisDetail integration — replace inline Section helper + DocumentUpload framing

- [x] 2.1 Import `AnalysisSection` in `AnalysisDetail.tsx`. Delete the inline `Section` helper function (replaced by the new component)
- [x] 2.2 Replace every existing `<Section id="...">` with `<AnalysisSection id="...">` (no title/lead yet — that comes per-section)
- [x] 2.3 Migrate the DocumentUpload framing: replace the inline `<h2 className="section-header">Improve This Analysis</h2>` + `<p>Upload financial statements...</p>` with the `title` and `lead` props of the wrapping `AnalysisSection`
- [x] 2.4 Run `cd frontend && npm test` — every test that depended on `data-testid="analysis-section-*"` should still pass (the new component emits the same attribute). The "page renders Improve This Analysis heading at page level" test should still find the text. Fix any breakages

## 3. Migrate RiskBreakdown

- [x] 3.1 In `frontend/src/components/RiskBreakdown.tsx`, remove the internal `<h2 className="section-header">Risk Breakdown</h2>` and any wrapping `<div style={{ marginBottom: '2rem' }}>` that exists only to host the heading
- [x] 3.2 In `AnalysisDetail.tsx`, set `<AnalysisSection id="risk-breakdown" title="Risk Breakdown">` around the `<RiskBreakdown ... />` call
- [x] 3.3 Update `frontend/src/tests/components/RiskBreakdown.test.tsx` (or the file containing those assertions): change any assertion that expects "Risk Breakdown" inside the component's render — it now lives in the page wrapper
- [x] 3.4 Add an AnalysisDetail-level assertion (in `frontend/src/tests/pages/AnalysisDetail.test.tsx`) that the heading "Risk Breakdown" renders inside `screen.getByTestId('analysis-section-risk-breakdown')`

## 4. Migrate EbitdaSection

- [x] 4.1 In `frontend/src/components/analysis/EbitdaSection.tsx`, remove the internal `<h2 className="section-header">EBITDA Impact Model<HelpTooltip term="ebitda_tree" /></h2>`
- [x] 4.2 In `AnalysisDetail.tsx`, set `<AnalysisSection id="ebitda" title={<>EBITDA Impact Model<HelpTooltip term="ebitda_tree" /></>}>` — import `HelpTooltip` if not already imported
- [x] 4.3 Update `frontend/src/tests/components/analysis/EbitdaSection.test.tsx`: relax any internal-heading assertion
- [x] 4.4 Add an AnalysisDetail-level assertion that "EBITDA Impact Model" renders inside `analysis-section-ebitda`

## 5. Migrate ValueChainDiagram

- [x] 5.1 In `frontend/src/components/ValueChainDiagram.tsx`, remove the internal section heading
- [x] 5.2 In `AnalysisDetail.tsx`, set `<AnalysisSection id="value-chain" title="Value Chain Analysis">`
- [x] 5.3 Update any existing ValueChainDiagram tests that asserted on the internal heading
- [x] 5.4 Add an AnalysisDetail-level assertion that "Value Chain Analysis" renders inside `analysis-section-value-chain`

## 6. Migrate ValueLeverSummary

- [x] 6.1 In `frontend/src/components/ValueLeverSummary.tsx`, remove the inline `<h2 style={{ fontSize: '1.125rem', fontWeight: 700, marginBottom: '1rem' }}>Value Impact<HelpTooltip term="value_lever" /></h2>` AND its wrapping `<div style={{ marginBottom: '2rem' }}>` if it exists only to host that heading
- [x] 6.2 In `AnalysisDetail.tsx`, set `<AnalysisSection id="value-lever" title={<>Value Impact<HelpTooltip term="value_lever" /></>}>`
- [x] 6.3 Update `frontend/src/tests/pages/AnalysisDetail.test.tsx` "Value Impact" assertions — the heading now lives at page level (the test currently asserts `screen.getByText('Value Impact')` which still works, but should target the wrapper)
- [x] 6.4 Verify the `hasValueLevers` early-return path still works: when no opportunities have `value_lever`, the component still returns `null` AND the `AnalysisSection` wrapper at the page level still emits its testid (since `<AnalysisSection>` always renders its wrapper, even if children are null). Decide: do we want the empty wrapper, or should the page-level call site be `{hasValueLevers && <AnalysisSection ...>}`? Pick the latter for consistency with how other conditional sections are rendered

## 7. Migrate OpportunitiesList (partial — see design D2)

- [x] 7.1 Read the existing `<h2>` + flex-row structure in `frontend/src/components/OpportunitiesList.tsx` to understand the category-chip strip's layout
- [x] 7.2 Remove the inline `<h2 style={{...}}>AI Opportunities ({n})<HelpTooltip term="impact_rating" /></h2>` from inside the flex container. The flex container becomes a single-row strip containing only the category chips. Update its `justifyContent` from `'space-between'` to `'flex-start'` (chips left-aligned now)
- [x] 7.3 In `AnalysisDetail.tsx`, set `<AnalysisSection id="opportunities" title={<>AI Opportunities ({opportunities.length})<HelpTooltip term="impact_rating" /></>}>`. The page passes the count via the title prop using `opportunities` from its scope
- [x] 7.4 Update `frontend/src/tests/pages/AnalysisDetail.test.tsx` — the existing test `screen.getByText(/AI Opportunities/)` should still pass since the text is now at page level. Confirm
- [x] 7.5 Add a regression test: assert the category chips no longer render in a `space-between` row with the `<h2>` (the test queries the `analysis-section-opportunities` wrapper and verifies the title appears once, then chips appear below in a separate row)

## 8. Verify exempt sections are unchanged

- [x] 8.1 Sanity-check that `StrategyMapView`, `Sc0redCTABanner`, `DeepDiveCTA`, `TopActionsCallout`, `AnalysisOverviewCards`, `AnalysisExecutiveStrap`, `AnalysisHeader` retain their current rendering — none of them should have been touched in the migration
- [x] 8.2 Verify the page-level `AnalysisSection` wrappers around them (today: `<Section id="header">`, etc.) are converted to `<AnalysisSection id="header">` with NO `title` prop — testid-only render

## 9. Full-stack verification

- [x] 9.1 `cd frontend && npm run lint` — fix any errors
- [x] 9.2 `cd frontend && npx tsc --noEmit` — no type errors
- [x] 9.3 `cd frontend && npm test` — all tests pass
- [x] 9.4 Confirm `AnalysisDetail.tsx` is still under the 360-line cap (estimate post-migration: ~280 lines)
- [ ] 9.5 Visually verify on local dev or after deploy: scan vertically down a full-data analysis. Every migrated section heading should have identical font/weight/size/color/spacing. Exempt sections (StrategyMap, CTAs) should look intentionally distinct, NOT broken
- [ ] 9.6 Verify `OpportunitiesList`'s decoupled chip row reads OK in the deployed UI. If it reads poorly, file a follow-up to add `headerRight` slot to `AnalysisSection` (per design D2 fallback plan)

## 10. Architecture review + commit + PR

- [ ] 10.1 Run the `architecture-reviewer` agent over the diff. Required because changes touch 6+ source files and alter component contracts. Resolve all CRITICAL findings before commit
- [ ] 10.2 Commit with a conventional-commit message: `refactor(analysis): unify section heading framing via AnalysisSection wrapper`
- [ ] 10.3 Open PR against `development`. Body should reference this OpenSpec change (`analysis-detail-consistency-wrapper`), explicitly call out the OpportunitiesList partial migration (D2 trade-off) and the exempt sections list, and note the manual visual verification gate (task 9.5)

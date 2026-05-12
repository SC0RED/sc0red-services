## 1. Section testids (foundation for order-based tests)

- [x] 1.1 Add stable `data-testid` markers at the page level by wrapping each rendered section in `AnalysisDetail.tsx` with a parent `<div data-testid="analysis-section-{name}">`: `analysis-section-header`, `analysis-section-strap`, `analysis-section-overview`, `analysis-section-top-actions`, `analysis-section-strategy-map`, `analysis-section-deep-dive-cta`, `analysis-section-ebitda`, `analysis-section-value-chain`, `analysis-section-risk-breakdown`, `analysis-section-value-lever`, `analysis-section-opportunities`, `analysis-section-sc0red-cta`, `analysis-section-document-upload`. (Page-level wrapping keeps section naming a page concern, so existing component-internal testids like `strategy-map-view` and `strategy-map-cta` are preserved and their tests don't churn.)
- [x] 1.2 Run existing test suite to verify no regression from added wrappers — 922 tests pass post-merge

## 2. AnalysisExecutiveStrap component

- [x] 2.1 Create `frontend/src/components/analysis/AnalysisExecutiveStrap.tsx` with props `{ data: AnalysisData }`. Component must be under 100 lines and have a single root element with `data-testid="analysis-section-strap"`
- [x] 2.2 Display EBITDA range using `data.ebitdaTree?.ebitdaEstimate` directly (it's already a precomputed string like `"$2M-$8M"`). Do NOT walk leaf nodes or fall back to `revenueEstimate` — see design D4 for rationale.
- [x] 2.3 Implement conditional segment rendering: omit EBITDA segment + leading separator if `ebitdaTree` is null; omit "last analysed" segment + leading separator if `analyzedAt` is null
- [x] 2.4 Style the strap as inline text with `·` separators between segments. Allow natural wrapping at narrow widths (do NOT apply `white-space: nowrap`). Wrapping to 2–3 lines on mobile is acceptable per resolved question 2 in design.md
- [x] 2.5 Create `frontend/src/tests/components/analysis/AnalysisExecutiveStrap.test.tsx` with cases: full data, null ebitdaTree, null analyzedAt, empty opportunities array, score formatting (one decimal), tier derivation when riskTier is null

## 3. DocumentUpload reframe

- [x] 3.1 Read existing `frontend/src/components/DocumentUpload.tsx` and existing tests to understand current structure and prop contract
- [x] 3.2 Rename the section header copy from its current label to **"Improve This Analysis"** (locked per resolved question 1 in design.md)
- [x] 3.3 Update the drop-zone subtitle to frame uploads as analysis improvement (e.g., "Upload financial statements, board decks, or product docs to refine this analysis")
- [x] 3.4 Add an explicit `<button>` labelled "Re-analyse" (or equivalent), visible when `documents.length > 0`, disabled when `reanalyzing === true`, with `aria-label`. onClick calls the existing `onReanalyze` prop
- [x] 3.5 Move the reanalyzing-progress block currently rendered in `AnalysisDetail.tsx` (lines ~153–174) into `DocumentUpload.tsx`. Render it conditionally on `reanalyzing === true`. Pass through any required state via existing `reanalyzing`, plus new props for `reanalysisLabel` and `reanalysisProgress` if not already passed
- [x] 3.6 Update `frontend/src/tests/components/DocumentUpload.test.tsx` (or create if absent) covering: button presence when documents exist, button disabled during reanalyzing, button click calls `onReanalyze` once, progress bar renders inside the section when reanalyzing, button accessible name contains "re-analyse" or "re-analyze"

## 4. AnalysisDetail reorder + integrate strap

- [x] 4.1 In `frontend/src/app/(authenticated)/analysis/[analysisId]/AnalysisDetail.tsx`, import `AnalysisExecutiveStrap`
- [x] 4.2 Re-order the JSX inside the success-path return to match the 13-section sequence in design D1: Header → ExecutiveStrap → OverviewCards → TopActions → StrategyMap → DeepDiveCTA → EBITDA → ValueChain → RiskBreakdown → ValueLever → Opportunities → Sc0redCTA → DocumentUpload
- [x] 4.3 Remove the orphaned reanalyzing-progress block from this file (it now lives inside DocumentUpload)
- [x] 4.4 Remove the `reanalyze.documentError` alert if it duplicates with DocumentUpload's own error handling — verify which surface owns document errors
- [x] 4.5 Update the comment block above DeepDiveCTA: replace the PR #239 D6 rationale (which justified the old position) with a reference to this change and note that the CTA now sits after WhatsMissingPanel by design
- [x] 4.6 Ensure DocumentUpload receives any new props it now needs (`reanalysisLabel`, `reanalysisProgress`, `documentError`) per the contract changes from task 3.5

## 5. AnalysisDetail tests

- [x] 5.1 Update or create `frontend/src/tests/app/(authenticated)/analysis/[analysisId]/AnalysisDetail.test.tsx` to assert the 13-section order using `data-testid` markers from task 1.1. Use `screen.getAllByTestId` filtered by an `analysis-section-` prefix and assert the array order — implemented in `frontend/src/tests/pages/AnalysisDetail.test.tsx` (existing test file location, not the spec-suggested path)
- [x] 5.2 Add a test for the conditional-section paths: no strategy map, no ebitda tree, no value chain, no opportunities — verify remaining sections preserve relative order
- [x] 5.3 Add a test that the orphaned reanalyzing-progress block is no longer a sibling of DocumentUpload at the AnalysisDetail level
- [x] 5.4 Run the full frontend test suite: `cd frontend && npm test`. All tests must pass before commit

## 6. Verification

- [x] 6.1 `cd frontend && npm run lint` — fix all lint errors
- [x] 6.2 `cd frontend && npx tsc --noEmit` — no type errors
- [x] 6.3 `cd frontend && npm test` — all tests pass
- [ ] 6.4 (deferred — manual) Visually verify on local dev: load an analysis with full data, walk top-to-bottom, confirm 13 sections render in the new order, ExecutiveStrap renders, Re-analyse button is visible, progress bar renders inside DocumentUpload during a re-analyse
- [ ] 6.5 (deferred — manual) Visually verify on local dev: load an analysis without an ebitda tree, confirm strap omits the EBITDA segment cleanly (no orphaned separator) and section ordering is preserved

## 7. Architecture review + commit

- [x] 7.1 Run the `architecture-reviewer` agent over the diff. Required because changes touch 3+ source files and alter component contracts (DocumentUpload prop additions). Resolve all CRITICAL findings before commit. (Two passes: first surfaced 3 MEDIUM findings — FailedAnalysisView divergence, file budget overrun, date-format inconsistency. Second pass confirmed all resolved; remaining LOW items addressed in same commit.)
- [x] 7.2 Commit with a conventional-commit message in the form `feat(analysis): redesign detail page narrative ordering` — committed as `0e0fa2c`, follow-up review fixes as `ba446a9`, squash-merged to development as `155b00d`
- [x] 7.3 Open PR with a body summarising the 5-beat narrative, the executive-strap addition, and the re-analyse-affordance fix. Reference both BA reviews (this conversation + the Cowork PDF) in the rationale — PR #250 opened and merged. CI all green (Lint, Test, Frontend Test, Audit, Security, Naming, E2E, Playwright, PR Summary, CodeRabbit)

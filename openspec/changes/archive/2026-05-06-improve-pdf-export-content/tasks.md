## 1. Scaffolding & shared utilities

- [x] 1.1 Create the `frontend/src/components/print/` directory and a barrel `index.ts` that re-exports each new print component.
- [x] 1.2 Add a `frontend/src/lib/pdf/sortOpportunities.ts` helper that returns a sorted-with-original-index array (sorted by `impact_rating` then original index, with index preserved for linkage). Unit tests cover empty, single, and mixed-rating arrays.
- [x] 1.3 Add a `frontend/src/lib/pdf/derivedSummary.ts` helper that derives the executive-summary view (top-3 risks, top-3 opportunities, EBITDA-uplift figures) from `AnalysisData`. Returns `null` when both `riskScores` and `opportunities` are empty. Unit tests cover the omission rule and the sort order.

## 2. Print components

- [x] 2.1 Create `PrintCover.tsx` (extracted from the existing `PrintReport.tsx` cover block — no new logic, just isolation so the rewrite is reviewable).
- [x] 2.2 Create `PrintExecutiveSummary.tsx` rendering the EBITDA-uplift bar, top-3 opportunity one-liners, and top-3 risk-driver lines from the `derivedSummary` helper. Returns `null` when the helper returns `null`.
- [x] 2.3 Create `PrintRiskTable.tsx` rendering each `riskScores` entry as a fixed-expanded row (category, score, score bar, full rationale). Sorted by score descending. No collapse controls.
- [x] 2.4 Create `PrintOpportunityCard.tsx` rendering one opportunity fully expanded — title, lever badge, impact, timeline, strategic category, full description, numbered implementation steps, investment range, ROI estimate. Accepts `printedIndex` so linkage callouts can reference it.
- [x] 2.5 Create `PrintOpportunityList.tsx` that groups opportunities by `value_lever` (Revenue → Cost → Both → no-lever), inserts a section divider per group, and composes `PrintOpportunityCard` per opp. Preserves the printed-index used for linkage.
- [x] 2.6 Create `PrintEbitdaOutline.tsx` — implementation simplified during architecture review to always render as a nested HTML outline. The earlier design's CSS-grid "small-tree" mode lost parent-child alignment on unbalanced trees; outline preserves hierarchy via indentation regardless of shape. Spec + design updated to match.
- [x] 2.7 Create `PrintValueChainList.tsx` rendering value-chain steps as vertically stacked rows — primary group first, support group second. Per-row: name, role description, risk-category chips, linkage callout. No horizontal flex layout.
- [x] 2.8 Create `PrintMethodologyAppendix.tsx` with the source URL(s), model and rubric reference, and AI-disclosure paragraph. Uses only fields already visible in the live app.
- [x] 2.9 Create `PrintBackCover.tsx` rendering the single sc0red CTA. Returns `null` when there are no opportunities.

## 3. Print stylesheet

- [x] 3.1 Add named `@page` rules to `frontend/src/app/print/print.css`: default A4 portrait, plus `@page ebitda-page { size: A3 landscape; }`. Add `.print-ebitda { page: ebitda-page; }` to scope the override.
- [x] 3.2 Add `page-break-inside: avoid` rules for `.print-opportunity-card`, `.print-risk-row`, `.print-ebitda-outline-block`, and `.print-value-chain-row`.
- [x] 3.3 Add `page-break-before: always` rules between major sections via a `.print-section--break-before` modifier (already used by today's `PrintReport`; verify each new section uses it).
- [x] 3.4 Add no-orphan-headings handling — `h2 { break-after: avoid-page; }` plus `widows: 3; orphans: 3;` on body copy.

## 4. Strip in-component CTAs from the print path

- [x] 4.1 Audit `OpportunitiesList.tsx` for any embedded sc0red CTA block; remove it from the component entirely. Add a screen-only `<Sc0redCTABanner />` invocation at the analysis detail page (where it currently lives via the list).
- [x] 4.2 Audit `ValueChainDiagram.tsx` for any embedded sc0red CTA; remove it. (Verified: no CTA was embedded.)
- [x] 4.3 Verify by grep that `frontend/src/components/print/` contains exactly one CTA call site (`PrintBackCover.tsx`) and that `Sc0redCTABanner` is no longer imported anywhere under the print path.

## 5. Rewrite PrintReport.tsx

- [x] 5.1 Replace the body of `frontend/src/app/print/[analysisId]/PrintReport.tsx` so it composes the new print components in order: Cover → Executive Summary → Risk Profile → Opportunity Roadmap → EBITDA Impact Model → Value Chain → Methodology Appendix → Back Cover. Skip sections cleanly when their data is empty.
- [x] 5.2 Sort opportunities once at the top of `PrintReport` using the `sortOpportunities` helper; thread the sorted-with-original-index array down to every section that needs linkage.
- [x] 5.3 Keep the existing `useEffect` that forces `data-theme="light"` on `<html>` — required for headless renders.
- [x] 5.4 Keep the existing print-status `<meta>` marker emission so the Lambda's wait-for-ready signal still fires.

## 6. Tests

- [x] 6.1 RTL test for `PrintExecutiveSummary` — renders with full data, omits when `riskScores` and `opportunities` are both empty, renders partial data correctly.
- [x] 6.2 RTL test for `PrintRiskTable` — every entry shows rationale text without interaction; missing-rationale row renders the score bar only.
- [x] 6.3 RTL test for `PrintOpportunityCard` — all populated fields visible, no expand control, lever badge shows.
- [x] 6.4 RTL test for `PrintOpportunityList` — grouping order (Revenue → Cost → Both → no-lever), section dividers appear, printed-index threading is correct.
- [x] 6.5 RTL test for `PrintEbitdaOutline` — every node label rendered for small, wide, and deep trees; linkage callout resolves to opportunity titles.
- [x] 6.6 RTL test for `PrintValueChainList` — six primary + five support all render with full names; linkage callouts resolve correctly; no horizontal flex DOM.
- [x] 6.7 RTL test for `PrintMethodologyAppendix` — disclosure text present verbatim, source URL rendered.
- [x] 6.8 RTL test for `PrintBackCover` — renders with opportunities, returns null without.
- [x] 6.9 Unit test for `sortOpportunities` and `derivedSummary` helpers (covered in §1 but verify both pass before §5 lands).
- [x] 6.10 New `PrintReport.test.tsx` smoke test asserts presence of Executive Summary, Methodology Appendix, and exactly one sc0red CTA in the rendered tree.

## 7. Visual verification on representative analyses

- [x] 7.1 Pick three representative production analyses (one with sparse data, one mid-size, one with a deep EBITDA tree). Capture the current PDF for each (label `before-{slug}.pdf`) and store under `openspec/changes/improve-pdf-export-content/visual/before/`.
- [x] 7.2 After the rewrite, generate the new PDF for each of those three analyses (label `after-{slug}.pdf`) and store under `visual/after/`.
- [x] 7.3 Cross-check the after-PDFs page-by-page against the spec scenarios. Document any deviations in `visual/notes.md` for sign-off before rollout.

## 8. Lint, type-check, and architecture review

- [x] 8.1 `cd frontend && npm run lint` — clean.
- [x] 8.2 `cd frontend && npx tsc --noEmit` — clean.
- [x] 8.3 `cd frontend && npm test` — all 783 tests pass; new tests included.
- [x] 8.4 Verified each new print component file is under the 360-line frontend limit. Plus opportunistically split `AnalysisDetail.tsx` (was 426 lines, now 173) into `useReanalyze` hook + `AnalysisOverviewCards` sub-component.
- [x] 8.5 Architecture-reviewer agent run. CRITICAL findings: 0. MEDIUM findings: 2 (`CAT_LABELS` import from `'use client'` screen file → moved to `riskUtils.ts`; depth-bucketed grid loses parent-child alignment on unbalanced trees → simplified to always-outline rendering). LOW findings: 2 (dead CSS selectors removed; explicit `'en-US'` locale for `generatedDate`; missing `--break-before` on `PrintRiskTable` added). All resolved.

## 9. Rollout

- [x] 9.1 Open a PR against `development`. Include the before/after visual PDFs as PR description artifacts (or link to the change folder).
- [x] 9.2 After merge to `development`, soak for 24h. Verify three real analyses render correctly via the Export PDF button.
- [x] 9.3 Open the `development → testing` promotion PR. Re-run visual verification on testing for the same three analyses.
- [x] 9.4 Open the `testing → production` promotion PR after sign-off.
- [x] 9.5 Post-rollout: archive the polished-pdf-export change first (so its baseline merges into `openspec/specs/polished-pdf-export/spec.md`), then archive this change so the MODIFIED requirements resolve cleanly.

## 1. AnalysisSection — add titleAdornment slot

- [ ] 1.1 Update `frontend/src/components/analysis/AnalysisSection.tsx`: add `titleAdornment?: ReactNode` to the props interface; render the heading + adornment inside a wrapping `<div className="section-header-row">` when EITHER `title` or `titleAdornment` is provided. Heading uses existing `<h2 className="section-header">` for the title; adornment renders as a sibling `<span className="section-header-adornment">`. Update JSDoc to document the new slot.
- [ ] 1.2 Add CSS rules to `frontend/src/app/globals.css`: define `--section-gap-y: 1rem` as a new token (per resolved question — locks heading-row's margin into the token system); add `.section-header-row` (flex, align-items center, gap 0.5rem, margin-bottom var(--section-gap-y)), `.section-header-row > .section-header { margin-bottom: 0 }` to override the heading's existing bottom margin when it lives in a row, and `.section-header-adornment` (inline-flex container).
- [ ] 1.3 Update `frontend/src/tests/components/analysis/AnalysisSection.test.tsx`: add 4 new tests covering titleAdornment slot — renders inside section, NOT inside `<h2>`, both title + adornment as siblings in row, adornment-only without title doesn't crash. Verify existing tests still pass.

## 2. Migrate AnalysisDetail call sites

- [ ] 2.1 In `frontend/src/app/(authenticated)/analysis/[analysisId]/AnalysisDetail.tsx`, migrate the `ebitda` section: change `title={<>EBITDA Impact Model<HelpTooltip term="ebitda_tree" /></>}` to `title="EBITDA Impact Model"` + `titleAdornment={<HelpTooltip term="ebitda_tree" />}`
- [ ] 2.2 Migrate the `value-lever` section the same way (title `"Value Impact"` + adornment `<HelpTooltip term="value_lever" />`)
- [ ] 2.3 Migrate the `opportunities` section: title becomes a plain string template `\`AI Opportunities (${opportunities.length})\``; adornment is `<HelpTooltip term="impact_rating" />`
- [ ] 2.4 Search the codebase for the pattern `title={<>` to confirm no other call sites still embed adornments inside title fragments

## 3. Tighten heading-framing tests

- [ ] 3.1 Update `frontend/src/tests/pages/AnalysisDetail.test.tsx`: change the EBITDA, Value Impact, and AI Opportunities heading-framing assertions from regex matchers (`getByRole('heading', { name: /EBITDA Impact Model/ })`) to exact matchers (`getByRole('heading', { name: 'EBITDA Impact Model' })`). The exact match would have failed under the old structure (because the accessible name included the help-tooltip button label); under the new structure it passes — which is the regression guard.
- [ ] 3.2 Add new assertions: for each migrated section, query the wrapper testid and verify the help-tooltip button (find via role=`button` with name matching `/What is/`) is INSIDE the wrapper but OUTSIDE the `<h2>` (use `compareDocumentPosition` or DOM-tree walking).

## 4. Verification

- [ ] 4.1 `cd frontend && npm run lint` — fix any errors
- [ ] 4.2 `cd frontend && npx tsc --noEmit` — no type errors
- [ ] 4.3 `cd frontend && npm test` — all tests pass
- [ ] 4.4 Confirm `AnalysisSection.tsx` is still under the 100-line component target (currently ~73 lines; new prop + row wrapper add ~10-12 lines, well within budget)
- [ ] 4.5 (deferred — manual) Screen-reader verification on dev: navigate the page with VoiceOver / NVDA, listen to migrated headings — should hear ONLY the title text (e.g. "EBITDA Impact Model"), NOT "EBITDA Impact Model What is EBITDA Tree?". Tab order should reach the help-tooltip button as a separate focus stop AFTER the heading

## 5. Architecture review + commit + PR

- [ ] 5.1 Run the `architecture-reviewer` agent over the diff. Focus areas: (a) does the new prop fit the existing component contract cleanly, (b) is the CSS specificity of the row > section-header override correct, (c) are there other call sites of `.section-header` that could be affected by the row-owns-margin pattern (audit `globals.css` and grep for `section-header` usages outside `AnalysisSection`)
- [ ] 5.2 Commit with conventional-commit message: `fix(analysis): extract help-tooltip from section h2 to fix accessible-name regression`
- [ ] 5.3 Open PR against `development`. Body should reference the architecture-reviewer's pass-1 finding from PR #251 (the noted limitation we knowingly shipped), reference UX review Audit 1 + Audit 6, and call out the test posture inversion (regex → exact match) as the structural proof of the fix

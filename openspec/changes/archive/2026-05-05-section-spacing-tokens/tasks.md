## 1. Add token + utility class

- [x] 1.1 In `frontend/src/app/globals.css`, add `--section-margin-bottom: 2rem` to the `:root` block next to `--section-gap-y` and `--section-header-row-gap`. Update the existing comment block to explain the picker rule between `--section-gap-y` (intra-section) and `--section-margin-bottom` (inter-section).
- [x] 1.2 Add `.analysis-section-spacing { margin-bottom: var(--section-margin-bottom); }` rule. Place near the `.section-header` / `.section-lead` rules so it lives in the same logical section of the stylesheet.

## 2. Migrate consumers

- [x] 2.1 `frontend/src/components/RiskBreakdown.tsx` — replace `<div style={{ marginBottom: '2rem' }}>` with `<div className="analysis-section-spacing">`.
- [x] 2.2 `frontend/src/components/OpportunitiesList.tsx` — same migration.
- [x] 2.3 `frontend/src/components/ValueChainDiagram.tsx` — same migration.
- [x] 2.4 `frontend/src/components/analysis/EbitdaSection.tsx` — same migration.
- [x] 2.5 `frontend/src/components/DocumentUpload.tsx` — same migration.
- [x] 2.6 `frontend/src/components/analysis/AnalysisHeader.tsx` — wrapper has compound inline style (flex + gap + wrap + marginBottom). Add `className="analysis-section-spacing"` AND remove only the `marginBottom: '2rem'` line from the style object; keep the other inline styles.

## 3. Verification

- [x] 3.1 `cd frontend && npm run lint` — fix any errors
- [x] 3.2 `cd frontend && npx tsc --noEmit` — no type errors
- [x] 3.3 `cd frontend && npm test` — all tests pass (no test changes expected — token is presentation-only)
- [x] 3.4 Grep for any remaining `marginBottom: '2rem'` on section wrappers in the analysis-detail page consumer files. Confirm only the exempt sections (AnalysisExecutiveStrap `1.25rem`, AnalysisOverviewCards `1.5rem`) retain non-standard inline values.
- [ ] 3.5 (deferred — manual) Visually verify on local dev or after deploy: every migrated section retains the same `2rem` bottom margin as before. No visual delta expected.

## 4. Architecture review + commit + PR

- [x] 4.1 Run the `architecture-reviewer` agent. Focus areas: (a) does the token name (`--section-margin-bottom`) make sense alongside `--section-gap-y`? (b) any consumer I missed in the migration list? (c) is the exempt-list rationale (strap + overview-cards intentional pairing) honest, or is something else going on?
- [x] 4.2 Commit with conventional-commit message: `refactor(analysis): tokenize section-to-section vertical spacing`
- [x] 4.3 Open PR against `development`. Body should reference UX review Audit 8, list the 6 migrated consumers + 2 exempt consumers with rationale, note the manual visual verification gate, and call out that this is the FINAL UX-review-driven proposal in the analysis-detail-narrative track.

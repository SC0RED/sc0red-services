## 1. Add card-density variants to globals.css

- [x] 1.1 Open `frontend/src/app/globals.css` and locate the existing `.card` rule (under "Glassmorphism Cards"). Add a new section "Card density variants" immediately AFTER the bare `.card` rules.
- [x] 1.2 Add a comment block at the top of the section documenting the picker rule (per design D5) — three variants, when to use each, BEM-style application, no inline padding override.
- [x] 1.3 Add three CSS rules using compound selectors (`.card.card--metric`, `.card.card--list`, `.card.card--rich`) per design D1:
  - `.card.card--metric` — `padding: 2rem; text-align: center;`
  - `.card.card--list` — `padding: 0.75rem 1rem;`
  - `.card.card--rich` — `padding: 1.25rem 1.5rem;`

## 2. Migrate analysis-detail-page consumers

- [x] 2.1 `frontend/src/components/analysis/AnalysisOverviewCards.tsx` — Overall AI Risk Score wrapper (line ~39): `className="card"` + `padding: 2rem` → `className="card card--metric"` + remove `padding` from inline style. Risk Dimensions wrapper (line ~101): `className="card"` + `padding: 1.5rem` → `className="card card--rich"` + remove `padding`.
- [ ] 2.2 ~~`frontend/src/components/RiskBreakdown.tsx`~~ — **DEFERRED to ExpandableCard proposal (UX queue item A)**. Discovered during apply: this is a button-card pattern (inner `<button>` owns padding), not a content-card. See design D2.
- [ ] 2.3 ~~`frontend/src/components/OpportunitiesList.tsx`~~ — **DEFERRED to ExpandableCard proposal**. Same button-card pattern.
- [ ] 2.4 ~~`frontend/src/components/ValueChainDiagram.tsx`~~ — **DEFERRED to ExpandableCard proposal**. The button IS the `.card` (`<button className="card">`); same pattern, no separate outer card.
- [x] 2.5 `frontend/src/components/analysis/EbitdaSection.tsx` (line ~48) — inner tree wrapper: `className="card"` + `style={{ padding: '1rem' }}` → `className="card card--rich"` + remove inline padding.
- [x] 2.6 `frontend/src/components/analysis/TopActionsCallout.tsx` (line ~10) — outer callout: `className="card"` + `style={{ padding: '1.25rem 1.5rem', ... }}` → `className="card card--rich"` + remove the padding from the inline style (preserve other inline styles like `marginBottom`, `borderColor`, `background`).
- [x] 2.7 `frontend/src/components/DocumentUpload.tsx` (line ~265) — per-document row: `className="card"` + `style={{ padding: '0.75rem 1rem', ... }}` → `className="card card--list"` + remove the padding from inline style.
- [x] 2.8 `frontend/src/components/analysis/ReanalyzeProgressCard.tsx` (line ~41) — outer card: `className="card"` + `style={{ padding: '1.5rem', ... }}` → `className="card card--rich"` + remove padding from inline style.

## 3. Verification

- [x] 3.1 `cd frontend && npm run lint` — fix any errors
- [x] 3.2 `cd frontend && npx tsc --noEmit` — no type errors
- [x] 3.3 `cd frontend && npm test` — all tests pass. Update any tests that asserted on inline padding values (assertions either query the variant class on the wrapper, or delete — testing inline-style values is brittle).
- [x] 3.4 Search the codebase for any remaining `className="card"` with an inline `padding` style on the analysis-detail page — these are migration misses. (`grep -rn 'className="card"' frontend/src/components/analysis/ frontend/src/components/RiskBreakdown.tsx frontend/src/components/OpportunitiesList.tsx frontend/src/components/ValueChainDiagram.tsx frontend/src/components/DocumentUpload.tsx | grep "padding"`.)
- [ ] 3.5 (deferred — manual) Visually verify on local dev or after deploy: load an analysis with full data; scan vertically; every migrated card should look identical to before (variant padding matches the inline value it replaced) but with NO inline `padding` style on the wrapper.

## 4. Architecture review + commit + PR

- [ ] 4.1 Run the `architecture-reviewer` agent over the diff. Focus areas: (a) does the compound-selector pattern (`.card.card--metric` instead of `.card--metric` alone) actually win over inline `padding` styles via specificity? (b) are all 9 analysis-detail-page consumers migrated correctly? (c) any consumers I missed in the migration list (audit `grep`)? (d) any tests that asserted on inline padding that need updates?
- [ ] 4.2 Commit with conventional-commit message: `refactor(analysis): introduce .card variants (metric/list/rich) for density consistency`
- [ ] 4.3 Open PR against `development`. Body should reference UX review Audit 3, list the 9 migrated consumers, explicitly note the 38 non-analysis-detail consumers that intentionally stay on bare `.card`, and call out the manual visual verification gate.

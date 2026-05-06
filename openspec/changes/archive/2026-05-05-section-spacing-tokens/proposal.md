## Why

UX review **Audit 8** flagged irregular vertical rhythm across the analysis-detail page. Sections accreted bottom margins per-component over the lifetime of the page: every section's outer wrapper ended up with `marginBottom: '2rem'` inline, but the value lives in 9+ different files and any future tweak requires editing all of them.

PR #252 (`extract-definition-popover`) introduced `--section-gap-y: 1rem` for **within-section** spacing (heading-to-body via `.section-header-row` and `.section-lead`). That handled half the rhythm. The other half — **between-section** spacing — remains hardcoded inline in every section component:

| Section | Outer bottom margin |
|---|---|
| RiskBreakdown | `2rem` inline |
| OpportunitiesList | `2rem` inline |
| ValueChainDiagram | `2rem` inline |
| EbitdaSection | `2rem` inline |
| DocumentUpload | `2rem` inline |
| AnalysisHeader | `2rem` inline |

Same value, six places. UX Audit 8 explicitly called this out: *"Sections aren't on a consistent vertical rhythm... define `--section-gap-y` as a CSS token and apply it via a screen analog of the print stylesheet's `.print-section--break-before`."*

This proposal completes that recommendation by introducing the **section-to-section** spacing token and migrating the 6 hardcoded consumers.

This is the **fifth and final** UX-review-driven proposal in the analysis-detail-narrative track. After this lands, every UX Audit (1 through 8) is either closed or has an explicit deferred-exception with rationale.

## What Changes

- **Add** `--section-margin-bottom: 2rem` CSS token to `globals.css` `:root`, declared next to the existing `--section-gap-y` and `--section-header-row-gap` tokens. Naming distinguishes it from `--section-gap-y` (which is intra-section, between heading and body) — `--section-margin-bottom` is inter-section, between consecutive section wrappers.
- **Migrate** the 6 inline `marginBottom: '2rem'` values on section outer wrappers to consume the token via a new utility class `.analysis-section-spacing { margin-bottom: var(--section-margin-bottom) }`. Each section component drops the inline style and adds the class to its outer `<div>`.
- **Document** the picker rule in the `:root` token block: when to use `--section-gap-y` (inside a section) vs `--section-margin-bottom` (between sections). Same forward-compatibility pattern PRs #252 and #254 established.
- **Skip** the per-component inline `marginBottom: '1rem' | '1.25rem' | '1.5rem'` values that appear inside section bodies — those are content-internal (heading-to-body, between paragraphs, etc.) and tokenizing them would require a bigger design call about the full vertical-rhythm system. Out of scope for this proposal.

## Capabilities

### New Capabilities

<!-- None. Token addition extends the existing analysis-detail-narrative capability surface. -->

### Modified Capabilities

- `analysis-detail-narrative`: extends with one new requirement governing section-to-section vertical spacing — every section wrapper on the analysis-detail page applies `--section-margin-bottom` via `.analysis-section-spacing`, and inline `marginBottom` for that purpose is forbidden.

## Impact

**Code:**

- `frontend/src/app/globals.css` — add `--section-margin-bottom: 2rem` to `:root` + new `.analysis-section-spacing` utility class. Update the documentation comment to explain the picker rule between the two section-spacing tokens.
- `frontend/src/components/RiskBreakdown.tsx` — replace `<div style={{ marginBottom: '2rem' }}>` with `<div className="analysis-section-spacing">`
- `frontend/src/components/OpportunitiesList.tsx` — same migration
- `frontend/src/components/ValueChainDiagram.tsx` — same migration
- `frontend/src/components/analysis/EbitdaSection.tsx` — same migration
- `frontend/src/components/DocumentUpload.tsx` — same migration
- `frontend/src/components/analysis/AnalysisHeader.tsx` — same migration (the page header IS a section in this layout)

**Surfaces affected:** every section on the analysis detail page success path.

**Data / APIs / dependencies:** none

**Out of scope (explicitly deferred):**

- **Inside-section margin tokens** — the `1rem` / `1.25rem` / `1.5rem` values that appear between paragraphs, between heading and lead, between cards in a grid, etc. These are content-internal vertical rhythm. A follow-up proposal could introduce `--content-gap-y` or similar, but tokenizing them now would require auditing 30+ inline values across the codebase.
- **Page-wide spacing tokens** beyond the analysis-detail page. AnalysesTable, ComparisonView, ScanProgressPhase, etc. have their own spacing patterns; they migrate separately when each surface gets its own audit.
- **Top margins** — sections use `marginBottom` consistently; switching to `gap` on a parent flex column would be the more modern approach but is a bigger refactor (each section's parent is `<>` fragment in `AnalysisDetail.tsx`, no flex container today). Token migration first; layout-system migration later.
- **`AnalysisExecutiveStrap`'s `1.25rem` bottom margin** — intentionally tighter than the standard 2rem because the strap visually pairs with the OverviewCards beneath it. Stays at 1.25rem; documented as intentional in the strap's existing JSDoc.

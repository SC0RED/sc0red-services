## Context

The `redesign-analysis-detail-narrative` change (PR #250, merged as `155b00d`) introduced an inline page-level `Section` helper inside `AnalysisDetail.tsx`:

```tsx
function Section({ id, children }: { id: string; children: ReactNode }) {
    return <div data-testid={`analysis-section-${id}`}>{children}</div>
}
```

That helper was deliberately minimal — its job at the time was to give order tests a stable handle without churning every component's internal testid. The PR shipped with the "Improve This Analysis" heading + lead paragraph rendered inline at the page level inside one of those wrappers:

```tsx
<Section id="document-upload">
    <h2 className="section-header">Improve This Analysis</h2>
    <p style={{ ... }}>Upload financial statements, ...</p>
    <DocumentUpload ... />
</Section>
```

That worked for one section but obviously doesn't scale. Every other section currently renders its heading INSIDE its own component, with three different visual treatments:

| Component | Heading style | Notes |
|---|---|---|
| RiskBreakdown | `<h2 className="section-header">Risk Breakdown</h2>` | canonical |
| EbitdaSection | `<h2 className="section-header">EBITDA Impact Model</h2>` + `<HelpTooltip>` | canonical |
| ValueChainDiagram | uses `section-header` class | canonical |
| ValueLeverSummary | `<h2 style={{ fontSize: '1.125rem', fontWeight: 700, marginBottom: '1rem' }}>` + `<HelpTooltip>` | inline-styled, visually identical to canonical |
| OpportunitiesList | `<h2 style={{ fontSize: '1.125rem', fontWeight: 700 }}>AI Opportunities ({n})</h2>` + `<HelpTooltip>` | inline-styled, sits in a flex-row with category chips on the right |
| TopActionsCallout | `<span style={{...}}>Top 3 Immediate Actions</span>` | not a real heading element — pseudo-heading inside a callout card |
| AnalysisHeader | `<h1>` for company name | NOT a section heading — the page heading. Skip. |
| AnalysisExecutiveStrap | no heading | one-line text band |
| AnalysisOverviewCards | inline tracking-wide labels ("Overall AI Risk Score", "Risk Dimensions") | card-internal labels, not a section heading |
| StrategyMapView | "STRATEGY MAP" uppercase blue tracking-wide treatment | INTENTIONAL — marquee artifact gets a marquee header |
| DeepDiveCTA | `<h3>Want a deeper analysis?</h3>` | CTA card heading, not a section heading |
| Sc0redCTABanner | internal CTA-card heading | similar to DeepDiveCTA — CTA, not section |

Three different visual shapes for "this is the start of a section" makes the page read as a stack of independently-styled cards rather than one document. The reader's eye re-orients at every transition.

The `.section-header` CSS class is already defined in `app/globals.css`:

```css
.section-header {
    font-size: 1.125rem;
    font-weight: 700;
    margin-bottom: 1rem;
}
```

Two sections (ValueLever, Opportunities) duplicate this rule inline — that's pure DRY violation. The fix is straightforward.

## Goals / Non-Goals

**Goals:**

- One visual treatment for every page-level section heading. No inline duplication of `.section-header`'s rule.
- Page-level framing (testid + heading + lead) is owned by a single shared `AnalysisSection` component. Every section that needs framing uses it.
- Components own their *body*; the page owns their *framing*. The architectural split established for `DocumentUpload` in PR #250 generalises here.
- Existing component-internal testids (`strategy-map-view`, `strategy-map-cta`, `drop-zone`, `reanalyze-progress`, `ebitda-tree`, etc.) are preserved — zero churn for the tests that target them.

**Non-Goals:**

- Accordion-everywhere — interaction redesign, separate proposal.
- Empty-state handling for conditional sections — UX research task.
- Banded background colours per beat — visual layering on top of this; can come later.
- Migrating the `OpportunitiesList` flex-row category-chip strip into the wrapper — see D2 trade-off.
- Changing `StrategyMapView`'s marquee "STRATEGY MAP" header — intentional divergence.
- Changing `Sc0redCTABanner`, `DeepDiveCTA`, `TopActionsCallout`, `AnalysisOverviewCards`, `AnalysisExecutiveStrap`, `AnalysisHeader` — none are "sections with a heading-then-body" shape; each has its own framing reason. Documented as exempt.
- Any data, API, or analytics changes.
- Changing section *order* — governed by the merged `analysis-detail-narrative` spec.

## Decisions

### D1 — Component shape

```tsx
interface AnalysisSectionProps {
    /** Stable id for `data-testid="analysis-section-{id}"`. Required. */
    id: string
    /**
     * Optional section heading. Rendered as `<h2 className="section-header">`
     * when provided. Accepts `ReactNode` (not just string) so callers can
     * include adornments — e.g. `<HelpTooltip>` next to "EBITDA Impact Model"
     * or the count `({opportunities.length})` next to "AI Opportunities".
     */
    title?: ReactNode
    /**
     * Optional lead paragraph rendered below the heading. Used by sections
     * that need a one-sentence orienting line (e.g. "Improve This Analysis"
     * → "Upload financial statements, board decks, or product docs to refine
     * this analysis"). Omitted by default.
     */
    lead?: ReactNode
    /** Body content of the section. */
    children: ReactNode
}
```

**Why no `headerRight` slot for trailing content?** Considered, rejected. The only section that would use it is `OpportunitiesList` for the category-chip filter row. Adding the slot to support one caller bloats the API; the trade-off in D2 keeps OpportunitiesList's flex row intact and accepts that the `<h2>` migration there is partial.

**Why `ReactNode` for `title` and `lead` (not `string`)?** Several sections need adornments next to the heading — `<HelpTooltip>` (EBITDA, ValueLever), count badge (Opportunities). Forcing `string` would push callers into JSX-string-templating workarounds. `ReactNode` is the natural shape.

**Why render `<h2>` (not `<h3>`)?** Existing sections all use `<h2>`. Page heading is `<h1>` (company name in `AnalysisHeader`). Maintains the document outline.

### D2 — OpportunitiesList: hoist title only, leave chips in place

`OpportunitiesList`'s heading row is a flex container with `justifyContent: 'space-between'`:

```tsx
<div style={{display: 'flex', justifyContent: 'space-between', ... }}>
    <h2 style={{...}}>AI Opportunities ({count})<HelpTooltip /></h2>
    <CategoryFilterChips />
</div>
```

Two paths:

| Option | Pros | Cons |
|---|---|---|
| **A. Hoist whole flex row** to page level via a new `headerRight` slot | Title and chips visually paired in DOM | Bloats the wrapper API for one caller; widens the testable surface |
| **B. Hoist title alone**; chips stay in the component | Wrapper API stays minimal; one component (Opportunities) keeps its complexity | Title and chips visually decoupled in DOM (chips render below the title now, not aside it) |

**Pick: B.** The category chips are a *body* concern (filter the list) more than a *header* concern. Decoupling them from the title visually is acceptable — they read fine as "controls above the list" rather than "controls aside the title." If users complain, we add the `headerRight` slot in a follow-up; until then, the API is simpler.

Implementation in OpportunitiesList: remove the heading + the flex `<div>` that wrapped it; the chips become a top-of-body row. The `<h2>AI Opportunities ({count})</h2>` is hoisted to the page-level `<AnalysisSection title={<>AI Opportunities ({count})<HelpTooltip term="impact_rating" /></>}>`.

### D3 — Migration scope per section

| Section | Before | After |
|---|---|---|
| `RiskBreakdown` | `<h2 className="section-header">Risk Breakdown</h2>` inside | headerless; page wraps with `<AnalysisSection id="risk-breakdown" title="Risk Breakdown">` |
| `EbitdaSection` | `<h2 className="section-header">EBITDA Impact Model<HelpTooltip /></h2>` inside | headerless; page wraps with `<AnalysisSection id="ebitda" title={<>EBITDA Impact Model<HelpTooltip term="ebitda_tree" /></>}>` |
| `ValueChainDiagram` | internal section heading | headerless; page wraps with `<AnalysisSection id="value-chain" title="Value Chain Analysis">` |
| `ValueLeverSummary` | inline `<h2 style={{...}}>Value Impact<HelpTooltip /></h2>` | headerless; page wraps `<AnalysisSection id="value-lever" title={<>Value Impact<HelpTooltip term="value_lever" /></>}>` |
| `OpportunitiesList` | inline `<h2>AI Opportunities ({n})<HelpTooltip /></h2>` inside flex row | partial — heading hoisted to page; category chips stay (D2). |
| `DocumentUpload` framing | inline `<h2 className="section-header">Improve This Analysis</h2>` + `<p>...</p>` at page level (PR #250) | use `<AnalysisSection id="document-upload" title="Improve This Analysis" lead="Upload financial statements, ...">` instead of the inline JSX |

Sections NOT migrated (each with explicit rationale captured in code comments):

- `StrategyMapView` — marquee artifact, intentional divergent header
- `Sc0redCTABanner` — CTA card, internal framing is part of its identity
- `DeepDiveCTA` — CTA card, same
- `TopActionsCallout` — callout card with pseudo-heading (`<span>Top 3 Immediate Actions</span>`); this is a stylized callout, not a sectioned region
- `AnalysisOverviewCards` — paired card row (score + radar), no section heading by design
- `AnalysisExecutiveStrap` — one-line transcribable summary, no heading by design
- `AnalysisHeader` — page heading, not a section

### D4 — Do not delete the `.section-header` CSS class

The class stays in `app/globals.css`. The new `AnalysisSection` component renders `<h2 className="section-header">` internally — same rule, single source. If we ever swap the visual treatment, we change one CSS rule and one React component.

Alternative considered: inline the styles into the React component, delete the CSS class. Rejected — keeping the styles in CSS lets print stylesheets, future themes, and any non-component renderers (e.g. PDF print path) reuse the same look without importing the React component.

### D5 — Test coverage strategy

1. **`AnalysisSection.test.tsx`** (new) — renders with no title, with title only, with title + lead, with ReactNode title (verify adornments render), and asserts the testid attribute is `analysis-section-{id}`.
2. **`AnalysisDetail.test.tsx`** (existing, augmented) — assert the page-level wrappers carry the correct titles for the migrated sections (one assertion per migrated section that the page renders the expected `<h2>` text). The existing 13-section order test stays as-is (testids unchanged).
3. **Each migrated component's existing tests** — relax assertions that targeted the now-removed internal heading. Specifically: `EbitdaSection.test.tsx` expects "EBITDA Impact Model" inside `EbitdaSection`'s render; that assertion moves to the AnalysisDetail level. Same pattern for the other components.

**Why not snapshot tests?** Snapshot tests would over-couple to JSX shape. The targeted text-presence + testid-presence approach is more robust to future style refactors.

### D6 — Sequencing of file edits

Order matters because tests run between phases:

1. Create `AnalysisSection` component + its tests (component renders fine in isolation)
2. Create `AnalysisDetail` integration but keep the OLD per-component headings → both old and new render together (duplicate headings briefly, but tests pass)
3. Migrate component-by-component, removing the internal heading and updating the component's tests. Each removal is a small atomic commit candidate.
4. Final pass: remove the inline `Section` helper from `AnalysisDetail.tsx` (replaced by `AnalysisSection`).
5. Run full test suite + lint + typecheck.

Skipping step 2 (going directly from inline-heading to wrapper-only) means tests fail mid-migration. Doing it in this order keeps every commit green if we want to land this in multiple PRs.

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| Migration touches 6+ component files; risk of missing a test assertion that targeted an internal heading | D6 sequencing — each component migration is independent, and the existing `npm test` suite catches missed assertions. |
| `OpportunitiesList`'s split (title hoisted, chips stay) creates a visually orphaned chip row | Accept per D2; revisit if the chip row reads poorly in the deployed dev build. Adding `headerRight` later is a 5-line wrapper API extension. |
| `<HelpTooltip>` adornments render fine inside `<h2>` today; need to verify they still render fine when the title is a ReactNode passed via prop | Covered by `AnalysisSection.test.tsx`'s ReactNode-title test case. |
| Future contributor adds a section with an inline `<h2 style={{...}}>` heading, missing the new pattern | Add a comment to `AnalysisSection.tsx` JSDoc explicitly stating "all section-level headings on the analysis detail page render through this component" — and the new requirement in the spec delta makes this enforceable in review. |
| `.section-header` CSS class no longer used by any direct caller (only by the new component) and may look like dead CSS | It's still actively used (by the component); leave a comment in `globals.css` noting "consumed by `AnalysisSection.tsx`". |
| File budget: `AnalysisDetail.tsx` already at 246 lines + the migration adds inline JSX adornments (HelpTooltip imports, ReactNode titles) | Each migrated section adds ~3 lines (title prop with adornment) and removes 0 (the `<Section id>` wrapper stays — just gets more props). Estimate: 246 → ~280 lines, well under the 360 cap. |

## Migration Plan

Frontend-only, presentation-only. No data migration, no feature flag, no staged rollout.

1. PR merges to `development`.
2. Amplify auto-deploys.
3. Manual sniff test: scan vertically down a full-data analysis — every section heading should look identical (font, weight, size, spacing, color). The exempt sections (Strategy Map, CTAs) should look intentionally different — confirm they don't read as "broken."

**Rollback:** `git revert` of the merge commit. No data implications.

## Resolved Questions

- **`headerRight` slot on `AnalysisSection`?** → **NO for v1.** D2's partial-migration of OpportunitiesList (title hoisted, chips become a row below) ships as-is. Revisit only if the decoupled chip row reads poorly on dev. The fallback plan (5-line API extension) is documented in the risks table.
- **Migrate `TopActionsCallout`'s pseudo-heading?** → **NO.** It's a stylized callout card with intentional differentiation, not a sectioned region. Stays exempt.
- **Tooltip-prop sugar (e.g., `helpTerm="ebitda_tree"` on the wrapper)?** → **Deferred to follow-up.** This proposal is already wide; tooltip-prop API is a separate API-design call that doesn't block the framing consistency win.

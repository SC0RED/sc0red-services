## Why

The `redesign-analysis-detail-narrative` change (PR #250) shipped the right beat ordering and a clean page-level `<Section>` wrapper for testids — but it did NOT address the sibling concern the user originally flagged: visual inconsistency between section headings. Today the analysis detail page renders section titles in three different ways:

1. `<h2 className="section-header">` (RiskBreakdown, EbitdaSection, ValueChainDiagram, page-level DocumentUpload framing) — the canonical CSS-class pattern
2. `<h2 style={{ fontSize: '1.125rem', fontWeight: 700, marginBottom: '1rem' }}>` (ValueLeverSummary, OpportunitiesList) — inline styles that DUPLICATE the `.section-header` rule verbatim
3. Pseudo-headings inside flex containers without a real heading element (TopActionsCallout's `<span>` styled as a title, AnalysisOverviewCards' uppercase tracking-wide labels)

The PR #250 code-review automation flagged this directly: *"the `<h2 class='section-header'>` + lead-paragraph pattern recurs across multiple sections … a `<SectionFraming heading='...' lead='...'>` component would dedupe and make the framing consistent across the page."* The page-level inline `<Section>` helper introduced in PR #250 was the right shape but the wrong scope — it only carries the testid, not the visual framing.

The reader-facing cost: scanning down the page, the eye re-orients at each section because the heading shape differs. With a single visual treatment, the page reads as one document; without, it reads as a stack of independently-styled cards.

## What Changes

- **Add** an `AnalysisSection` component at `frontend/src/components/analysis/AnalysisSection.tsx`. It owns three concerns in one wrapper: (1) the page-level testid (`data-testid="analysis-section-{id}"`), (2) the optional heading (rendered as `<h2 className="section-header">`), and (3) the optional lead paragraph below the heading. Children render inside the section.
- **Replace** the inline `Section` helper currently defined inside `AnalysisDetail.tsx` with the new component (`Section` was a deliberately minimal placeholder; promoting it to a named export with framing slots is the natural evolution).
- **Migrate** the page-level "Improve This Analysis" framing for DocumentUpload (currently inline `<h2>` + `<p>` in `AnalysisDetail.tsx`) into props on the new component.
- **Migrate** sections that already use `<h2 className="section-header">` internally to render headerless and have the page wrap them with `AnalysisSection title="..."`. Affected: `EbitdaSection`, `ValueChainDiagram`, `RiskBreakdown`. The CSS class `.section-header` is preserved (still used by the new component); only the *location* of the `<h2>` moves.
- **Migrate** sections with inline-styled equivalents (`ValueLeverSummary`, `OpportunitiesList`) the same way — strip the inline `<h2 style={{...}}>` from the component, hoist title to the page-level `AnalysisSection`. The `<HelpTooltip>` + count adornments that currently sit next to those headings move with the heading (the `title` prop accepts `ReactNode`, not just string).
- **Document** in the new component's JSDoc that `StrategyMapView`'s "STRATEGY MAP" uppercase-blue treatment is an *intentional* divergence — it's the page's marquee artifact and gets a marquee header. Not migrated. (Same rationale: `Sc0redCTABanner` is a CTA card with its own internal styling, not a section in the page-level grid; left alone.)
- **No changes** to: section *order* (governed by `analysis-detail-narrative`), conditional-rendering logic, accordion behaviour, or any data shape.

## Capabilities

### New Capabilities

<!-- None. This is a pure-presentation refactor that preserves the contracts of the existing `analysis-detail-narrative` capability. -->

### Modified Capabilities

- `analysis-detail-narrative`: the requirement that "each top-level section is wrapped at the page level by an element carrying a stable `data-testid` of the form `analysis-section-{name}`" is preserved verbatim. A new requirement is added: when a section has a title, that title SHALL be rendered at the page level via the shared `AnalysisSection` wrapper using the `.section-header` CSS class (or its componentised equivalent). Specific sections explicitly exempt from this rule are listed (StrategyMapView, Sc0redCTABanner, AnalysisHeader, AnalysisExecutiveStrap, AnalysisOverviewCards, TopActionsCallout, DeepDiveCTA — each documented with rationale).

## Impact

**Code:**
- `frontend/src/components/analysis/AnalysisSection.tsx` — NEW component
- `frontend/src/app/(authenticated)/analysis/[analysisId]/AnalysisDetail.tsx` — replace inline `Section` helper, move "Improve This Analysis" framing to props
- `frontend/src/components/analysis/EbitdaSection.tsx` — remove internal `<h2 className="section-header">EBITDA Impact Model</h2>` + the adjacent `<HelpTooltip>` (hoisted to page)
- `frontend/src/components/RiskBreakdown.tsx` — remove internal `<h2>Risk Breakdown</h2>`
- `frontend/src/components/ValueChainDiagram.tsx` — remove internal section heading
- `frontend/src/components/ValueLeverSummary.tsx` — remove internal `<h2 style={{...}}>Value Impact</h2>` + adjacent `<HelpTooltip>` (both hoisted)
- `frontend/src/components/OpportunitiesList.tsx` — remove internal `<h2>AI Opportunities ({n})</h2>` from its current flex-row context. **Caveat:** the OpportunitiesList heading row currently contains the category-filter chip strip on the right side via `justifyContent: 'space-between'`. Moving the title alone would orphan the chips. Either: (a) the wrapper grows a `headerRight` slot for trailing content, or (b) the chips stay in the component and the title alone moves up — design.md picks one. See D2.
- `frontend/src/tests/components/analysis/AnalysisSection.test.tsx` — NEW
- Each affected component's test file — assertions for the moved heading update (test the page-level rendering, not the component-internal heading)

**Surfaces affected:**
- Analysis detail page success path (every successful analysis)
- `FailedAnalysisView` is NOT affected (it composes `DocumentUpload` directly with its own `<h3>` heading; that's intentional per the previous PR's architecture-review fix)

**Data / APIs:** none

**Dependencies:** no new packages

**Out of scope (explicitly deferred to separate proposals):**
- Accordion-everywhere (uniform expand/collapse for long sections like RiskBreakdown / OpportunitiesList) — this is an interaction redesign, not a framing change. Tracked as a follow-up.
- Empty-state handling for conditional sections — when an analysis lacks an EBITDA tree, the section vanishes silently. A consistent "this analysis didn't produce X because Y" empty state is a UX research task, not a refactor.
- Banded background colours per beat (visually grouping Beats 1-6 with subtle background shifts) — useful but separable; can layer on top of this wrapper later.
- Migrating `OpportunitiesList`'s category-filter chip strip into the wrapper. The chips and the title currently share a flex row; design D2 picks the lower-risk option (chips stay).
- StrategyMap's marquee header treatment, Sc0redCTABanner's CTA framing — both are intentional divergences, documented but not changed.

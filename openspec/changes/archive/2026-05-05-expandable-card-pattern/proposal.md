## Why

UX review **Audit 2** flagged the most visible inconsistency on the analysis-detail page: the same fundamental "click-to-reveal-detail" interaction renders four different ways across the page.

| Surface | Current glyph | Implementation |
|---|---|---|
| Risk cards (×8) | none rendered | `<button aria-expanded>` inside `<div className="card">` |
| Opportunity cards (×5) | none rendered | same pattern |
| Value chain steps (×8) | none rendered | `<button className="card">` (button IS the card) |
| What's Missing? gaps (×4) | ▼ (down triangle) | `<button aria-expanded>` |
| Strategy Map disclosures | ▶ (right triangle) | native `<details>/<summary>` |

The risk / opportunity / value-chain cards have NO chevron at all — the entire card is clickable, but a reader scanning the page can't tell. The other two surfaces use different glyphs (▼ vs ▶), different motion, different positions. Same interaction, four visual treatments.

UX review's recommendation: one `ExpandableCard` component, one chevron position (top-right corner), one glyph rotating via CSS transform, one motion duration. Replace the button-pattern surfaces with it; leave `<details>` alone (native primitive works fine — only its chevron alignment needs CSS to match).

This proposal also absorbs the 3 button-card consumers explicitly deferred from `card-density-variants` (PR #254): RiskBreakdown, OpportunitiesList, ValueChainDiagram. Migrating them requires the canonical button-card primitive that ExpandableCard provides — they couldn't migrate to `card--list` alone because the inner button owned the padding and the variant would have stacked.

## What Changes

- **Add** `frontend/src/components/ui/ExpandableCard.tsx` — new component encapsulating the button-card-with-chevron pattern. Single chevron at top-right of the header row, one glyph (▼ rotating to ▲ on open, matching the convention WhatsMissingPanel established with the largest existing surface count). One motion duration. Built on `.card card--list` (the variant from PR #254 — now perfectly applicable since the variant + the migration ship together).
- **Component shape**: header content slot + revealed body slot. State can be uncontrolled (component owns `isOpen` via `useState`) OR controlled (parent passes `isOpen` + `onToggle` for accordion-style single-open coordination). All the existing surfaces use the controlled pattern (single-open accordion at parent level); the uncontrolled mode is for future independent-expand surfaces.
- **Migrate** 4 surfaces:
  - `RiskBreakdown.tsx` — 8 risk cards become `<ExpandableCard>` (controlled; parent owns `expandedRisk`)
  - `OpportunitiesList.tsx` — 5 opportunity cards become `<ExpandableCard>` (controlled; parent owns `expandedOpp`)
  - `ValueChainDiagram.tsx` — 8 value-chain steps become `<ExpandableCard>` (controlled; parent owns `expandedStep`). The button-IS-card pattern collapses naturally — ExpandableCard owns the button + card surface as one.
  - `WhatsMissingPanel.tsx` — 4 gap rows become `<ExpandableCard>` (controlled; parent owns `expandedGapId`)
- **Leave alone** `StrategyMapHeader.tsx` — it uses native `<details>/<summary>` with parent-controlled `open`, which is a different primitive (uses browser defaults + parent override). The UX review acknowledged this: "Native `<details>` is fine internally, but style its summary so the chevron position matches the cards." Chevron alignment between `<details>` and `ExpandableCard` is a CSS-only follow-up — explicit out-of-scope here.
- **Tests**: new `ExpandableCard.test.tsx` covers controlled + uncontrolled modes, aria contracts, chevron rotation. Existing tests for RiskBreakdown / OpportunitiesList / ValueChainDiagram / WhatsMissingPanel update to query the new component's accessible structure.
- **No backend changes.** No data, API, analytics, or component-contract changes beyond the migrated frontends.

## Capabilities

### New Capabilities

<!-- None. The new component lives within the analysis-detail-narrative capability surface. -->

### Modified Capabilities

- `analysis-detail-narrative`: extends with one new requirement governing the expandable-card pattern — every "click to reveal detail" surface on the analysis-detail page (excepting the StrategyMapHeader's `<details>`-based accordion) SHALL render through `ExpandableCard`, with one chevron position, one glyph, one motion duration.

## Impact

**Code:**

- `frontend/src/components/ui/ExpandableCard.tsx` — NEW (~120 lines)
- `frontend/src/components/RiskBreakdown.tsx` — replace per-card button + body pattern with `<ExpandableCard>`. Header content (score + name + tier badge) stays; body content (rationale) stays; the wrapping `<div className="card" overflow:hidden>` + `<button>` structure becomes `<ExpandableCard>`.
- `frontend/src/components/OpportunitiesList.tsx` — same migration pattern. Header content (title + impact + timeline + category badges) stays; body content (description + implementation steps + investment + ROI) stays.
- `frontend/src/components/ValueChainDiagram.tsx` — slightly more involved. Currently `<button className="card">` (button IS the card); becomes `<ExpandableCard>` where the component owns the button-card composition.
- `frontend/src/components/strategy-map/WhatsMissingPanel.tsx` — gap rows migrate to `<ExpandableCard>`. Single-open accordion semantics preserved (parent owns `expandedGapId`).
- New + updated tests for the 4 migrated components.

**Surfaces affected:**

- Analysis-detail page (Risk, Opportunities, Value Chain) + Strategy Map's What's Missing? panel.

**Data / APIs / dependencies:** none

**Out of scope (explicitly deferred):**

- StrategyMapHeader's `<details>/<summary>` accordion. UX review accepted this as a different primitive ("Native `<details>` is fine internally"); chevron alignment between `<details>` and `ExpandableCard` is a CSS-only follow-up not blocking this work.
- Section-spacing tokens (item C2 in the UX queue — separate proposal, will extend `--section-gap-y`).
- Re-using `ExpandableCard` outside the analysis-detail surface (other expandable rows in the codebase like AnalysesTable's filter rows). Variants are additive — those consumers can migrate later.
- Animation polish beyond a single rotation transform (e.g., body-height animation, fade-in). Locked to one motion duration via CSS transition; no animations beyond that until a user reports the snap as jarring.

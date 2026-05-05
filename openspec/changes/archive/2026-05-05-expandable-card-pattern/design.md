## Context

Four analysis-detail-page surfaces today implement the same "click-to-reveal-detail" pattern with four different visual treatments and slightly different DOM shapes. Per UX Audit 2:

```
RiskBreakdown:        outer .card → inner <button> → conditional body div. No chevron.
OpportunitiesList:    same shape. No chevron.
ValueChainDiagram:    <button className="card"> directly. No chevron.
WhatsMissingPanel:    outer wrapper → <button> with ▼ rotation → conditional body. ▼ glyph.
```

(StrategyMapHeader uses `<details>/<summary>` controlled by parent state — different primitive, not in scope per the UX review's own guidance.)

Three of these surfaces (`RiskBreakdown`, `OpportunitiesList`, `ValueChainDiagram`) were explicitly deferred from `card-density-variants` because the button-card pattern doesn't fit the `card--list` variant cleanly: the outer `.card` carries no padding (the inner button owns it), so adding `card--list` would stack two padding layers and regress visually. ExpandableCard is the canonical primitive that resolves both concerns at once: it owns the button + card composition, applies the right variant internally, and exposes a clean `header + body` API.

WhatsMissingPanel does NOT have the deferred-from-card-variants problem (it uses a wrapper div, not `.card`), but it shares the underlying interaction pattern. Migrating it in the same proposal closes the consistency gap UX Audit 2 flagged.

## Goals / Non-Goals

**Goals:**

- One `ExpandableCard` component, used everywhere the click-to-reveal-detail interaction appears on the analysis-detail page.
- One chevron position (top-right of the header row), one glyph (▼ rotating to ▲ on open), one motion duration (CSS transition matching the existing `0.2s ease` precedent).
- Controlled-state API for accordion-style coordination (parent owns "which one is open"); uncontrolled mode for independent-expand surfaces (none in current scope, but available).
- ARIA-correct: `aria-expanded` on the trigger button, `aria-controls` linking trigger to body, focus-visible ring on the trigger, body has a stable `id`.
- Visually consistent with the `.card card--list` variant from PR #254.
- Zero net regression in tests — existing assertions that target the leaf components' content continue to pass against the migrated structure.

**Non-Goals:**

- Migrating StrategyMapHeader's `<details>/<summary>` accordion. Different primitive; chevron alignment is a CSS-only follow-up.
- Animating the body's height during expand/collapse (would require measuring intrinsic height or `<details>`-style `:open` rules; locked to single rotation animation in v1).
- Replacing or rebuilding the components' header content layouts — header content is passed as `ReactNode`, callers keep their existing JSX.
- Adding more interaction modes (hover-preview, keyboard-only, etc.) beyond click/tap + Space/Enter (which `<button>` provides for free).
- Re-using `ExpandableCard` outside the analysis-detail surface in this PR.

## Decisions

### D1 — Component API

```tsx
interface ExpandableCardProps {
    /**
     * Stable id used for `aria-controls` on the trigger and `id`
     * on the body. Must be unique within the rendered page (the
     * component prepends `expandable-card-` to disambiguate).
     */
    id: string
    /** Header content rendered inside the trigger `<button>`. */
    header: ReactNode
    /** Body content revealed when expanded. */
    children: ReactNode
    /**
     * Controlled-mode flag. When provided alongside `onToggle`,
     * the parent owns the open state (used for accordion-style
     * coordination across siblings). When omitted, the component
     * owns its own state via `useState(false)`.
     */
    isOpen?: boolean
    /**
     * Controlled-mode toggle handler. When provided alongside
     * `isOpen`, called whenever the user clicks the trigger.
     * Receives no arguments — the parent computes the next open
     * state based on its own model (typical pattern: `setExpanded(prev => prev === id ? null : id)`).
     */
    onToggle?: () => void
    /**
     * Optional className applied to the wrapping `.card` element.
     * Use for caller-specific extras (`overflow: hidden` is already
     * applied internally; don't duplicate). Most callers don't need this.
     */
    className?: string
}
```

Controlled vs uncontrolled detection: if `isOpen !== undefined`, treat as controlled and call `onToggle` on click; else use internal state. Standard React pattern.

### D2 — DOM shape

```tsx
<div className={`card card--list ${className}`} style={{ overflow: 'hidden' }}>
    <button
        type="button"
        aria-expanded={isOpen}
        aria-controls={bodyId}
        onClick={handleClick}
        className="expandable-card-trigger"
    >
        <div className="expandable-card-header-content">{header}</div>
        <ChevronGlyph isOpen={isOpen} />
    </button>
    {isOpen && (
        <div id={bodyId} className="expandable-card-body">
            {children}
        </div>
    )}
</div>
```

The button is full-width inside the `.card` wrapper; the chevron sits at top-right of the header row via flex alignment. Body renders conditionally (`{isOpen && ...}`) — no display:none so the closed state has no DOM cost.

### D3 — Chevron glyph + animation

Inline SVG chevron pointing down by default. Rotates 180° via CSS transform when `isOpen`:

```css
.expandable-card-chevron {
    transition: transform 0.2s ease;
    color: var(--text-tertiary);
}
.expandable-card-chevron[data-open='true'] {
    transform: rotate(180deg);
}
```

`data-open` attribute on the chevron lets the CSS rule key off it without a class swap. Same `0.2s ease` timing as RiskBreakdown's existing chevron transition (the closest existing precedent). Honors `prefers-reduced-motion` via the global `globals.css` override (already in place).

### D4 — Card surface

Uses `.card card--list` from PR #254. The variant's locked padding (`0.75rem 1rem`) sits on the OUTER `.card`, NOT on the inner button — so the button gets `padding: 0` and the visual padding comes from the variant. This is the structural fix that the `card-density-variants` deferral teed up.

For the consumers that previously had the button absorbing padding (RiskBreakdown's `1rem 1.25rem`, OpportunitiesList's `1.25rem`), the new `0.75rem 1rem` is slightly tighter. Per the same design principle in `card-density-variants` D2 — "the variant is the new source of truth" — this is intentional standardization. Manual visual verification confirms acceptability.

### D5 — Migration shape per consumer

```tsx
// RiskBreakdown.tsx — Before
<div key={rs.category} className="card" style={{ overflow: 'hidden' }}>
    <button onClick={...} aria-expanded={isOpen} aria-controls={...} style={{ ... }}>
        {/* header content */}
        <ChevronSVG style={{ transform: isOpen ? 'rotate(180deg)' : 'none' }} />
    </button>
    {isOpen && <div id={...}>{rs.rationale}</div>}
</div>

// After
<ExpandableCard
    id={rs.category}
    isOpen={expandedRisk === rs.category}
    onToggle={() => setExpandedRisk(isOpen ? null : rs.category)}
    header={/* score + name + tier badge */}
>
    {rs.rationale && <p>{rs.rationale}</p>}
</ExpandableCard>
```

Same pattern for OpportunitiesList, ValueChainDiagram, WhatsMissingPanel. Each migration:
1. Replace the manual `<div className="card">` + `<button>` + chevron + conditional body with `<ExpandableCard>`
2. Move the header JSX into the `header` prop
3. Move the body JSX into `children`
4. Remove the inline-styled chevron SVG (ExpandableCard renders its own)
5. Remove the inline `aria-expanded` + `aria-controls` (component handles them)

### D6 — Test posture

New test file `frontend/src/tests/components/ui/ExpandableCard.test.tsx`:
- Uncontrolled mode: clicking the trigger toggles `aria-expanded`; body appears + disappears
- Controlled mode: `isOpen` prop drives the rendering; `onToggle` fires on click but parent decides whether to flip
- ARIA: `aria-expanded` on the button, `aria-controls` referencing the body's `id`
- Chevron rotation: `data-open` attribute reflects state
- Keyboard: Space + Enter trigger the toggle (free from `<button>`)

Existing tests for migrated components:
- `RiskBreakdown.test.tsx` — assertions querying the rationale text continue to work (the body still renders that text). Click handler now goes via `ExpandableCard`'s button, but tests query by role/text and don't care about the structural path.
- Same for OpportunitiesList, ValueChainDiagram, WhatsMissingPanel.

Updates only if a test asserts on the inline chevron SVG (those become regression-prone since the chevron now lives inside ExpandableCard, not the migrated component) — those assertions either delete or move to ExpandableCard's tests.

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| Migrated card padding is tighter than before (0.75rem 1rem vs RiskBreakdown's 1rem 1.25rem and OpportunitiesList's 1.25rem) | Same standardization principle as `card-density-variants` D2. Manual visual verification post-deploy. If any delta reads poorly, the option is to add a `card--list-loose` variant or expose a padding override prop on ExpandableCard — both small follow-up edits. |
| Controlled vs uncontrolled mode complexity | Detection is `isOpen !== undefined` — a single React idiom familiar to anyone who's worked with Material UI / Chakra / Radix. Tests cover both modes. JSDoc explains the rule. |
| `aria-controls` must reference an existing DOM id when the body renders conditionally | The body always has a stable id (set on the wrapping `<div>` even when closed... wait, the body only renders when open). Need to handle this — either render the body in DOM at all times with `hidden` attribute when closed (preserves aria-controls reference), or accept that aria-controls points at a non-existent id when closed (which is technically a violation but most screen readers handle it gracefully). Pick the first — render body always, hide via `hidden` attribute, so the `aria-controls` reference is always valid. |
| ValueChainDiagram's pre-existing structure used `<button className="card">` directly — migration changes the DOM tree shape (button no longer carries the .card class) | Existing tests for ValueChainDiagram query by text content + role, not by the `.card` className being on the button. Sample-checked before migration. |
| **ValueChainDiagram is a chain visualization, NOT a list of cards.** Discovered during apply: the cards have shared borders + arrow connectors + custom border-radius (0 for connected primary steps, normal for last/support). Migrating to ExpandableCard would replace the chain visual with a vertical list — visual regression. | **Knowingly deferred** to a separate proposal (`value-chain-step-redesign` or similar). The chain visual is correct for the data shape (Porter's value chain — sequential primary activities + parallel support activities); flattening it to a list would lose the structural metaphor. ExpandableCard is the right primitive for the OTHER 3 button-card consumers but not this one. Documented in spec deferred-exceptions section. |
| Single-open accordion semantics need parent to coordinate `expandedRisk`, `expandedOpp`, `expandedStep`, `expandedGapId` separately — no risk of a global "what's open" state, just per-component state survives the migration | Each parent already has the state today. Migration just plumbs the same state through `isOpen` + `onToggle` props. No new state machinery. |

## Migration Plan

Frontend-only, presentation-only.

1. PR merges to `development`
2. Amplify auto-deploys
3. Manual visual verification: load an analysis with full data; click each Risk / Opportunity / Value-chain / What's-Missing card; confirm consistent chevron rotation, body reveal, accordion semantics. Tab keyboard through; confirm focus order + space/enter work.

**Rollback:** `git revert` of the merge commit.

## Resolved Questions

- **Migrate StrategyMapHeader's `<details>`?** → **No.** Native primitive, controlled by parent, works fine. Chevron-alignment between the two primitives is a CSS-only follow-up.
- **One chevron glyph or per-surface customization?** → **One glyph (▼ rotating to ▲).** Matches WhatsMissingPanel's existing convention; UX review explicitly requested one glyph.
- **Controlled or uncontrolled API only?** → **Both.** Controlled is what current consumers use; uncontrolled is for future independent-expand surfaces (zero current callers but trivial to support).

## Open Questions

1. **Should the body render with `hidden` attribute when closed (always in DOM), or render conditionally (`{isOpen && ...}`)?** Recommend `hidden` attribute path so `aria-controls` always references a valid element. Tradeoff: closed-card DOM cost. For 8 risk cards × 5 opportunity cards × 8 value-chain steps × 4 gaps = 25 closed-card bodies in the DOM at once. Each body's content is small (a paragraph + maybe a list); negligible. Pick `hidden` attribute path.
2. **CSS class names: `.expandable-card-*` BEM-style or plain modifier classes?** Matching the established pattern from `card-density-variants` (`.card.card--list`), use `.expandable-card` base + `.expandable-card__trigger` / `.expandable-card__chevron` / `.expandable-card__body` (BEM element notation with `__`). Defer final naming to implementation; document choice in the test file's coverage comment.

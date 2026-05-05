## ADDED Requirements

### Requirement: Click-to-reveal-detail surfaces use the shared ExpandableCard component

Every "click-to-reveal-detail" interaction surface on the analysis-detail page SHALL render through a shared `ExpandableCard` component (`@/components/ui/ExpandableCard`), which encapsulates the button-card-with-chevron pattern. Specifically:

- `RiskBreakdown` per-risk cards (×8)
- `OpportunitiesList` per-opportunity cards (×5)

**Deferred exceptions** (different visual model, not just different padding):

1. **`ValueChainDiagram` per-step cards (×8)** — horizontal Porter's-value-chain visualization with shared borders, arrow connectors between primary activities, and custom border-radius rules (0 for connected steps, normal for last/support). Migrating to ExpandableCard would replace the chain visual with a vertical list and lose the structural metaphor of sequential primary + parallel support activities. Deferred to a future `value-chain-step-redesign` proposal.

2. **`WhatsMissingPanel` per-gap rows (×4)** — uses `bg-surface-2` + 3px accent-blue left border, NOT the `.card` glassmorphism surface. The accent-strip aesthetic is part of the gaps' visual identity ("here are deep-dive prompts, distinct from regular content"). Migrating to ExpandableCard's `.card.card--list` surface would replace the accent-strip with a glass-card and dilute that identity. Same interaction pattern; different chrome. Deferred to a future `whats-missing-panel-style-alignment` proposal (or absorbed into the `value-chain-step-redesign` follow-up if scope allows).

The interaction pattern (single-open accordion via parent state, ▼ chevron, body reveal) is correct for both deferred consumers; only the visual model differs from `.card.card--list`.

The component SHALL:

- Wrap content in a `.card.card--list` surface (the `card-density-variants` variant from PR #254), with `overflow: hidden` to clip the rounded corners around the body reveal.
- Render exactly one chevron, positioned at the top-right of the header row, in a single glyph (▼ rotating to ▲ on open via CSS `transform: rotate(180deg)` keyed by a `data-open` attribute on the chevron element).
- Use a single motion duration (`0.2s ease`) for the chevron rotation, honoring `prefers-reduced-motion: reduce` via the existing global stylesheet rule.
- Expose ARIA-correct semantics: `aria-expanded` on the trigger `<button>`, `aria-controls` referencing the body's stable id, focus-visible ring on the trigger.
- Support both **controlled** mode (parent passes `isOpen` + `onToggle` for accordion coordination) and **uncontrolled** mode (component owns `useState(false)` internally). Detection is `isOpen !== undefined`.
- Always render the body in the DOM (`hidden` attribute when closed, not conditional rendering) so `aria-controls` always references a valid element.

The strategy-map header's `<details>/<summary>` accordion (`StrategyMapHeader`) is EXEMPT — it uses a different primitive (native `<details>` controlled by parent state) and is intentionally not migrated. Chevron-glyph alignment between `<details>` and `ExpandableCard` is a separate CSS-only follow-up not blocking this requirement.

The 3 button-card consumers previously deferred from `card-density-variants` (RiskBreakdown, OpportunitiesList, ValueChainDiagram) are migrated through `ExpandableCard` in this proposal, completing the card-density consistency rollout.

#### Scenario: Each migrated surface renders through ExpandableCard

- **WHEN** the analysis-detail page renders with full data
- **THEN** every Risk card, Opportunity card, Value-chain step, and What's-Missing gap is rendered as an `ExpandableCard` component (importable from `@/components/ui/ExpandableCard`)
- **AND** none of those surfaces renders an inline `<button aria-expanded>` + chevron pattern outside of `ExpandableCard`'s internals

#### Scenario: Single chevron glyph + position across all migrated surfaces

- **WHEN** any of the migrated cards is rendered (open or closed)
- **THEN** exactly one chevron renders, positioned at the top-right of the header row
- **AND** the chevron is the same SVG element across all migrated surfaces (rendered by `ExpandableCard`'s internal `Chevron` element, not per-consumer inline SVGs)
- **AND** the chevron rotates 180° via CSS transform when the card is in the open state, with `0.2s ease` transition

#### Scenario: Controlled mode coordinates accordion semantics

- **WHEN** an `ExpandableCard` is rendered with both `isOpen={...}` and `onToggle={...}` props
- **THEN** the component uses the parent's `isOpen` value as the source of truth (does NOT manage its own state)
- **AND** clicking the trigger calls `onToggle()` exactly once (parent decides the next state)
- **AND** keyboard activation (Space, Enter) on the trigger has the same effect

#### Scenario: Uncontrolled mode for independent-expand callers

- **WHEN** an `ExpandableCard` is rendered without `isOpen` (or with `isOpen={undefined}`)
- **THEN** the component manages its own open/closed state via `useState(false)`
- **AND** clicking the trigger toggles the internal state — no parent coordination required

#### Scenario: ARIA-correct trigger + body relationship

- **WHEN** an `ExpandableCard` is rendered in any state
- **THEN** the trigger `<button>` has `aria-expanded` set to the current open state (`"true"` or `"false"`)
- **AND** the trigger has `aria-controls` referencing the body's `id`
- **AND** the body element with the matching `id` exists in the DOM regardless of open state (closed cards use the `hidden` HTML attribute, not conditional rendering, so the aria-controls reference is always valid)

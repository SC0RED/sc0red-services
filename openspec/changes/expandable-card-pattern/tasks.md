## 1. ExpandableCard component

- [ ] 1.1 Create `frontend/src/components/ui/ExpandableCard.tsx` per design D1+D2. Props: `{ id, header, children, isOpen?, onToggle?, className? }`. Renders `.card card--list` outer + button trigger with `aria-expanded` + `aria-controls` + chevron at top-right + body with stable `id` always in DOM (`hidden` attribute when closed). Component under 130 lines.
- [ ] 1.2 Add CSS rules to `globals.css` for the chevron rotation (`.expandable-card-chevron[data-open='true'] { transform: rotate(180deg) }`), trigger button reset (no border, transparent background, full width, padding 0 to let `.card--list` own the visual padding), body styling. Use BEM-style class names `.expandable-card`, `.expandable-card__trigger`, `.expandable-card__chevron`, `.expandable-card__body`.
- [ ] 1.3 Create `frontend/src/tests/components/ui/ExpandableCard.test.tsx`. Cases:
  - Uncontrolled mode: clicking the trigger toggles aria-expanded
  - Controlled mode with `isOpen={false}` + `onToggle`: trigger click calls onToggle exactly once but doesn't flip state until parent decides
  - Controlled mode with `isOpen={true}`: body is visible
  - ARIA: `aria-expanded` matches state; `aria-controls` references body's `id`; body always present in DOM with `hidden` attribute when closed
  - Chevron: `data-open` attribute reflects state
  - Keyboard: Space + Enter trigger toggle (free from `<button>`, just verify)
  - Header content: passed `header` prop renders inside the trigger button
  - Body content: passed children render inside the body element

## 2. Migrate RiskBreakdown

- [ ] 2.1 In `RiskBreakdown.tsx`, replace the per-card `<div className="card">` + manual `<button aria-expanded>` + body block with `<ExpandableCard id={rs.category} isOpen={expandedRisk === rs.category} onToggle={() => setExpandedRisk(isOpen ? null : rs.category)} header={...}>`. Move score+name+badge JSX into the `header` prop. Move rationale JSX into children. Remove the inline chevron SVG.
- [ ] 2.2 Update `RiskBreakdown.test.tsx` if any assertion targeted the inline chevron — those become regression-prone. Delete or move to ExpandableCard's test. Existing assertions on rationale text continue to pass.

## 3. Migrate OpportunitiesList

- [ ] 3.1 Same migration pattern. `id={opp.title}` (or stable identifier), `isOpen={expandedOpp === opp.title}`, `onToggle={() => setExpandedOpp(isOpen ? null : opp.title)}`. Header = title + impact badge + timeline badge + category badge + value-lever pill. Children = description + implementation steps + investment + ROI grid.
- [ ] 3.2 Update tests accordingly.

## 4. ~~Migrate ValueChainDiagram~~ — DEFERRED

- [ ] 4.1 ~~ValueChainDiagram migration~~ — **DEFERRED to a future `value-chain-step-redesign` proposal**. Discovered during apply: the value-chain steps form a horizontal Porter's-value-chain visualization (shared borders + arrow connectors + custom border-radius rules), not a vertical list. Migrating to ExpandableCard would replace the chain visual with a list and lose the sequential-primary + parallel-support structural metaphor. Same interaction (click-to-reveal); fundamentally different visual model. See design D6 / spec deferred-exceptions section.
- [ ] 4.2 ~~Update tests~~ — DEFERRED with the migration.

## 5. ~~Migrate WhatsMissingPanel~~ — DEFERRED

- [ ] 5.1 ~~WhatsMissingPanel migration~~ — **DEFERRED to a future style-alignment proposal**. Discovered during apply: the GapRow uses `bg-surface-2` + 3px accent-blue left border, NOT the `.card` glassmorphism surface. Migrating to ExpandableCard's `.card.card--list` would replace the accent-strip aesthetic (which is part of the gaps' visual identity as "deep-dive prompts, distinct from regular content") with a glass-card. Same interaction; different chrome. See spec deferred-exceptions section.
- [ ] 5.2 ~~Update tests~~ — DEFERRED with the migration.

## 6. Verification

- [ ] 6.1 `cd frontend && npm run lint`
- [ ] 6.2 `cd frontend && npx tsc --noEmit`
- [ ] 6.3 `cd frontend && npm test` — all tests pass
- [ ] 6.4 Grep the codebase for any remaining manual `<button aria-expanded>` + chevron pattern within `components/RiskBreakdown.tsx`, `OpportunitiesList.tsx`, `ValueChainDiagram.tsx`, `strategy-map/WhatsMissingPanel.tsx`. Confirm zero remain.
- [ ] 6.5 (deferred — manual) Visually verify on local dev or after deploy: load an analysis with full data; click each migrated card type; confirm chevron rotates uniformly, body reveals + collapses, accordion semantics work (only one open at a time per surface). Tab keyboard through; confirm focus order and Space/Enter activation.

## 7. Architecture review + commit + PR

- [ ] 7.1 Run the `architecture-reviewer` agent over the diff. Focus areas: (a) ExpandableCard prop API completeness (controlled/uncontrolled detection, no unused props), (b) ARIA semantics (aria-expanded on button, aria-controls referencing valid body id, body always in DOM), (c) chevron rotation CSS specificity (no inline styles competing), (d) all 4 migrations consistent, (e) any tests asserting on chevron SVG or button structure that need updating.
- [ ] 7.2 Commit with conventional-commit message: `feat(analysis): introduce ExpandableCard for click-to-reveal-detail surfaces`
- [ ] 7.3 Open PR against `development`. Body should reference UX review Audit 2, list the 4 migrated surfaces, explicitly note StrategyMapHeader's `<details>` is intentionally NOT migrated (different primitive), call out the 3-button-card-deferral closure from PR #254, and the manual visual + keyboard verification gates.

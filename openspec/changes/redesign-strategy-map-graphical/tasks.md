## 1. Layout helper (pure functions, fully unit-testable)

- [x] 1.1 Create `frontend/src/lib/strategyMap/layout.ts` exporting a single `buildStrategyMapGraph(strategyMap: StrategyMap): { nodes: Node[]; edges: Edge[] }` function typed against `@xyflow/react`. No React imports.
- [x] 1.2 Implement column-assignment algorithm "α′" inside `layout.ts`: (a) Financial chips use `theme.supports_financial_objectives`; (b) Internal-Process chips use enclosing theme index; (c) Customer chips follow outbound arrows to Financial, fall back to inbound arrows from Internal, fall back to centre lane; (d) Capacity chips follow outbound arrows to Internal, fall back to centre lane.
- [x] 1.3 Implement arrow validation: drop edges whose `from` or `to` references an objective ID not in the assembled chip set. `console.warn` in development only (gated on `process.env.NODE_ENV !== 'production'`).
- [x] 1.4 Implement `(x, y)` coordinate computation: row index = perspective band (0 Financial → 3 Capacity); column index = theme column from step 1.2; convert to pixels with constant band height + column width.
- [x] 1.5 Add unit tests at `frontend/src/tests/lib/strategyMap/layout.test.ts` covering: deterministic Financial placement; inferred Customer placement via outbound arrow; centre-lane fallback for unconnected Customer; centre-lane fallback for unconnected Capacity; arrow with unknown `from` is dropped (with warn-suppression); arrow with unknown `to` is dropped; multi-theme layout (3 priorities, full chip set); single-theme layout (1 priority, all chips in one column).

## 2. React Flow custom node (`StrategyMapNode`)

- [x] 2.1 Create `frontend/src/components/strategy-map/StrategyMapNode.tsx`. Mirror the structure of `EbitdaNodeComponent.tsx`: `useState<boolean>(false)` for `hovered`, `onMouseEnter` / `onMouseLeave`, conditional tooltip rendered absolutely-positioned beneath the chip when hovered or focused.
- [x] 2.2 Default chip content: ID (mono font, small), single-line title with `text-overflow: ellipsis`, 8 px circular confidence dot using the existing `--risk-low` / `--risk-moderate` / `--risk-high` palette.
- [x] 2.3 Hover/focus tooltip content: full `definition` paragraph, the literal confidence label (`HIGH` / `MEDIUM` / `LOW` — reuse `ConfidenceChip`), `rationale_source` if non-null. Match EBITDA tooltip styling tokens (background, border, blur).
- [x] 2.4 Customer chips render the title wrapped in quotation marks (`"…"`) and italicised, matching the existing house-style.
- [x] 2.5 Add `role="button"` + `aria-label={`${id}: ${title}`}` on the node root for screen-reader compatibility.
- [x] 2.6 Component tests at `frontend/src/tests/components/strategy-map/StrategyMapNode.test.tsx`: default render shows ID + title + dot; hover surfaces tooltip with definition + confidence label; mouse-leave dismisses tooltip; HIGH/MEDIUM/LOW dot colour resolution; customer-voice formatting.

## 3. Edge tooltip (hypothesis popover)

- [x] 3.1 Implement an edge-hover popover using React Flow's `onEdgeMouseEnter` / `onEdgeMouseLeave` handlers in the parent canvas component (or a custom edge type if the simpler hook approach is cumbersome).
- [x] 3.2 The popover shows the arrow's `hypothesis` text, anchored near the cursor, dismissed on leave.
- [x] 3.3 Visual: low-opacity edges (so chips read as primary), full opacity on hover for the hovered edge, marker-end arrowhead.
- [x] 3.4 Component test: hovering an edge renders the popover with the hypothesis text; leaving dismisses it.

## 4. Strategy-map canvas composition

- [x] 4.1 Rewrite `frontend/src/components/strategy-map/StrategyMapView.tsx` to render: header band (vision + value-prop chip + mission `<details>` + strategic-priority column headers), then a React Flow canvas calling `buildStrategyMapGraph(strategyMap)`, then `WhatsMissingPanel`. No vertical card stacks remaining.
- [x] 4.2 Header — vision: italic single line, `white-space: nowrap; text-overflow: ellipsis`, `title={vision.statement}` for native browser tooltip on overflow (or hand-rolled tooltip for consistency with chip behaviour).
- [x] 4.3 Header — mission: native `<details>` element, summary `Mission ▾`, closed by default.
- [x] 4.4 Header — value-proposition chip: keep the existing chip (`Customer Intimacy` / `Operational Excellence` / `Hybrid (with …)`); attach `onMouseEnter` / `onMouseLeave` for a tooltip showing `valueProposition.rationale`.
- [x] 4.5 Header — strategic priorities: render priorities as column headers above the canvas, named after `priority.name`; tooltip on hover shows `priority.result`.
- [x] 4.6 Canvas configuration: `nodesDraggable={false}`, `nodesConnectable={false}`, `elementsSelectable={true}` (so tap-to-focus works on touch), `fitView` with reasonable padding, `panOnDrag` and `zoomOnPinch` enabled (mobile), `minZoom`/`maxZoom` bounds set so users can't zoom themselves into uselessness.
- [x] 4.7 Make `StrategyMapView.tsx` stay under the 360-line frontend component limit. Extract band-label / priority-header sub-components if needed.
- [x] 4.8 Delete or significantly trim `PerspectiveRow.tsx` (its responsibilities are absorbed by `layout.ts` + `StrategyMapNode.tsx`).
- [x] 4.9 `ObjectiveCard.tsx`: keep only if reused by the print path (it isn't — `PrintStrategyMapObjectives.tsx` uses its own `PrintObjectiveCard`). Delete `ObjectiveCard.tsx` after confirming no remaining imports.
- [x] 4.10 Component test for the rewritten `StrategyMapView.test.tsx`: canvas renders with chips for every objective in the fixture; arrows render as edges; vision rendered italic; mission `<details>` closed by default; value-prop chip present; strategic-priority headers visible.

## 5. Gaps panel — click to expand inline

- [x] 5.1 Update `frontend/src/components/strategy-map/WhatsMissingPanel.tsx`: render each gap as a button-row showing only `<id> · <title>` plus an expand chevron. Manage open state via `useState<string | null>(null)` (single-open accordion, mirrors `OpportunitiesList`).
- [x] 5.2 Add `aria-expanded`, `aria-controls`, and an `id` matching `aria-controls` on the detail region for screen-reader compatibility.
- [x] 5.3 Expanded state shows the full `description` paragraph and the italic `deepDiveFraming` sentence (existing render content; just gated behind the open state).
- [x] 5.4 Update `frontend/src/tests/components/strategy-map/WhatsMissingPanel.test.tsx` to cover: collapsed-by-default, click expands, click another collapses the previous, `aria-expanded` toggles correctly.

## 6. CTA relocation

- [x] 6.1 Edit `frontend/src/components/AnalysisDetail.tsx` — remove the existing `<DeepDiveCTA … variant="headline" />` rendering below the strategy map; render it instead immediately under the analysis header action buttons (export PDF, delete).
- [x] 6.2 Confirm `DeepDiveCTA.tsx` itself does NOT need code changes — the analytics emit semantics carry over (`_rendered_strategy_map` still fires on mount; `_clicked_strategy_map` on click).
- [x] 6.3 Visual review: ensure the relocated CTA visually distinguishes from neighbouring action buttons (it's a coloured banner CTA, not a button — there should be no confusion).
- [x] 6.4 Update or extend the existing CTA tests if any assert positional context relative to the strategy-map section. Add a smoke test: on a mount with a populated `strategyMap`, the headline CTA renders ABOVE the `StrategyMapView` in the DOM tree.

## 7. Cleanup

- [x] 7.1 Delete `frontend/src/components/strategy-map/PerspectiveRow.tsx` after confirming all imports have been removed.
- [x] 7.2 Delete `frontend/src/components/strategy-map/ObjectiveCard.tsx` after confirming all imports have been removed.
- [x] 7.3 Update the strategy-map barrel export `frontend/src/components/strategy-map/index.ts` — remove deleted exports, add `StrategyMapNode`.
- [x] 7.4 Delete `frontend/src/tests/components/strategy-map/PerspectiveRow.test.tsx` and `ObjectiveCard.test.tsx` (replaced by `StrategyMapView.test.tsx` + `StrategyMapNode.test.tsx`).
- [x] 7.5 Update fixture `frontend/src/tests/components/strategy-map/_fixtures.ts` if any field shape relied on the deleted helpers.

## 8. Cross-cutting verification

- [x] 8.1 Run `cd frontend && npm run lint` — fix any new errors from the redesign.
- [x] 8.2 Run `cd frontend && npx tsc --noEmit` — fix any type errors from the new `Node` / `Edge` shapes.
- [x] 8.3 Run `cd frontend && npm test -- --run` — all tests pass; new component + layout tests covered. Frontend test count ≥ existing baseline (818) — replacing some, adding others.
- [x] 8.4 Run `python3 backend/scripts/check_analytics_type_parity.py` — clean (no analytics surface changes; this is a regression guard).
- [x] 8.5 Run `bash scripts/audit.sh` — clean.
- [ ] 8.6 Manually verify on three representative analyses (sparse-data, mid-size, deep arrow set): canvas renders within ≤ ~700 px, gaps panel + CTA above the fold on a 1,080 px viewport, no chip text clipped beyond the truncate-on-purpose case.
- [ ] 8.7 Manually verify on a 390 px-wide mobile viewport (simulated iPhone 12 in browser dev tools): canvas pans/zooms via touch; tap on a chip surfaces tooltip; tap on a gap row expands.
- [ ] 8.8 Manually verify the PDF export still renders the verbose layout (the print path is unchanged but worth a paranoid eyeball).
- [ ] 8.9 Visual regression: regenerate any snapshot tests that captured the old vertical-stack rendering. Document the snapshot diff in the PR body for reviewer eyeball.

## 9. Architecture review + commit

- [x] 9.1 Run the `architecture-reviewer` agent on the diff (touches 5+ frontend files; rewrites a major component; per CLAUDE.md the gate is mandatory).
- [x] 9.2 Resolve all CRITICAL findings; address or explicitly defer MEDIUM findings with user approval.
- [ ] 9.3 Write the commit message — conventional commit `feat(strategy-map): graphical 2D canvas redesign`. Body summarises: layout helper, custom node, gaps accordion, CTA relocation; calls out that print is untouched and backend/schema unchanged.
- [ ] 9.4 Open the PR against `development`. Body: paste the proposal's "What Changes" + a screenshot of the new layout (before/after) + the verification checklist results.

## 10. Post-merge follow-ups (out of this change's scope, captured for tracking)

- [ ] 10.1 (Future, separate proposal) `β` — add a `theme` field to `FinancialObjective`, `CustomerObjective`, `CapacityObjective`. AI prompts updated. Layout helper switches from arrow inference to deterministic theme lookup. Verifiable by the same `layout.test.ts` cases (centre-lane fallback should disappear).
- [ ] 10.2 (Future, separate proposal) `IntersectionObserver`-based impression event so `_rendered_strategy_map` fires only when the strategy-map section scrolls into view. Currently fires on AnalysisDetail mount.
- [ ] 10.3 (Future, separate proposal) Per-gap inline `DeepDiveCTA` (the inline variant exists but isn't rendered) — extends `WebEventContext` with `gapId` and adds it to the analytics payload.

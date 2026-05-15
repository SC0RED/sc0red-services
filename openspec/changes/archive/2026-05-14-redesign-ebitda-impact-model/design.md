## Context

``EbitdaTree.tsx`` (285 lines) renders an ``EbitdaTreeResult`` via ``@xyflow/react`` + ``@dagrejs/dagre``. The data carries 5 top-level sibling nodes with no edges between them — the subtotal arithmetic (Revenue − COGS = Gross Profit, etc.) is implicit, not modelled. Dagre lays each top-level node as its own mini-tree, producing a horizontal forest that:

- Forces ~30 % default zoom to fit five parents across the viewport width.
- Leaves ~50 % of the 700 px container empty (only 2 vertical ranks of nodes inside a tall canvas).
- Surfaces zoom + pan controls (``Fit`` / ``Expand`` / +/−) that exist to fight a layout problem, not to enable any genuine exploration.
- Hides the financial flow — there are no arrows from Revenue to COGS to Gross Profit etc.

The data is fundamentally a 5-row linear chain (a P&L statement). A graph library is over-tooled for it. ``PrintEbitdaOutline.tsx`` already renders the same data as a static vertical layout for PDF export, with no complaints — that proves the static treatment carries the story.

## Goals / Non-Goals

**Goals:**

- Render the EBITDA Impact Model at the correct visual size by default — no zoom interaction needed to read it.
- Eliminate the top/bottom whitespace by sizing the container to the content.
- Make the financial flow visible: Revenue → minus → COGS → equals → Gross Profit → minus → OpEx → equals → EBITDA, top-to-bottom.
- Preserve every functional affordance: confidence chips on leaves, opportunity-linked leaves with hover affordance, the existing ``EbitdaNode`` data model.
- Improve mobile rendering — vertical scroll instead of pinch-zoom.
- Improve accessibility — semantic HTML with screen-reader-navigable headings instead of a single React Flow ``application`` region.
- Drop ``@dagrejs/dagre`` from the frontend dependency closure (only consumer disappears).

**Non-Goals:**

- Changing the ``EbitdaNode`` Pydantic model, the ``build_programmatic_ebitda_tree`` pipeline step, or the analysis-payload contract. Backend untouched.
- Changing ``ebitda-tree-confidence`` requirements. Confidence chips on leaves stay in place visually and semantically.
- Changing ``PrintEbitdaOutline.tsx`` — the print path already does the right thing; the web rendering converges with it.
- Removing ``@xyflow/react`` from the dependency closure — the strategy-map canvas still uses it.
- A pan/zoom escape hatch ("expand to full-screen graph") — the data doesn't earn one. If a user ever needs more space, the print/PDF export is the right surface.

## Decisions

### §1 — Drop React Flow + dagre for this component

The financial story is a 5-row linear chain. The features React Flow earns elsewhere (graph layout, edge routing, pan/zoom navigation, mini-map) do not pay rent here. The static layout is rendered with semantic HTML + CSS only.

The strategy map keeps React Flow — that surface has 15+ chips across 4 perspective bands plus inter-perspective arrows, a legitimate graph. The EBITDA section is the misfit.

### §2 — Vertical waterfall layout, leaves fan beside each subtotal

The on-screen layout is:

```
        ┌────────────────────────┐
        │ Total Revenue          │    ▸ Subscriptions $12M (80%)
        │ $15M-$200M             │    ▸ Professional   $2M (15%)
        └───────────┬────────────┘    ▸ Other          $750K (5%)
                    │  minus
        ┌───────────▼────────────┐
        │ Cost of Revenue        │    ▸ Customer Support
        │ $2M-$60M               │    ▸ Cloud Infrastructure
        └───────────┬────────────┘    ▸ Implementation Costs
                    │  equals
        ┌───────────▼────────────┐
        │ Gross Profit           │
        │ $10M-$170M             │
        └───────────┬────────────┘
                    │  minus
        ┌───────────▼────────────┐
        │ Operating Expenses     │    ▸ Sales & Marketing
        │ $5M-$140M              │    ▸ R&D
        └───────────┬────────────┘    ▸ G&A
                    │  equals
        ┌────────────────────────┐
        │ EBITDA $2M-$70M        │
        └────────────────────────┘
```

The five subtotal/parent cards form a centered vertical column. Each card has a connector arrow underneath labelled "minus" or "equals" (so the financial arithmetic is on-screen). Leaves of each parent fan out to the right of the parent card on desktop, stacked as compact pills.

On mobile (viewport < 768 px), the leaves move from "beside the parent" to "below the parent" — single column, no horizontal scroll. The vertical-waterfall arithmetic is preserved.

### §3 — No pan, no zoom, no fullscreen escape hatch

The ``Fit``, ``Expand``, +/−, and "Scroll to pan, pinch or use controls to zoom" affordances all go away. The new layout is sized to the content; there is nothing to fit. If a user needs the data in another format, the PDF export already exists.

### §4 — Connector arrows carry the arithmetic semantics

Each between-card connector renders both an arrow glyph (▼) and a tiny "minus" / "equals" label so a screen reader hears the relationship and a sighted user sees it. The four connectors are:

- Total Revenue ── minus ──→ Cost of Revenue
- Cost of Revenue ── equals ──→ Gross Profit
- Gross Profit ── minus ──→ Operating Expenses
- Operating Expenses ── equals ──→ EBITDA

These are pure presentation — no data-model edge exists, no need for one.

### §5 — Reuse ``ConfidenceIndicator``; no leaf-card duplication

Each leaf renders the existing ``ConfidenceIndicator`` (the 3-dot scale standardised across the analysis page and the strategy map). Leaf cards drop the React Flow ``Handle`` / ``Position`` imports — they become plain ``<article>`` elements with the same visual treatment as today (label, value range, percentage-of-parent, confidence dots).

### §6 — Opportunity-linking remains inline

Each leaf carries ``linked_opportunity_indices`` referencing rows in the opportunities array. Today the leaf shows a badge or tooltip indicating "N opportunities target this line" and clicking jumps to the opportunity card. That affordance is preserved verbatim — the new card layout keeps the same hover/click contract.

### §7 — Semantic HTML

The new layout uses:

- ``<section aria-labelledby="ebitda-impact-model-heading">`` as the root.
- ``<ol>`` for the five subtotal rows so screen readers announce ordinal position (1 of 5, etc.).
- ``<h3>`` for each subtotal label (Total Revenue, Cost of Revenue, …).
- ``<ul>`` for each parent's leaves, with ``aria-label="Drivers of {parent label}"`` so the screen reader knows which subtotal a leaf belongs to.
- The connector glyphs are ``aria-hidden`` decorations; the "minus" / "equals" labels are exposed as plain text alongside.

### §8 — Drop ``@dagrejs/dagre`` from ``frontend/package.json``

``EbitdaTree.tsx`` is the only consumer. After the rewrite it's dead weight. Removing it shrinks the JS bundle and removes one transitive dep on ``@xyflow/react``'s sibling layout libs.

## Risks / Trade-offs

### Risk: existing visual regression tests / screenshots

If there are visual-regression baselines pinned on the React Flow canvas (Playwright, Percy, etc.), they will all fail. **Mitigation**: rebaseline as part of the implementation. Cost is one-time.

### Risk: jsdom mocks for ``@xyflow/react``

Tests that exercise the EBITDA section previously stubbed ``ResizeObserver`` / ``DOMRect`` for React Flow. After the rewrite those mocks are dead. **Mitigation**: remove from the affected test files; verify the strategy-map tests still set them up locally (they still need them).

### Trade-off: no pan/zoom for very-wide leaf rows

If a future EBITDA template carries 5+ leaves per parent, the row of pills beside the parent card could overflow horizontally on desktop. **Mitigation**: flex-wrap the leaves to a second row beside the parent. The fallback is the same single-column stack that mobile uses.

### Trade-off: print and web visuals converge

``PrintEbitdaOutline.tsx`` is the existing template for the new web rendering. They share spatial layout but the web version retains interactive affordances (hovers, links) that print doesn't need. Visual divergence is intentional and minor.

### Risk: opportunity-link hover affordance regression

The current React Flow node wires ``onMouseEnter`` / ``onMouseLeave`` through React Flow's node API. The new plain-card implementation uses native DOM events. **Mitigation**: explicit regression test that mounts ``EbitdaSection`` with a leaf carrying ``linked_opportunity_indices: [0, 2]`` and asserts the hover surface is reachable.

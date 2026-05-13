## Why

The EBITDA Impact Model section on the analysis page renders as a React Flow canvas with pan + zoom controls. In practice users can't read it at the default zoom level, ~50 % of the canvas is empty whitespace at the top and bottom, and the 5 top-level rollups (Total Revenue, Cost of Revenue, Gross Profit, Operating Expenses, EBITDA) sprawl side-by-side because they're modelled in the data as siblings with no edges between them — dagre lays them out as 5 disconnected mini-trees in a wide horizontal forest.

The financial story (Revenue − COGS = Gross Profit; Gross Profit − OpEx = EBITDA) lives only in the user's head, not in the layout. A P&L summary is a 5-row linear chain, not an explorable graph; pan/zoom is fighting the user instead of helping them.

## What Changes

- Replace the React Flow / dagre canvas in ``EbitdaTree.tsx`` with a static vertical-waterfall layout: Total Revenue → minus → Cost of Revenue → equals → Gross Profit → minus → Operating Expenses → equals → EBITDA, top-to-bottom, with each subtotal's leaves fanning out beside it on desktop and stacking below on mobile.
- **BREAKING (UI)**: drop the pan, zoom, "Fit", and "Expand" controls. The new layout renders at the right size by default — there is nothing to fit and nothing to expand to. ``EbitdaSection`` no longer wraps its child in a ``ReactFlowProvider``.
- Strip ``EbitdaNodeComponent`` of its ``@xyflow/react`` bindings (``Handle`` / ``Position``); reuse the visual treatment as a plain card component rendered by the new waterfall.
- Drop ``@dagrejs/dagre`` from ``frontend/package.json`` — ``EbitdaTree`` is its only consumer.
- Leave the ``EbitdaNode`` Pydantic model + the ``EbitdaTreeResult`` API shape untouched. Confidence-level provenance (per ``ebitda-tree-confidence``) and opportunity-linking on leaves continue to work.
- ``PrintEbitdaOutline.tsx`` (PDF render path) is untouched — it already uses a static vertical layout. The new web rendering will be stylistically aligned with the print version so the two surfaces tell the same story.

## Capabilities

### New Capabilities
- `ebitda-impact-model`: rendering contract for the on-screen EBITDA Impact Model section — vertical-waterfall layout, no pan/zoom interaction, leaves fan beside their subtotal on desktop and stack below on mobile, subtotal-to-subtotal arrows surface the "minus / equals" financial flow.

### Modified Capabilities
<!-- ``ebitda-tree-confidence`` is unaffected — the confidence chips on each leaf survive the rewrite and remain the same visual treatment. No requirement changes there. -->

## Impact

- **Frontend code**:
  - Rewrite ``frontend/src/components/EbitdaTree.tsx`` (~285 lines → smaller static layout).
  - Simplify ``frontend/src/components/EbitdaNodeComponent.tsx`` (drop React Flow ``Handle`` / ``Position``).
  - Update ``frontend/src/components/analysis/EbitdaSection.tsx`` (drop ``ReactFlowProvider`` wrapper).
- **Frontend tests**: rewrite ``EbitdaTree.test.tsx`` + ``EbitdaNodeComponent.test.tsx`` (no more React Flow jsdom shims); update consumer tests in ``EbitdaSection.test.tsx`` and ``AnalysisDetail.test.tsx``.
- **Dependencies**: drop ``@dagrejs/dagre`` from ``frontend/package.json``. ``@xyflow/react`` stays — the strategy-map canvas still uses it.
- **Backend**: no changes. ``EbitdaNode`` data model, ``build_programmatic_ebitda_tree``, and the analysis-payload contract are unaffected.
- **Print path**: ``PrintEbitdaOutline.tsx`` and its tests are unaffected; the visual treatment will converge.
- **Accessibility**: the new layout uses semantic HTML (``<section>``, ``<ol>``, headings) so screen-reader navigation improves vs. the React Flow canvas (which announces as a single ``application`` region).

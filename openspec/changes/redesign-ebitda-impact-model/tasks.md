## 1. Rewrite the renderer

- [x] 1.1 Rewrite ``frontend/src/components/EbitdaTree.tsx`` as a static vertical-waterfall layout: a ``<section>`` with an accessible name, an ``<ol>`` of five subtotal rows in P&L order (Total Revenue → Cost of Revenue → Gross Profit → Operating Expenses → EBITDA), and a connector between each pair labelled "minus" / "equals" per Decision §4. Remove all imports from ``@xyflow/react`` and ``@dagrejs/dagre``. Remove the ``Fit`` / ``Expand`` / zoom-control affordances and the "Scroll to pan, pinch or use controls to zoom" legend.
- [x] 1.2 Implement the leaf-row presentation: on viewports ≥ 768 px the leaves render to the right of the parent subtotal card; on viewports < 768 px they stack in a single column directly below the parent. Use CSS (flexbox or grid) — no JS-driven layout.
- [x] 1.3 Simplify ``frontend/src/components/EbitdaNodeComponent.tsx``: drop the ``@xyflow/react`` ``Handle`` / ``Position`` bindings. Expose it as a plain ``<article>`` rendering the label, value range, percentage-of-parent, and ``ConfidenceIndicator``. Preserve every visual treatment + every prop the consumer test relies on; preserve the opportunity-link hover/focus affordance unchanged.
- [x] 1.4 Update ``frontend/src/components/analysis/EbitdaSection.tsx``: drop the ``ReactFlowProvider`` wrapper. The component should now be a thin pass-through that renders the new ``EbitdaTree``.

## 2. Drop the dead dependency

- [x] 2.1 Remove ``@dagrejs/dagre`` from ``frontend/package.json`` dependencies. Run ``npm install`` (or equivalent) to regenerate the lockfile.
- [x] 2.2 Verify no remaining import of ``@dagrejs/dagre`` anywhere in ``frontend/src``. ``@xyflow/react`` stays — the strategy map still uses it.

## 3. Tests

- [x] 3.1 Rewrite ``frontend/src/tests/components/EbitdaTree.test.tsx``: drop the React Flow jsdom shims (``ResizeObserver`` / ``DOMRect``); add assertions for the new requirements — five subtotal rows in P&L order, four connectors with the correct ``minus`` / ``equals`` labels, no zoom controls in the DOM, container height equals content height.
- [x] 3.2 Rewrite ``frontend/src/tests/components/EbitdaNodeComponent.test.tsx``: drop the ``@xyflow/react`` shims; cover the plain-card variant; pin the ``ConfidenceIndicator`` integration via the ``aria-label="Confidence: {Level}"`` selector; pin the opportunity-link hover/focus affordance for a leaf with non-empty ``linked_opportunity_indices``.
- [x] 3.3 Update ``frontend/src/tests/components/analysis/EbitdaSection.test.tsx`` to drop any ``ReactFlowProvider`` mount and assert the new layout invariants surface in the consumer.
- [x] 3.4 Update ``frontend/src/tests/pages/AnalysisDetail.test.tsx`` if it references the deleted zoom controls or container-height assertions.
- [x] 3.5 Add a mobile-breakpoint test: render at viewport width 375 px and assert the leaves appear in a column below their parent (no horizontal scroll).
- [x] 3.6 Add a semantic-HTML test: assert the section root is a ``<section>`` with an accessible name, the subtotals are inside an ``<ol>``, each parent's leaves are inside a ``<ul>`` with an ``aria-label`` referencing the parent.

## 4. Verify + ship

- [x] 4.1 Run ``npm test -- --run`` in ``frontend/`` — all tests green.
- [x] 4.2 Run ``npx tsc --noEmit`` and ``npm run lint`` — clean.
- [x] 4.3 Run the ``architecture-reviewer`` agent (touches 3+ frontend files + a dependency); resolve CRITICAL + MEDIUM findings before commit.
- [ ] 4.4 Visual verification on testing env: the section renders without zoom, has no top/bottom whitespace, the five subtotals + four connector labels are readable at default zoom, and leaves are visibly attached to their parent.
- [ ] 4.5 Mobile verification on testing env (or browser devtools at 375 px width): leaves stack below their parent, no horizontal scroll, all five subtotals reachable by vertical scroll.
- [x] 4.6 Commit, push, open PR against ``development``.

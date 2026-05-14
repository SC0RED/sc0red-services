## 1. Implementation

- [x] 1.1 In ``frontend/src/components/analysis/EbitdaSection.tsx``, add a recursive ``treeHasLinkedOpportunities(nodes: EbitdaNode[]): boolean`` predicate next to the existing ``treeHasConfidence`` predicate. The walk returns ``true`` when any node (at any depth) carries a ``linked_opportunity_indices`` array of length ≥ 1.
- [x] 1.2 In the same file, add an ``EbitdaOpportunityLinkLegend`` sibling component (or inline JSX block) gated on ``treeHasLinkedOpportunities(ebitdaTree.treeData)``. The legend renders one line:
  - Opening ``<strong>Opportunity links:</strong>`` label
  - Three inline dot+label pairs: ``● Revenue Side``, ``● Cost Side``, ``● Both``
  - Trailing prose: ``— AI Opportunities targeting this P&L line.``
  - Each dot is a 10 × 10 px ``<span>`` with ``background: var(--lever-revenue)`` / ``var(--lever-cost)`` / ``var(--lever-both)`` respectively.
  - The outer element carries ``data-testid="ebitda-opportunity-link-legend"``.
- [x] 1.3 Render the new legend in ``EbitdaSection`` next to the existing ``ebitda-confidence-legend``. Order: confidence legend first (today's pre-existing position), opportunity-link legend immediately below. Both legends stack as separate rows inside the section's header region (above the ``<div className="card card--rich">``).
- [x] 1.4 Style the legend to match the existing ``ebitda-confidence-legend`` posture: ``fontSize: '0.875rem'`` (body-small canonical step), ``color: 'var(--text-tertiary)'``, ``marginBottom: '0.75rem'``, ``lineHeight: 1.6``. Lever-name labels are ``<strong>``-wrapped with ``color: 'var(--text-secondary)'`` (same as the confidence-legend's "<strong>High</strong>" / etc.).

## 2. Tests

- [x] 2.1 In ``frontend/src/tests/components/analysis/EbitdaSection.test.tsx``, add a new test: "renders the opportunity-link legend when at least one leaf carries linked opportunities". Fixture: a tree with one leaf whose ``linked_opportunity_indices: [0]``. Assertions: the element with ``data-testid="ebitda-opportunity-link-legend"`` is in the DOM AND its text content contains "Revenue Side", "Cost Side", AND "Both".
- [x] 2.2 Add a complementary test: "does NOT render the opportunity-link legend when no leaf carries linked opportunities". Fixture: a tree where every node's ``linked_opportunity_indices`` is empty. Assertion: ``queryByTestId('ebitda-opportunity-link-legend')`` is null.
- [x] 2.3 Add a "deeply nested" regression test: top-level node has empty ``linked_opportunity_indices`` but a nested child leaf has ``linked_opportunity_indices: [0]``. Assert the predicate walks children recursively and the legend renders.
- [x] 2.4 Add a token-binding regression test: query the three legend dots (e.g. via ``data-testid="ebitda-opportunity-link-legend"`` then ``querySelectorAll('span[style]')``) and assert each dot's ``background`` style references the matching ``var(--lever-*)`` token.

## 3. Verify + ship

- [x] 3.1 Run ``npm test -- --run`` in ``frontend/`` — all tests green.
- [x] 3.2 Run ``npx tsc --noEmit`` and ``npm run lint`` — clean.
- [x] 3.3 Run the ``architecture-reviewer`` agent (touches 1 component file + 1 test file); resolve CRITICAL + MEDIUM findings before commit.
- [ ] 3.4 Visual verification on testing env: scroll to EBITDA section. Confirm the new legend renders below the confidence legend, one line, three colored dots matching the chips below. Hover-test on a leaf's dot row — the colors should match the legend exactly.
- [x] 3.5 Commit, push, open PR against ``development``.

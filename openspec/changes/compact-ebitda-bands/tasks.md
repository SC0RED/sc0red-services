## 1. Restructure the renderer

- [x] 1.1 Restructure ``frontend/src/components/EbitdaTree.tsx``: each P&L row's content collapses from "vertical flex (parent card on top, leaf list below)" to "vertical flex (band header on top, horizontal chip row below)". Keep the outer ``<ol>`` waterfall + connectors + ``aria-labelledby`` heading reference unchanged.
- [x] 1.2 In ``EbitdaTree.tsx``, switch the leaf container from ``<ul>`` with ``flex-direction: column`` to ``<ul>`` with ``flex-direction: row; flex-wrap: wrap; gap: 12px`` so chips arrange horizontally and wrap to a second row when the band is narrow. Preserve the ``aria-label="Drivers of {parent.label}"`` attribute.

## 2. Restructure the card component

- [x] 2.1 In ``frontend/src/components/EbitdaNodeComponent.tsx``, branch the visual on the existing ``isSubtotalHeading`` prop:
  - When ``true``: render the band-header variant — a single-row element with a ``border-left: 4px solid {colors.text}`` strip, the label in ``<h3>`` (preserve the heading scale from PR #299), the value range inline to the right, no description tooltip, no opportunity dots, no confidence chip.
  - When ``false``: render the compact-chip variant — same fields as today (label / value range / percentage / confidence / opportunity dots) but with reduced padding (``8px 12px``), smaller fonts, no box-shadow glow, ``maxWidth: 200px``, ``minWidth: 150px``, single border.
- [x] 2.2 Remove the absolutely-positioned hover description overlay (``position: absolute; top: 100%; transform: translateX(-50%)`` block). The chip's outer element instead carries an HTML ``title`` attribute equal to the leaf's ``description`` (when non-empty).
- [x] 2.3 Preserve the opportunity-link indicator dot row inside the chip with its existing per-dot ``title={'{opp.title} ({opp.valueLever})'}`` attribute (this surface is already correct, just stays).

## 3. Tests

- [x] 3.1 Update ``frontend/src/tests/components/EbitdaTree.test.tsx``:
  - Existing "renders <ol> with five rows" + "<h3> on subtotal labels" + "connectors in [minus, equals, minus, equals] order" + "leaves grouped in <ul aria-label=...>" tests stay — the contract is preserved.
  - Update the "renders each leaf with its label, value range, and percentage" test to assert the new chip dimensions are within the visual budget (rendered footprint ≤ 200 × 110 px, e.g. by querying computed styles or by querying that the chip's container does NOT match ``maxWidth: 280px`` or larger).
  - Add a regression test: render a band whose parent has 3+ leaves, and assert all chips render inside the same flex container (single ``<ul>``) without a horizontal scroll trap.
- [x] 3.2 Rewrite ``frontend/src/tests/components/EbitdaNodeComponent.test.tsx`` to assert:
  - With ``isSubtotalHeading: true``: the rendered element has a ``border-left`` style of ``4px solid`` (or equivalent), the label is inside ``<h3>``, AND the rendered DOM contains no ``ebitda-confidence-chip``, no ``ebitda-linked-opportunity-dots``, no description-overlay element.
  - With ``isSubtotalHeading: false`` (leaf chip): the chip carries the description on its outer element's ``title`` attribute, AND no descendant element has ``position: absolute`` referring to the description content, AND the confidence chip + opportunity-link dot tests carried over from today still pass.
- [x] 3.3 Add a regression test that asserts the chip's outer element exposes the leaf description via ``title`` when ``description`` is non-empty, AND that ``title`` is absent when the description is empty.
- [x] 3.4 Add a regression test that asserts NO element in the rendered chip has ``position: absolute`` (the prior overlay's signature) — this pins the "no custom overlay" rule from the spec.

## 4. Verify + ship

- [x] 4.1 Run ``npm test -- --run`` in ``frontend/`` — all tests green.
- [x] 4.2 Run ``npx tsc --noEmit`` and ``npm run lint`` — clean.
- [x] 4.3 Run the ``architecture-reviewer`` agent (touches 2-3 frontend files, no dependency change); resolve CRITICAL + MEDIUM findings before commit.
- [ ] 4.4 Visual verification on testing env: the EBITDA section is ≤ ⅓ the height of the today's PR #299 rendering, band headers carry a colored left strip, leaves are compact chips ≤ 200 × 110 px arranged horizontally, no hover tooltip overlaps the next row.
- [ ] 4.5 Mobile verification (375 px width): chips wrap to multiple rows inside the band; no horizontal scroll; band header still readable.
- [ ] 4.6 Commit, push, open PR against ``development``.

## ADDED Requirements

### Requirement: EBITDA Impact Model renders as a static vertical waterfall

The EBITDA Impact Model section on the analysis-detail page SHALL render the ``EbitdaTreeResult`` as a static vertical layout. The five subtotal/parent rollups (Total Revenue, Cost of Revenue, Gross Profit, Operating Expenses, EBITDA) SHALL appear top-to-bottom in P&L order. The container SHALL size itself to fit its content with no fixed height that produces empty whitespace.

The rendering SHALL NOT use a graph library, dagre layout, or React Flow components for this section. ``@dagrejs/dagre`` SHALL NOT be a frontend runtime dependency after this change.

#### Scenario: All five subtotals render in P&L order

- **WHEN** ``EbitdaSection`` is rendered with an ``EbitdaTreeResult`` containing all five canonical subtotals
- **THEN** the rendered DOM contains a single ordered list with five rows in the order: Total Revenue, Cost of Revenue, Gross Profit, Operating Expenses, EBITDA, AND each subtotal card surfaces its ``label`` and ``value_range``

#### Scenario: Container has no scrollable empty whitespace

- **WHEN** ``EbitdaSection`` is rendered at any viewport width
- **THEN** the section's rendered height equals the height of its content (no fixed 700px container, no internal scroll area, no zoom canvas)

### Requirement: Subtotal connectors carry the financial arithmetic

Between each pair of adjacent subtotal cards SHALL appear a visible connector that names the arithmetic relationship between the two cards. The connector text uses the words "minus" and "equals" (case-insensitive in the rendered DOM) in the following order:

1. Total Revenue — minus → Cost of Revenue
2. Cost of Revenue — equals → Gross Profit
3. Gross Profit — minus → Operating Expenses
4. Operating Expenses — equals → EBITDA

#### Scenario: Connector labels render in the correct sequence

- **WHEN** the full P&L tree is rendered
- **THEN** the connectors between subtotals carry the labels ``minus``, ``equals``, ``minus``, ``equals`` in that order, AND each label is exposed as plain text (not only via an aria-label) so sighted users see the arithmetic

### Requirement: Subtotal leaves render alongside their parent on desktop and stack below on mobile

Each leaf node attached to a subtotal (e.g. ``Subscriptions`` under ``Total Revenue``) SHALL render visually associated with its parent subtotal. On viewports ≥ 768 px the leaves render to the right of the parent card. On viewports < 768 px the leaves render in a single column immediately below the parent card. In both modes the leaves SHALL be reachable in keyboard tab order between the parent card above them and the next connector below.

#### Scenario: Desktop layout places leaves beside the parent

- **WHEN** the section is rendered on a viewport ≥ 768 px and ``Total Revenue.children`` is non-empty
- **THEN** the leaves visually flank ``Total Revenue`` on the right of the parent card

#### Scenario: Mobile layout stacks leaves below the parent

- **WHEN** the section is rendered on a viewport < 768 px
- **THEN** every leaf renders in a single column directly below its parent, AND no element of the section requires horizontal scroll

### Requirement: No pan, zoom, or fullscreen controls

The section SHALL NOT render any pan, zoom, fit-to-view, or fullscreen / expand control. The legend text "Scroll to pan, pinch or use controls to zoom. Hover nodes for details." SHALL NOT appear.

#### Scenario: No zoom controls in the DOM

- **WHEN** ``EbitdaSection`` is rendered
- **THEN** the rendered DOM contains no element with ``aria-label="Zoom in"``, ``aria-label="Zoom out"``, ``aria-label="Fit view"``, or any button labelled ``Fit`` / ``Expand``

### Requirement: Confidence chips and opportunity-linking on leaves are preserved

The new layout SHALL preserve the existing leaf-card affordances:

- The ``confidence_level`` chip (rendered via ``ConfidenceIndicator``) on every leaf that carries one.
- The opportunity-link affordance for leaves whose ``linked_opportunity_indices`` is non-empty — the leaf MUST be hoverable / focusable to surface the link.

#### Scenario: Confidence chip survives the rewrite

- **WHEN** a leaf with ``confidence_level: "medium"`` renders
- **THEN** the leaf card contains a ``ConfidenceIndicator`` element with ``aria-label="Confidence: Medium"``

#### Scenario: Opportunity-linked leaf is reachable

- **WHEN** a leaf with ``linked_opportunity_indices: [0, 2]`` renders
- **THEN** the leaf card is keyboard-focusable AND surfaces an affordance (link, button, or tooltip) referencing the linked opportunities

### Requirement: Section uses semantic HTML for screen-reader navigation

The section SHALL be structured with semantic HTML so a screen reader announces the P&L sequence intelligibly:

- A ``<section>`` element wraps the whole model with an accessible name ("EBITDA Impact Model" or equivalent).
- The five subtotals are children of an ordered list (``<ol>``) so position-in-sequence is announced.
- Each subtotal's label renders inside a heading element (``<h3>`` or equivalent within the page heading scale).
- Each parent's leaves are grouped in an ``<ul>`` with an accessible label that identifies the parent (e.g. ``aria-label="Drivers of Total Revenue"``).

#### Scenario: Screen-reader navigation sequence

- **WHEN** a screen-reader user navigates the section by heading
- **THEN** the user hears the five subtotal labels in P&L order (Total Revenue → Cost of Revenue → Gross Profit → Operating Expenses → EBITDA), AND each leaf list is announced with a name that identifies its parent

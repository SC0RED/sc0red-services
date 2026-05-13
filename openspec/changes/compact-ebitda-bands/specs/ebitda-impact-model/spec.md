## MODIFIED Requirements

### Requirement: EBITDA Impact Model renders as a static vertical waterfall

The EBITDA Impact Model section on the analysis-detail page SHALL render the ``EbitdaTreeResult`` as a static vertical layout. The five subtotal/parent rollups (Total Revenue, Cost of Revenue, Gross Profit, Operating Expenses, EBITDA) SHALL appear top-to-bottom in P&L order as **band rows** — a one-line header surfacing the subtotal label and value range, followed (when the subtotal has children) by a row of compact leaf chips visually contained inside the same band. Subtotals SHALL NOT render as standalone cards.

The container SHALL size itself to fit its content with no fixed height that produces empty whitespace. The rendering SHALL NOT use a graph library, dagre layout, or React Flow components for this section. ``@dagrejs/dagre`` SHALL NOT be a frontend runtime dependency.

#### Scenario: All five subtotals render in P&L order as band headers

- **WHEN** ``EbitdaSection`` is rendered with an ``EbitdaTreeResult`` containing all five canonical subtotals
- **THEN** the rendered DOM contains a single ordered list with five rows in the order: Total Revenue, Cost of Revenue, Gross Profit, Operating Expenses, EBITDA, AND each row's band header surfaces the subtotal's ``label`` and ``value_range`` on a single line

#### Scenario: Band header carries a colored left-edge strip per subtotal type

- **WHEN** a band header renders for a subtotal of a given ``type`` (``revenue`` / ``cost`` / ``margin`` / ``subtotal``)
- **THEN** the header element carries a left-edge colored strip whose hue matches the canonical ``NODE_COLORS`` mapping for that type, AND no other border or glow chrome that would visually compete with the strip

#### Scenario: Container has no scrollable empty whitespace

- **WHEN** ``EbitdaSection`` is rendered at any viewport width
- **THEN** the section's rendered height equals the height of its content (no fixed 700 px container, no internal scroll area, no zoom canvas)

### Requirement: Subtotal leaves render as compact chips inside their parent's band

Each leaf node attached to a subtotal (e.g. ``Subscriptions`` under ``Total Revenue``) SHALL render as a **compact chip** visually contained inside the same band as its parent. Chips SHALL be rendered in a single flex container that allows wrapping to a second row when the chip count exceeds the available horizontal space (``flex-wrap: wrap``). Chips SHALL be reachable in keyboard tab order between the band header above them and the next connector below.

The chip MUST be visually smaller than the band header — specifically, the chip's typical rendered width SHALL be ≤ 200 px and its rendered height SHALL be ≤ 110 px, so that three chips fit beside the band header on viewports ≥ 768 px without overflow.

Each chip SHALL surface, at minimum:

- The leaf ``label`` (in the leaf's type-color, NOT inside a heading element).
- The leaf ``value_range``.
- The leaf ``percentage_of_parent`` (when present).
- The ``ConfidenceIndicator`` (small variant) when the leaf carries a ``confidence_level``.
- An opportunity-link indicator row (one small dot per linked opportunity) when ``linked_opportunity_indices`` is non-empty.

#### Scenario: Leaves of a parent render inside the same band container

- **WHEN** the section is rendered with a subtotal that has leaves
- **THEN** the leaves render inside a flex container that is a descendant of the same band element as the parent header, AND that flex container has ``flex-wrap`` enabled so chips wrap when the row is narrow

#### Scenario: A chip's rendered footprint stays under the visual budget

- **WHEN** a leaf chip is rendered with all surfaces present (label, value range, percentage, confidence chip, two opportunity dots)
- **THEN** the chip's CSS dimensions yield a rendered footprint no larger than 200 × 110 px, so three chips fit side-by-side on viewports ≥ 768 px

#### Scenario: Mobile layout wraps chips inside the band

- **WHEN** the section is rendered on a viewport < 768 px
- **THEN** chips wrap to additional rows within the same band container (single-column when the band is narrowest), AND no element of the section requires horizontal scroll

#### Scenario: Confidence chip survives the new chip variant

- **WHEN** a leaf chip renders with ``confidence_level: "medium"``
- **THEN** the chip contains a ``ConfidenceIndicator`` element with ``aria-label="Confidence: Medium"``

#### Scenario: Opportunity-linked leaf surfaces its links inline

- **WHEN** a leaf chip renders with ``linked_opportunity_indices: [0, 2]``
- **THEN** the chip is keyboard-focusable, AND a row of indicator dots renders inline on the chip with one dot per linked opportunity, AND each dot's HTML ``title`` attribute carries the opportunity's title plus value lever

### Requirement: Hover detail is delivered via native ``title`` attributes, not a custom positioned overlay

A leaf chip's long-form ``description`` field SHALL be surfaced via the HTML ``title`` attribute on the chip's outer element. The opportunity-link dot row inside the chip SHALL continue to surface per-opportunity context via each dot's HTML ``title`` attribute.

The chip SHALL NOT render an absolutely-positioned custom description box (``position: absolute`` with ``top: 100%`` or similar) that can overflow into neighbouring DOM elements. Any prior custom overlay that overflowed adjacent rows is removed end-to-end.

#### Scenario: Chip surfaces its description via the native title attribute

- **WHEN** a leaf chip renders with a non-empty ``description``
- **THEN** the chip's outer element carries an HTML ``title`` attribute whose value equals the description

#### Scenario: No custom hover overlay exists in the DOM

- **WHEN** any leaf chip is hovered or focused
- **THEN** no element with ``position: absolute`` carrying the chip's description appears in the rendered DOM tree, AND the description content does not visually overlap with any subsequent band, chip, or connector

### Requirement: Subtotal connectors carry the financial arithmetic

(Carried forward unchanged from `redesign-ebitda-impact-model`.) Between each pair of adjacent band rows SHALL appear a visible connector labelled with the arithmetic relationship between the two bands: ``minus``, ``equals``, ``minus``, ``equals`` in P&L order. Each label SHALL be exposed as plain text (not only via ``aria-label``) so sighted users see the arithmetic.

#### Scenario: Connector labels render in the correct sequence

- **WHEN** the full P&L tree is rendered
- **THEN** the connectors between bands carry the labels ``minus``, ``equals``, ``minus``, ``equals`` in that order, AND each label is visible plain text

### Requirement: Section uses semantic HTML for screen-reader navigation

(Carried forward unchanged from `redesign-ebitda-impact-model`.) The section SHALL be structured with semantic HTML so a screen reader announces the P&L sequence intelligibly. A ``<section>`` element wraps the model with an accessible name. The five band rows are children of an ordered list (``<ol>``). Each band's subtotal label renders inside a heading element (``<h3>``). Each parent's leaves are grouped in an ``<ul>`` with an ``aria-label`` identifying the parent (e.g. ``aria-label="Drivers of Total Revenue"``).

#### Scenario: Screen-reader heading navigation sequence

- **WHEN** a screen-reader user navigates the section by heading
- **THEN** the user hears the five subtotal labels in P&L order (Total Revenue → Cost of Revenue → Gross Profit → Operating Expenses → EBITDA), AND each leaf list is announced with a name that identifies its parent

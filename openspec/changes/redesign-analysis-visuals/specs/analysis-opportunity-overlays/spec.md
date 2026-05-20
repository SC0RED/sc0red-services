## ADDED Requirements

### Requirement: Opportunity-link dots use one shared treatment across all three analysis tools

Every analysis tool that has a relationship between its visual nodes and the `Opportunity[]` array (strategy map objectives, EBITDA tree leaves, value chain steps) SHALL render opportunity links as coloured dots at the bottom of the affected node/step. Dot colour SHALL be derived from the linked opportunity's `value_lever` via the existing `LEVER_COLORS` map (Revenue Side → revenue green, Cost Side → cost violet, Both → both cyan). The dot strip SHALL be rendered by a single shared component (`OpportunityDotStrip`) so the three tools cannot drift on visual treatment.

#### Scenario: EBITDA leaf with two linked opportunities

- **WHEN** an EBITDA leaf node has `linked_opportunity_indices: [0, 3]` and the opportunities at indices 0 and 3 carry `value_lever` values `Revenue Side` and `Cost Side` respectively
- **THEN** the leaf renders an `OpportunityDotStrip` with two dots — one revenue-green, one cost-violet — in stable index order
- **AND** the dots are decorative (`aria-hidden="true"`); the linkage is exposed to assistive tech via the dot strip's accessible name (`aria-label="2 opportunities target this line item"`)

#### Scenario: Value chain step with one linked opportunity

- **WHEN** a value chain step has `opportunity_indices: [2]` and the opportunity at index 2 carries `value_lever: 'Both'`
- **THEN** the step renders a single both-cyan dot via `OpportunityDotStrip`
- **AND** the previous text list of opportunity titles below the step is no longer rendered

#### Scenario: Strategy-map objective with linked opportunities

- **WHEN** a strategy-map objective has `linked_opportunity_indices: [1, 4, 7]` populated by the AI pipeline and the three opportunities span all three value-lever buckets
- **THEN** the objective cell renders a three-dot strip via `OpportunityDotStrip` with one dot per bucket
- **AND** the dot order matches the index order in `linked_opportunity_indices`

#### Scenario: Strategy-map objective without linked opportunities renders no dots

- **WHEN** a strategy-map objective has `linked_opportunity_indices` either absent (legacy analysis) or empty
- **THEN** no dot strip is rendered on that objective cell
- **AND** the cell height matches cells with dots so the grid row alignment is preserved

#### Scenario: Node with more than five linked opportunities collapses to "+N more"

- **WHEN** a node has `linked_opportunity_indices.length > 5`
- **THEN** the first five dots render and a trailing `+N` badge indicates the overflow count
- **AND** the `+N` badge is keyboard-focusable; activating it expands a popover listing all linked opportunity titles

### Requirement: Each analysis tool displays a shared opportunity-link legend

When at least one node in a tool carries linked opportunities, that tool SHALL display a one-line legend above its canvas/table. The legend SHALL be rendered by a single shared component (`AnalysisLegend`) so the three tools cannot drift on copy or styling. Legend copy SHALL match across the three tools:

> "● Revenue Side · ● Cost Side · ● Both — AI opportunities targeting this <noun>."

Where `<noun>` is "P&L line" for EBITDA, "value-chain step" for value chain, and "objective" for strategy map.

#### Scenario: EBITDA legend renders above the tree

- **WHEN** the EBITDA section has at least one leaf with `linked_opportunity_indices` non-empty
- **THEN** an `AnalysisLegend` component renders above the tree canvas
- **AND** its copy contains "P&L line"
- **AND** the three dot swatches in the legend are colored by the `LEVER_COLORS` map

#### Scenario: Value-chain legend renders above the diagram

- **WHEN** the value chain section has at least one step with `opportunity_indices` non-empty
- **THEN** an `AnalysisLegend` renders above the diagram
- **AND** its copy contains "value-chain step"

#### Scenario: Strategy-map legend renders above the table

- **WHEN** the strategy map has at least one objective with `linked_opportunity_indices` non-empty
- **THEN** an `AnalysisLegend` renders above the table
- **AND** its copy contains "objective"

#### Scenario: Legend is omitted when no node carries links

- **WHEN** none of the tool's nodes carry linked opportunities (e.g., a legacy analysis)
- **THEN** no `AnalysisLegend` is rendered for that tool
- **AND** the tool's canvas/table renders normally without an explanatory line above it

### Requirement: Hovering a node or step highlights its linked opportunities

The analysis detail page SHALL wrap its sections in an `OpportunityHoverProvider` that lets any node/step/cell in any analysis tool publish a hover-highlight signal carrying its `opportunity_indices`. Cards in the `OpportunitiesList` below SHALL subscribe to this signal and apply a visual highlight (background pulse + scroll-into-view with `block: 'nearest'`) when their index appears in the active set.

#### Scenario: Hovering an EBITDA leaf highlights its linked opportunities

- **WHEN** the user hovers an EBITDA leaf node with `linked_opportunity_indices: [0, 2]`
- **THEN** the opportunity cards at index 0 and 2 in the `OpportunitiesList` apply a 400 ms pulse animation
- **AND** if either card is fully outside the current viewport, the page scrolls so it becomes visible
- **AND** when the pointer leaves the leaf, the pulse and highlight class are removed

#### Scenario: Hovering a value-chain step highlights its linked opportunities

- **WHEN** the user hovers a value-chain step with `opportunity_indices: [1]`
- **THEN** the opportunity card at index 1 pulses and scrolls into view if needed

#### Scenario: Hovering a strategy-map objective cell highlights its linked opportunities

- **WHEN** the user hovers a strategy-map objective cell with `linked_opportunity_indices: [3, 5]`
- **THEN** the opportunity cards at indices 3 and 5 pulse
- **AND** the page does not scroll if both cards are partially visible

#### Scenario: Hovering an opportunity card highlights matching nodes in all three tools

- **WHEN** the user hovers an opportunity card at index 4 in the `OpportunitiesList`
- **THEN** every strategy-map cell, EBITDA leaf, and value-chain step whose linked-indices set contains 4 receives a visual highlight class
- **AND** when the pointer leaves the card, every node returns to its default state

#### Scenario: Keyboard focus triggers the same highlight as hover

- **WHEN** a keyboard user focuses any hover-source (objective cell, leaf, step, opportunity card) via tab
- **THEN** the same highlight set fires as on pointer hover
- **AND** the highlight is cleared on blur

### Requirement: Confidence dots are removed from analysis-tool visuals

The strategy-map objective chips and the EBITDA leaf chips SHALL NOT render the `confidence_level` field as a visual indicator (no "•••" dot row, no chip, no badge). The underlying `confidence_level` and `confidence_basis` fields remain in the data pipeline and the API response — only the visual is removed.

#### Scenario: Strategy-map objective cell renders no confidence indicator

- **WHEN** a strategy-map objective cell is rendered
- **THEN** no element styled as `confidence-dots` or `confidence-chip` is present in the cell
- **AND** the cell's `confidence_level` field, if any, is not used by the renderer

#### Scenario: EBITDA leaf chip renders no confidence chip

- **WHEN** an EBITDA leaf chip is rendered
- **THEN** no element styled as `confidence-chip` is present in the chip
- **AND** the EBITDA tree's `AnalysisLegend` no longer references confidence

#### Scenario: AnalysisData.confidence fields remain in the API response

- **WHEN** the analysis API response is inspected for an analysis whose objectives or EBITDA leaves carry `confidence_level`
- **THEN** the field is still present in the response payload
- **AND** any future surface (audit panel, debug overlay) that wants to render it can do so without a pipeline change

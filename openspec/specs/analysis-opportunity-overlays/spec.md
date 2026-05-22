# analysis-opportunity-overlays Specification

## Purpose

Cross-tool opportunity-link overlay system shared by the strategy map, EBITDA tree, and value-chain diagrams. Renders coloured dots at the affected nodes (one per linked opportunity, dot colour from the existing `LEVER_COLORS` map), a shared one-line legend above each tool, hover-to-pulse highlighting that syncs with the `OpportunitiesList` cards below, and a source-side popover listing linked opportunity titles. The three tools share a single renderer (`OpportunityDotStrip`), legend (`AnalysisLegend`), hover context (`OpportunityHoverProvider`), and popover (`SourceLinkedOpportunitiesPopover`) so they cannot drift on visual treatment.

Introduced by the `redesign-analysis-visuals` change. Replaces the prior ad-hoc per-tool treatments (EBITDA had dots from PR #305, value chain had a text list, strategy map had nothing).

## Requirements

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

### Requirement: Hovering a node or step pulses its linked opportunities

The analysis detail page SHALL wrap its sections in an `OpportunityHoverProvider` that lets any node/step/cell in any analysis tool publish a hover-highlight signal carrying its `opportunity_indices`. Cards in the `OpportunitiesList` below SHALL subscribe to this signal and apply a visual highlight (background pulse only — NOT scroll-into-view) when their index appears in the active set.

**Scroll-on-hover was removed by PR #361** after production PE reviewers complained the page was scrolling out from under them. The pulse remains as the visual highlight; scroll behaviour is reserved for **intentional navigation gestures** (clicking a Quick Wins matrix chip, clicking a source-side popover entry per the next requirement). Hovering is information-seeking, not navigation.

#### Scenario: Hovering an EBITDA leaf pulses its linked opportunities (no scroll)

- **WHEN** the user hovers an EBITDA leaf node with `linked_opportunity_indices: [0, 2]`
- **THEN** the opportunity cards at index 0 and 2 in the `OpportunitiesList` apply a 400 ms pulse animation
- **AND** the page does NOT scroll, regardless of whether the cards are in view
- **AND** when the pointer leaves the leaf, the pulse and highlight class are removed

#### Scenario: Hovering a value-chain step pulses its linked opportunities

- **WHEN** the user hovers a value-chain step with `opportunity_indices: [1]`
- **THEN** the opportunity card at index 1 pulses
- **AND** the page does NOT scroll

#### Scenario: Hovering a strategy-map objective cell pulses its linked opportunities

- **WHEN** the user hovers a strategy-map objective cell with `linked_opportunity_indices: [3, 5]`
- **THEN** the opportunity cards at indices 3 and 5 pulse
- **AND** the page does NOT scroll

#### Scenario: Hovering an opportunity card highlights matching nodes in all three tools

- **WHEN** the user hovers an opportunity card at index 4 in the `OpportunitiesList`
- **THEN** every strategy-map cell, EBITDA leaf, and value-chain step whose linked-indices set contains 4 receives a visual highlight class
- **AND** when the pointer leaves the card, every node returns to its default state

#### Scenario: Keyboard focus triggers the same pulse as hover

- **WHEN** a keyboard user focuses any hover-source (objective cell, leaf, step, opportunity card) via tab
- **THEN** the same pulse set fires as on pointer hover
- **AND** the pulse clears on blur

### Requirement: Hover sources surface a popover listing linked opportunity titles

Every analysis-tool source surface (strategy-map cell, EBITDA leaf, value-chain step) that carries `linked_opportunity_indices` (or `opportunity_indices`) SHALL render an inline floating popover near the source when hovered or focused. The popover SHALL list the linked opportunity titles — each entry prefixed with a small lever-coloured dot matching the opportunity's `value_lever`. Each entry SHALL be a button: clicking imperatively scrolls + pulses the matching opportunity card via the same imperative `scrollIntoView({ behavior: 'smooth', block: 'nearest' })` pattern used by Quick Wins matrix clicks.

The popover lifecycle:

- **Open**: 150 ms dwell after `mouseEnter` (debounce against fast cursor transit) OR on `focus` (no debounce for keyboard).
- **Close**: 200 ms grace after `mouseLeave` (so the cursor can transit from source → popover without dismissal). Also close on `Escape` keypress and on outside click. Focus-blur closes when the relatedTarget is NOT inside the popover.

The popover is rendered by a single shared component (`SourceLinkedOpportunitiesPopover`) so the three tools cannot drift on visual treatment.

Sources with **zero linked opportunities** SHALL NOT render the popover (no empty surface). Sources with **1-5 linked opportunities** render every title inline. Sources with **6+ linked opportunities** render the first 5 titles + a `+N more` row that, when clicked, opens the existing OpportunitiesList in a "filtered to linked indices" view (or, lacking that, falls back to scrolling the OpportunitiesList section into view).

#### Scenario: Hovering a source opens the popover after 150 ms dwell

- **WHEN** the user hovers a strategy-map cell with `linked_opportunity_indices: [0, 2, 5]` and the pointer remains on the source for ≥ 150 ms
- **THEN** a floating popover renders adjacent to the source listing three rows: "● Opportunity title 0", "● Opportunity title 2", "● Opportunity title 5" (each ● coloured per the matching opportunity's `value_lever`)
- **AND** the matching opportunity cards below pulse via the existing hover provider

#### Scenario: Cursor transit from source to popover does not close it

- **WHEN** the popover is open and the user moves the cursor from the source into the popover content
- **THEN** the popover remains open (the 200 ms close grace period absorbs the transit)
- **AND** entries in the popover are interactive

#### Scenario: Clicking a popover entry scrolls + pulses the matching card

- **WHEN** the popover is open and the user clicks the entry for opportunity index 5
- **THEN** the page scrolls so the matching opportunity card is in view (`scrollIntoView({ behavior: 'smooth', block: 'nearest' })`)
- **AND** the card pulses
- **AND** the popover closes

#### Scenario: Escape closes the popover

- **WHEN** the popover is open and the user presses `Escape`
- **THEN** the popover closes
- **AND** focus returns to the source surface (if focus was inside the popover)

#### Scenario: Source with no linked opportunities renders no popover

- **WHEN** a strategy-map cell has `linked_opportunity_indices: []` (or absent) and the user hovers it
- **THEN** no popover renders
- **AND** the cell still receives the standard focus / hover styling

#### Scenario: Source with 7 linked opportunities shows 5 + "+2 more"

- **WHEN** a source has 7 linked opportunities and the user opens the popover
- **THEN** the first 5 titles render as clickable entries
- **AND** a "+2 more" row renders at the bottom
- **AND** clicking "+2 more" scrolls the OpportunitiesList section into view (or opens a filtered view if implemented)

#### Scenario: Keyboard focus opens the popover immediately (no debounce)

- **WHEN** a keyboard user tabs into a source surface with linked opportunities
- **THEN** the popover renders immediately (no 150 ms debounce)
- **AND** the first popover entry is focusable via Tab

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

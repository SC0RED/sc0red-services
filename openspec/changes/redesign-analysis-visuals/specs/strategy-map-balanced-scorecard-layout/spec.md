## ADDED Requirements

### Requirement: Strategy-map header shows Mission and Vision only

The strategy-map section header SHALL render exactly two elements on top of the table body: the Mission as a banner with full statement text, and the Vision as an eyebrow line above the Mission. The previous four-row disclosure stack (Mission / Value Proposition / Strategic Priorities / Core Values) SHALL be replaced — Value Proposition and Strategic Priorities are absorbed into the table body's row labels and cells; Core Values move to the Values strip at the bottom of the table (see separate requirement).

#### Scenario: Header renders Vision eyebrow above Mission banner

- **WHEN** an analysis with a populated strategy map loads
- **THEN** the strategy-map section header contains exactly two text elements: the Vision statement styled as an uppercase eyebrow ("VISION · <statement>") and the Mission statement styled as a banner headline below it
- **AND** no disclosure / accordion triggers labelled "Mission", "Value Proposition", "Strategic Priorities", or "Core Values" appear in the header

#### Scenario: Vision is absent when the strategy map has no vision statement

- **WHEN** an analysis's `strategyMap.vision.statement` is null or empty
- **THEN** the Vision eyebrow line is omitted
- **AND** the Mission banner renders directly under the section heading

#### Scenario: Mission is absent when the strategy map has no mission statement

- **WHEN** an analysis's `strategyMap.mission.statement` is null or empty
- **THEN** the Mission banner is omitted
- **AND** the section heading sits directly above the table

### Requirement: Strategy-map body renders as a Balanced Scorecard table

The strategy-map body SHALL render as a CSS-grid table with four perspective rows × N theme columns. Each perspective row SHALL display a row label on the left side made up of (a) the perspective name in bold (Financial / Customer / Internal Processes / Organizational Capacity) and (b) a fixed subtitle prose label underneath:

- Financial: "What success looks like"
- Customer: "Who we serve & why us"
- Internal Processes: "The themes we must master"
- Organizational Capacity: "Who we are inside"

Each cell SHALL display its objective's title in bold, the first sentence of its `definition` in muted text (truncated to 2 lines with ellipsis), and the opportunity-dot strip from the `analysis-opportunity-overlays` capability when the objective carries `linked_opportunity_indices`. Cells SHALL be empty placeholder boxes when a perspective row has no objective in a given theme column.

#### Scenario: Table renders four perspective rows in canonical order

- **WHEN** an analysis with a populated strategy map renders the body
- **THEN** the table contains four rows in this top-to-bottom order: Financial, Customer, Internal Processes, Organizational Capacity
- **AND** each row's left-side label shows the perspective name and its fixed subtitle

#### Scenario: Theme columns derive from the AI-generated theme keys

- **WHEN** the strategy map contains objectives spanning two theme columns
- **THEN** the table renders two theme columns in the order the AI emitted them
- **AND** each column's header (above the Financial row) shows the theme label

#### Scenario: Empty cells render placeholder boxes

- **WHEN** the Customer row has objectives in column 1 but not column 2
- **THEN** column 2 of the Customer row renders an empty cell with the same border styling as filled cells
- **AND** the row alignment is preserved across all four perspectives

#### Scenario: Cell shows title, truncated definition, and opportunity dots

- **WHEN** an objective with `title: "Grow ARR"`, a two-sentence `definition`, and `linked_opportunity_indices: [0, 3]` is rendered
- **THEN** the cell shows "Grow ARR" in bold
- **AND** the first sentence of the definition in muted text, truncated to 2 lines with `text-overflow: ellipsis` if longer
- **AND** an `OpportunityDotStrip` with two dots colored from the linked opportunities' value levers

### Requirement: Strategy-map body ends with a Core Values strip

The bottom of the strategy-map table SHALL render the Core Values as a single-row strip spanning all theme columns. The strip SHALL display the values list inline with a leading "VALUES" eyebrow label. When `strategyMap.coreValues.values` is empty or missing, the strip SHALL be omitted.

#### Scenario: Values strip renders when core values are present

- **WHEN** an analysis has `strategyMap.coreValues.values: ["Trust", "Excellence", "Long-term partnership"]`
- **THEN** the strategy-map table renders a Values strip at the bottom containing "VALUES · Trust · Excellence · Long-term partnership"
- **AND** the strip spans all theme columns

#### Scenario: Values strip is omitted on legacy analyses

- **WHEN** an analysis's `strategyMap.coreValues` is null or has an empty `values` array
- **THEN** the Values strip is not rendered
- **AND** the table ends with the Organizational Capacity row

### Requirement: Value Proposition and Strategic Priorities render in a collapsed section below the table

The strategy-map header SHALL contain Mission + Vision only (per the requirement above). The Value Proposition classification + rationale AND the Strategic Priorities list SHALL render in a separate `<ExpandableSection>` (default closed) that sits between the Balanced Scorecard table and the next page section (EBITDA / value-chain / risk breakdown — whichever comes next). The summary label of the expandable section SHALL read "Value Proposition & Strategic Priorities" with a count badge showing the number of strategic priorities (e.g. "Value Proposition & Strategic Priorities · 3").

The expanded body SHALL contain, in order:

1. A "VALUE PROPOSITION" eyebrow label, the primary classification (and secondary if present), and the rationale prose.
2. A horizontal rule.
3. A "STRATEGIC PRIORITIES" eyebrow label and a numbered list of each priority's `name` + `result`.

This relocation responds to Diagnostic Tool Feedback #4 ("at the top here I would just have mission and vision") + the reviewer's recommendation that VP + Strategic Priorities are reference content, not above-the-fold content.

#### Scenario: VP + Strategic Priorities render below the table when both are present

- **WHEN** an analysis with `strategyMap.valueProposition.primary` and `strategyMap.strategicPriorities.length >= 1` renders
- **THEN** an `<ExpandableSection>` labelled "Value Proposition & Strategic Priorities · N" (where N is the priority count) renders between the table's Values strip and the next page section
- **AND** the section is collapsed by default
- **AND** no Value Proposition block appears inside the strategy-map header

#### Scenario: Section is omitted when both fields are absent

- **WHEN** an analysis has no value proposition AND no strategic priorities
- **THEN** the expandable section is not rendered
- **AND** the next page section follows directly after the Values strip

#### Scenario: Section renders when only one of the two is present

- **WHEN** an analysis has `valueProposition.primary` set but `strategicPriorities` empty
- **THEN** the section renders with the VP block only and the priority badge omitted (label reads "Value Proposition")
- **AND** the STRATEGIC PRIORITIES eyebrow is omitted from the expanded body

### Requirement: Strategy-map table is responsive below 900 px viewport

The strategy-map table SHALL maintain readable layout below 900 px viewport by wrapping theme columns into two-up grids and stacking the perspective rows vertically. Row labels SHALL remain visible on every perspective row regardless of viewport width.

#### Scenario: Desktop viewport renders the canonical 4-row × N-column grid

- **WHEN** the viewport is ≥ 900 px wide
- **THEN** the table renders four rows × N columns horizontally
- **AND** row labels sit to the left of each row

#### Scenario: Narrow viewport stacks perspective rows vertically

- **WHEN** the viewport is < 900 px wide
- **THEN** the table renders each perspective as a section block stacked vertically
- **AND** within each section, theme columns wrap into a two-column grid (with one column on viewports < 600 px)

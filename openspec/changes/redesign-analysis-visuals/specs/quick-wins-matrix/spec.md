## ADDED Requirements

### Requirement: Analysis detail renders a 2x2 Quick Wins matrix below the opportunities list

The analysis detail page SHALL render a Quick Wins matrix as a dedicated section (`<AnalysisSection id="quick-wins-matrix">`) immediately after the `OpportunitiesList` section. The matrix SHALL plot every opportunity as a dot positioned by `impact_rating` (Y axis) and `timeline` (X axis), with the conceptual quadrants labeled "Quick Wins", "Strategic Bets", "Fill-Ins", and "Deprioritise".

#### Scenario: Matrix renders when at least one opportunity is present

- **WHEN** the analysis has `opportunities.length >= 1`
- **THEN** a `QuickWinsMatrix` component renders in an `<AnalysisSection id="quick-wins-matrix">` between `opportunities` and `document-upload` (or between `opportunities` and `deep-dive-cta-end` if the end-CTA renders)
- **AND** the section heading reads "Quick Wins Matrix"

#### Scenario: Matrix is omitted on sparse analyses

- **WHEN** the analysis has `opportunities.length === 0`
- **THEN** no `quick-wins-matrix` section is rendered
- **AND** the page transitions directly from `opportunities` to the next section

### Requirement: Matrix axes use existing opportunity fields

The Y axis SHALL bucket on `impact_rating ∈ {High, Medium, Low}` (top-to-bottom: High, Medium, Low). The X axis SHALL bucket on `timeline` parsed into one of three categories based on which substring it starts with:

- "Quick" → Quick Win column (leftmost)
- "Medium" → Medium-term column (centre)
- "Long" → Long-term column (rightmost)

`timeline` strings that don't match any of the three prefixes (legacy or malformed data) SHALL be placed in the Medium-term column with a console warning in development mode.

#### Scenario: High-impact quick-win opportunity lands in the top-left quadrant

- **WHEN** an opportunity has `impact_rating: "High"` and `timeline: "Quick Win (1-3 months)"`
- **THEN** its dot is plotted in the top-left cell of the matrix
- **AND** the cell is part of the "Quick Wins" quadrant

#### Scenario: High-impact long-term opportunity lands in the top-right quadrant

- **WHEN** an opportunity has `impact_rating: "High"` and `timeline: "Long-term (9+ months)"`
- **THEN** its dot is plotted in the top-right cell
- **AND** the cell is part of the "Strategic Bets" quadrant

#### Scenario: Low-impact quick-win lands in the bottom-left

- **WHEN** an opportunity has `impact_rating: "Low"` and `timeline: "Quick Win (1-3 months)"`
- **THEN** its dot is plotted in the bottom-left cell
- **AND** the cell is part of the "Fill-Ins" quadrant

#### Scenario: Low-impact long-term lands in the bottom-right

- **WHEN** an opportunity has `impact_rating: "Low"` and `timeline: "Long-term (9+ months)"`
- **THEN** its dot is plotted in the bottom-right cell
- **AND** the cell is part of the "Deprioritise" quadrant

#### Scenario: Unrecognised timeline string falls back to Medium-term

- **WHEN** an opportunity has `impact_rating: "High"` and `timeline: "Unspecified"` (or any string not matching the three prefixes)
- **THEN** its dot is plotted in the top-centre cell (High × Medium-term)
- **AND** in development builds a `console.warn` records the unrecognised timeline value

### Requirement: Each dot is interactive and respects the hover provider

Every dot SHALL be a button (`role="button"`) carrying the opportunity's index. Clicking or focusing a dot SHALL publish a hover-highlight signal via the `OpportunityHoverProvider` (same provider that `analysis-opportunity-overlays` defines) and scroll the matching opportunity card into view.

#### Scenario: Clicking a dot scrolls the matching opportunity card into view

- **WHEN** the user clicks a dot for the opportunity at index 3
- **THEN** the opportunity card at index 3 in the `OpportunitiesList` scrolls into view
- **AND** the card applies the standard highlight-pulse animation

#### Scenario: Dot click is keyboard-accessible

- **WHEN** a keyboard user focuses a dot via tab and presses Enter or Space
- **THEN** the same scroll + pulse fires as on click
- **AND** the dot's focus ring is visible

### Requirement: Cells render opportunity title chips with overflow popover

Each opportunity SHALL render as a **title chip** — a small button pairing a `value_lever`-coloured dot with the opportunity title (truncated with ellipsis when needed). Chips stack vertically inside the cell, sorted by `strategic_category` then by opportunity index for stable ordering across renders. The earlier dot-only design (where the title was only reachable via hover) was abandoned during P7 verification because the AI clusters most opportunities into one cell, and a cluster of unlabelled dots told the reader nothing at a glance. Title chips keep the cell readable even when the dataset clusters.

If a cell would contain more than four chips, the first four chips SHALL render and the fifth slot SHALL be a `+N more` badge that opens a click-popover listing all opportunities in that cell.

#### Scenario: Cell with three opportunities stacks all three chips

- **WHEN** the High × Quick Win cell contains three opportunities at indices [0, 4, 7]
- **THEN** three title chips stack vertically in the cell in stable order
- **AND** each chip surfaces the opportunity title inline (no hover required to read it)

#### Scenario: Cell with ten opportunities shows four chips and a +6 badge

- **WHEN** a cell would contain ten opportunities
- **THEN** four chips render plus a `+6 more` badge
- **AND** clicking the badge opens a popover listing all ten opportunity titles
- **AND** clicking a title in the popover scrolls the matching opportunity card into view

### Requirement: Matrix mirrors to the PDF print export as a static block

The print export SHALL include a static rendering of the matrix between the opportunity list and the back cover. The print variant SHALL drop hover/click interactivity (no event handlers) but SHALL preserve the dot positions, quadrant labels, and dot colours so the visual landmark survives the export.

#### Scenario: PDF includes the matrix when opportunities are present

- **WHEN** the print export renders an analysis with `opportunities.length >= 1`
- **THEN** the PDF includes a section with the same layout, axes, and dots as the screen matrix
- **AND** the dots carry no `onClick` handlers in the print DOM

#### Scenario: PDF omits the matrix on sparse analyses

- **WHEN** the print export renders an analysis with `opportunities.length === 0`
- **THEN** the PDF does not include a matrix section
- **AND** the page transitions directly from the opportunity list to the back cover

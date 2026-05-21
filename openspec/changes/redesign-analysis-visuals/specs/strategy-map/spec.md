## MODIFIED Requirements

### Requirement: Strategy map renders as a Balanced Scorecard table

The screen view of the AI-generated strategy map SHALL render as a CSS-grid table with four perspective rows (Financial, Customer, Internal Processes, Organizational Capacity) and N theme columns determined by the AI output. The previous React-Flow 2D canvas rendering (chips on a free-form canvas + directed arrow edges) SHALL NOT be used.

Each cell SHALL display the objective's title (bold), the first sentence of its `definition` (muted, 2-line truncated), and an opportunity-dot strip (when the objective carries `linked_opportunity_indices`). The full Balanced-Scorecard layout requirements are owned by the `strategy-map-balanced-scorecard-layout` capability spec — this requirement only fixes that the strategy map is no longer a 2D canvas.

The rendered section SHALL fit within the same scroll-economy budget the previous canvas met: header + table + below-table elements collectively ≤ ~700 px on a populated mid-size analysis at 1,080 px viewport height.

#### Scenario: Strategy map renders as a four-row CSS-grid table

- **WHEN** an analysis page loads with a populated `strategyMap`
- **THEN** the strategy-map section renders a CSS-grid table with four perspective rows in canonical order (Financial → Customer → Internal Processes → Organizational Capacity) and N theme columns reflecting the `internalProcesses.themes[]` ordering
- **AND** no element styled as a React Flow canvas (`<div class="react-flow">`) is present in the section

#### Scenario: Strategy map fits within scroll-economy budget on 1,080px viewport

- **WHEN** the strategy-map section renders on a viewport 1,080 px tall
- **THEN** the section height (header + Vision eyebrow + Mission banner + 4-row table + Values strip) is collectively ≤ ~700 px on a typical analysis so the next page section starts within the viewport

### Requirement: Each objective cell displays title, truncated definition, and opportunity dots

Each objective cell SHALL display exactly three elements: the objective's title in bold, the first sentence of its `definition` in muted text (truncated to 2 lines with `text-overflow: ellipsis`), and — when `linked_opportunity_indices` is populated — the shared `OpportunityDotStrip` defined by the `analysis-opportunity-overlays` capability. Confidence dots (the previous 8 px coloured indicator derived from `confidence: HIGH | MEDIUM | LOW`) SHALL NOT be rendered.

#### Scenario: Cell renders title, definition, and dot strip

- **WHEN** an objective with `title: "Grow ARR"`, a two-sentence `definition`, and `linked_opportunity_indices: [0, 3]` is rendered in a cell
- **THEN** the cell shows "Grow ARR" in bold, the first sentence of `definition` in muted text (truncated if longer than 2 lines), and a two-dot `OpportunityDotStrip`

#### Scenario: Cell renders no confidence indicator

- **WHEN** any objective cell is rendered, regardless of the objective's `confidence` value
- **THEN** no element styled as a confidence dot or confidence chip is present in the cell
- **AND** the `confidence_level` field of the objective is not referenced by the renderer

### Requirement: Hover on an objective cell highlights linked opportunities

When a user hovers an objective cell with a pointer device, focuses it via keyboard, or taps it on a touch device, the cell SHALL publish a hover-highlight signal via the `OpportunityHoverProvider` carrying its `linked_opportunity_indices`. The previous tooltip behaviour (surfacing `definition` paragraph + `confidence` label + `rationale_source` text on hover) SHALL NOT be implemented — those fields are either rendered inline in the cell (definition) or removed from the visual (confidence).

The cause-and-effect arrow rendering between chips (and its associated `hypothesis`-on-hover tooltip) SHALL NOT be rendered.

#### Scenario: Mouse hover publishes the highlight signal

- **WHEN** the user moves the pointer over an objective cell with `linked_opportunity_indices: [2, 5]`
- **THEN** the `OpportunityHoverProvider` receives a `highlightOpportunities([2, 5])` call within 100 ms
- **AND** the opportunity cards at index 2 and 5 in the `OpportunitiesList` apply their highlight class

#### Scenario: Pointer leaving the cell clears the highlight

- **WHEN** the pointer leaves the cell's bounding box
- **THEN** the provider receives `clearHighlight()`
- **AND** the highlight class on the corresponding opportunity cards is removed

#### Scenario: Keyboard focus publishes the same signal as hover

- **WHEN** a keyboard user focuses an objective cell via tab
- **THEN** the same `highlightOpportunities(...)` call fires as on pointer hover

## REMOVED Requirements

### Requirement: Hovering an arrow surfaces the cause-effect hypothesis

**Reason:** The Balanced Scorecard table layout has no arrows. Cause-and-effect intent is communicated via row order (Financial at top, Org Capacity at bottom — the canonical Kaplan-Norton vertical read).

**Migration:** Arrow data continues to be produced by the AI pipeline and stored on `strategyMap.arrows`. If a future "story view" wants to surface arrows again, the data is still available without a pipeline change.

### Requirement: Arrows referencing unknown objective IDs are dropped gracefully

**Reason:** No arrows are rendered in the new layout (see above). The frontend's arrow-endpoint validation helper is therefore no longer reached at render time and can be deleted.

**Migration:** None — the helper was defensive code for a render path that no longer exists.

### Requirement: Header band collapses non-essential content behind disclosure

**Reason:** Replaced by the simpler Mission + Vision header defined in the `strategy-map-balanced-scorecard-layout` capability spec. The previous four-row stack (Vision italic line + Mission disclosure + Value Proposition chip + Strategic Priorities pill row) is collapsed into two lines (Vision eyebrow + Mission banner). Strategic Priorities content moves into the table's theme-column headers; Value Proposition rationale moves into a header tooltip.

**Migration:** Frontend renderers that read `strategyMap.mission`, `strategyMap.vision`, `strategyMap.valueProposition`, and `strategyMap.strategicPriorities` continue to work — the fields are still on the data shape. Only the rendering treatment changes.

### Requirement: Gap rows collapse to titles by default and expand on click

**Reason:** Gap rows (the "What's Missing?" section that surfaced strategy-gap rationale below the canvas) sit between the canvas and the deep-dive CTA in the current layout. With the Balanced Scorecard table absorbing the role of "show the structure", gap rows duplicate signal from the deep-dive CTA below and from the missing-cell placeholders in the table itself. Removing the gap-row UI keeps the strategy-map section focused on the table; gap rationale stays in the data and is surfaced by the `DeepDiveCTA` body copy if needed.

**Migration:** `strategyMap.gaps` data continues to flow through the API. Components that consumed it (`StrategyMapGapsRow`) are deleted as part of this change.

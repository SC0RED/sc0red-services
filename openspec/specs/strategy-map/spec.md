# strategy-map Specification

## Purpose

Screen rendering of the AI-generated strategy map as a Balanced Scorecard table (four perspective rows × N theme columns), with each cell carrying an objective's title, first-sentence definition, and opportunity-dot strip. The previous React-Flow free-form canvas (chips + directed cause-and-effect arrows) was replaced by the `redesign-analysis-visuals` change — the Balanced Scorecard table format matches the Kaplan-Norton convention PE readers expect and is the layout the AI exemplars (wawa, mobil) actually use. Cell hover publishes a highlight signal via the shared `OpportunityHoverProvider` (defined in `analysis-opportunity-overlays`); the header, responsive layout, and print parity are defined in `strategy-map-balanced-scorecard-layout`; CTA placement + analytics are defined in `analysis-detail-narrative` (under the *DeepDiveCTA distinguishes placement in analytics* requirement).

## Requirements

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

### Requirement: Theme columns derive deterministically where the schema permits

The horizontal column placement of each objective SHALL follow this priority:

1. **Financial objectives** SHALL be placed in the column of the `InternalProcessTheme` that lists their ID in `supports_financial_objectives`. If multiple themes claim the same financial objective, the first listed theme wins.
2. **Internal Process objectives** SHALL be placed in the column of their enclosing `InternalProcessTheme` (theme order in the `themes[]` array determines column index).
3. **Customer objectives** SHALL be placed in the column of the Financial objective(s) they target via outbound arrows. If a Customer objective has no outbound arrow targeting a Financial objective, it SHALL fall back to inbound arrows from Internal Process objectives. If still ambiguous, it SHALL be placed in a centre "shared" lane.
4. **Capacity objectives** SHALL be placed in the column of the Internal Process objective(s) they target via outbound arrows. If ambiguous, the same centre "shared" lane.

This algorithm is referred to as "α′ layout" in the design document. It is deterministic for Financial and Internal Process objectives (which together form the spine of a K&N strategy map) and best-effort for the other two perspectives. The algorithm is layout-agnostic — it computes column index from the data shape, regardless of whether the renderer outputs canvas chips or table cells.

#### Scenario: Financial objective placed via supports_financial_objectives

- **WHEN** the analysis has two themes — Theme A whose `supports_financial_objectives = ["F1", "F2"]` and Theme B whose `supports_financial_objectives = ["F3"]`
- **THEN** objectives F1 and F2 render in column A; objective F3 renders in column B

#### Scenario: Customer objective inferred via outbound arrow

- **WHEN** objective C1 has an arrow `{ from: "C1", to: "F1" }` and F1 is placed in column A
- **THEN** C1 renders in column A

#### Scenario: Customer objective with no disambiguating arrow lands in shared lane

- **WHEN** objective C2 has no outbound arrow to any Financial objective and no inbound arrow from any Internal Process objective
- **THEN** C2 renders in the centre "shared" lane


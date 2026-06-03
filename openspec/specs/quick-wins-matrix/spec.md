# quick-wins-matrix Specification

## Purpose

ROI × Investment 2 × 2 scatter plot rendered below the `OpportunitiesList` on the analysis detail page. Plots each opportunity by its numeric `investment_value_usd` and `roi_estimate_pct` fields on a log-scale Investment X-axis and a linear ROI Y-axis. Median split lines (computed per-analysis) define the four quadrants — Quick Wins (top-left, low investment + high ROI), Strategic Bets (top-right), Fill-Ins (bottom-left), Deprioritise (bottom-right). Opportunities the AI couldn't size (either axis `None`) land in an uncalibrated footer strip below the plot. Dots are interactive: hover pulses the matching opportunity card, click scrolls it into view. Mirrors to the PDF print export as a static block.

Introduced by the `redesign-analysis-visuals` change (Diagnostic Tool Feedback item #6). Supersedes the original categorical impact × timeline matrix from Phase 7 — Zack explicitly asked for ROI × Investment axes.

## Requirements

### Requirement: Opportunity schema carries numeric ROI + Investment fields

The `Opportunity` Pydantic model and the AI opportunity-generation prompt SHALL produce two new fields filled per-opportunity:

- `investment_value_usd: Optional[int]` — estimated USD cost to implement the opportunity end-to-end. `None` when the AI cannot infer a number from the available context (the AI MUST emit `None` rather than guess).
- `roi_estimate_pct: Optional[float]` — estimated ROI percentage in the range 0 .. 500. `None` when the AI cannot infer a number.

The AI prompt SHALL include explicit instructions that:

- `investment_value_usd` is total cash + opportunity cost of implementing the opportunity in the next 12-24 months. Software licences, integration cost, dedicated headcount fraction × salary, opportunity cost of redirected effort.
- `roi_estimate_pct` is `(annualised_value_created - annualised_cost) / annualised_cost × 100`. A 50% ROI means the opportunity returns 1.5× its cost in year one.
- Both fields MAY be `None` if the AI cannot ground the number in the provided context. **`None` is preferred over a hallucinated guess.**

The frontend `Opportunity` TypeScript type SHALL match the Pydantic model exactly:

```ts
interface Opportunity {
  // ... existing fields ...
  investment_value_usd?: number | null
  roi_estimate_pct?: number | null
}
```

#### Scenario: AI emits both fields for a well-grounded opportunity

- **WHEN** the AI generates an opportunity "Migrate to managed Postgres" with a public-cloud-pricing-grounded cost estimate
- **THEN** the `investment_value_usd` field contains an integer (e.g. `120000`)
- **AND** the `roi_estimate_pct` field contains a float (e.g. `45.0`)
- **AND** both fields validate against the Pydantic model

#### Scenario: AI emits null when it cannot estimate

- **WHEN** the AI generates an opportunity "Build a strategic partnership with X" where the implementation cost depends on negotiation outcomes
- **THEN** the `investment_value_usd` field is `None` (or absent)
- **AND** the `roi_estimate_pct` field is `None` (or absent)
- **AND** both fields validate against the Pydantic model

#### Scenario: Legacy analyses validate without the new fields

- **WHEN** an analysis persisted before this change is re-hydrated
- **THEN** every opportunity object validates against the updated `Opportunity` model
- **AND** the missing fields default to `None`

### Requirement: Analysis detail renders a Quick Wins matrix below the opportunities list

The analysis detail page SHALL render a Quick Wins matrix as a dedicated section (`<AnalysisSection id="quick-wins-matrix">`) immediately after the `OpportunitiesList` section. The matrix SHALL plot every opportunity as a dot positioned by `investment_value_usd` (X axis) and `roi_estimate_pct` (Y axis), with four quadrant labels — "Quick Wins" (top-left), "Strategic Bets" (top-right), "Fill-Ins" (bottom-left), "Deprioritise" (bottom-right) — rendered in the cell corners.

Opportunities that carry `None` for either axis SHALL render in an "uncalibrated" footer strip below the scatter, NOT in the main plot area. The strip SHALL be labelled "Opportunities without ROI / investment estimates" and use the same lever-colour treatment as in-plot dots.

#### Scenario: Matrix renders when at least one opportunity is present

- **WHEN** the analysis has `opportunities.length >= 1`
- **THEN** a `QuickWinsMatrix` component renders in an `<AnalysisSection id="quick-wins-matrix">` between `opportunities` and `document-upload`
- **AND** the section heading reads "ROI × Investment Matrix"

#### Scenario: Matrix is omitted on sparse analyses

- **WHEN** the analysis has `opportunities.length === 0`
- **THEN** no `quick-wins-matrix` section is rendered
- **AND** the page transitions directly from `opportunities` to the next section

### Requirement: Matrix axes are log-scale Investment × linear ROI

The X axis SHALL be log-scale Investment spanning 10K USD → 10M USD, with tick labels at 10K, 100K, 1M, 10M. Opportunities with `investment_value_usd < 10000` SHALL clamp visually to the 10K tick. Opportunities with `investment_value_usd > 10_000_000` SHALL clamp visually to the 10M tick.

The Y axis SHALL be linear ROI spanning 0% → 300%, with tick labels at 0%, 100%, 200%, 300%. Opportunities with `roi_estimate_pct > 300` SHALL clamp visually to the 300% tick and render with a small "↑" caret marker on the dot to indicate the clamp.

The four-quadrant split lines SHALL be drawn at the **median investment** and **median ROI** of all in-plot opportunities for that analysis (not at fixed thresholds). This keeps the quadrant labels meaningful regardless of the scan's absolute scale — a portfolio of all-low-investment opportunities still has a relative "high investment" half.

#### Scenario: High-ROI low-investment opportunity lands in the Quick Wins quadrant

- **WHEN** an opportunity has `investment_value_usd: 50000` and `roi_estimate_pct: 180.0`, and the in-plot opportunities have median investment of `200000` and median ROI of `80.0`
- **THEN** its dot is plotted in the top-left quadrant of the matrix (below the investment median, above the ROI median)
- **AND** the dot's enclosing cell carries the "Quick Wins" label

#### Scenario: High-ROI high-investment opportunity lands in Strategic Bets

- **WHEN** an opportunity has `investment_value_usd: 2_500_000` and `roi_estimate_pct: 220.0`, and the in-plot opportunities' median investment is `200000` and median ROI is `80.0`
- **THEN** its dot is plotted in the top-right quadrant
- **AND** the dot's enclosing cell carries the "Strategic Bets" label

#### Scenario: ROI above 300% clamps with caret marker

- **WHEN** an opportunity has `roi_estimate_pct: 450.0`
- **THEN** its dot is positioned at the 300% tick of the Y axis
- **AND** a "↑" caret renders adjacent to the dot to indicate the clamp

### Requirement: Opportunities without estimates render in an uncalibrated footer strip

When an opportunity has `investment_value_usd === None` or `roi_estimate_pct === None`, the matrix SHALL render its dot in a horizontal "uncalibrated" footer strip below the main scatter. The strip SHALL be a single row of dots, each clickable (same hover-provider wiring as in-plot dots).

#### Scenario: One opportunity has no ROI estimate

- **WHEN** the analysis has three opportunities, two with both fields populated and one with `roi_estimate_pct: None`
- **THEN** the scatter shows two dots
- **AND** the uncalibrated strip below the scatter shows one dot
- **AND** the strip's label reads "Opportunities without ROI / investment estimates"

#### Scenario: All opportunities lack estimates (legacy analysis pre-schema-flip)

- **WHEN** the analysis pre-dates this change and every opportunity has both axes `None`
- **THEN** the scatter renders empty (axes + quadrant labels visible)
- **AND** every opportunity dot renders in the uncalibrated strip below
- **AND** the user can still click any dot to navigate to its card

### Requirement: Each dot is interactive

Every dot — in-plot AND in the uncalibrated strip — SHALL be a button (`role="button"`) carrying the opportunity's index. Clicking or activating a dot SHALL:

1. Publish a hover-highlight signal via the `OpportunityHoverProvider` (same provider that `analysis-opportunity-overlays` defines), and
2. Imperatively scroll the matching `opportunity-card-{n}` element into view with `scrollIntoView({ behavior: 'smooth', block: 'nearest' })`.

Hover (without click) SHALL pulse the matching card via the hover provider but SHALL NOT scroll. This matches the pattern established in `analysis-opportunity-overlays` and prevents the scroll-on-hover regression PR #361 fixed.

Each dot's `title` attribute SHALL display the opportunity title + value lever (e.g. `"Launch citation-backed AI audit (Revenue Side)"`) so a hover-pointer reader sees the identity without clicking.

#### Scenario: Clicking a dot scrolls the matching opportunity card into view

- **WHEN** the user clicks a dot for the opportunity at index 3
- **THEN** the opportunity card at index 3 in the `OpportunitiesList` scrolls into view
- **AND** the card applies the standard highlight-pulse animation

#### Scenario: Hovering a dot pulses but does not scroll

- **WHEN** the user hovers (mouse-enter without click) a dot
- **THEN** the matching opportunity card receives the `.card-pulse` class
- **AND** the page does NOT scroll

#### Scenario: Dot click is keyboard-accessible

- **WHEN** a keyboard user focuses a dot via tab and presses Enter or Space
- **THEN** the same scroll + pulse fires as on click
- **AND** the dot's focus ring is visible

### Requirement: Overlapping dots are individually addressable

Opportunities whose pixel position would collide (within 4 px) SHALL render with a small jitter offset (±4 px) so each dot remains individually clickable. When a single quadrant accumulates more than 10 jittered dots, the renderer SHALL collapse them into a single "+N more" cluster pin. Clicking the cluster pin SHALL open a popover listing every opportunity in that quadrant. Clicking an entry in the popover SHALL scroll + pulse the matching opportunity card (same imperative-scroll pattern as a normal dot click).

#### Scenario: Two opportunities at the same coordinate jitter apart

- **WHEN** two opportunities have identical `investment_value_usd` and `roi_estimate_pct`
- **THEN** they render as two distinct dots offset by ~4 px so each can be individually targeted by mouse and keyboard

#### Scenario: Quadrant with 12 opportunities collapses to a cluster pin

- **WHEN** a single quadrant contains 12 opportunities after jittering
- **THEN** the quadrant renders one "+12" cluster pin (no individual dots)
- **AND** clicking the pin opens a popover listing all 12 opportunity titles
- **AND** clicking any popover entry scrolls + pulses the matching card

### Requirement: Matrix mirrors to the PDF print export as a static block

The print export SHALL include a static SVG rendering of the matrix between the opportunity list and the methodology appendix. The print variant SHALL drop hover / click interactivity (no event handlers) but SHALL preserve dot positions, quadrant labels, axis ticks, and dot colours so the visual landmark survives the export.

Opportunities in the uncalibrated strip SHALL also render in print, with the same labelled strip below the scatter.

#### Scenario: PDF includes the matrix when opportunities are present

- **WHEN** the print export renders an analysis with `opportunities.length >= 1`
- **THEN** the PDF includes a section with the same axes, quadrant labels, and dots as the screen matrix
- **AND** the dots carry no `onClick` handlers in the print DOM
- **AND** opportunities without estimates appear in the uncalibrated footer strip

#### Scenario: PDF omits the matrix on sparse analyses

- **WHEN** the print export renders an analysis with `opportunities.length === 0`
- **THEN** the PDF does not include a matrix section
- **AND** the page transitions directly from the opportunity list to the back cover

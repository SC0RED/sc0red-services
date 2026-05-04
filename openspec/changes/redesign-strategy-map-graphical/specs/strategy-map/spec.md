## ADDED Requirements

### Requirement: Strategy map renders as a 2D graphical canvas

The screen view of the AI-generated strategy map SHALL render as a
2D canvas with four horizontal perspective bands (Financial,
Customer, Internal Processes, Organizational Capacity), with each
objective rendered as a compact chip and each cause-and-effect
arrow rendered as a directed edge between chips. The canvas SHALL
use the same React Flow rendering primitive (`@xyflow/react`)
already used by the EBITDA tree.

The default rendered height of the strategy-map section
(header + canvas + gaps + below-canvas elements) SHALL be small
enough that the gaps row and at least the start of the next page
section (Top Actions / Risk Profile) are visible above the fold
on a 1,080 px viewport.

#### Scenario: Strategy map renders as four-band canvas with chips and arrows

- **WHEN** an analysis page loads with a populated `strategyMap`
- **THEN** the strategy-map section renders a React Flow canvas
  containing four horizontal bands labeled Financial, Customer,
  Internal Processes, Organizational Capacity; each band contains
  one chip per objective belonging to that perspective; arrows
  declared in `arrows[]` render as directed edges between the
  source and target chips

#### Scenario: Strategy map fits within scroll-economy budget on 1,080px viewport

- **WHEN** the strategy-map section renders on a viewport 1,080 px
  tall
- **THEN** the section height is small enough that the
  `What's Missing?` gaps row remains visible without scrolling on
  a typical analysis (vision + value-prop chip header + 4-band
  canvas + gaps row collectively ≤ ~700 px)

### Requirement: Each objective chip displays minimal identity by default

Each chip SHALL display only its objective ID, a single-line title
(truncated with ellipsis if longer than the chip width), and an
8 px coloured confidence dot. The full definition, the literal
HIGH/MEDIUM/LOW confidence label, and the `rationale_source` (when
present) SHALL NOT be displayed in the default chip state.

The confidence dot colour SHALL reuse the existing risk-tier
palette: HIGH → `var(--risk-low)` (green), MEDIUM →
`var(--risk-moderate)` (amber), LOW → `var(--risk-high)`
(red/orange).

#### Scenario: Chip in default state shows ID, truncated title, and confidence dot

- **WHEN** a chip renders in the canvas without focus or hover
- **THEN** the chip's content is exactly: the objective ID (e.g.
  `F1`, `C2`, `I1.3`, `O.P`), a single line of title text, and an
  8 px circular confidence dot

#### Scenario: Confidence dot colour matches risk-tier palette

- **WHEN** a chip renders for an objective with `confidence: HIGH`
- **THEN** the dot's `background-color` resolves to
  `var(--risk-low)`

- **WHEN** the objective has `confidence: MEDIUM`
- **THEN** the dot's colour resolves to `var(--risk-moderate)`

- **WHEN** the objective has `confidence: LOW`
- **THEN** the dot's colour resolves to `var(--risk-high)`

### Requirement: Hovering or focusing a chip surfaces the full definition

When a user hovers a chip with a pointer device or focuses it via
keyboard or touch, a tooltip SHALL appear that contains the full
`definition` paragraph, the literal confidence label
(`HIGH` / `MEDIUM` / `LOW`), and the `rationale_source` text if
present. The tooltip SHALL dismiss when the chip loses
hover/focus.

The interaction pattern SHALL match the EBITDA tree's
`EbitdaNodeComponent` hover-tooltip behaviour so the user
experience of detail-on-spatial-node is consistent across the
analysis page.

#### Scenario: Mouse hover surfaces tooltip with full content

- **WHEN** the user moves the pointer over a chip on a desktop
  browser
- **THEN** a tooltip appears within 100 ms containing the full
  definition paragraph, the confidence label
  (`HIGH` / `MEDIUM` / `LOW`), and the `rationale_source` if it
  is present in the data

#### Scenario: Touch device tap exposes the same tooltip

- **WHEN** the user taps a chip on a touch device
- **THEN** the chip enters its focused state (React Flow's
  default selection behaviour) and the tooltip appears with the
  same content as on hover

#### Scenario: Pointer leaving the chip dismisses the tooltip

- **WHEN** the pointer leaves the chip's bounding box (mouse) or
  the user taps elsewhere on the canvas (touch)
- **THEN** the tooltip is removed from the DOM and the chip
  returns to its default appearance

### Requirement: Hovering an arrow surfaces the cause-effect hypothesis

When a user hovers an arrow edge with a pointer device or focuses
it, a tooltip SHALL appear that contains the `hypothesis` text
of that arrow.

#### Scenario: Hover an arrow shows its hypothesis

- **WHEN** the user hovers an arrow connecting two chips
- **THEN** a tooltip appears containing the `hypothesis` text of
  that arrow, anchored near the cursor

### Requirement: Theme columns derive deterministically where the schema permits

The horizontal column placement of each chip SHALL follow this
priority:

1. **Financial chips** SHALL be placed in the column of the
   `InternalProcessTheme` that lists their ID in
   `supports_financial_objectives`. If multiple themes claim the
   same financial objective, the first listed theme wins.
2. **Internal Process chips** SHALL be placed in the column of
   their enclosing `InternalProcessTheme` (theme order in the
   `themes[]` array determines column index).
3. **Customer chips** SHALL be placed in the column of the
   Financial chip(s) they target via outbound arrows. If a
   Customer chip has no outbound arrow targeting a Financial
   chip, it SHALL fall back to inbound arrows from Internal
   Process chips. If still ambiguous, it SHALL be placed in a
   centre "shared" lane.
4. **Capacity chips** SHALL be placed in the column of the
   Internal Process chip(s) they target via outbound arrows. If
   ambiguous, the same centre "shared" lane.

This algorithm is referred to as "α′ layout" in the design
document. It is deterministic for Financial and Internal Process
chips (which together form the spine of a K&N strategy map) and
best-effort for the other two perspectives.

#### Scenario: Financial chip placed via supports_financial_objectives

- **WHEN** the analysis has two themes — Theme A whose
  `supports_financial_objectives = ["F1", "F2"]` and Theme B whose
  `supports_financial_objectives = ["F3"]`
- **THEN** chips F1 and F2 render in column A; chip F3 renders in
  column B

#### Scenario: Customer chip inferred via outbound arrow

- **WHEN** chip C1 has an arrow `{ from: "C1", to: "F1" }` and F1
  is placed in column A
- **THEN** C1 renders in column A

#### Scenario: Customer chip with no disambiguating arrow lands in shared lane

- **WHEN** chip C2 has no outbound arrow to any Financial chip
  and no inbound arrow from any Internal Process chip
- **THEN** C2 renders in the centre "shared" lane

### Requirement: Arrows referencing unknown objective IDs are dropped gracefully

The layout helper SHALL validate every arrow's `from` and `to`
endpoints against the assembled chip set and SHALL omit any arrow
whose endpoint is not a known chip. The omission SHALL log a
`console.warn` in development builds and SHALL NOT prevent the rest
of the strategy map from rendering.

This guards against a known AI-output failure mode where Step 7 of
the generation pipeline occasionally emits arrows referencing
objective IDs that don't exist in the assembled output.

#### Scenario: Arrow with unknown from-id is silently dropped

- **WHEN** the data contains `{ from: "F9", to: "C1", hypothesis: "..." }`
  but no chip with ID `F9` exists in the assembled map
- **THEN** the arrow is not rendered as an edge, the rest of the
  canvas renders normally, and a `console.warn` is logged in
  development builds

### Requirement: Header band collapses non-essential content behind disclosure

The header band above the canvas SHALL render the vision and
value-proposition prominently and SHALL collapse the mission and
the value-proposition rationale behind progressive disclosure:

- **Vision** SHALL render as a single italic line. Text exceeding
  the line width SHALL be truncated with CSS ellipsis. Hovering
  or focusing the line SHALL surface the full text in a tooltip.
- **Mission** SHALL render with only its label visible. The
  statement SHALL be hidden behind a native `<details>` disclosure
  whose summary is `Mission ▾`. The disclosure SHALL be closed by
  default.
- **Value Proposition** SHALL render as the existing chip
  (e.g. `Customer Intimacy`). The `rationale` text SHALL move into
  a tooltip on the chip rather than rendering inline.
- **Strategic Priorities** SHALL render as a legend pill row
  above the React Flow canvas (each priority is its own pill,
  positioned outside the canvas). Each priority SHALL show its
  `name`; the `result` text SHALL move into a hover/focus tooltip
  on the pill. The 1:1 correspondence between `strategicPriorities[i]`
  and `internalProcesses.themes[i]` is encoded by ordering — first
  priority pill corresponds to leftmost theme column, etc. (See
  design.md decision D3 for why the legend pattern was chosen
  over canvas-internal column headers.)

#### Scenario: Mission is closed by default

- **WHEN** the strategy-map section renders fresh
- **THEN** the mission `<details>` element is closed; only the
  `Mission ▾` summary is visible

#### Scenario: User opens mission disclosure

- **WHEN** the user clicks `Mission ▾`
- **THEN** the `<details>` opens and reveals the full mission
  statement

#### Scenario: Vision tooltip surfaces full text on overflow

- **WHEN** the vision statement is longer than the available
  width and the user hovers the truncated line
- **THEN** a tooltip appears with the full text

### Requirement: Gap rows collapse to titles by default and expand on click

The `What's Missing?` panel SHALL render each gap as a single row
showing only the gap ID and title, with the description and the
deep-dive framing hidden by default. Clicking a gap row SHALL
expand it inline to show the full description and the deep-dive
framing. The panel SHALL implement single-open accordion
behaviour: clicking a different gap SHALL collapse the previously
open gap.

The interaction pattern SHALL match `OpportunitiesList`'s
expand-row behaviour, including `aria-expanded` and `aria-controls`
attributes for screen-reader compatibility.

#### Scenario: Gap row collapsed by default

- **WHEN** the strategy-map section renders fresh
- **THEN** every gap row in the `What's Missing?` panel shows
  only `<id> · <title>` with `aria-expanded="false"`; description
  and deep-dive framing are not in the DOM (or are
  visually hidden)

#### Scenario: Click gap expands its detail inline

- **WHEN** the user clicks a collapsed gap row
- **THEN** the row expands to show the full `description`
  paragraph and the italic `deepDiveFraming` sentence;
  `aria-expanded` becomes `"true"`

#### Scenario: Click another gap closes the previous

- **WHEN** the user clicks a different gap while one is already
  expanded
- **THEN** the previously expanded gap collapses and the new gap
  expands

### Requirement: DeepDiveCTA headline variant renders at the top of analysis page

The headline `DeepDiveCTA` (the "Want a deeper analysis?" call to
action) SHALL render at the top of `AnalysisDetail`, immediately
under the analysis action buttons (export PDF, delete). It SHALL
NOT render below the strategy map's `WhatsMissingPanel`.

This relocates the conversion affordance to a position visible
above the fold for every analysis page load, regardless of how
much the user scrolls.

#### Scenario: CTA visible without scrolling on analysis page load

- **WHEN** the user lands on an analysis page that has a
  populated `strategyMap`
- **THEN** the headline `DeepDiveCTA` is rendered above the
  strategy map within the visible viewport

#### Scenario: CTA does not render below the gaps panel

- **WHEN** the user scrolls past the strategy map and the
  `What's Missing?` panel
- **THEN** there is no headline `DeepDiveCTA` rendered between
  the gaps panel and the next page section

### Requirement: Strategy-map CTA emits rendered and clicked analytics events

The headline `DeepDiveCTA` SHALL emit
`sc0red_cta_rendered_strategy_map` once per mount (via
`useEffect`) and SHALL emit `sc0red_cta_clicked_strategy_map` on
the contact link's `onClick`. Both events MUST carry
`source: "web"` and MUST carry `active_lever_filter: null` (the
strategy-map surface has no lever-filter concept; backend
validation rejects non-null filters on these event types).

The `_rendered` event semantic in v1 is "the analysis page that
contains a strategy map has loaded", not "the user scrolled the
strategy map into view". This is a known relaxation introduced by
relocating the CTA to the top of the page; if funnel analysis
later requires viewport-based impression accounting, a separate
`IntersectionObserver`-driven event can be added without
redefining the existing one.

#### Scenario: Mount fires the rendered event once

- **WHEN** an analysis page with a populated `strategyMap` first
  loads
- **THEN** exactly one `sc0red_cta_rendered_strategy_map` event
  posts to `/api/analytics/events` with
  `analytics_context = { analysisId, opportunityCount: 0, activeLeverFilter: null }`

#### Scenario: Click fires the clicked event before navigation

- **WHEN** the user clicks the CTA's contact link
- **THEN** a `sc0red_cta_clicked_strategy_map` event fires (fire
  and forget; `keepalive: true` ensures delivery survives the
  new-tab navigation)

#### Scenario: Rerender with same analysisId does not re-fire the rendered event

- **WHEN** the component rerenders with an unchanged `analysisId`
  (e.g. parent re-renders for unrelated reasons)
- **THEN** the `sc0red_cta_rendered_strategy_map` event does not
  fire a second time

### Requirement: Print PDF view is unchanged

The PDF export's strategy-map rendering (`PrintStrategyMap.tsx`
and `PrintStrategyMapObjectives.tsx`) SHALL continue to use the
existing verbose vertical layout. None of the screen-redesign
behaviours specified above (graphical canvas, hover tooltips,
disclosure, click-to-expand gaps) apply to the print surface.

Paper has no scroll constraint; the verbose layout remains the
right artefact for print.

#### Scenario: PDF export preserves verbose layout

- **WHEN** a user exports an analysis to PDF
- **THEN** the strategy-map page in the PDF renders all
  objectives as fully-expanded cards in a vertical stack,
  matching the layout that shipped in PR #239

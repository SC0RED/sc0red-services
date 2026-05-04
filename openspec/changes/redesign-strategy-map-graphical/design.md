## Context

PR #239 shipped the AI-generated strategy map as a vertical stack of
fully-expanded objective cards. The result is correct but UX-hostile:
on a typical analysis the section is 1,500–1,800px tall, and the
deep-dive CTA — the funnel's conversion mechanic — sits at the
bottom. The user has to scroll past the entire strategy map and gaps
panel before reaching Top Actions, Risk Profile, Opportunities,
EBITDA, and Value Chain.

The product brief framed the strategy map as a *conversion artifact*:
buyers see the canonical Kaplan & Norton structure, recognise it as
work product, then convert via the deep-dive CTA. The current
rendering shows the *inputs* of a strategy map (objectives, themes,
gaps) but doesn't compose them into the canonical 2D shape with
cause-and-effect arrows that "looks like" a strategy map. The
`arrows[]` data — 5–12 testable cause-effect hypotheses produced by
Step 7 of the pipeline — is generated but never rendered.

The codebase already uses `@xyflow/react` for the EBITDA tree
(`EbitdaTree.tsx` + `EbitdaNodeComponent.tsx`). That gives us a
proven pattern for chips + edges + hover-tooltip + pan/zoom +
mobile touch + accessibility — and reusing it is the cheapest path
to a graphical map that visually integrates with the rest of the
analysis page.

Constraints in scope:

- Backend, Pydantic models, JSON schema, AI prompts: **unchanged**.
  This is a screen-only redesign.
- Print PDF view (`PrintStrategyMap.tsx`): **unchanged**. Paper has
  no scroll constraint; the verbose layout works there.
- Frontend file size cap: 360 lines per component (CLAUDE.md).
- Consistency: where we have an interaction pattern elsewhere on
  the analysis page, the strategy-map redesign matches it. Spatial
  graph elements follow EBITDA's hover-tooltip pattern; list rows
  follow OpportunitiesList's click-to-expand-inline pattern.

## Goals / Non-Goals

**Goals:**

- Default screen height for the strategy-map section ≤ ~700 px so
  the gaps row + CTA + at least the start of the next section
  (Top Actions / Risk Profile) are visible above the fold on a
  typical 1,080 px viewport.
- Render the canonical K&N 2D structure: four perspective bands,
  objective chips, theme columns, cause-and-effect arrows.
- Detail surfaces consistently with the rest of the analysis
  page (chip hover for graph nodes; click-to-expand for gap rows).
- Mobile-friendly via React Flow's built-in pan/zoom + tap-to-focus.
- Zero data shape changes (no Pydantic/schema/prompt churn). All
  layout decisions derive from data the schema already guarantees.
- Existing PDF export keeps its verbose presentation.

**Non-Goals:**

- Adding a `theme` field to `FinancialObjective`, `CustomerObjective`,
  `CapacityObjective`. (Considered as decision D2; deferred to a
  follow-up proposal as a v2 hardening.)
- Adding new analytics events. The existing `_rendered_strategy_map`
  / `_clicked_strategy_map` events keep firing on the relocated
  CTA.
- Editing/admin UI. The strategy map remains read-only.
- Per-gap inline CTAs (the inline `DeepDiveCTA` variant exists
  but is not yet rendered; this redesign does not change that).
- Re-styling unrelated analysis sections (Top Actions, Risk Profile,
  Opportunities) for visual coherence. Out of scope for this change.

## Decisions

### D1. Use `@xyflow/react` for the strategy map canvas

**Decision**: render the four perspective bands + chips + arrows as
a React Flow canvas, with a custom `StrategyMapNode` component
mirroring the structure of `EbitdaNodeComponent.tsx`.

**Alternatives considered:**

- **CSS grid + absolutely-positioned SVG arrow overlay.** Cheaper
  for the chip layout but the arrow overlay is brittle. Routing
  Bezier curves around chip boundaries, recomputing on resize, and
  handling responsive layout is exactly what graph libraries
  exist to solve. Mobile touch (pan/zoom) would have to be
  hand-rolled.
- **A different graph library (`reactflow` v11, `react-archer`,
  `react-xarrows`).** Adds a new dependency for a problem the
  existing one already solves. `@xyflow/react` is the React Flow
  package's current name (formerly `reactflow`); we already pinned
  it via the EBITDA tree.

**Rationale:** consistency wins on three axes — same library, same
hover-tooltip pattern, same mobile pan/zoom story. Zero new
dependencies. The custom-node pattern already exists in the
codebase as a proven template.

### D2. Theme-column placement uses data the schema guarantees, falls back to arrows for the rest

**Decision**: compute each chip's theme-column index using a
two-pass algorithm (`α′` per the explore-mode discussion):

1. **Direct membership** (deterministic):
   - Each `InternalProcessObjective` belongs to its enclosing
     `InternalProcessTheme`. Theme order in the array gives the
     column index.
   - Each `FinancialObjective` belongs to whichever theme(s) list
     it in `supports_financial_objectives`. If multiple, the
     left-most theme wins (or place in a shared lane — see fallback
     rules below).
2. **Arrow inference** (best-effort) for objectives the schema
   doesn't anchor:
   - Each `CustomerObjective` C* — find arrows from C* targeting
     any `FinancialObjective` F*; place C* in F*'s column. Fall
     back to arrows from any `InternalProcessObjective` I* into
     C* (reverse arrow walk). If still ambiguous, place in the
     shared centre lane.
   - Each `CapacityObjective` O.* — find arrows from O.* targeting
     any I*; place O.* in the column of the I*'s theme. Same
     shared-centre fallback.

**Alternatives considered:**

- **Pure arrow-driven layout (`α`).** Cluster the arrow graph
  into connected components, place each component as a column.
  Simpler but ignores the theme membership the schema already
  guarantees — Financial chips would land in arbitrary columns
  even though `supports_financial_objectives` already declares
  the right answer.
- **Schema enhancement: add `theme` field to all objectives
  (`β`).** Add a required `theme: str` field on
  `FinancialObjective`, `CustomerObjective`,
  `CapacityObjective`. Requires updating the JSON schema + 3
  prompt templates + Pydantic + frontend types + tests.
  Deterministic for every chip but a much bigger change.

**Rationale:** `α′` produces a deterministic column for every
Financial and Internal-Process chip (which are the spine of a
K&N strategy map — the financial outcomes and the internal
processes that produce them). Customer and Capacity columns fall
out of arrows in the typical case; a sparse-arrow analysis falls
through to a centre lane that visually communicates "spans
multiple themes" rather than mis-attributing. Code complexity
is small (~120 lines of pure functions, fully unit-testable).
The renderer is identical to what `β` would render, so a future
upgrade to `β` swaps only the layout pre-pass.

### D3. Header band layout — collapse mission, keep vision and value-prop visible

**Decision**:

- **Vision**: rendered as a single italic line. Truncate at the
  CSS level (`white-space: nowrap; text-overflow: ellipsis`).
  Hover or focus reveals the full statement in a tooltip. Synthesised
  marker (`(synthesised)` label) stays.
- **Mission**: not rendered by default. Hidden behind a
  `<details>` disclosure (`Mission ▾`). The label is always
  visible; opening shows the full statement.
- **Value Proposition**: chip stays visible (small pill with
  `Customer Intimacy` / `Operational Excellence` / `Hybrid` etc.).
  The `rationale` text moves out of the header into the chip's
  own hover tooltip.
- **Strategic Priorities**: rendered as a **legend pill row above
  the React Flow canvas** (not as canvas-internal column headers
  as initially considered — see "Implementation deviation" below).
  Each priority shows just `name`; the `result` text moves into a
  hover/focus tooltip on the pill.

  *Implementation deviation:* an earlier draft of this section
  specified "column headers above the perspective bands inside the
  React Flow canvas (visually defining the theme columns the chip
  layout uses)". During implementation that approach turned out to
  carry costs disproportionate to the benefit:
  - Required a new node type rendered at `y < 0` (above the
    Financial band), with custom rendering distinct from chip nodes.
  - Header position would track the canvas camera — when the user
    pans/zooms, the headers move with the chips (potentially
    desired for alignment, potentially confusing).
  - Theme column widths can vary with the largest chip; perfectly
    pixel-aligned headers would need a custom layout pass.
  - Headers as React Flow nodes are read by screen readers in
    canvas-tree order alongside chips, mixing decorative labels
    with semantic content.

  The chosen pill-legend pattern is simpler, accessible
  (a separate semantic block above the canvas), and mobile-friendly
  (no canvas zoom interaction). The 1:1 connection between
  `strategicPriorities[i]` and `internalProcesses.themes[i]` is
  encoded by ordering — first priority corresponds to leftmost
  theme column, etc. If user testing reveals readers can't make
  the connection from ordinal correspondence alone, we revisit
  with explicit visual gridlines or column-internal labels.

**Rationale:** this collapses the header from ~240 px to ~80 px
while keeping the most identity-relevant pieces (vision quote,
value proposition) visible. Mission is the most paragraph-like
field and benefits most from disclosure.

### D4. Detail interaction patterns match the rest of the analysis page

**Decision**:

- **Chips and edges** (spatial graph elements) use the EBITDA
  tree's hover/focus tooltip pattern. No click action in v1.
  Mobile users get the tooltip on tap-to-focus (React Flow's
  default selection behaviour) without any custom code.
- **Gap rows** (list elements) use `OpportunitiesList`'s
  click-to-expand-inline pattern. Single-open accordion: clicking
  a gap collapses any other open gap. Default state is collapsed
  (only `id · title` visible). Expanded state shows the
  `description` paragraph and the `deepDiveFraming` italic
  sentence (the existing render of the panel).
- **`Mission ▾` disclosure** uses the native HTML `<details>`
  element for accessibility-by-default.

**Alternatives considered:**

- **Click-to-open-drawer for chip detail** (modal sheet that
  slides in from the side). More space for content but breaks
  the spatial mental model (the user loses the map context while
  reading detail). Rejected for v1; could revisit if hover
  tooltips prove too small for the longer definitions.
- **Always-expanded gaps with virtualised list.** Saves a click
  but reproduces the verbosity problem the redesign is trying
  to solve.

**Rationale:** maximum consistency with patterns the user already
sees elsewhere on the analysis page. Each interaction is one the
user has already learned by the time they reach the strategy map.

### D5. Confidence visualisation: 8px coloured dot on chip, full label in tooltip

**Decision**:

- Chip displays an 8 px circular dot positioned in the chip's
  header next to the ID. Color follows the existing risk palette:
  - HIGH → `var(--risk-low)` (green)
  - MEDIUM → `var(--risk-moderate)` (amber)
  - LOW → `var(--risk-high)` (red/orange)
- The full text label (`HIGH` / `MEDIUM` / `LOW`) appears inside
  the chip's hover tooltip alongside the definition.

**Alternatives considered:**

- **Keep the existing `ConfidenceChip` text pill on the chip.**
  At ~60 px wide it dominates the chip. Visually noisy at the
  density we want.
- **Drop the dot entirely; rely only on chip border colour.** The
  chip border is already used for theme-column tinting in
  Internal Processes; reusing it for confidence creates two
  meanings on one signal. Keep them separate.

**Rationale:** dot reuses the colour vocabulary already in use on
the analysis page (risk badges, EBITDA value-lever dots), keeping
the screen palette unified. The existing `ConfidenceChip`
component is preserved unchanged for use inside the tooltip and
in the print view.

### D6. CTA placement: top of `AnalysisDetail`, below export/delete

**Decision**: move the headline `DeepDiveCTA` from below the
strategy map (currently rendered in `AnalysisDetail.tsx` after
`StrategyMapView`) to a new position immediately under the action
buttons in the analysis header (export PDF, delete, etc.). The
strategy map's `WhatsMissingPanel` no longer has a CTA below it.

**Rationale:** the CTA is the funnel mechanic. Persistent
visibility above the fold is more valuable than narrative ramping.
The gaps still surface specific deep-dive framings inside their
expandable rows; the conversion affordance is just always
reachable.

**Trade-off accepted:** the `sc0red_cta_rendered_strategy_map`
event currently fires on `useEffect` mount. With the CTA at the
top of the page, "mount" no longer means "the user saw the map."
For v1 we accept that the impression event becomes "loaded an
analysis page that has a strategy map." The `_clicked` event
remains a clean signal. If funnel analysis later shows the looser
impression definition is unhelpful, we can wire an
`IntersectionObserver` on the strategy map itself and emit a
distinct `_strategy_map_in_view` event without redefining the
existing one.

### D7. Layout helper as a pure function module

**Decision**: implement the column-assignment + node/edge construction
in a pure-function helper module (`strategyMapLayout.ts`) with
no React dependencies. Inputs: a `StrategyMap` object. Outputs:
`{ nodes: Node[], edges: Edge[] }` typed against `@xyflow/react`'s
`Node` / `Edge`.

**Rationale:**

- Pure functions are unit-testable without rendering the React
  Flow canvas.
- Keeps `StrategyMapView.tsx` focused on composition (header,
  canvas, gaps panel) under the 360-line limit.
- Locates the algorithm in one place — when (or if) we move to
  decision `β` the only file that changes is
  `strategyMapLayout.ts` and a couple of tests.

## Risks / Trade-offs

- **Sparse arrows produce ambiguous Customer/Capacity column
  placement.** → Fall back to a centre "shared" lane that
  visually communicates "spans multiple themes." Not wrong, just
  less specific. Hardenable later via decision `β`.
- **AI sometimes emits arrows referencing nonexistent objective
  IDs** (review feedback raised this in PR #239 as a MEDIUM that
  was deferred). → The layout helper validates every arrow's
  endpoints against the assembled chip set; arrows pointing at
  unknown IDs are dropped (with a `console.warn` in dev mode and
  a log line that flows to CloudWatch via the analytics-error
  proxy). Visual degrades gracefully; data correctness is not
  compromised.
- **Edge density (5–12 arrows) can look messy** when many cross.
  → React Flow's bezier curve routing + ordering edges by source
  band → target band reduces crossings. We additionally render
  edges at lower opacity than chips so the chip layer reads as
  primary content.
- **Mobile chip text truncation on narrow screens.** → React
  Flow viewport pinch-zoom is built-in. Chips on first render
  show ID + 1-line truncated title; tap → tooltip surfaces full
  text. Tested against an iPhone 12 viewport (390 px wide) is
  added to the tasks list.
- **Hover-only on touch devices loses the tooltip.** → React Flow
  selects nodes on tap by default; we hook the same selection state
  used by `EbitdaNodeComponent`'s `hovered` flag. The tooltip
  surface is identical for hover-with-mouse and tap-to-focus. The
  only failure mode is users not knowing tap exposes detail; we
  add a one-line "tap a chip for detail" hint near the canvas
  header on viewports under 768 px.
- **Existing visual regression snapshots will need to be
  regenerated.** → The redesign is the point. We document the
  snapshot regeneration in the verification section of `tasks.md`.
- **Print PDF stays verbose** while the screen view changes —
  divergent rendering between surfaces. → Acceptable: paper and
  screen optimise for different constraints (no scroll on paper;
  scroll-economy on screen). The PDF code path is fully
  separate (`frontend/src/components/print/PrintStrategyMap.tsx`)
  and explicitly out of scope.
- **Header band collapse (mission disclosure) hides content from
  shallow scanners.** → Mission label always visible; the
  disclosure is one click. Vision and value-prop — the most
  identity-defining pieces — remain visible. We accept this.

## Migration Plan

This is a frontend-only screen redesign.

1. Land the new layout helper, custom node, and rewritten
   `StrategyMapView` behind no flag — there is no analytics-driven
   choice between old and new, and the data shape is unchanged.
   Browsers refresh, see the new layout.
2. Existing analyses persisted under the old code path render
   correctly under the new code path: nothing about the data
   format has changed.
3. PDF export continues to render the verbose layout via
   `PrintStrategyMap.tsx`. No coordinated migration needed.
4. Visual regression snapshots are regenerated as part of the PR.
5. If the redesign produces an unfixable layout bug for some class
   of analysis (e.g. a 12-arrow analysis where chips overlap
   beyond what edge routing can clear), rollback is `git revert`
   of the merge — the old code path is fully recoverable from
   history without a data migration.

## Open Questions

- Is the centre "shared" lane visually intuitive to users when an
  analysis has sparse arrows, or does it look like a layout bug?
  Worth a quick review with one or two pre-funding analyses
  before merge.
- The hint text "tap a chip for detail" on mobile — is that
  actually needed, or does iOS/Android default behaviour
  communicate it? Defer to manual testing in the verification
  task.

## Why

PR #251 (`analysis-detail-consistency-wrapper`) standardized section heading rendering through `<AnalysisSection title={...}>`. To preserve the help-tooltip affordance next to titles like "EBITDA Impact Model" and "AI Opportunities", callers pass a fragment `<>{text}<HelpTooltip term="..." /></>` as the title prop. Visually correct.

But the architecture-reviewer's pass-1 review explicitly flagged the cost: *"the accessible name of the h2 includes the button's `aria-label` ("What is EBITDA Tree?"), making the full computed accessible name longer than just the visible text."* When `<HelpTooltip>` lives inside an `<h2>`, screen readers compute the heading's accessible name by concatenating descendants — including the trigger button's `aria-label`. A screen-reader user hears `"AI Opportunities 3 What is Impact Rating?"` as one run-on heading.

The UX review (`Janus-Analysis-Page-Review-2-UX.pdf`, Audit 1 + Audit 6) flagged the same anti-pattern from the user-visible side. The recommended fix is to render the help affordance as a **sibling** of the heading, not a child — so the `<h2>`'s accessible name is just the title text, and the help button is a separate focusable element next to it.

This is debt we knowingly shipped. Closing it now is a 1-PR, M-sized change.

`HelpTooltip` is well-built and used elsewhere (table column headers via `SortableHeader`); we are NOT replacing the component — we are fixing how it composes with `<AnalysisSection>` so it stops contaminating the heading's accessible name.

## What Changes

- **Add** an optional `titleAdornment?: ReactNode` slot to `AnalysisSection`. When provided, renders inside the same flex row as the `<h2>` but as a sibling — NOT inside the heading element. The heading's accessible name stays clean; the adornment is independently focusable and announceable.
- **Migrate** the 3 existing call sites in `AnalysisDetail.tsx` (`ebitda` / `value-lever` / `opportunities` sections) to use the new slot:
  - Title prop becomes a plain string
  - HelpTooltip moves to `titleAdornment={<HelpTooltip term="..." />}`
- **Verify** `HelpTooltip` itself needs no changes — its existing API (button with `aria-label`, popover with `role="tooltip"`) works correctly when rendered as a sibling rather than a descendant of `<h2>`.
- **Update tests**: `AnalysisDetail.test.tsx` page-level heading-framing assertions still pass (heading text inside the wrapper); add new assertions that the `<h2>`'s computed accessible name does NOT include the help-tooltip text. `AnalysisSection.test.tsx` adds tests for the `titleAdornment` slot — renders next to title, NOT inside `<h2>`.
- **No changes** to `HelpTooltip.tsx`, `help-content.ts`, or other `HelpTooltip` consumers (`SortableHeader`).

This is **NOT** the UX review's full "DefinitionPopover everywhere" recommendation — that scope (Audit 6) calls for definitions on risk dimensions, confidence markers, Top 3 Actions, and more. Those are deferred. This proposal closes the structural a11y bug at the section-heading layer specifically; broader rollout of help affordances to currently-undocumented terms is a separate proposal.

## Capabilities

### New Capabilities

<!-- None. -->

### Modified Capabilities

- `analysis-detail-narrative`: extends the `AnalysisSection` component contract with a new optional `titleAdornment` prop, and adds a requirement that the heading's accessible name SHALL NOT include adornment text. Modified scenarios for sections that today render with help-tooltip-in-title.

## Impact

**Code:**
- `frontend/src/components/analysis/AnalysisSection.tsx` — add `titleAdornment?: ReactNode` prop; render it as a flex sibling of `<h2>`, not inside
- `frontend/src/app/(authenticated)/analysis/[analysisId]/AnalysisDetail.tsx` — 3 sections (`ebitda`, `value-lever`, `opportunities`) move HelpTooltip from `title={<>...<HelpTooltip /></>}` to `titleAdornment={<HelpTooltip term="..." />}`. Title props become plain strings (or string + count badge for Opportunities).
- `frontend/src/tests/components/analysis/AnalysisSection.test.tsx` — new tests for the `titleAdornment` slot
- `frontend/src/tests/pages/AnalysisDetail.test.tsx` — assertions on the `<h2>`'s accessible name excluding adornment text
- `frontend/src/app/globals.css` — possible new `.section-header-row` class if the flex layout needs CSS support; otherwise the `AnalysisSection` component renders the row inline

**Surfaces affected:**
- Analysis detail page success path (the 3 sections that currently use HelpTooltip in their title)

**Data / APIs / dependencies:** none

**Out of scope (explicitly deferred to separate proposals):**
- Adding HelpTooltip to currently-undocumented terms (risk dimensions, Top 3 Actions, Strategic Priorities, confidence markers — UX Audit 6's broader recommendation)
- Renaming `HelpTooltip` to `DefinitionPopover` (UX review used the latter as a hypothetical name; the existing component name is established and used by `SortableHeader`)
- Vertical rhythm tokens (UX Audit 8 — separate `card-density-variants` and `section-spacing-tokens` proposals already queued)
- ExpandableCard, ConfidenceIndicator, ProvenanceMarker (later proposals in the queue per the UX review's priority order)

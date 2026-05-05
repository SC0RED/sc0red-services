## Context

Three section headings on the analysis detail page currently render help-tooltip affordances inside their `<h2>`:

```tsx
// AnalysisDetail.tsx — ebitda section
<AnalysisSection
    id="ebitda"
    title={
        <>
            EBITDA Impact Model
            <HelpTooltip term="ebitda_tree" />
        </>
    }
>
    <EbitdaSection ... />
</AnalysisSection>
```

`AnalysisSection` renders `title` as `{title != null && <h2 className="section-header">{title}</h2>}`. So the produced DOM is:

```html
<h2 class="section-header">
  EBITDA Impact Model
  <span class="help-tooltip">
    <button aria-label="What is EBITDA Tree?">⓵</button>
    <span role="tooltip" class="help-tooltip-popover" data-state="closed" aria-hidden="true">
      EBITDA Tree definition...
    </span>
  </span>
</h2>
```

Per the [W3C accessible name computation algorithm](https://www.w3.org/TR/accname-1.2/), an element's accessible name is built by walking its descendants and concatenating their text content (or `aria-label` for elements that have one). For our `<h2>`, that produces:

```
"EBITDA Impact Model What is EBITDA Tree?"
```

A screen-reader user navigating headings hears this as ONE run-on phrase. NVDA, JAWS, and VoiceOver all behave consistently here. The architecture-reviewer flagged it in PR #251's pass 1 review:

> *"The accessible name of the h2 includes the button's `aria-label` ('What is EBITDA Tree?'), making the full computed accessible name longer than just the visible text. The heading-framing tests at lines 903 and 915 correctly use regex matchers (`/EBITDA Impact Model/`, `/Value Impact/`) for this reason."*

The review accepted it as a known limitation and moved on. This proposal closes that.

## Goals / Non-Goals

**Goals:**

- The accessible name of the page-level `<h2>` for sections like "EBITDA Impact Model" SHALL be exactly the visible heading text — no concatenation of help-tooltip button labels.
- The help-tooltip affordance remains visually next to the heading (same row, right of the title), keyboard-focusable, screen-reader-discoverable as a separate element.
- Existing `HelpTooltip` component is unchanged. `SortableHeader`'s use of `HelpTooltip` is unchanged (table column headers don't have the `<h2>` accessible-name issue — column header text isn't a heading element).
- Tests pin the new contract: `getByRole('heading', { name: 'Exact Title' })` matches by exact name, not regex.

**Non-Goals:**

- NOT replacing `HelpTooltip` with a new "DefinitionPopover" component. The existing component works correctly outside heading contexts.
- NOT adding help-tooltips to terms that don't have one today (risk dimensions, confidence markers, Top 3 Actions, etc. — UX Audit 6's broader recommendation). Separate proposal.
- NOT changing the visual appearance of the help-tooltip button or its popover.
- NOT touching `SortableHeader` or any other `HelpTooltip` consumer.
- NOT vertical-rhythm tokens or banded backgrounds (UX Audit 8 — separate proposal).
- NOT changing `AnalysisSection`'s `title`, `lead`, or `id` contract — only adding one new optional prop.

## Decisions

### D1 — Add `titleAdornment?: ReactNode` slot to `AnalysisSection`

Three rejected alternatives, then the chosen one:

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| **A. `aria-hidden="true"` on the help button** | One-line "fix" — heading's accessible name auto-excludes the button | Removes the help affordance from screen-reader users entirely. The whole point of a tooltip is to *help* ALL users; hiding from a11y is the wrong fix. | Reject |
| **B. `aria-label="EBITDA Impact Model"` on the `<h2>` itself** | Forces screen readers to use the explicit label, ignoring descendants | Brittle — relies on every caller remembering to pass the same string twice (visual + aria-label). Fails open if forgotten. | Reject |
| **C. `aria-labelledby` on the `<h2>` pointing at a child `<span>` containing only the title text** | Standards-compliant — heading's accessible name comes from one specific element | Adds DOM noise (extra `<span id>`); still leaves the popover button as a child of `<h2>`, which is structurally still wrong even if accessible name is now clean | Reject |
| **D. Render adornment as SIBLING of `<h2>` via new `titleAdornment` slot** | Structural fix at the right layer. Heading is just the title; adornment is a separate flex child. Both are independently focusable / announceable. Future adornments (count badges, status indicators) get the same slot. | Adds one prop to `AnalysisSection`. New flex container around the heading + adornment. | **Pick** |

### D2 — `AnalysisSection` rendering shape

Current:

```tsx
{title != null && <h2 className="section-header">{title}</h2>}
```

New:

```tsx
{(title != null || titleAdornment != null) && (
    <div className="section-header-row">
        {title != null && <h2 className="section-header">{title}</h2>}
        {titleAdornment != null && <span className="section-header-adornment">{titleAdornment}</span>}
    </div>
)}
```

The wrapping `<div>` only renders when there's something to put in it. Pure-body sections (header, strap, overview, etc. — the exempt list from PR #251) still render no heading row at all.

The `<span className="section-header-adornment">` is a generic container for whatever the caller passes — could be `<HelpTooltip>` today, could be a count badge or status indicator tomorrow. It's `aria-hidden="false"` by default; the caller's adornment owns its own a11y semantics.

### D3 — CSS for the row

Two new rules in `globals.css`:

```css
.section-header-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 1rem; /* was on .section-header — moved up to the row */
}

.section-header-row > .section-header {
    margin-bottom: 0; /* row owns the bottom margin now */
}

.section-header-adornment {
    display: inline-flex;
    align-items: center;
}
```

The `margin-bottom: 1rem` migration from `.section-header` to `.section-header-row` is intentional — when the heading sits in a row with an adornment, the row should own the bottom spacing, not the heading. Sections WITHOUT an adornment still render `<h2 class="section-header">` directly via the existing rule, so spacing is identical for them.

Actually — re-thinking this. If we keep `margin-bottom` on `.section-header` AND add it to `.section-header-row`, sections with adornments would get `1rem + 1rem = 2rem`. The cleaner fix:

```css
.section-header {
    font-size: 1.125rem;
    font-weight: 700;
    margin-bottom: 1rem;
}

/* When inside a row with an adornment, the row owns the bottom margin
   (so the heading doesn't double up). */
.section-header-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 1rem;
}

.section-header-row > .section-header {
    margin-bottom: 0;
}
```

CSS specificity (`.section-header-row > .section-header` is more specific than `.section-header`) ensures the override wins.

### D4 — Migration shape per call site

```tsx
// Before                                     // After
title={                                       title="EBITDA Impact Model"
    <>                                        titleAdornment={<HelpTooltip term="ebitda_tree" />}
        EBITDA Impact Model
        <HelpTooltip term="ebitda_tree" />
    </>
}
```

```tsx
// Opportunities — count badge stays in title (it's part of the heading text,
// not an interactive adornment); HelpTooltip moves to adornment slot
title={`AI Opportunities (${opportunities.length})`}
titleAdornment={<HelpTooltip term="impact_rating" />}
```

Note: previously the `title` for Opportunities was `<>AI Opportunities ({n})<HelpTooltip /></>` — a ReactNode. After this change, it's a plain string `\`AI Opportunities (${n})\``. Simpler call site, simpler test assertion.

The `title` prop's type stays `ReactNode` (some callers may want to pass JSX for other reasons), but in practice all three migrated sections collapse to plain strings.

### D5 — Test posture

1. **`AnalysisSection.test.tsx`** — add 4 new tests:
   - `titleAdornment` renders inside the section
   - `titleAdornment` is NOT inside the `<h2>` (the structural fix)
   - When BOTH `title` and `titleAdornment` are passed, the row-wrapper renders with both as flex siblings
   - When only `titleAdornment` is passed (no title), it still renders without crashing — though we don't expect this in production

2. **`AnalysisDetail.test.tsx`** — tighten the existing heading-framing assertions:
   - Change `getByRole('heading', { name: /EBITDA Impact Model/ })` (regex matcher) to `getByRole('heading', { name: 'EBITDA Impact Model' })` (exact match). The exact match would have failed under the old structure because the accessible name included the help-tooltip button label; under the new structure it matches exactly.
   - Add an assertion that the help-tooltip button is INSIDE the wrapper but OUTSIDE the `<h2>`.

The test posture inversion (regex → exact) is the structural proof that the bug is fixed.

### D6 — `HelpTooltip` itself: zero changes

The existing component renders a button + popover. Outside an `<h2>`, the button's `aria-label` does NOT contaminate any other element's accessible name. So the component as-is is already correct for the new structural arrangement. No edits to `HelpTooltip.tsx`, `help-content.ts`, or any `HelpTooltip` consumer (notably `SortableHeader.tsx`).

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| Existing pre-PR-251 tests that did `expect(screen.getByText('EBITDA Impact Model')).toBeInTheDocument()` would still pass — but the new exact-match heading test would not have caught the bug if we don't add it | Add the explicit `getByRole('heading', { name: 'EBITDA Impact Model' })` exact-match assertion — failing under the OLD structure, passing under the new. That's the regression guard. |
| The CSS change from `margin-bottom: 1rem` on `.section-header` to the row-owns-margin pattern could shift layout if any caller renders `.section-header` outside of `AnalysisSection` | Audit: all `.section-header` usages today live inside `AnalysisSection`. The class is also documented as "consumed by `AnalysisSection.tsx`" per PR #251. Risk is low but check during implementation. |
| Adding the row wrapper introduces an extra `<div>` in the DOM tree for every section that has a title | Trivial — single div, no semantic meaning. Existing tests querying by testid or heading-name are unaffected. |
| `titleAdornment` could be misused for non-adornment content (e.g. a caller passing a button that competes for visual focus with the heading) | Document in JSDoc: "trailing inline content that visually accompanies the heading — typically a help-tooltip or a status indicator. NOT a primary action affordance; primary actions belong in the section body or a dedicated CTA." |
| Three call sites migrate; any I miss leaves a partial regression | Lint/grep for the pattern `title={<>` after migration to confirm zero remain; tests assert exact heading names |

## Migration Plan

Frontend-only, presentation-only change. No data migration, no feature flag.

1. PR merges to `development`
2. Amplify auto-deploys
3. Manual verification: navigate the analysis page with VoiceOver/NVDA, listen to each migrated heading announce — should be the title text only, no "What is X?" suffix. Tab order should reach the help-tooltip button as a separate focus stop AFTER the heading.

**Rollback:** `git revert` of the merge commit. No data implications.

## Resolved Questions

- **Replace HelpTooltip with new DefinitionPopover?** → **No.** HelpTooltip is well-built (proper Esc handling, click-outside dismiss, focus management, reduced-motion support) and used by `SortableHeader`. Renaming would be churn for no win. The UX review's "DefinitionPopover" was a hypothetical name; we keep the existing component name.
- **Use `aria-labelledby` on `<h2>` (option C)?** → **No.** The structural fix (sibling, not child) is more honest than overriding the accessible-name computation. Future contributors who add adornments don't need to remember to wire up labelledby; the slot does the right thing automatically.
- **Introduce the `--section-gap-y` CSS token now?** → **Yes.** Define it once in `globals.css` (initial value `1rem`, matching current behavior) and use it on `.section-header-row` in this PR. The future spacing-tokens proposal (C2 in the BA queue) will extend the token's reach to section-to-section and card-to-card spacing — but introducing it here costs nothing extra and locks the heading-row's margin-bottom into the token system from day one. Naming is intentional: `--section-gap-y` is the vertical-spacing token within and between sections; `--card-gap-y` will follow for card-internal spacing in C2.
- **Validate that callers don't put primary actions in `titleAdornment`?** → **Yes — via strong JSDoc warning, NOT runtime validation.** Runtime validation would require walking the React node tree to detect button/form-submit elements, which is fragile and overengineered for a v1 component contract. Instead: prominently document in the prop's JSDoc the typical valid uses (HelpTooltip, count badge, status pill) AND call out the anti-pattern (primary action button) by name. Add a test that exercises a HelpTooltip in the slot to lock the typical use. If misuse appears in the wild, escalate to a runtime check or a TypeScript-narrowed `AdornmentNode` type later.

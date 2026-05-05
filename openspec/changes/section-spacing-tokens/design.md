## Context

Two existing CSS tokens already govern *intra*-section spacing on the analysis-detail page:

- `--section-gap-y: 1rem` (PR #252) — vertical gap inside a section. Used by `.section-header-row` (between heading and adornment row, locking the bottom margin to the body) and `.section-lead` (between lead paragraph and body).
- `--section-header-row-gap: 0.5rem` (PR #254 review fix) — horizontal gap inside the heading row, between heading and adornment.
- `--card-padding-{metric,list,rich}` (PR #254) — three card-density variant paddings.

What's missing from the system: a token for **inter-section** spacing — the `2rem` gap between consecutive section wrappers. That value is currently hardcoded inline in 6 components, with no central definition. UX Audit 8 specifically called this out as the missing piece of the vertical-rhythm picture.

This proposal adds the missing token and migrates the 6 consumers. Same pattern as the previous spacing-token additions: define once, consume by class.

## Goals / Non-Goals

**Goals:**

- One token (`--section-margin-bottom`) and one utility class (`.analysis-section-spacing`) for inter-section vertical spacing on the analysis-detail page.
- Migrate the 6 inline `marginBottom: '2rem'` values on section outer wrappers to consume the token via the class.
- Documentation in `:root` block clarifying the difference between `--section-gap-y` (intra-section) and `--section-margin-bottom` (inter-section). Pickable by intent.

**Non-Goals:**

- Tokenizing the 30+ inside-section margins (`1rem`, `1.25rem`, `1.5rem` between paragraphs, between heading and content, etc.). Different concern (content rhythm, not page rhythm).
- Page-wide rhythm tokens for non-analysis-detail surfaces.
- Switching from `marginBottom` to a parent `gap` flex/grid layout. Bigger refactor; token-first.
- AnalysisExecutiveStrap's `1.25rem` (intentionally tighter — pairs with OverviewCards). Stays.

## Decisions

### D1 — Token name and value

```css
--section-margin-bottom: 2rem;
```

Why `--section-margin-bottom` and not `--section-gap-between` or similar? Three reasons:
1. **Symmetry with `--section-gap-y`** which lives in the same `:root` block. The `gap-y` ↔ `margin-bottom` pairing reads as "inside-section gap" vs "outside-section margin."
2. **Implementation reality**: the consumers literally apply it as `margin-bottom`. Naming the token after the property keeps the intent obvious at the call site.
3. **Future flexibility**: when we eventually move to a parent `gap` flex layout, the token can be renamed (or a `--section-gap` alias added) without churning every consumer at once.

`2rem` value matches every existing inline use, so there's no visual delta on migration.

### D2 — Application via utility class, not inline `style`

Rejected: `<div style={{ marginBottom: 'var(--section-margin-bottom)' }}>`. While valid, it leaves an inline style on every consumer and requires every future consumer to know the variable name.

Picked: `<div className="analysis-section-spacing">`. The class encapsulates the property + variable mapping; consumers just opt in. Same pattern as `.section-header-row`, `.section-lead`, `.card--list`, etc. — class-based application is the established pattern for the analysis-detail spacing tokens.

```css
.analysis-section-spacing {
    margin-bottom: var(--section-margin-bottom);
}
```

### D3 — Migration list per consumer

| File | Before | After |
|---|---|---|
| `RiskBreakdown.tsx` | `<div style={{ marginBottom: '2rem' }}>` | `<div className="analysis-section-spacing">` |
| `OpportunitiesList.tsx` | same | same |
| `ValueChainDiagram.tsx` | same | same |
| `analysis/EbitdaSection.tsx` | same | same |
| `DocumentUpload.tsx` | same | same |
| `analysis/AnalysisHeader.tsx` | `<div style={{ ... marginBottom: '2rem', flexWrap: 'wrap', gap: '1rem' }}>` (compound style) | className + remaining inline styles |

For consumers that have OTHER inline styles on the same wrapper (like AnalysisHeader's flex/wrap/gap), keep those inline; only the `marginBottom` migrates.

### D4 — Out-of-scope: AnalysisExecutiveStrap

The strap currently has `marginBottom: '1.25rem'` — intentionally tighter than `2rem` so the strap visually pairs with the OverviewCards beneath it. Migrating it to `--section-margin-bottom` would expand the gap to `2rem` and break that pairing.

Two options:
1. Keep the strap's `1.25rem` inline (current state). Defer.
2. Introduce a second token like `--section-margin-bottom-tight: 1.25rem`. Adds complexity for one consumer.

Pick option 1. Document the strap's intentional divergence in its existing JSDoc (already partially documented). If a second consumer ever needs `1.25rem` between sections, then introduce the second token.

### D5 — No new tests

Token + utility-class addition is presentation-only with no behavior change. The 2rem gap before migration equals the 2rem gap after migration. Existing component tests don't assert on inline `marginBottom` values (verified via grep across the test files), so they continue to pass without updates.

A regression guard worth adding: a manual visual eyeball post-deploy confirms each migrated section retains its visible 2rem gap. Trivial visual delta or no delta at all.

### D6 — Order of operations

1. CSS edits in `globals.css`: add `--section-margin-bottom` to `:root`, add `.analysis-section-spacing` rule, update the comment block to explain the picker rule.
2. Migrate the 6 consumers — each is a one-line edit (replace inline `marginBottom: '2rem'` with className).
3. Lint + typecheck + tests (no test changes expected).
4. Architecture review.

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| Visual regression: a migrated consumer's gap shrinks/grows because the token doesn't exactly match the inline value. | Token value (`2rem`) is the exact value used by all 6 consumers today. Zero visual delta is the design intent. |
| Picker confusion between `--section-gap-y` and `--section-margin-bottom`. | Comment block at the top of the token group lists both names with one-line descriptions of when to use each. Same documentation pattern PR #252 used. |
| Some consumers have OTHER inline styles on the same wrapper (AnalysisHeader has flex + gap + wrap rules). Naive migration drops those. | Each migration is reviewed individually — only the `marginBottom` rule moves to className; other inline styles stay. |
| Inside-section margins (1rem / 1.25rem / 1.5rem) deliberately stay inline. A future contributor sees this proposal close but the broader rhythm isn't done. | Proposal explicitly names this as out-of-scope. Future `content-rhythm-tokens` proposal can extend the system once the design system is ready. |
| Migration could miss a consumer (e.g. a wrapper that uses 2rem bottom margin but isn't on the in-scope list). | Final task: grep `marginBottom: '2rem'` across the analysis-detail-page consumer files + the page itself; flag any unmigrated cases for explicit decision (in or out of scope). |

## Migration Plan

Frontend-only, presentation-only.

1. PR merges to `development`
2. Amplify auto-deploys
3. Manual visual verification: every migrated section shows the same `2rem` bottom margin as before. No visual delta expected.

**Rollback:** `git revert` of the merge commit.

## Resolved Questions

- **Token name**: `--section-margin-bottom` (D1).
- **Application via class or inline `var(...)`?**: Utility class (D2).
- **AnalysisExecutiveStrap migration?**: No (D4) — intentional `1.25rem` stays.

## Open Questions

1. **Should AnalysisHeader migrate?** AnalysisHeader is the `<h1>` company-name + actions row at the top of the page. Semantically it's the page header, not a section. But it currently uses the same `marginBottom: '2rem'` pattern as section wrappers, so a future contributor would expect the token there too. Migrate? **Yes — include it.** The token names the SPACE BELOW; whatever produces that space (page header or section wrapper) consumes the token. Documented in D3.
2. **What about `marginBottom: '1.5rem'` on AnalysisOverviewCards?** It's the gap between the score+radar row and what comes after — `1.5rem` is tighter than the standard `2rem`. The OverviewCards are paired with the strap above (per the strap's pairing logic) and visually distinct from the rest of the page. Defer; the `1.5rem` value is intentional. Keep inline.

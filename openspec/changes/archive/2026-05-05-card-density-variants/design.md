## Context

The `.card` CSS class is the codebase's glassmorphism surface — backdrop blur + border + radius + shadow + transition. It's defined in `globals.css` and consumed by 48 callers across the frontend. The class is *intentionally unopinionated* about padding and internal typography — that worked when the codebase had ~10 cards, but has fragmented as it grew to 48.

UX Audit 3 was specific:

> The page has roughly 20 cards using the same `.card` class but rendering very different densities. Same surface design doing too much work alone — each card needed bespoke padding and typography to read well, so the system has fragmented.

The audit listed 6 representative card types ranging from "sparse" (Overall AI Risk Score) to "high" (Risk Dimensions, Value Chain steps). The fix the audit proposed: 2-3 variants with locked density.

This proposal ships exactly the variants the audit named, scoped to analysis-detail-page consumers (where the audit was done). Non-analysis-detail consumers keep the bare `.card` class until a follow-up.

## Goals / Non-Goals

**Goals:**

- Three variant classes (`.card--metric`, `.card--list`, `.card--rich`) with explicit padding + internal typography rules, applied as additional classes alongside `.card` (BEM-style modifier).
- Every analysis-detail-page consumer of `.card` migrates to one of the three variants. No new bespoke `padding` inline style.
- Picker rule documented at the top of the variant section in `globals.css` so future contributors choose the right variant by intent, not by eyeballing existing examples.
- Variants are additive — bare `.card` continues to work for non-analysis-detail consumers (no breaking change).

**Non-Goals:**

- Migrating non-analysis-detail-page consumers (AnalysesTable, ComparisonView, etc.) — separate proposal once the variant set is settled.
- Adding a fourth or fifth variant on speculation — start with 3, extend additively if real cases need them.
- Replacing the `.card` base class with something more opinionated — that would force every consumer to adopt a variant and is too aggressive for v1.
- Changing the glassmorphism appearance (backdrop blur, shadow, border radius) — these stay on `.card`.
- ExpandableCard, section-spacing-tokens, or any other queued UX-review proposals — separate.

## Decisions

### D1 — Three variants and their rules

```css
/* Sparse: single-number / single-badge / single-graphic cards.
   Overall AI Risk Score, ConfidenceIndicator-style stat cards. */
.card.card--metric {
    padding: 2rem;
    text-align: center;
}

/* Compact list row: a single line of card-styled content,
   typically inside an expandable accordion. Risk-breakdown
   rows, opportunity rows, value-chain steps, document rows. */
.card.card--list {
    padding: 0.75rem 1rem;
}

/* Multi-element: card with multiple sub-elements at comfortable
   spacing. Risk Dimensions radar wrapper, Top-3 Actions, EBITDA
   wrapper, business-model summary, ReanalyzeProgressCard. */
.card.card--rich {
    padding: 1.25rem 1.5rem;
}
```

Internal typography is NOT locked in v1 — too brittle (each card's content is too different to lock font sizes globally). The variants lock *padding* (the dominant inconsistency the audit flagged) and document the *intended use* via the comment block. Future iterations can lock typography per variant if a real pattern emerges.

**Compound selector (`.card.card--metric` instead of `.card--metric` alone)** — increases specificity so the variant's padding wins over a stray inline `style={{ padding: ... }}` left from a partial migration. Without the compound, a contributor who forgets to remove the inline padding gets the inline value silently winning.

### D2 — Migration list per consumer

**Discovered during apply phase**: 3 of the originally-listed consumers (`RiskBreakdown`, `OpportunitiesList`, `ValueChainDiagram`) are "button-cards" — the outer `.card` has no padding because an inner `<button>` owns the click + padding semantics. Adding `card--list` to those would stack two padding layers (variant on outer + button's own inline) and produce a visual regression. This pattern is the same one ExpandableCard (UX queue item A) is designed to capture; deferring those migrations to the ExpandableCard proposal lets it ship with the right semantics from day one.

**In-scope for this proposal (pure-content cards):**

| File | Card site | Variant |
|---|---|---|
| `AnalysisOverviewCards.tsx` | Overall AI Risk Score wrapper | `card--metric` |
| `AnalysisOverviewCards.tsx` | Risk Dimensions wrapper | `card--rich` |
| `EbitdaSection.tsx` | inner tree wrapper | `card--rich` |
| `TopActionsCallout.tsx` | outer callout | `card--rich` |
| `DocumentUpload.tsx` | per-document row | `card--list` |
| `analysis/ReanalyzeProgressCard.tsx` | wrapper | `card--rich` |

**Deferred to the ExpandableCard proposal (button-cards):**

| File | Pattern |
|---|---|
| `RiskBreakdown.tsx` | outer `.card` is a frame; inner `<button>` (padding `1rem 1.25rem`) is the click target |
| `OpportunitiesList.tsx` | same pattern — inner `<button>` padding `1.25rem` |
| `ValueChainDiagram.tsx` | even more direct: `<button className="card">` — the button IS the card |

**Why deferred and not "fixed in this PR"**: the button-card pattern is fundamentally different from a content-card. It needs a coordinated decision (does the variant override the button's padding? does the button keep its own padding and the variant adds 0? do button-cards use a 4th variant?). That decision belongs in the ExpandableCard proposal (UX queue item A) which will introduce the canonical interaction pattern for clickable expandable rows. Migrating those consumers now would either (a) regress visually or (b) lock in a button-card padding rule that ExpandableCard would have to revisit.

Each in-scope migration:
1. Add the variant class to the `className` string.
2. Remove the now-redundant inline `padding` style that the variant locks in.
3. Verify visual output matches (or is intentionally tighter — the variant is the new source of truth).

### D3 — Non-analysis-detail consumers stay on bare `.card`

48 total `.card` consumers. ~10 are on the analysis detail page. The remaining 38 (AnalysesTable, EmptyState, ComparisonView, ScanProgressPhase, FailedAnalysisView, etc.) keep `.card` as-is.

This is intentional. The audit was scoped to the analysis-detail page; non-page consumers haven't been visually audited for the same fragmentation. Ship variants where we have evidence, defer where we don't.

A future proposal can audit non-analysis-detail consumers and migrate them. The variants are additive — adding `.card card--list` to those consumers later is a one-line edit per consumer.

### D4 — Bare `.card` continues to work

No breaking change. The variant classes are new; the base class is untouched. Consumers can apply zero, one, or (theoretically) multiple variants — though only one variant should be applied in practice, and a runtime warning isn't worth building for this.

### D5 — Documentation

Above the three variant rules in `globals.css`, a comment block:

```css
/* ── Card density variants ──────────────────────────────────
   Three opinionated density variants of `.card`. Pick one based
   on what's INSIDE the card:
     - `.card--metric` — single number / single badge / single graphic.
       Big central content, generous padding. Use for stat cards.
     - `.card--list`   — compact single-line list row, often inside
       an expandable accordion. Use for risk rows, opportunity rows,
       value-chain steps, document list rows.
     - `.card--rich`   — multi-element card with comfortable internal
       spacing. Use for radar wrappers, paired stat groups, callout
       cards with multiple lines.

   Apply alongside `.card` (BEM-style modifier):
     <div className="card card--list" />

   Inline `padding` overrides the variant's lock — don't use them.
*/
```

### D6 — Test posture

This change is presentation-only — there's no behavior to test. The migration is verified by:

1. **No new tests for variants.** They're CSS rules; there's nothing to unit-test that wouldn't be a tautology against the CSS itself.
2. **Existing component tests** continue to pass — the variant adds a class, doesn't change render structure.
3. **Updates to tests that asserted on inline `padding`** — those assertions become regression-prone (the inline style they tested was removed). The assertions either update to query the variant class on the wrapper, or delete (testing inline-style values is a brittle pattern anyway).

A regression guard worth adding: a manual visual eyeball post-deploy confirms each migrated card looks correct (same density as before, since the variant locks in the same padding the inline style had).

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| A migrated consumer's visual output shifts because the variant's padding doesn't exactly match the inline value it replaced | Each variant's padding value is chosen to MATCH the most common inline value for that card type today. Pre-migration audit noted: `0.75rem 1rem` (list rows), `1.25-1.5rem` (rich), `2rem` (metric). Variant values match. Manual visual verification post-deploy catches any miss. |
| A consumer applies BOTH variants (e.g. `card card--list card--rich`) and gets cascading-style chaos | CSS specificity is identical between variants, so the last-declared one wins per rule. Document in the comment block: "apply ONE variant per card." Add a lint rule (eslint-plugin-tailwindcss style) only if misuse appears. |
| Non-analysis-detail consumers get accidentally migrated by a contributor who doesn't realise the scope is bounded | The proposal explicitly lists which 9 files are in scope. Any other consumer touched is out-of-scope and should NOT migrate in this PR. Architecture-reviewer catches scope drift. |
| The `.card.card--metric` compound selector pattern is unfamiliar to contributors used to `.card-metric` (no compound) | Comment block documents the BEM-style choice and the why (specificity). This is also the convention the UX review proposed verbatim. |
| `padding-locked` variants are less flexible than the inline-padding-per-caller pattern | That's the goal — fewer variants, more uniformity. If a one-off card legitimately needs different padding, it skips the variant and uses bare `.card` with inline padding. The variants are for the common cases. |

## Migration Plan

Frontend-only, presentation-only.

1. PR merges to `development`
2. Amplify auto-deploys
3. Manual visual verification: load an analysis with full data; scan vertically; every migrated card should look identical to before (variant padding matches the inline value it replaced) but with NO inline `padding` style on the wrapper

**Rollback:** `git revert` of the merge commit. No data implications.

## Resolved Questions

- **3 variants vs 4-5?** → **Three.** Audit named three; start there. Add more additively if needed.
- **Lock typography per variant?** → **No, not in v1.** Card content is too varied to lock font sizes globally. Padding is the primary inconsistency the audit flagged; lock that.
- **Bare `.card` deprecated?** → **No.** Stays as-is. 38 non-analysis-detail consumers are untouched.
- **Migrate all 48 consumers in one PR?** → **No, scoped to analysis-detail-page.** Non-analysis-detail consumers haven't been audited for fragmentation; ship where we have evidence.

## Open Questions

1. **Should `.card.card--list` apply `overflow: hidden`?** Several existing list-row cards have inline `style={{ overflow: 'hidden' }}` (e.g. `RiskBreakdown.tsx:29`, `OpportunitiesList.tsx:91`). The variant could lock this too. Defer — `overflow: hidden` is a content-clipping choice, not a density choice; rolling it into the variant adds coupling.
2. **Comparison page consumers** (`ComparisonScoreCards`, `ComparisonRadar`, `ComparisonRiskTable`) look density-similar to the analysis-detail consumers — should they migrate in this PR for parity? Defer — out of scope for the analysis-detail-narrative track. Migration is a one-line edit per file when the comparison page gets its own audit.

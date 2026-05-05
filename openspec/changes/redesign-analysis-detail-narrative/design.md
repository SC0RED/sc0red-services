## Context

`AnalysisDetail.tsx` renders 13 sections in a JSX order that accumulated incrementally. Two independent BA reviews (one source-walk reading the JSX, one live-DOM walk on the deployed dev build at `/analysis/efe1046d-...`) reached convergent conclusions:

| BA-flagged issue | Current order position | Proposed position |
|---|---|---|
| EBITDA buried at the bottom | #13 (last) | #7 (paired with ValueChain) |
| DeepDiveCTA upsells before any analysis is shown | #2 | #6 (after WhatsMissingPanel gaps) |
| Re-analyse loop has no visible affordance | implicit-on-upload | explicit labelled button |
| TopActionsCallout sits between strategy map and risk breakdown — neither synthesis-up-top nor evidence-down-low | #5 | #4 (synthesis directly after verdict) |
| ValueChain orphaned between Opportunities and Documents | #10 | #8 (paired with EBITDA — VC is an EBITDA-decomposition lens) |
| No one-line summary for skim readers | n/a | new ExecutiveStrap at #2 |
| Reanalyzing progress bar renders above the button that triggers it | #11 (orphaned) | inside DocumentUpload at #12 |

The JSX-order vs deployed-DOM-order claim from one of the reviews ("the wire-up code placed StrategyMapView first, the deployed page does the opposite") was investigated and rejected: the JSX explicitly puts DeepDiveCTA before StrategyMap (line 118 vs line 122 in current `AnalysisDetail.tsx`), and the placement is documented in the prior change's `design.md` as decision D6. The deployed page matches the source. This proposal supersedes that D6 decision rather than reverting drift.

**Persona scope.** The page primarily serves the PE buy-side reader who triages in 3 minutes and deep-dives in 10–15. Beat ordering is optimised for the 3-minute triage path (synthesis-first); the 10-minute deep-dive consumes the same beats top-to-bottom with no penalty.

**Constraint.** Frontend file budget caps components at 360 lines. `AnalysisDetail.tsx` is currently 192 lines. New ExecutiveStrap component must stay self-contained.

## Goals / Non-Goals

**Goals:**

- Page reads top-to-bottom as a 5-beat narrative (identity → synthesis → strategic frame → financial picture → action evidence → improvement loop).
- A skimmer who reads only the first viewport gets a transcribable verdict (ExecutiveStrap one-liner) without scrolling.
- The re-analyse loop has an explicit, labelled control surface — no implicit-on-upload-only behaviour.
- The reanalyze progress bar renders next to the affordance that triggers it (inside DocumentUpload), not orphaned above.
- All ordering and component additions are pure presentation changes — no data-shape, API, or analytics-event semantic changes.

**Non-Goals:**

- Consistency wrapper (`<Section>` component, accordion-everywhere, banded backgrounds, unified empty states) — separate follow-up proposal.
- Tabbed navigation across beats — explicitly rejected (single-scroll page is the v1 contract).
- Changes to `FailedAnalysisView` (the failed-analysis branch is out of scope).
- Changes to the strategy-map's internal layout, EBITDA tree internals, or any other component's internal structure. This change reorders + reframes.
- New analytics events for the re-ordered sections. Existing events (`_rendered_strategy_map`, opportunity CTA tracking) keep their current semantics.
- Pricing, copy, or visual treatment changes to `DeepDiveCTA` or `Sc0redCTABanner` — only their position on the page changes.

## Decisions

### D1 — Final 5-beat order

```
Beat 1 — IDENTITY
  1. AnalysisHeader
  2. AnalysisExecutiveStrap (NEW)
  3. AnalysisOverviewCards

Beat 2 — SYNTHESIS
  4. TopActionsCallout

Beat 3 — STRATEGIC FRAME
  5. StrategyMapView (WhatsMissingPanel rendered inside it)
  6. DeepDiveCTA

Beat 4 — FINANCIAL PICTURE
  7. EbitdaSection
  8. ValueChainDiagram

Beat 5 — RISK + OPPORTUNITY EVIDENCE
  9. RiskBreakdown
  10. ValueLeverSummary
  11. OpportunitiesList
  12. Sc0redCTABanner

Beat 6 — IMPROVE THIS ANALYSIS
  13. DocumentUpload (with reanalyzing progress bar absorbed inside)
```

Note: "5-beat narrative" in the proposal is the reader-facing framing; structurally the JSX renders 6 beat groups because identity has both the strap and the overview cards, and improvement is its own terminal beat. Beat numbering above is for design clarity, not user-visible labelling.

**Why TopActionsCallout at #4 (high)** and not at #11-near-Opps (the alternative one BA review preferred): the persona is the buy-side reader making a triage-to-attach decision. Top-3 Actions IS the executive summary — Pyramid Principle puts synthesis directly under the verdict. The counter-argument (Top-3 Actions are operational, belong with Opportunities they're drawn from) is valid for the portfolio-CFO persona that already owns the deal — but that persona reads in the same top-to-bottom order with no penalty, while the triage persona breaks down if synthesis is buried.

**Why DeepDiveCTA at #6 (after WhatsMissingPanel)** and not at the very end: the CTA's literal value proposition is "we will help you fill these strategic gaps." Placing it immediately after the gaps — at the moment of maximum buying intent — beats both the current placement (asks for the upsell before any analysis) and an end-of-page placement (dilutes the narrative thread between gap and offer).

**Why EBITDA + ValueChain paired at #7-8**, not separated: ValueChain is an EBITDA-decomposition lens (where the cost and revenue lines actually originate in the operations). They answer the same question ("where does the money come from / go?") at different abstraction levels. Splitting them with Documents in between (current order) makes neither read well.

### D2 — AnalysisExecutiveStrap content + data sources

The strap is a single visual element (one-line, transcribable, between AnalysisHeader and AnalysisOverviewCards).

```
{companyName} — AI Risk {score} / {tier} · {N} opportunities · est. EBITDA range {range} · last analysed {date}
```

Field sources from existing `AnalysisData`:

| Strap field | Data source | Fallback |
|---|---|---|
| companyName | `data.companyName` | always present |
| score | `data.overallRiskScore.toFixed(1)` | `—` if null |
| tier | `data.riskTier` (or `getRiskTier(score)` if null) | always derivable |
| N opportunities | `data.opportunities.length` | `0` |
| EBITDA range | `data.ebitdaTree.ebitdaEstimate` directly (already a string like `"$2M-$8M"`) | omit segment if `ebitdaTree?.ebitdaEstimate` is missing |
| last analysed | `data.analyzedAt` formatted as a short date | omit segment if null |

**Conditional segments.** If `ebitdaTree` is null OR `analyzedAt` is null, those segments are dropped from the strap (with their leading `·` separator) rather than rendered as `—`. The strap is a marketing-grade summary; partial-data placeholders cheapen it.

**Why not a fancier card?** The PDF review (Cowork) suggested a one-line strap modeled on a sell-side analyst report. Anything taller than one line competes with `AnalysisOverviewCards` directly below. The constraint is "transcribable in one line by a skim reader."

### D3 — DocumentUpload section reframe

Three changes inside `DocumentUpload.tsx`:

1. **Section header rename**: from "Documents" to **"Improve This Analysis"** (the user-facing copy — confirmed). Picked over "Re-analyse with Context" because "Improve" is a verb phrase that covers both paths (upload + re-analyse) without locking the user into thinking about either mechanism. The drop-zone subtitle becomes "Upload financial statements, board decks, or product docs to refine this analysis."
2. **Explicit `Re-analyse` button** — visible at all times when documents are uploaded (`documents.length > 0`), disabled when `reanalyzing === true`. Clicking it calls the same `onReanalyze` prop currently triggered implicitly on upload. The button must have aria-label and be reachable by keyboard.
3. **Reanalyzing progress bar absorbed**: the progress block currently rendered conditionally between Sc0redCTABanner and DocumentUpload in `AnalysisDetail.tsx` moves INSIDE `DocumentUpload`, rendered when `reanalyzing === true`. Existing styling preserved; only the location changes.

**Why a button instead of an "Auto re-analyse on upload" checkbox?** Explicit user intent matches the buy-side reader's mental model ("I uploaded a doc; I want to see the impact"). Auto-trigger-on-upload is the current behaviour and it is invisible — the BA review classified that as both an IA gap and a UX gap. The button makes the loop legible.

### D4 — Where the EBITDA range comes from

The ExecutiveStrap shows "est. EBITDA range $2M–$8M" style content. The backend already produces a precomputed top-level `ebitdaEstimate` string on `EbitdaTree` (e.g., `"$2M-$8M"`) — we display that directly. No client-side parsing or leaf-walking needed.

```ts
// from frontend/src/lib/types/api.ts
interface EbitdaTree {
  treeData: EbitdaNode[]
  revenueEstimate?: string
  ebitdaEstimate?: string
  businessModelSummary?: string
}
```

If `ebitdaEstimate` is absent on a particular tree (older analyses, partial data), the EBITDA segment of the strap drops cleanly per the conditional-segment rule — we do NOT fall back to `revenueEstimate` or to a leaf-walked computation, because either substitute would silently mislabel revenue as EBITDA, which is the worst possible outcome for a buy-side reader.

**Original plan (rejected).** I initially proposed walking leaf nodes and computing min(low)/max(high). Rejected because: (1) `EbitdaNode.value_range` is a string like `"$10M-$50M"`, so client parsing would be required and brittle; (2) the precomputed `ebitdaEstimate` is already the analyst-grade summary the strap wants to show; (3) min-of-leaves/max-of-leaves can produce ranges wider than reality (any single outlier leaf widens the strap's headline range).

### D5 — Test coverage strategy

Three test files cover the change:

1. `AnalysisDetail.test.tsx` — assert SECTION ORDER via stable `data-testid` markers on each section. Don't assert pixel positions (jsdom doesn't lay out reliably). Use `getAllByTestId` and check the array order.
2. `AnalysisExecutiveStrap.test.tsx` — render with full data, render with null `ebitdaTree`, render with null `analyzedAt`. Assert text composition + that conditional segments drop cleanly.
3. `DocumentUpload.test.tsx` (existing, augmented) — assert the explicit "Re-analyse" button is present, calls `onReanalyze` when clicked, is disabled during `reanalyzing`. Assert the progress bar renders inside this component (not in the parent) when `reanalyzing === true`.

Each section gets a `data-testid` on its top-level wrapper to make ordering testable: `analysis-section-header`, `analysis-section-strap`, `analysis-section-overview`, `analysis-section-top-actions`, etc. This is also good for E2E hooks if we ever need them.

### D6 — Reverting prior decision D6 from PR #239's design

PR #239's `design.md` decision D6 ("hoist DeepDiveCTA above StrategyMapView for visibility") is explicitly superseded by this change. The analytics-event semantic relaxation that came with that hoist (`_rendered_strategy_map` = "page with strategy map loaded" rather than "user saw the map") **stays** — this proposal is not changing analytics. We're moving the CTA to a position where the user has scrolled past the strategy map content by the time the CTA fires, which actually re-tightens the meaning of "saw the map" in practice; we just don't depend on it for the analytics contract.

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| Skim readers who never scroll past the fold lose access to the DeepDiveCTA (it now lives below the strategy map) | Acceptable. The whole point of moving it is that the CTA-before-value variant under-converts in principle. We can A/B if signal is needed. |
| TopActionsCallout high-position breaks existing user muscle memory | Low risk — section is < 1 month old. No external docs reference its position. |
| EBITDA range derivation produces nonsense for some analyses (extreme outliers, single-node trees) | Strap segment gracefully drops if `ebitdaTree` is null or has no leaves. For real edge cases we iterate. |
| Re-analyse button + auto-trigger-on-upload could double-fire | DocumentUpload owns the trigger logic; we keep auto-trigger-on-upload AND add the button. The button's onClick is the same code path. Re-clicking during `reanalyzing === true` is blocked by the disabled state. |
| ExecutiveStrap competes visually with AnalysisOverviewCards directly below | Strap is one line, OverviewCards is a 280px-tall row. Visual weight is asymmetric on purpose; the strap is "headline", the cards are "the data." |
| Existing tests asserting current section order will fail | All AnalysisDetail-related tests are updated as part of this change (task list covers this). |
| Per CLAUDE.md, frontend components have a 360-line cap. AnalysisDetail.tsx + DocumentUpload.tsx may grow | AnalysisDetail.tsx is currently 192 lines and the change is a JSX reorder + one new import, expected to stay flat. DocumentUpload.tsx absorbs the progress block (~22 lines) and adds a button (~15 lines); current size is ~120 lines so the cap is not at risk. ExecutiveStrap is a new component, will be under 100 lines. |

## Migration Plan

This is a frontend-only, presentation-only change. No data migration. No feature flag. No staged rollout.

**Deploy path:**

1. PR merges to `development` branch.
2. Amplify auto-builds + deploys to dev.janus.sc0red.com.
3. Manual sniff test: load a known analysis, walk top-to-bottom, verify all 13 sections render in the new order, verify ExecutiveStrap renders, verify Re-analyse button is visible, verify progress bar renders inside DocumentUpload during a re-analyse.

**Rollback:** `git revert` of the merge commit. No data implications.

## Open Questions

1. **EBITDA range formula** — derive from leaf nodes (proposed) vs derive from top-level revenue/cost children (alternative). Defer until we render against real data and look at it.
2. **Should ExecutiveStrap link anywhere?** (e.g., the `{N} opportunities` segment becomes a click-to-scroll-to-Opportunities anchor). Stretch goal — not part of v1.
3. **Section data-testid naming convention** — confirm `analysis-section-{name}` matches existing testids elsewhere on the page. If a different convention is in use, align with it during implementation.

## Resolved Questions

- **Section header copy** → **"Improve This Analysis"** (verb-phrase, covers both upload and re-analyse paths).
- **ExecutiveStrap mobile behaviour** → **Allow natural wrapping** at narrow widths. The strap remains the highest-density summary even when wrapped to 2–3 lines on a phone, and the maintenance cost of a progressive-collapse breakpoint isn't justified for v1. Implementation should NOT use `white-space: nowrap`; segments separated by `·` flow as inline text and wrap at word boundaries.

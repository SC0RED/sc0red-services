## Why

The analysis detail page (`/analysis/[analysisId]`) renders 13 sections in an order that grew incrementally as features were added — not in an order that matches how a PE buy-side reader actually consumes the page. Two BA-style reviews (one source-walk, one live-DOM walk on the deployed dev build) independently reached the same headline conclusions: EBITDA is buried at the bottom (last section, ~12 screens of scroll) when it is the single metric a PE buyer cares about most; the strategy-map upsell CTA fires above any analysis content, asking for the upsell before the user has seen value; and the document re-analyse loop — the operationally most useful action on the page — is invisible (no labelled button, only an implicit on-upload trigger). The page reads as a stack of features, not a deliberately ordered narrative. PE readers triaging in 3 minutes lose the thread before reaching the financial picture.

## What Changes

- **Re-order** sections in `AnalysisDetail.tsx` to a 5-beat narrative: identity → synthesis → strategic frame → financial picture → risk + opportunity evidence → improve-this-analysis. Specifically: promote `TopActionsCallout` directly after the verdict cards (synthesis-up-top per Pyramid Principle); promote `EbitdaSection` from position #13 to immediately after the strategy frame; pair `ValueChainDiagram` with `EbitdaSection` (value chain is an EBITDA-decomposition lens); move `DeepDiveCTA` from position #2 to immediately after the strategy map's `WhatsMissingPanel` gaps (where the upsell pitch matches the moment of maximum buying intent — "we'll help you fill these gaps").
- **Add** a new `AnalysisExecutiveStrap` component between `AnalysisHeader` and `AnalysisOverviewCards`. One-line, transcribable summary in the form `{company} — AI Risk {score} / {tier} · {N} opportunities · est. EBITDA range {range} · last analysed {date}`. Serves the 3-minute skim persona who never scrolls past the fold.
- **Reframe** the `DocumentUpload` section. Rename the section header from "Documents" to "Improve This Analysis" (or "Re-analyse with Context"). Add an explicit, labelled `Re-analyse` button — the current implicit-on-upload behaviour is invisible. Move the inline `Reanalyzing progress` block from its current orphaned position (rendered above the button that triggers it) into the `DocumentUpload` component itself so the progress bar appears next to the affordance.
- **Remove** dead/orphaned positioning of the reanalyze progress block from `AnalysisDetail.tsx`.
- No data-shape changes. No backend changes. No API changes. No analytics-event semantic changes (the `_rendered_strategy_map` event already relaxed under PR #239 D6 — that decision stands).

## Capabilities

### New Capabilities

- `analysis-detail-narrative`: governs the section ordering, executive-summary strap, and re-analyse affordance on the analysis detail page. Specifies the 5-beat narrative contract, the data shown in the executive strap, and the visibility requirements for the re-analyse loop.

### Modified Capabilities

<!-- None. The existing analysis-detail page is not currently captured as a spec. -->

## Impact

**Code**:
- `frontend/src/app/(authenticated)/analysis/[analysisId]/AnalysisDetail.tsx` — JSX render order changes; reanalyze progress block removed (relocated into DocumentUpload)
- `frontend/src/components/analysis/AnalysisExecutiveStrap.tsx` — new component
- `frontend/src/components/DocumentUpload.tsx` — section header rename, explicit Re-analyse button added, reanalyze progress block absorbed
- `frontend/src/tests/app/(authenticated)/analysis/[analysisId]/AnalysisDetail.test.tsx` (or equivalent) — order assertions updated
- `frontend/src/tests/components/analysis/AnalysisExecutiveStrap.test.tsx` — new tests
- `frontend/src/tests/components/DocumentUpload.test.tsx` — assertions for Re-analyse button + relocated progress

**Surfaces affected**:
- Analysis detail page (every successful analysis with a strategy map)
- Failed-analysis path is NOT affected (`FailedAnalysisView` is a separate render branch and out of scope here)

**Data / APIs**: none. The executive strap consumes existing fields on `AnalysisData` (`companyName`, `overallRiskScore`, `riskTier`, `opportunities.length`, `analyzedAt`, and a derived EBITDA range from `ebitdaTree` if present).

**Dependencies**: no new packages.

**Out of scope (explicitly deferred)**:
- The "consistency wrapper" axis (shared `<Section>` component, accordion-everywhere, banded backgrounds, conditional-vs-always-on empty states) is a separate proposal that should follow this one.
- Pricing or content changes to the DeepDiveCTA copy itself.
- Any backend or data model changes.

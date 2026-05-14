## Why

After PR #299 (EBITDA waterfall) and PR #301 (compact bands), the analysis-detail page is functionally correct but two readability gaps remain:

1. **The EBITDA section looks chromatically different from the rest of the page.** Every chip body, border, and label uses hardcoded RGB literals (`rgba(34, 197, 94, ...)` for revenue, `rgba(239, 68, 68, ...)` for cost, etc.). Three layers of saturated semantic color per chip × ~9 chips per page = chromatic noise. The strategy-map's chips already follow a calmer pattern (neutral body + 3px colored left-border accent — same as the Value Impact card's top-border pattern). The EBITDA section is the only place on the page that bathes content in semantic color rather than reserving color for a single edge accent.

2. **Body text contrast and type rhythm are weak across the analysis page.** Audit findings on the dark theme: `--text-tertiary: #4d5b7f` renders at ~1.9:1 contrast on `--bg-base: #060a12` — **fails WCAG AA** (needs 4.5:1). `--text-secondary: #8b9ac4` is at ~5.0:1 — passes AA but feels weak under dense content. The light-theme equivalents already pass at acceptable ratios. Separately, the analysis components use **11 distinct inline `fontSize` values** (`0.7rem`, `0.75rem`, `0.8125rem`, `0.875rem`, `0.9rem`, `0.9375rem`, `0.9875rem`, `1rem`, `1.125rem`, `1.5rem`, `1.625rem`) — no coherent type scale, no shared vertical rhythm.

The two issues compound: low-contrast captions inside saturated colored boxes feels especially noisy. Same content, better presentation — three small surgical changes lift legibility across every section.

## What Changes

- **EBITDA chip + band-header palette swap** (presentation-only — same content, same data, same layout):
  - Chip body uses `var(--bg-surface-2)` instead of `rgba({type-color}, 0.10)`.
  - Chip border uses `1px solid var(--border-subtle)` instead of `1px solid rgba({type-color}, 0.35)`.
  - Chip label uses `var(--text-primary)` instead of the hardcoded `#22C55E` / `#EF4444` / etc.
  - Chip gains a **3px colored left border** carrying the semantic accent (revenue green / cost red / margin blue / subtotal amber) — mirrors the strategy-map chip's `borderLeft: '3px solid {accent}'` pattern.
  - Band header keeps its 4px colored left strip from PR #301 — unchanged.
  - **BREAKING (visual)**: the previously-green tinted revenue chips are now neutral with a green left strip. Distinguishability via accent column on the left, not via saturated body.

- **Dark-theme text-token contrast lift** (single global edit in `globals.css`):
  - `--text-secondary: #8b9ac4` → `#a8b4d6` (~5.0:1 → ~7.5:1 contrast).
  - `--text-tertiary: #4d5b7f` → `#7c8aaf` (~1.9:1 → ~4.6:1 contrast — was failing WCAG AA, now passes).
  - Light theme tokens unchanged — already pass at acceptable ratios. Net effect: both themes now express the same design intent at the token level (secondary = "supporting", tertiary = "caption", both meeting AA).
  - **BREAKING (visual)**: every page that uses `--text-secondary` or `--text-tertiary` on the dark theme reads more clearly. Includes the dashboard, admin, and login surfaces beyond the analysis page — by design, this is the single global lift the user explicitly chose over the analysis-only scope.

- **Type-scale consolidation on analysis components**:
  - Replace the 11 inline `fontSize` values with five canonical steps: `0.75rem` (caption), `0.875rem` (body-small), `1rem` (body), `1.125rem` (heading-small), `1.5rem` (heading).
  - Sweep covers `frontend/src/components/EbitdaTree.tsx`, `EbitdaNodeComponent.tsx`, `RiskBreakdown.tsx`, `OpportunitiesList.tsx`, `ValueChainDiagram.tsx`, `DocumentUpload.tsx`, `ValueLeverSummary.tsx`, the `analysis/` directory, and the strategy-map components.
  - Page-level `<h1>` in `AnalysisHeader` stays at its current size. No new type-scale tokens introduced — uses the five canonical rem values directly so the change stays scoped.

## Capabilities

### New Capabilities
- `analysis-page-readability`: the visual-presentation invariants that govern legibility on the analysis-detail page — text-token contrast floors, the type-scale ceiling, and the "semantic color on edge accents, not on content surfaces" rule.

### Modified Capabilities
- `ebitda-impact-model`: the EBITDA chip's color treatment moves from "saturated body" to "colored-left-border accent". The chip body, border, and label use theme tokens; only the 3px left edge carries the semantic accent.

## Impact

- **Frontend code**:
  - `frontend/src/app/globals.css` — two color-value edits to `--text-secondary` and `--text-tertiary` under the `:root` (dark) selector.
  - `frontend/src/components/EbitdaNodeComponent.tsx` — drop `NODE_COLORS` literals from chip body/border/label; add 3px `borderLeft` to the chip's outer `<article>` with the accent color.
  - `frontend/src/components/{EbitdaTree,EbitdaNodeComponent,RiskBreakdown,OpportunitiesList,ValueChainDiagram,DocumentUpload,ValueLeverSummary}.tsx` + `frontend/src/components/analysis/*.tsx` + `frontend/src/components/strategy-map/*.tsx` — replace 11 inline `fontSize` values with 5 canonical rem steps.
- **Frontend tests**:
  - Update `EbitdaNodeComponent.test.tsx` regression assertions: the "border-left 4px solid" assertion (band header) stays; add a new "border-left 3px solid" assertion for the chip variant.
  - Where existing tests assert specific inline `fontSize` values, replace with assertions on the canonical step.
- **Backend**: no changes.
- **Accessibility**: the failing-AA `--text-tertiary` token is fixed in the dark theme. Every surface using this token (captions on the analysis page, dashboard counts, admin labels) becomes AA-compliant.
- **Other surfaces using the bumped tokens** (dashboard, admin, login): they get the contrast lift automatically. Per the user's explicit choice, this is the single global lift, not an analysis-scoped patch.
- **Spec evolution**: a new `analysis-page-readability` capability codifies the contrast/type-scale invariants so future contributors can see them at a glance. The `ebitda-impact-model` spec gains a modified requirement covering the chip's color treatment.

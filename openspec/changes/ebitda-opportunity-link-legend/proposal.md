## Why

Each EBITDA leaf chip carries a row of small colored dots at the bottom — one dot per AI Opportunity that targets that P&L line, colored by the opportunity's value lever (green = Revenue Side, red = Cost Side, cyan = Both). The wiring is correct and information-rich: a user looking at "Subscriptions" with four green dots knows four Revenue-Side opportunities target that revenue stream.

But the dots aren't discoverable. They sit at the bottom of the chip with no label, no surrounding context, no on-page legend. The only hint is a native HTML `title` attribute on each dot — invisible until you hover the exact 8px target. Users (including the page owner) ask "what are those dots?" — exactly the same problem the strategy-map confidence dots had before PR #298 introduced a static legend below the canvas.

PR #298 set the precedent: when a section relies on a row of small colored dots that carry semantic meaning, the section gets a one-line legend that documents the dot colors inline. The EBITDA section should follow the same pattern.

## What Changes

- Add a one-line legend below the EBITDA waterfall (between the EBITDA Impact Model section's final connector and any subsequent content) that documents the opportunity-link dot scale: `● Revenue Side · ● Cost Side · ● Both — dots indicate AI opportunities targeting this P&L line.`
- The legend uses the same `LEVER_COLORS` palette the chips themselves use, via the existing `--lever-revenue` / `--lever-cost` / `--lever-both` theme tokens (already declared in `globals.css`). No new color tokens, no hardcoded hex.
- The legend renders only when the analysis has at least one linked opportunity — same gating as the EBITDA section's existing confidence-legend (`treeHasConfidence` predicate in `EbitdaSection.tsx`). When the rendered tree carries zero linked opportunities, the legend stays absent — no chips render dots, no legend explains them, no clutter.
- Visual style mirrors the strategy-map's existing `ConfidenceLegend` and the EBITDA section's existing `ebitda-confidence-legend`: small caption-step font, theme-token colors, sits inside a low-emphasis container so it doesn't compete with the band headers.

No other changes — chip-level dot rendering, `LEVER_COLORS` palette, backend `linked_opportunity_indices` field, opportunity card list rendering all stay exactly as today.

## Capabilities

### New Capabilities
<!-- None — extends the existing `ebitda-impact-model` rendering contract. -->

### Modified Capabilities
- `ebitda-impact-model`: gains a requirement that the EBITDA section MUST render a documented legend for the opportunity-link dots on every chip (when at least one chip carries them).

## Impact

- **Frontend code**:
  - `frontend/src/components/analysis/EbitdaSection.tsx` — add a sibling component `EbitdaOpportunityLinkLegend` (rendered alongside the existing `ebitda-confidence-legend`). Hook into a new `treeHasLinkedOpportunities(nodes)` walk that mirrors the existing `treeHasConfidence` predicate.
- **Frontend tests**:
  - Update `EbitdaSection.test.tsx` with two new tests: legend renders when at least one node has a non-empty `linked_opportunity_indices`; legend stays absent when no node has any.
- **Backend**: no changes.
- **Spec evolution**: `ebitda-impact-model` gains a Modified Requirement covering the legend's presence, contents, and gating.
- **Accessibility**: the legend is a `<div>` (not a heading) with explicit text labels for each lever color. Screen readers hear the legend as plain content alongside the section. No new heading-scale entries.
- **Print / PDF**: no changes — `PrintEbitdaOutline.tsx` is its own render path and does not depend on this legend.

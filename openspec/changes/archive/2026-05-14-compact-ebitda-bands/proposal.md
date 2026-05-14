## Why

The `redesign-ebitda-impact-model` change (PR #299, merged) replaced a React Flow canvas with a static vertical waterfall. The waterfall fixes the original "can't read without zooming" complaint but creates two new problems immediately visible on the rendered page:

- **Cards are huge.** Each leaf is a full ~300 × 150 px card with the same visual weight as its parent subtotal. Three leaves under "Total Revenue" eat ~500 px of vertical space before "Cost of Revenue" begins; users lose the P&L narrative by the time they scroll to EBITDA.
- **Hover description is broken.** Each card renders an absolutely-positioned description box at `top: 100%` that overflows into the row below, visually covering the next leaf or subtotal (visible in user-attached screenshot: an opportunity tooltip lands on top of "Other Revenue").

The strategy-map section, redesigned earlier in this iteration, has the right compact aesthetic: small chips with confidence dots, organised into colored bands, hover detail delivered via native `title` (not a custom overlay). Apply that same aesthetic to the EBITDA Impact Model.

## What Changes

- **BREAKING (UI)**: each P&L row collapses from a "parent card + leaf cards in a row" into a **band**: a single-line header (colored left strip + label + value range) followed by leaves rendered as compact ~150 × 70 px **chips arranged horizontally inside the band**. Subtotals are no longer cards. This mirrors the strategy-map's "perspective band + objective chips" treatment.
- Drop the custom absolutely-positioned hover description box. Hover detail is delivered via the native HTML `title` attribute on each chip (same posture the strategy-map chips already use). Custom overlays that overflow neighbouring rows are gone — eliminates the visible bug.
- Reuse the existing `ConfidenceIndicator` (small variant) on each leaf chip — same component, same dot pattern, same `aria-label="Confidence: {level}"` selector as the strategy-map chips and the EBITDA cards today.
- Connector arrows + arithmetic labels (`minus` / `equals`) between bands stay — they're the only on-screen artifact of the P&L sequence, and removing them would lose the financial story.
- Mobile breakpoint: chips wrap to a second row inside their band when the band is too narrow (`flex-wrap`), no horizontal scroll. Same responsive mechanism as today.

## Capabilities

### New Capabilities
<!-- None — this change modifies the existing rendering contract introduced by `redesign-ebitda-impact-model`. -->

### Modified Capabilities
- `ebitda-impact-model`: the rendering contract introduced by `redesign-ebitda-impact-model` is tightened. Subtotals collapse from cards to band headers; leaves collapse from cards to compact chips; the custom hover description overlay is replaced by native `title` tooltips.

## Impact

- **Frontend code**:
  - Restructure `frontend/src/components/EbitdaTree.tsx`: each P&L row becomes a band (header + horizontal chip row) instead of a parent card with a vertical leaf column.
  - Restructure `frontend/src/components/EbitdaNodeComponent.tsx`: drop the custom absolutely-positioned hover description; collapse the leaf variant to a compact chip (smaller padding, smaller fonts, no glow); collapse the subtotal variant to a single-row band header with a colored left strip.
- **Frontend tests**: update `EbitdaTree.test.tsx` and `EbitdaNodeComponent.test.tsx` to assert the new band/chip structure; drop the hover-description assertions; keep all confidence-chip and opportunity-link tests intact.
- **Backend**: no changes. `EbitdaNode` data model and `build_programmatic_ebitda_tree` are unaffected.
- **Spec evolution**: the `ebitda-impact-model` spec (introduced by `redesign-ebitda-impact-model`, not yet archived) gains modified requirements covering the band-header / chip / native-tooltip contract.
- **Accessibility**: the `<h3>` heading semantics introduced for screen-reader navigation in PR #299 are preserved — the band header still renders its label inside `<h3>`. The `<ol>` waterfall structure and the `<ul aria-label="Drivers of {parent}">` leaf list are also preserved.
- **Print path** (`PrintEbitdaOutline.tsx`): unaffected — already uses its own static layout.

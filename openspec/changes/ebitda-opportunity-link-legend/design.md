## Context

Every EBITDA leaf chip emits a row of 8 × 8 px colored dots at the bottom (in `EbitdaNodeComponent.tsx`'s `LeafChip`). The row is rendered only when `linkedOpportunities.length > 0`; each dot is colored via `LEVER_COLORS[opp.valueLever]` (`var(--lever-revenue)` / `var(--lever-cost)` / `var(--lever-both)`) and carries the opportunity title + lever name on its `title` attribute.

The dots are semantically rich — they communicate which AI Opportunities (from the dedicated Opportunities section further down the page) target each specific P&L line. Without them, users would have to read every opportunity card and mentally re-map them to the EBITDA tree. With them, the cross-reference is visual and immediate — *when you know what they mean*.

The discoverability gap is identical to the one the strategy-map confidence dots had before PR #298. The strategy map's `ConfidenceIndicator` (3-dot scale on every chip) was equally semantic-rich and equally undocumented; PR #298 added a single static legend below the canvas that lists each dot pattern with its meaning. The legend made the dots legible without changing them.

The EBITDA section also already carries a precedent: `ebitda-confidence-legend` (in `EbitdaSection.tsx`) — a one-line caption that documents the leaf confidence chip's three-dot scale (high / medium / low). It's gated on `treeHasConfidence(nodes)` so it only renders when at least one leaf carries a confidence level. Same shape applies here.

## Goals / Non-Goals

**Goals:**

- Document the lever-color dot scale inline on the analysis page so users don't have to hover a single 8 × 8 px target to know what the dots mean.
- Render the legend only when at least one chip in the rendered tree actually has dots — no on-page noise when the data is sparse.
- Reuse the existing `LEVER_COLORS` palette (via theme tokens) so the legend dots are pixel-identical to the chip dots.
- Mirror the EBITDA section's existing `ebitda-confidence-legend` posture (caption-step font, theme-token colors, low-emphasis container).

**Non-Goals:**

- Changing the chip-level dot rendering. The dot row inside the chip stays exactly as today.
- Making the dots clickable / linkable to the opportunity cards. That's the right long-term answer (cross-reference navigation between EBITDA and Opportunities sections) but it's a separate scope.
- Removing the dots entirely. They have real semantic value; the diagnostic was discoverability, not over-use.
- Changing the print/PDF render path.
- Touching `LEVER_COLORS` or the underlying theme tokens.

## Decisions

### §1 — Legend placement: inside `EbitdaSection`, alongside the existing confidence legend

The existing `EbitdaSection.tsx` already gates a confidence legend on `treeHasConfidence(nodes)`. The opportunity-link legend follows the same shape: a sibling component `EbitdaOpportunityLinkLegend`, gated on a parallel predicate `treeHasLinkedOpportunities(nodes)`.

Both legends sit in the section's header region — above the `<div className="card card--rich">` that wraps the `EbitdaTree`. This keeps the legend visible without needing to scroll past the waterfall, and groups it with the badges + business-model summary that already orient the user before the tree renders.

Two legends in the same region:
- Confidence legend: explains the three-dot confidence scale on each leaf
- Opportunity-link legend: explains the dot row at the bottom of each chip

If both render, they stack vertically as separate `<div>` rows. The confidence legend renders first (matches today's ordering); the opportunity-link legend follows.

### §2 — Legend content + format

The legend is a single line:

```
● Revenue Side  ·  ● Cost Side  ·  ● Both  —  AI Opportunities targeting this P&L line.
```

Each `●` is a 10 × 10 px filled circle in the matching theme color (slightly larger than the in-chip dot's 8 × 8 px so it reads cleanly at this typography scale — same trick the strategy-map confidence legend uses).

Format mirrors the EBITDA confidence-legend's existing text-secondary + bold-strong combination:

```
<strong>Opportunity links:</strong> <dot ●> Revenue Side · <dot ●> Cost Side · <dot ●> Both — AI Opportunities targeting this P&L line.
```

The "Opportunity links:" prefix establishes what the section is about; the `<strong>` matches the existing confidence-legend's `<strong>Confidence:</strong>` opener.

### §3 — Predicate: `treeHasLinkedOpportunities(nodes)`

Walks the tree (same recursive pattern as `treeHasConfidence`):

```ts
function treeHasLinkedOpportunities(nodes: EbitdaNode[]): boolean {
    for (const node of nodes) {
        if (node.linked_opportunity_indices && node.linked_opportunity_indices.length > 0) {
            return true
        }
        if (node.children && treeHasLinkedOpportunities(node.children)) {
            return true
        }
    }
    return false
}
```

Returns `true` when at least one leaf in the tree carries any linked opportunity index. The recursion bottoms out at leaves; rollups (subtotals / margin) typically don't carry linked opportunities in production but the walk is permissive.

### §4 — Styling: caption step + theme tokens, mirroring `ebitda-confidence-legend`

The legend's outer `<div>` uses:

```ts
{
    fontSize: '0.875rem',       // body-small step (caption-step is 0.75rem; this matches confidence-legend)
    color: 'var(--text-tertiary)',
    marginBottom: '0.75rem',
    lineHeight: 1.6,
}
```

Each inline dot is a 10 × 10 px span:

```ts
{
    display: 'inline-block',
    width: '10px',
    height: '10px',
    borderRadius: '50%',
    background: 'var(--lever-revenue)',   // or --lever-cost / --lever-both
    verticalAlign: 'middle',
    marginRight: '4px',
}
```

The lever labels render as `<strong>` to match the confidence-legend's "<strong>High</strong> = ..." treatment for its categories.

### §5 — Test gating

Test fixtures mirror the `EbitdaSection.test.tsx` pattern for the confidence legend:

- "Legend absent when no node carries linked opportunities" — render with a tree where every `linked_opportunity_indices` is empty or undefined; assert `queryByTestId('ebitda-opportunity-link-legend')` is null.
- "Legend present when at least one leaf carries linked opportunities" — render with a tree where one leaf has `linked_opportunity_indices: [0]`; assert the legend renders AND contains the lever labels "Revenue Side", "Cost Side", "Both".
- "Legend handles nested linked opportunities on a child leaf" — mirrors the deeply-nested confidence test; assert the predicate walks the children recursively.

## Risks / Trade-offs

### Risk: legend feels redundant on data-heavy analyses

If an analysis has dozens of dots scattered across chips, the legend is a one-line caption among rich content and might feel like an obvious footnote. **Mitigation**: this is acceptable — the legend is a *discovery aid*, not a primary surface. The same trade-off applies to the strategy-map confidence legend; users glance once, learn the scale, and never read it again on subsequent visits. The legend doesn't earn its keep on every page load — it earns its keep on first-encounter and onboarding.

### Risk: two legends on the same section feels cluttered

`EbitdaSection` will now render up to two legends (confidence + opportunity-link) above the tree. **Mitigation**: both are caption-step, low-emphasis, and gated on data presence. Most analyses have at least confidence (so the confidence legend renders on most loads), and most also have linked opportunities (so the opportunity-link legend renders too). The combined visual cost is two lines of caption text. Cheaper than the alternative of nested popovers or hover-only documentation.

### Risk: lever palette could drift from the chip palette

If a future change touches `LEVER_COLORS` or its theme tokens without also touching the legend, the legend's dots could drift from the chip's dots. **Mitigation**: the legend reads from the same `--lever-revenue` / `--lever-cost` / `--lever-both` theme tokens the chip already uses via `LEVER_COLORS`. They drift together by construction. A regression test asserts the legend's dot backgrounds match the corresponding theme-token strings — same selector-based contract the strategy-map `ConfidenceLegend` uses.

### Trade-off: legend rendered as plain text, not a `<dl>` definition list

A `<dl>` / `<dt>` / `<dd>` semantic structure would be more "correct" for a definition-list of color → meaning pairs. We're using a single-line `<div>` with inline dots + plain text instead, matching the existing `ebitda-confidence-legend`. The trade-off: simpler markup, no new heading-scale impact, less screen-reader noise — but slightly weaker semantic structure. Acceptable because the legend is a single horizontally-arranged line and the lever count is fixed (always three).

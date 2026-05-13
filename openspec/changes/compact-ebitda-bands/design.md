## Context

PR #299 (the `redesign-ebitda-impact-model` change) replaced a React Flow + dagre canvas with a static vertical waterfall. That fixed the original "can't read without zooming" problem but two new issues surfaced as soon as the layout was rendered with real data:

1. **Each leaf is a full card the same size as its parent subtotal.** Three leaves under "Total Revenue" (Subscriptions / Professional Services / Other Revenue) stack into a ~500 px vertical block before COGS starts. The whole section is ~3× taller than it needs to be, and the visual hierarchy "this is a subtotal, these are its drivers" is invisible — the parent card looks like a fourth leaf.
2. **The hover description overlay overflows into the next row.** Each card renders a custom `position: absolute; top: 100%; transform: translateX(-50%)` description box. When a leaf in row N is hovered, the box overlays the leaves in row N+1, visually covering them (an opportunity description blocking "Other Revenue" is visible in the user-attached screenshot).

The strategy-map redesign (PRs #292–#296) shipped earlier in the same arc has the right compact aesthetic for this kind of data: small chips with confidence dots, organised into colored perspective bands, hover detail via native `title`. The EBITDA Impact Model should adopt that same posture without re-introducing React Flow.

## Goals / Non-Goals

**Goals:**

- Shrink the section to ~⅓ of its current vertical height by collapsing subtotal cards into band headers and leaf cards into compact chips.
- Make the "subtotal vs leaf" hierarchy visually obvious — leaves should look like drivers OF the subtotal, not siblings OF the subtotal.
- Eliminate the hover-tooltip overlap bug by adopting the strategy-map's native-`title` tooltip posture (no custom absolutely-positioned overlay).
- Preserve every functional affordance from PR #299: confidence dots (`ConfidenceIndicator`), opportunity-linking dots, `<h3>` subtotal headings, `<ol>`/`<ul>` semantic structure, mobile flex-wrap behaviour, connector arithmetic labels.
- Stay on the same static-HTML scaffold — no React Flow re-introduction.

**Non-Goals:**

- Changing the `EbitdaNode` Pydantic model, the `build_programmatic_ebitda_tree` pipeline step, or the analysis-payload contract. Backend untouched.
- Changing the strategy-map components. The styling is *inspired by* strategy-map chips/bands but the components stay independent — no shared component library extracted in this change.
- Changing `PrintEbitdaOutline.tsx` (PDF render path) — already a static layout, untouched.
- Introducing a fullscreen / expand affordance. The new layout fits at default zoom; there's nothing to escape to. PDF export remains the alternate surface.

## Decisions

### §1 — Subtotals become band headers, not cards

Each P&L row is a `<section>` (or `<li>` within the existing `<ol>`) with the structure:

```
┌─ band header ─────────────────────────────────────────────┐
│ ▎ TOTAL REVENUE          $15M-$200M                       │
└───────────────────────────────────────────────────────────┘
   ┌─ chip ──┐ ┌─ chip ──┐ ┌─ chip ──┐
   │Subs 80% │ │Prof 15% │ │Other 5% │
   │$12M-160M│ │$2M-$30M │ │$750K-10M│
   │  ●●●    │ │  ●●○    │ │  ●○○    │
   └─────────┘ └─────────┘ └─────────┘
```

The band header:
- One row tall (height equals the leaf-chip row when no leaves exist).
- A colored left strip (`border-left: 4px solid <type-color>`) — same treatment the strategy-map perspective headers use.
- The subtotal label in `<h3>` (preserved from PR #299 — screen-reader navigation contract holds).
- The subtotal `value_range` displayed inline to the right of the label.
- No description, no opportunity-dot row, no confidence chip — subtotals carry no own confidence per `ebitda-tree-confidence`, and the description was never read on subtotals.

### §2 — Leaves become compact chips

Each leaf is a chip dimensioned and styled like the strategy-map's objective chips:

- Width: ~150–180 px, height: ~80–100 px (vs. today's ~300 × 150).
- Padding: `8px 12px` (vs. today's `14px 18px`).
- Label: 13 px bold colored by `type` (revenue green / cost red), single line.
- Value range: 14 px on its own line.
- Percentage of parent + `ConfidenceIndicator` (small) on the same line below.
- Opportunity-link indicator dots: same row of small dots as today, but no separate row — inline with the value range.

The visual treatment (background tint, border, slight box-shadow) matches the existing strategy-map chip aesthetic — single border, no glow.

### §3 — Drop the custom hover description overlay

The absolutely-positioned `position: absolute; top: 100%; transform: translateX(-50%)` block in today's `EbitdaNodeComponent` is the source of Problem 2 (overlapping the next row). Replace with the strategy-map's posture:

- The leaf chip's *node-level* description becomes the native HTML `title` attribute on the chip's outer element. Browser-controlled tooltip; no overflow risk.
- The opportunity-link tooltip (which today renders inside the same overlay) becomes a native `title` on each dot, listing the opportunity's name and value lever — exactly the same wording, just delivered via `title` instead of a custom overlay. Today's per-dot `title="${opp.title} (${opp.valueLever})"` already exists; we just remove the redundant overlay that duplicates the same info.

Net effect: no custom overlay, no overflow, hover behaviour stays informative.

### §4 — Connectors and `<ol>` structure preserved

The `▼ minus` / `▼ equals` connectors between bands stay verbatim. They're the only on-screen artifact of the P&L sequence; removing them would lose the arithmetic. They sit between the band rows in the same `<ol>` (one `<li>` per band, connector inside that `<li>` per current implementation).

### §5 — Mobile breakpoint via `flex-wrap` (no media query)

The chip row inside each band uses `display: flex; flex-wrap: wrap; gap: 12px`. On a 375 px viewport the chips wrap to a second row inside the band; the band header still sits on its own row above. Same responsive mechanism PR #299 introduced; no new media queries.

### §6 — Type-color palette stays

Each band header's left-strip colour and each chip's accent colour follow the existing `NODE_COLORS` map (`revenue: green`, `cost: red`, `margin: blue`, `subtotal: amber`). No re-skin — only structural changes.

### §7 — `<h3>` heading scale preserved

PR #299 added `<h3>` on subtotal labels for screen-reader navigation. The band-header form keeps `<h3>` (still renders the same five subtotal labels in P&L order). Leaves still render their labels in non-heading elements. Heading-scale contract from `ebitda-impact-model` Requirement §6 is unchanged.

### §8 — `EbitdaNodeComponent` interface evolves, not splits

Rather than introduce two separate components (`EbitdaBandHeader` + `EbitdaChip`), keep one `EbitdaNodeComponent` with the existing `isSubtotalHeading` boolean prop steering between the two visual variants. The component's body branches:

- `isSubtotalHeading: true` → render the band-header variant (one-line, colored strip, `<h3>`, no opportunity dots, no description tooltip).
- `isSubtotalHeading: false` → render the compact-chip variant (multi-line, full type-color treatment, `ConfidenceIndicator`, `title` tooltip, opportunity dots).

Two variants, one component, minimal new exports. Diff stays small.

## Risks / Trade-offs

### Risk: visual-regression baselines break again

PR #299 already broke any Playwright / Percy screenshot baselines pinned on the React Flow canvas. This PR breaks them again. **Mitigation**: rebaseline once after this change lands. The cost is one-time; the result is a baseline that matches the *user-visible* design rather than a transitional state.

### Risk: native `title` tooltips are less rich than the custom overlay

Today's custom overlay shows the description plus a styled "AI Opportunities" subsection listing each linked opportunity's title with a colored dot. The native `title` is a plain text bubble — no rich content. **Mitigation**: the value-range + percentage + confidence-chip on the chip itself carries the headline information; the long-form description is a "tell me more on hover" detail. The hover audience is users who already saw the chip and want context; a plain tooltip is sufficient. If product feedback says otherwise, a follow-up change can re-introduce a portal-based tooltip that doesn't overflow.

### Risk: chip row overflow when a parent has 5+ leaves

The fixtures today don't exceed 3-4 leaves per parent, but the backend templates *could* emit more for a future industry. **Mitigation**: `flex-wrap` already handles this — chips wrap to a second row inside the band. Visual cost is one extra row of chips, which is fine; the band header still anchors the row.

### Trade-off: chips look more like the strategy-map than EBITDA's current identity

The user explicitly asked for this. The current "EBITDA aesthetic" (big cards, glow, heavy borders) is what this change is removing. The convergence with strategy-map styling is a feature, not a bug — both surfaces benefit from the same compact-chip language across the analysis page.

### Risk: opportunity-link dots become harder to spot on a smaller chip

Today's 10 px dots will scale down to ~8 px on the chip. **Mitigation**: keep the 10 px dot size unchanged — chips have room for a dot row in the available padding. If readability suffers, the dot row can sit underneath the chip body as a separate row inside the chip (same flex-direction column structure, just tighter).

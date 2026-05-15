## Context

The analysis-detail page has been iterated section-by-section across half a dozen changes (the strategy-map redesign series, the EBITDA waterfall, the EBITDA compact-bands follow-up). Each section ended up internally coherent but the page as a whole has visual drift:

- The strategy-map chips and the Value Impact card already follow a "neutral body, colored-edge accent" pattern (`borderLeft: '3px solid {accent}'` and `borderTop: '3px solid {color}'` respectively).
- The EBITDA chips bypass theme tokens entirely and paint chip backgrounds, borders, and label text with hardcoded RGB literals (`rgba(34, 197, 94, 0.10)` etc.).
- The result is that scrolling from Strategy → EBITDA feels like switching between two design systems.

In parallel, the design tokens for body text have a contrast hole on the dark theme:

| Token | Dark value | Contrast vs `--bg-base` | WCAG |
|-------|-----------|------------------------|------|
| `--text-primary` | `#eef2ff` | 16.1 : 1 | ✓ excellent |
| `--text-secondary` | `#8b9ac4` | 5.0 : 1 | ✓ AA (feels weak) |
| `--text-tertiary` | `#4d5b7f` | 1.9 : 1 | ✗ **fails AA** |

The light theme already passes at acceptable ratios — the design *intent* (primary = "page body", secondary = "supporting", tertiary = "caption") is honored in light mode but is fictitious in dark mode where tertiary is below the AA floor.

Cross-cutting concern: the analysis components use 11 distinct inline `fontSize` values, with no shared scale. The codebase has utility classes (`.text-sm`, `.text-base`, `.text-lg`) that the inline-styled components mostly ignore.

## Goals / Non-Goals

**Goals:**

- Align the EBITDA section visually with the strategy-map and Value Impact patterns — neutral body, single colored-edge accent.
- Lift dark-theme `--text-tertiary` above WCAG AA (4.5:1 minimum). Lift `--text-secondary` to feel "comfortable to read in dense layouts" (~7:1+).
- Replace the 11 inline `fontSize` values in the analysis components with five canonical rem steps for consistent vertical rhythm.
- Keep light theme unchanged where it already passes — touch the dark theme only.
- Same content, same data, same layout, same backend.

**Non-Goals:**

- Changing the page's beat order (governed by `analysis-detail-narrative`; out of scope).
- Introducing a new component library / shared chip component. EBITDA and strategy-map already use independent components that *converge stylistically* on the colored-edge pattern; we're not extracting a shared abstraction here.
- Adding new theme tokens for the type scale. The five rem values are used directly in inline styles for now; a follow-up could introduce `--text-size-{caption|body-small|body|heading-small|heading}` tokens if that surface earns its keep.
- Adjusting the EBITDA `NODE_COLORS` text colors that survive (the 3px accent stripe color). Those keep their existing semantic mapping (revenue green, cost red, margin blue, subtotal amber).
- A full visual-regression rebaseline of every page. Snapshots may need updating; this change accepts that as one-time cost.

## Decisions

### §1 — EBITDA chip adopts the strategy-map colored-left-border pattern

The strategy-map chip uses `borderLeft: '3px solid {perspective-accent}'`. The Value Impact card uses `borderTop: '3px solid {lever-color}'`. The EBITDA chips arrange horizontally inside their band (chips side-by-side, band header above). The natural fit is the strategy-map pattern: a 3px **left border** on each chip, accent-colored per type.

Diagram:

```
Today (chromatic bath)              Proposed (colored-left-border)

┌──── rgba(34,197,94,0.10) ────┐    ▎┌──────────────────────┐
│ #22C55E bold green label      │    ▎│ Subscriptions         │  ← var(--text-primary)
│ #FFF value range              │    ▎│ $12M-$160M            │
│ #888 80% of parent            │    ▎│ 80% of parent         │  ← var(--text-secondary)
│ ●● opp dots                   │    ▎│ ●● opp dots           │
└── rgba(34,197,94,0.35) ───────┘    ▎└──────────────────────┘
   border                              ↑           ↑
                                       3px solid   var(--bg-surface-2) body
                                       {accent}    var(--border-subtle) border (1px)
                                       left
```

Concrete style change on the chip's outer `<article>` (in `EbitdaNodeComponent.tsx`):

```diff
- background: colors.bg,                         // rgba({type}, 0.10)
+ background: 'var(--bg-surface-2)',
- border: `1px solid ${colors.border}`,          // rgba({type}, 0.35)
+ border: '1px solid var(--border-subtle)',
+ borderLeft: `3px solid ${colors.text}`,        // ← only color signal
```

And on the chip's label `<div>`:

```diff
- color: colors.text,                            // #22C55E / #EF4444 / etc.
+ color: 'var(--text-primary)',
```

The band header's 4px colored left strip from PR #301 is **unchanged**. Two stripes line up vertically — one on the band, one on each chip below it — both carrying the same hue. Calm and consistent.

### §2 — Dark-theme `--text-secondary` and `--text-tertiary` get a contrast bump

The user explicitly chose the single global lift over the analysis-only scope. The edit is two lines in `globals.css`:

```diff
:root {
-   --text-secondary: #8b9ac4;    /* 5.0 : 1 contrast — passes AA but feels weak */
+   --text-secondary: #a8b4d6;    /* 7.5 : 1 contrast — AAA-large, AA-normal      */
-   --text-tertiary:  #4d5b7f;    /* 1.9 : 1 contrast — FAILS WCAG AA              */
+   --text-tertiary:  #7c8aaf;    /* 4.6 : 1 contrast — just passes AA-normal      */
}
```

The light-theme branch (under `[data-theme="light"]` in `globals.css`) is unchanged — the tokens there are already at acceptable ratios. After this change, both themes carry the same design *intent* — secondary reads as "supporting", tertiary as "caption" — both meeting AA.

Side effects (intentional per user direction): every page that uses these tokens benefits. Dashboard table captions, admin labels, login form helper text, sidebar nav muted items all become more legible on dark mode. If any non-analysis surface relied on the old dim values for *intentional* deemphasis, that surface should either accept the lift or migrate to a future `--text-quiet` token — but the current production posture is "honest about AA, consistent across themes".

### §3 — Five canonical type-scale steps for inline `fontSize`

The 11 inline `fontSize` values across analysis components are flattened to five steps that match the existing CSS utility-class scale (`globals.css` lines 233-269):

| Step | rem | Use |
|------|-----|-----|
| caption | `0.75rem` | helper text, dot labels, "% of parent" |
| body-small | `0.875rem` | dense secondary copy, chip subtitles |
| body | `1rem` | section body, list items |
| heading-small | `1.125rem` | subheadings within a section |
| heading | `1.5rem` | section titles when not page-level |

Three display-stat surfaces keep their existing custom sizes — they're "headline display" elements that establish the page at a glance, not body type:

- `AnalysisHeader` `<h1>` (company name) → `1.625rem`
- `AnalysisOverviewCards` big risk-score number → `2.5rem`
- `ValueLeverSummary` lever-count number → `1.75rem`

Mapping these into the five-step scale would visibly shrink the page's headline elements (the big risk score that anchors the overview, the count badges on the Value Impact card). That's "consistent but worse." The three carve-outs are documented in the `analysis-page-readability` spec.

This isn't introducing CSS tokens (e.g. `--text-size-body`) — it's a discipline change. Inline styles consume one of these five rem values directly. If we later commit to typography tokens, the migration is a regex away.

### §4 — Light theme parity check (not a rewrite)

The user wants both themes to "use the same design". After §2's dark-theme lift:

- Both themes have tertiary text at ~4.6:1 (AA pass).
- Both themes have secondary text at ~7.5:1.
- Light-theme tokens stay at their existing hex values — no rewrite. The proof of "same design" lives in the contrast math, not in the literal hex values.

If a future audit finds the light-theme contrast has drifted (it currently passes), that's a separate change; not this proposal's scope.

## Risks / Trade-offs

### Risk: visual regression on non-analysis pages

Bumping the global tokens means the dashboard / admin / login look subtly different in dark mode. **Mitigation**: the user explicitly opted into the single global lift. Pages that show muted captions become more legible; that's the intent. If any single surface looks "too loud", we file a follow-up to introduce a `--text-quiet` token for that case rather than reverting.

### Risk: EBITDA chip "looks too plain" without the colored body

Today's chips are visually loud — green tint on every revenue chip, red tint on every cost chip. After the swap, the chips are gray with a 3px colored left edge. **Mitigation**: this is exactly the strategy-map and Value Impact aesthetic that the user said the EBITDA section should match. If product feedback says the accent is too subtle, the fallback is a 4px or 5px left border (still well below the chromatic-bath floor of the current design).

### Risk: type-scale audit may regress information-density tuning

Some inline sizes were deliberately tuned (e.g. `0.9375rem` instead of `0.875rem` on a specific subtitle). Collapsing to five steps means some surfaces will read a hair larger or smaller than today. **Mitigation**: the migrated surfaces still pick the *closest* of the five steps; the visual delta is at most 4% on any single surface and improves overall rhythm. If a specific surface looks wrong after the sweep, we adjust it one rem step in either direction.

### Risk: snapshot / Playwright baselines

Existing visual-regression baselines pinned on the saturated EBITDA chips or specific font sizes will fail. **Mitigation**: rebaseline as part of this PR. One-time cost.

### Trade-off: no shared chip component extracted

Both `EbitdaNodeComponent` and `StrategyMapNode` now follow the same visual pattern (neutral body, colored-left-border). An obvious next step would be to extract a `Chip` primitive. We're not doing that here — the two components have different *contents* (EBITDA chip has value range + percentage + dots; strategy-map chip has confidence + lane indicator) and a shared abstraction risks forcing a lowest-common-denominator API. Defer to a future "ui-component-library" change if the cost-of-divergence becomes real.

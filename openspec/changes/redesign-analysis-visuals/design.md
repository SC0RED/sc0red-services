# Design — Redesign Analysis Visuals

## Context

The analysis page (`/analysis/[analysisId]`) renders three AI-generated visualisations on top of the same underlying data: strategy map (Balanced Scorecard objectives), EBITDA tree (P&L decomposition), and value chain (Porter-style step list). All three reference a shared `Opportunity[]` array via index pointers — `opportunity_indices` on value-chain steps, `linked_opportunity_indices` on EBITDA leaves. Strategy-map objectives do NOT currently carry opportunity links, even though the AI generates objectives and opportunities in the same call.

Today, each tool surfaces those links its own way:

- **EBITDA** — coloured dots at the bottom of each leaf chip, one per linked opportunity, dot colour derived from `value_lever` via `LEVER_COLORS` (Revenue green, Cost violet, Both cyan). Two captions sit above the canvas: "Confidence: high/medium/low" and "AI Opportunities targeting this P&L line" (PR #305).
- **Value chain** — a text list of opportunity titles rendered under each step.
- **Strategy map** — nothing. The objective chips show a "•••" confidence indicator and a hover tooltip with the objective's own detail, but no opportunity link.

Zack's feedback (PDF page 4, items #5a/#5d) reads as one observation expressed two ways: the three tools should share one visual language for "this object has an opportunity targeting it", and that language should be the EBITDA pattern. He separately wants confidence dots gone (#5b) — they compete with the more useful opportunity-link signal and aren't decision-relevant for a PE reader.

This design covers: (1) the shared overlay system, (2) the new strategy-map layout (#4, #5e), (3) the new 2x2 matrix (#6), (4) the schema additions needed to give strategy-map objectives an opportunity-link list.

## Goals / Non-Goals

**Goals:**

- Three analysis tools that read as one coordinated story, with one visual idiom for "X targets this".
- A single hover provider that lets a click on any node/step in any tool highlight the corresponding opportunity card below — and vice versa.
- Strategy map laid out as a Balanced Scorecard table, not a free-form canvas, with a Mission-first header.
- A Quick Wins matrix below the OpportunitiesList that surfaces the high-impact / short-timeline opportunities at a glance.
- Print-export parity: every screen change has a print counterpart.

**Non-Goals:**

- Numeric ROI / investment plotting in the matrix (Path B). Free-text fields stay; the matrix uses categorical buckets in v1.
- Removing the `confidence_level` / `confidence_basis` fields from the AI pipeline. The data stays — only the visual is dropped, in case a future review or audit surface wants it.
- Rebuilding the AI pipeline. We add one optional field to the strategy-map schema (objective-level opportunity links); everything else uses fields that already exist.
- Real-time hover sync via WebSocket or AppSync. Hover is a same-tab interaction; cross-tab sync isn't on the demo path.

## Decisions

### 1. One overlay system, three tools — lift EBITDA's pattern

**Decision:** The cross-tool opportunity overlay is colored dots at the affected node/step, one per linked opportunity, dot color from `LEVER_COLORS` keyed by the opportunity's `value_lever`. The legend above each canvas explains the colors in one sentence. EBITDA already does this (PR #305); value chain and strategy map adopt it.

**Alternatives considered:**

| Alternative | Why rejected |
|---|---|
| Sidebar overlay panel ("3 opportunities affect this node") on hover | Heavier UX, requires new layout slots in three components, doesn't read at a glance |
| Numeric badge ("3" in a circle) | Loses the lever colour (Revenue vs Cost vs Both) which is the more decision-relevant signal |
| Per-opportunity icon badges | Doesn't scale past ~3 opportunities per node |
| Keep EBITDA's dots but use a different idiom for the other two | Defeats the point — Zack flagged the inconsistency |

The dot pattern caps gracefully at ~5 dots per node; nodes with more get a `+N` badge. EBITDA's PR #305 already handles this case; the shared dot-strip component should be lifted out of EbitdaNodeComponent into `frontend/src/components/analysis/OpportunityDotStrip.tsx` and used by all three tools.

### 2. Strategy map carries opportunity links via a new optional schema field

**Decision:** Add `linked_opportunity_indices: list[int] | None` to each strategy-map objective in the AI schema. The pipeline already has access to the generated opportunities at strategy-map synthesis time; the prompt adds one instruction ("for each objective, list the indices into the opportunities array that would advance this objective; leave empty if none"). The field is optional (defaults to empty list) so legacy analyses produced before this change don't blow up the renderer.

**Alternatives considered:**

| Alternative | Why rejected |
|---|---|
| Compute the link in the frontend by string-matching titles | Brittle; AI-generated strings drift; produces false positives |
| Add a separate synthesis step after both arrays exist | Extra LLM call, extra latency, extra cost — for a field the existing synthesis step already has the context to fill |
| Use the existing `strategic_category` enum on the opportunity to bucket by perspective | Too coarse — buckets opportunities by perspective, not by specific objective |

This change touches `backend/src/pipeline/prompts/strategy_map/system/strategy_map_generator.md`, the strategy-map JSON schema, and the strategy-map Pydantic model. Same pattern as the existing EBITDA `linked_opportunity_indices`.

### 3. Strategy-map layout — Balanced Scorecard table, not React Flow canvas

**Decision:** Drop the React-Flow free-form canvas. Render the strategy map as a CSS-grid table:

```
┌────────────────────────────────────────────────────────────────────┐
│   MISSION   <mission statement, banner-style across the top>       │
├────────────────────────────────────────────────────────────────────┤
│   VISION    <vision statement, eyebrow above the table>            │
├──────────────┬─────────────────┬─────────────────┬─────────────────┤
│  Financial   │  <theme col 1>  │  <theme col 2>  │  <theme col N>  │
│  "What success                                                     │
│   looks like"                                                      │
├──────────────┼─────────────────┼─────────────────┼─────────────────┤
│  Customer    │                                                     │
│  "Who we serve                                                     │
│   & why us"                                                        │
├──────────────┼─────────────────┼─────────────────┼─────────────────┤
│  Internal    │                                                     │
│  Processes                                                         │
│  "The themes we                                                    │
│   must master"                                                     │
├──────────────┼─────────────────┼─────────────────┼─────────────────┤
│  Org. Capacity                                                     │
│  "Who we are                                                       │
│   inside"                                                          │
├────────────────────────────────────────────────────────────────────┤
│   VALUES    <comma-separated values, strip across the bottom>      │
└────────────────────────────────────────────────────────────────────┘
```

Each cell renders an objective: title (bold), one-line definition, and the opportunity-dot strip. No confidence dots. The cause-and-effect arrows from the current canvas are dropped — they were beautiful but reviewers consistently ignored them in usability sessions (per the WAWA / TRJ exemplars the AI is trained on, Balanced Scorecards are tables, not graphs).

**Alternatives considered:**

| Alternative | Why rejected |
|---|---|
| Keep React Flow, just add Mission banner + Values strip | Doesn't address Zack's "easier to read" feedback — the canvas IS the readability problem |
| HTML table (`<table>`) | Worse for responsive — CSS grid handles theme-column wrapping cleanly |
| Re-render the canvas's chips with new styling but keep the canvas | Layout drift between automatic and manual chip positioning would persist |

`StrategyMapCanvas.tsx` (the React Flow component) is deleted. `StrategyMapView` becomes the table renderer.

### 4. 2x2 Quick Wins matrix — categorical v1, numeric v2 deferred

**Decision:** Render the matrix on `impact_rating` (Y axis: High / Medium / Low) × `timeline` (X axis: Quick Win (1–3 months) / Medium-term (3–9 months) / Long-term (9+ months)). Each opportunity is plotted as a dot at the intersection, colored by `value_lever`. The 3×3 grid of intersections collapses visually into the four conceptual quadrants:

```
                       Quick Win  Medium-term  Long-term
                       ┌─────────┬───────────┬──────────┐
        High impact    │ Quick   │           │ Strategic│
                       │ Wins    │           │ Bets     │
                       ├─────────┼───────────┼──────────┤
        Medium impact  │         │           │          │
                       │         │           │          │
                       ├─────────┼───────────┼──────────┤
        Low impact     │ Fill-Ins│           │ Avoid    │
                       │         │           │          │
                       └─────────┴───────────┴──────────┘
```

Clicking a dot scrolls the matching OpportunitiesList card into view and pulses it.

**Three implementation paths considered:**

| Path | Approach | Verdict |
|---|---|---|
| **A. Parse free-text** | Regex midpoints out of `investment_range` and `roi_estimate` to get numeric (x, y) | Reject — fragile, AI format drifts, plots silently break |
| **B. Add numeric schema fields** | New `investment_value: int` (USD) + `roi_estimate_pct: float` fields, AI fills both prose + numbers | Defer — proper future, but requires schema migration + prompt rework. Out of scope for v1 |
| **C. Categorical 3×3 grid** | Use `impact_rating` × `timeline` (both already enum-like) as bucketed axes | **Recommend** — ships immediately, uses fields the user already sees on each opportunity card |

Path C is honest about what we have. The dot positions are deterministic (each opportunity lands in exactly one cell), and the quadrant labels translate the cell positions into the language a PE reader uses.

**Cells with overlapping dots** stack vertically with a small offset, sorted by `strategic_category` for stable ordering across renders. Cells with no opportunities render an empty placeholder cell so the grid never collapses.

### 5. Hover provider — React Context, no global state

**Decision:** A new `OpportunityHoverProvider` wraps the analysis sections. It exposes:

```ts
interface OpportunityHoverContext {
  hoveredOpportunityIndices: number[]
  highlightOpportunities: (indices: number[]) => void
  clearHighlight: () => void
}
```

Hover-source components (EBITDA leaves, value-chain steps, strategy-map cells, matrix dots) call `highlightOpportunities([...indices])` on mouse-enter and `clearHighlight()` on mouse-leave. Hover-target components (OpportunitiesList cards) subscribe via `useContext` and apply a pulse/scroll-into-view when their index appears in `hoveredOpportunityIndices`.

**Alternatives considered:**

| Alternative | Why rejected |
|---|---|
| Zustand / Redux | Heavy for one piece of ephemeral hover state, no benefit |
| URL params / search params | Hover is sub-second, not URL-worthy |
| Imperative refs and `scrollIntoView` from every source | Tight coupling; every source would have to know how to find OpportunitiesList |

The provider also coordinates the reverse direction — hovering an opportunity card highlights the corresponding nodes in the three tools above. That's the symmetry that makes the page feel like one document.

### 6. Print-export parity

**Decision:** Every screen change has a print counterpart in `frontend/src/components/print/`. Specifically:

- The strategy-map print component (`PrintStrategyMapObjectives.tsx`) loses its confidence-chip column and gains the opportunity-dot strip.
- The EBITDA print component (`PrintEbitdaOutline.tsx`) loses its confidence-callout block.
- The value-chain print component (`PrintValueChainList.tsx`) loses the text list and gains a dot strip (the print version is dot + opportunity-title-list, since the print medium has no hover).
- A new `PrintQuickWinsMatrix.tsx` renders the 2x2 as a static SVG (no hover, no click — but the visual landmark survives the export).

Hover behaviour is intentionally absent from print — it's a screen-only affordance. The legend captions are identical between screen and print so a reader who skims the PDF then opens the app gets the same vocabulary.

## Risks / Trade-offs

- **[Risk] Deleting `StrategyMapCanvas` strands the React Flow dependency** if no other component uses it. → **Mitigation:** Grep for `@xyflow/react` consumers before deleting; if EBITDA's tree still uses it (likely), the dependency stays. If nothing uses it, drop it from `package.json` to shed bundle weight.
- **[Risk] Categorical 2x2 looks crowded** on analyses with 20+ opportunities clustered in High-Impact / Medium-Term. → **Mitigation:** Cells stack vertically with offset; clicking the cell zooms a tooltip listing all opportunities at that intersection. If a single cell holds >8 dots, the cell shows a `+N more` badge with the same click-to-expand affordance.
- **[Risk] Schema addition (`linked_opportunity_indices` on objectives) breaks legacy analyses** that don't carry the field. → **Mitigation:** Field is optional and defaults to `None` / empty list in both Pydantic model and frontend type. Legacy analyses render the strategy map without dots — same as today. The opportunity-link legend is omitted when no objective carries the field.
- **[Risk] The hover provider's scroll-into-view becomes annoying** when a user is reading the opportunity list and hovers a node in the strategy map two screens up. → **Mitigation:** `scrollIntoView({ behavior: 'smooth', block: 'nearest' })` — `nearest` means the page only scrolls if the card is fully out of view, not if it's already partially visible.
- **[Risk] Removing confidence dots invalidates analyses that referenced "high-confidence objectives"** in prior reports / emails. → **Mitigation:** The data stays in the pipeline; only the chip is gone. If a future feature wants to surface confidence (e.g., a "confidence audit" toggle), the field is still there. No backfill needed.
- **[Risk] React Flow → CSS grid migration breaks responsive layout** below ~900 px viewport. → **Mitigation:** Theme columns wrap to two-up grid on viewports below 900 px; the perspective rows stack vertically. Visual smoke at 600 / 900 / 1200 / 1920 px before merge.
- **[Trade-off] Dropping the cause-and-effect arrows** loses a signal some PE readers genuinely use (the chain from "improve customer experience" → "grow ARR"). → Accepted because (a) the arrows live in the AI output and can be re-surfaced in a "story view" later, and (b) the Balanced Scorecard table communicates the cause-and-effect intent through row order — Financial at top (the outcome), Org Capacity at bottom (the cause). This is the canonical Kaplan-Norton read.

## Migration Plan

This change has no data migration. The AI schema gains one optional field; all existing analyses keep working.

**Phased rollout:**

1. **Phase 1 — Backend schema addition.** Add `linked_opportunity_indices` to strategy-map objective Pydantic model + JSON schema. Update the system prompt to instruct the AI to fill it. Re-generate one or two test analyses to confirm the field populates. No frontend change yet — the field is read but not rendered.

2. **Phase 2 — Shared overlay components.** Extract `OpportunityDotStrip` and the new shared `AnalysisLegend` component. Migrate `EbitdaNodeComponent` and `ValueChainDiagram` to use them. Drop the EBITDA confidence chip and value-chain text list. Strategy map still uses the old canvas — Phase 3 swaps that.

3. **Phase 3 — Strategy-map layout overhaul.** Replace `StrategyMapCanvas` with the CSS-grid table. Drop confidence dots. Add Mission banner + Values strip. Wire the opportunity dots from the schema field landed in Phase 1.

4. **Phase 4 — Hover provider.** Add `OpportunityHoverProvider` at the AnalysisDetail root. Wire hover-source events from all three tools. Wire hover-target reactions in OpportunitiesList.

5. **Phase 5 — Quick Wins matrix.** Add `QuickWinsMatrix` component, insert into `AnalysisDetail` and `PrintReport`, wire click-to-opportunity via the hover provider.

6. **Phase 6 — Print parity + visual verification.** Mirror all screen changes in print. Capture before/after PDFs on three representative analyses (sparse / mid-size / deep) and review.

7. **Phase 7 — Ship.** PR per phase if reviewers prefer small diffs, or one PR if a coordinated demo is the goal. Promote dev → testing → production once visual verification signs off.

**Rollback:** Each phase is git-revertable independently. The Phase 1 schema field is additive; even if Phases 2–5 are reverted, the field stays harmless in the pipeline.

### 7. Source-side opportunity popover (revises D5)

**Decision:** Hovering a source surface (strategy-map cell, EBITDA leaf, value-chain step) SHALL open an inline floating popover near the source that lists the 1-3 linked opportunity titles (each prefixed with a small lever-coloured dot). Each entry in the popover is a button — clicking imperatively scrolls + pulses the matching opportunity card via the same imperative-scroll pattern used by the Quick Wins matrix chip click. The hover ALSO pulses the matching cards below as before (D5 still applies for the pulse; what changes is that the hover provider no longer fires `scrollIntoView`).

**Background — why this update is needed:** D5 originally specified "pulse + scroll into view on hover". P5 (PR #356) shipped that behavior; in production a PE reviewer complained that hovering any strategy-map cell pulled the page down 1-2 sections. The opportunity cards always live below the strategy-map section, so `block: 'nearest'` never short-circuited the scroll. PR #361 removed scroll-on-hover entirely, leaving only the pulse. But the pulse alone is invisible when the linked card is below the fold — Diagnostic Tool Feedback #5c ("hover points to specific initiatives") fails because the user sees no per-initiative cue. This decision restores the missing source-side signal without re-introducing the scroll bug.

**Alternatives considered:**

| Alternative | Why rejected |
|---|---|
| Scroll-on-hover with 300 ms dwell guard | Still surprises new users on first hover; complex timing logic that the production complaint already invalidated |
| Replace the dot strip with a count pill ("→ 3 opportunities"); click-only navigation | Loses the at-a-glance lever-colour signal the dot strip gives today; removes a primitive we just shipped in P2 |
| Keep pulse-only and accept the gap | Leaves the reviewer's #5c check unfixed; offscreen targets feel broken |

The popover surfaces the same titles a user would reach by scrolling, without forcing the scroll. The click-to-navigate path stays consistent with the Quick Wins matrix chip click — both are intentional-navigation gestures.

Popover lifecycle:

- Open on **`mouseEnter` after 150 ms dwell** (avoids flicker when the user is moving the cursor past the source).
- Close on **`mouseLeave` after 200 ms grace** (so the cursor can transit from source → popover without dismissal).
- Close on **`Escape` keypress** + on outside click.
- Open on **keyboard focus**; close on blur with the same containment guard used elsewhere (P5 pattern).

The popover is a NEW shared primitive at `frontend/src/components/analysis/SourceLinkedOpportunitiesPopover.tsx`. Three consumers wire it in: `StrategyMapTable`'s `ObjectiveEntry`, `EbitdaNodeComponent`'s `LeafChip`, and `ValueChainDiagram`'s `StepCard`. The Quick Wins matrix chips do NOT need it — their titles are already inline.

### 8. Matrix axes flip — path B (numeric ROI × Investment), supersedes D4

**Decision:** Replace the 3×3 categorical matrix (impact_rating × timeline) with a continuous 2D scatter plot on numeric ROI vs Investment. The `Opportunity` Pydantic model + the AI opportunity-generation prompt gain two new fields:

- `investment_value_usd: int | None` — estimated USD cost to implement. `None` when the AI cannot infer a number from the available context.
- `roi_estimate_pct: float | None` — estimated ROI percentage, range 0 .. 500. `None` when the AI cannot infer a number.

The matrix's X axis is **log-scale Investment** (10K → 10M+ USD — investment ranges span 3 orders of magnitude in practice; linear scale crushes everything below $100K into a single column). The Y axis is **linear ROI** (0 → 300%, with a clamp to 300% so a single outlier doesn't squash the rest). Each opportunity is a dot positioned by its (investment, ROI) pair. Four quadrant labels render in the corners:

- **Quick Wins** (top-left): low investment + high ROI
- **Strategic Bets** (top-right): high investment + high ROI
- **Fill-Ins** (bottom-left): low investment + low ROI
- **Deprioritise** (bottom-right): high investment + low ROI

Opportunities with either field `None` render in a grey "uncalibrated" footer strip below the scatter (a horizontal row of dots labelled "Opportunities without ROI / investment estimates"). This is deliberate: forcing the AI to invent numbers it doesn't have produces worse data than admitting the gap.

**Background — why this overrides D4:** D4 chose path C (categorical impact × timeline) because the AI fields were free-text strings. The reviewer (Zack via the design review) pushed back: "this isn't a ROI × Investment 2×2, it's an impact × timeline 3×3 — and the 9-cell layout muddies the four-quadrant story". Zack literally asked for ROI × Investment in the original feedback (Diagnostic Tool Feedback #6). Path B is what was requested. The schema migration that D4 deferred as a follow-up is now in-scope.

**Alternatives considered (re-evaluated):**

| Alternative | Why rejected |
|---|---|
| Keep path C, tighten the copy | Doesn't address the literal ask; the reviewer flagged the axes |
| Binarise impact × timeline into a true 2×2 | Still uses the wrong axes; same complaint applies |
| Path B with no nullable fields (force AI to estimate every time) | AI hallucinates numbers when it has no signal; produces brittle, misleading plots |

**Migration:** The shipped path-C `QuickWinsMatrix` component is replaced wholesale. No flag, no fallback — the prior version stays in git history only. Legacy analyses that pre-date the new fields render their opportunities in the uncalibrated strip until re-analysed. The schema fields are `Optional[int]` / `Optional[float]` with `None` defaults, so existing API responses validate against the updated model without backfill.

**Print:** Static SVG render of the scatter; same axes, same quadrant labels, no event handlers. Uncalibrated strip survives in print.

**Dot-overlap handling:** Opportunities that land on the same (x, y) pixel get a small jitter (±4 px) to remain individually clickable. If a single quadrant has > 10 dots after jitter, the renderer collapses them into a "+N more" cluster pin that opens a popover listing all opportunities in that quadrant (same UI primitive as Decision 7).

## Open Questions

- **OQ1** — Should the matrix `Avoid` quadrant be labeled differently? "Avoid" reads judgmental on the AI's own output. Alternative: "Deprioritise" or "Low ROI". Lean toward "Deprioritise" for the v1 demo. **RESOLVED: Deprioritise.**
- **OQ2** — When an objective has more linked opportunities than fit in a single cell, do we render `+N more` inline or move all opportunity dots into a per-cell tooltip? Inline `+N more` keeps the visual density honest; tooltip avoids cell-height blowout. Pick inline for v1, revisit if cells overflow in practice. **RESOLVED: Inline `+N more` shipped in P7.**
- **OQ3** — Should the strategy-map cells render the objective's `definition` prose, or only the `title`? The wawa exemplar shows both; current React Flow chips show only the title. Inline definition risks runaway cell height. Recommend: title bold + first sentence of definition in muted text, truncated to 2 lines with `text-overflow: ellipsis`. **RESOLVED: Title + first-sentence preview shipped in P6.**
- **OQ4** — Does the OpportunitiesList itself host the matrix, or does the matrix get its own `<AnalysisSection>`? Hosting inside OpportunitiesList tightens the visual link ("here's the list, here's the same data plotted"). Separate section makes it scrollable independently. Lean toward a separate `<AnalysisSection id="quick-wins-matrix">` for navigability via the in-page nav. **RESOLVED: Separate section shipped in P7.**
- **OQ5** — When the AI cannot estimate `investment_value_usd` or `roi_estimate_pct`, should we drop the opportunity from the matrix entirely or render it in an "uncalibrated" footer strip? The footer strip preserves the "every opportunity is on this surface somewhere" promise. Dropping silently is the worse failure. **RESOLVED: Footer strip per D8.**
- **OQ6** — What does the source-side popover (D7) show for sources with > 3 linked opportunities? Inline list of the first 3 + "+N more" expander? Or always show all? Three is the typical case per the prompt heuristics in P1b; show all up to 5, then `+N more` for the rare cluster. Decision pending review.

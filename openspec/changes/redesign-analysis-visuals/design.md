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

## Open Questions

- **OQ1** — Should the matrix `Avoid` quadrant be labeled differently? "Avoid" reads judgmental on the AI's own output. Alternative: "Deprioritise" or "Low ROI". Lean toward "Deprioritise" for the v1 demo.
- **OQ2** — When an objective has more linked opportunities than fit in a single cell, do we render `+N more` inline or move all opportunity dots into a per-cell tooltip? Inline `+N more` keeps the visual density honest; tooltip avoids cell-height blowout. Pick inline for v1, revisit if cells overflow in practice.
- **OQ3** — Should the strategy-map cells render the objective's `definition` prose, or only the `title`? The wawa exemplar shows both; current React Flow chips show only the title. Inline definition risks runaway cell height. Recommend: title bold + first sentence of definition in muted text, truncated to 2 lines with `text-overflow: ellipsis`.
- **OQ4** — Does the OpportunitiesList itself host the matrix, or does the matrix get its own `<AnalysisSection>`? Hosting inside OpportunitiesList tightens the visual link ("here's the list, here's the same data plotted"). Separate section makes it scrollable independently. Lean toward a separate `<AnalysisSection id="quick-wins-matrix">` for navigability via the in-page nav.

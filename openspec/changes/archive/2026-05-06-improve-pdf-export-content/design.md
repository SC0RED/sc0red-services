## Context

The `polished-pdf-export` change shipped a Puppeteer-based render pipeline (Cognito-gated proxy → boto3-invoked Node.js Lambda → headless Chromium → `page.pdf()`). That pipeline works end-to-end. The remaining problem is purely on the React side: `PrintReport.tsx` composes the same components that drive the live `/analysis/{id}` screen — `RiskBreakdown`, `OpportunitiesList`, `EbitdaSection`, `ValueChainDiagram` — and those components are designed for an interactive UI:

- `RiskBreakdown` collapses each row behind a chevron; `rationale` text is hidden until the user clicks.
- `OpportunitiesList` shows badges only; `description`, `implementation_steps`, `investment_range`, `roi_estimate` live behind an expand-toggle.
- `EbitdaTree` is a pan/zoom canvas. In the printed output only the top level renders, the Fit/Expand/zoom UI bleeds into the page, and "Scroll to pan…" help text appears as part of the document.
- `ValueChainDiagram` is a horizontal flexbox. The 6th primary-row activity falls off the page and the 5th is truncated mid-name. The component embeds its own sc0red CTA, which produces a *second* CTA on top of the one `PrintReport` adds explicitly.

The data is fine: every field needed for a richer PDF is already on `AnalysisData` (rationale, description, implementation_steps, investment_range, roi_estimate, ebitda children, linked_opportunity_indices, opportunity_indices). The fix is presentation-only.

Stakeholders: deal partners (skim-in-5-minutes audience for IC memos), operating partners (100-day plan input), portfolio CFOs (EBITDA-bridge consumers). Today's PDF serves none of them well.

Constraints:
- Puppeteer Lambda + signed-token contract is fixed; we are not changing the back-end.
- The `/print/{analysisId}` route already runs server-rendered with light-theme forced; we keep that.
- File-size limits (360 lines per component, 400 for backend) apply to all new files.
- Existing PDF-related tests (filename, content-disposition, status marker, render success/error) must keep passing.

## Goals / Non-Goals

**Goals:**
- The exported PDF surfaces every meaningful field on `AnalysisData` (no more hidden-by-default content).
- The PDF reads as a standalone diligence document — sectioned ToC, executive summary, methodology appendix, single CTA at the back.
- Print-specific components are decoupled from screen components; future screen redesigns cannot regress the PDF and vice versa.
- The EBITDA tree and Value Chain render fully within the page bounds at every zoom level (no horizontal cuts, no UI chrome bleed-through).
- A reader can connect EBITDA branches to specific opportunities and value-chain steps to specific opportunities (linkage data already exists; we just need to render it).

**Non-Goals:**
- No backend, Lambda, or signed-token changes. The render pipeline stays as-is.
- No new analysis fields or schema migrations. Every render uses fields already on `AnalysisData`.
- No PR-preview deployments or per-environment template variants.
- No localization or per-region formatting (USD-only number formatting matches today's app).
- No interactive PDF features (form fields, hyperlinks beyond external CTA URL, bookmarks). Plain print-quality PDF only.
- No replacement of Puppeteer with WeasyPrint / typst / server-rendered HTML. That tradeoff was evaluated and rejected — see Decisions §1.
- No live-tree-with-print-flag approach. Also evaluated and rejected — see Decisions §1.

## Decisions

### 1. Print-specific React components — not "force expanded" props on screen components

**Decision**: Build a parallel set of components in `frontend/src/components/print/` that accept the same `AnalysisData` slices but render for paper. `PrintReport.tsx` composes only print components; screen components stay untouched.

**Alternatives considered:**

| Option | Why rejected |
|---|---|
| Add `printMode` prop to existing `RiskBreakdown` / `OpportunitiesList` / `EbitdaTree` / `ValueChainDiagram` | Couples screen evolution to print evolution. Every future screen redesign has to think about print regression. The horizontal-cut value chain isn't fixable with a flag — it's a layout problem. |
| Server-rendered template (Python + Jinja2 / WeasyPrint / typst) | Throws away the working Puppeteer pipeline. Two codebases for the same data. Marginal-quality wins not worth two weeks of work and ongoing maintenance. |
| `react-pdf` (`@react-pdf/renderer`) | Different rendering model (no DOM, no Recharts, no design tokens). Requires re-implementing every visual primitive. |

**Trade-off**: We carry two presentations of the same domain model. Mitigation: print components consume the same `AnalysisData` types, so a schema change still surfaces as a TypeScript error in both places.

### 2. Nested HTML outline for the EBITDA tree, not the interactive canvas

**Decision**: `PrintEbitdaOutline` renders the tree as a nested `<ol>` outline (label → value range → percent → children, indented), with all levels expanded and no event handlers. Indentation alone preserves parent-child hierarchy regardless of tree shape.

**Alternatives considered:**

| Option | Why rejected |
|---|---|
| Reuse `EbitdaTree` with `disableInteractions` prop | UI chrome (Fit/Expand/zoom controls, help text) is structurally part of the component, not styled-on. A flag would cover them with `display: none` but the underlying React subtree is still there — already-shipped code shows that approach is fragile. |
| Hybrid: hand-laid SVG grid for "small" trees, outline as fallback for trees >30 nodes or depth >4 | Initial design called for this. Architecture review caught that the depth-bucketed grid loses parent-child alignment on unbalanced trees — three grandchildren on branch A and zero on branch B render in the same flat 3-column row, with no visual encoding of which root each belongs to. The outline preserves hierarchy in every case. |
| Dagre / d3-tree at print time | Adds a layout-engine dependency for one component. Indentation already conveys the hierarchy a CFO needs; a more "diagram-like" rendering is not worth the dependency cost. |

**Trade-off**: The outline doesn't have the dashboard-style visual that a sun-burst or canvas tree provides. Acceptable: print readers get a structured outline they can scan at any zoom level, without the parent-child ambiguity that an unbalanced grid creates.

### 3. Vertical stacked rows for value chain on print, not the horizontal screen layout

**Decision**: `PrintValueChainList` renders primary activities as a vertical list (one row per activity, full page width), then a section break, then support activities as another vertical list. Each row carries the activity name, role description, risk chips, and an "Opportunities #N, #M, #P → titles" callout.

**Alternatives considered:**

| Option | Why rejected |
|---|---|
| Keep horizontal layout, fix overflow with smaller font | Tested visually — at 10pt the chip labels become unreadable; at 8pt the whole row collapses. PE readers will not squint. |
| Two-column landscape page | Helps width but doesn't solve the row-truncation when an activity has many risks. Vertical layout scales naturally with content. |
| Render as a table | Loses the "step → step → step" sequence that's the whole point of value-chain analysis. A list with sequence numbers preserves order. |

**Trade-off**: Visual difference from the screen version. That's the point — print readers have different needs than screen readers. Acceptable.

### 4. Single sc0red CTA on a dedicated back-cover page

**Decision**: Remove the CTA block embedded inside `OpportunitiesList`'s print path (or wrap that CTA in a screen-only conditional) and the CTA inside `ValueChainDiagram`. Add a single `PrintBackCover` component that renders only at the end of `PrintReport`.

**Alternatives considered:**

| Option | Why rejected |
|---|---|
| Keep multiple CTAs, accept duplication | Two of three confirmed user complaints. Visible regression. |
| CTA inline at end of executive summary | Less visible than a back-cover page; partners forwarding the PDF often clip the last page deliberately, so a too-early CTA accidentally survives. Back-cover is honest. |

**Trade-off**: Back cover adds one page to short PDFs. Acceptable — most analyses already produce 6+ pages; one more makes no practical difference.

### 5. Per-section page-format overrides via `@page :name { size }` rules

**Decision**: Use named `@page` rules in `print.css` so the EBITDA tree page can be A3 landscape while the cover, executive summary, risk table, opportunity cards, value chain, and methodology appendix stay A4 portrait.

```css
@page { size: A4 portrait; }
@page ebitda-page { size: A3 landscape; }
.print-ebitda { page: ebitda-page; }
```

**Alternatives considered:**

| Option | Why rejected |
|---|---|
| Single A4 portrait everywhere | Forces the EBITDA tree to outline-only mode for almost every real analysis. Loses the visual hierarchy from §2. |
| Single A3 landscape everywhere | Wastes paper for the cover and executive summary; awkward to read on screen. |
| Force-rotate the EBITDA tree 90° | CSS rotation tricks break Puppeteer's `page.pdf()` page-counting and create accessibility issues. |

**Trade-off**: Mixed page sizes are unusual but Puppeteer + the `@page :name` pattern handles it cleanly. We confirm via a render-time test on three sample analyses.

### 6. Executive Summary is a derived view, not a stored field

**Decision**: `PrintExecutiveSummary` derives its content from existing fields:
- Risk drivers: top 3 entries from `riskScores` sorted by score descending, take their `rationale` first sentence.
- Opportunity one-liners: first 3 entries from `opportunities` sorted by `impact_rating` (High > Medium > Low) then by index, formatted as `{title} — {investment_range} · {timeline}`.
- EBITDA-uplift bar: read top-level `ebitdaTree` margin / revenue / cost values.

If any source data is missing, the corresponding row is omitted. The full Executive Summary section is itself omitted if the analysis lacks both `riskScores` and `opportunities`.

**Alternative considered:** Add a backend-computed `executiveSummary` field on `AnalysisData`. Rejected — adds schema scope to a presentation change. The derivation is deterministic and lives entirely in the print component.

### 7. Linkage callouts use the existing index arrays directly

**Decision**: `PrintEbitdaOutline` and `PrintValueChainList` resolve their `linked_opportunity_indices` / `opportunity_indices` arrays against the `opportunities` array that's already passed alongside each section. Each callout renders as `Opportunities: #2 (title), #5 (title)` so the reader can flip back to the opportunity page.

**Trade-off**: The opportunity numbering must be stable within the PDF — `OpportunitiesList`'s display order is the source of truth. We sort opportunities once in `PrintReport` and pass the sorted-with-original-index array down so linkage numbers point at the right cards.

## Risks / Trade-offs

- **Risk**: Visual regression on existing analyses — partners who pulled a PDF last week will see a materially different document this week.
  - **Mitigation**: Pre-rollout, generate before/after PDFs on 3–5 representative analyses (mix of small/large opportunity counts, mix of populated/sparse EBITDA trees). Attach to the change folder for sign-off. Roll out to development first, soak for 24h, then testing, then production.
- **Risk**: A3-landscape EBITDA pages mid-document confuse some PDF viewers / printer drivers.
  - **Mitigation**: We test on Adobe Acrobat, Preview (macOS), Chrome's built-in viewer, and the Puppeteer-side Chromium rendering. If any fails, we fall back to outline-only on A4 for that section and accept the visual loss.
- **Risk**: Hand-laid SVG coordinates for the EBITDA tree don't fit deeper trees that arrive after rollout.
  - **Mitigation**: The component implements outline fallback as a sibling render mode. A simple `if (totalNodes > 30 || maxDepth > 4) renderOutline()` switch keeps the worst case bounded.
- **Risk**: Sorting opportunities by `impact_rating` then index for the executive summary may not match the screen's display order, breaking the "Opportunity #5" linkage from EBITDA / value chain.
  - **Mitigation**: We sort *once* in `PrintReport` (or do not sort at all and accept the API order), pass the sorted-with-original-index array to `PrintOpportunityCard` and to the linkage resolvers. Linkage numbers reference the printed-PDF position, not any other index.
- **Risk**: New components push us over the 360-line frontend file limit.
  - **Mitigation**: Each print component is single-purpose and small (estimated 60–180 lines each). The composition in `PrintReport.tsx` shrinks because it no longer has to coordinate live components.
- **Risk**: Methodology Appendix surfaces "what we scraped" — could expose private URLs or stale source data.
  - **Mitigation**: Pull only fields already shown elsewhere in the app (`companyUrl`, `industry`, model name, scoring rubric reference). No new field exposure.
- **Risk**: Increased Lambda render time as the page gets longer.
  - **Mitigation**: Today's render is ~3–4s, well under the 30s timeout. Estimated impact: +0.5–1s for the additional content. No mitigation needed unless we hit the timeout in practice.
- **Risk**: Print-only sc0red CTA conditional in `OpportunitiesList` and `ValueChainDiagram` adds a screen/print branch to live components — exactly the coupling we want to avoid.
  - **Mitigation**: Instead of branching, we *delete* the in-component CTA from those components entirely and add the screen-only CTA at the parent level (the analysis detail page). One source of truth per surface. Caught early because the architecture-reviewer agent flags this kind of coupling.

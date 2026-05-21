# Proposal — Redesign Analysis Visuals

## Why

Stream B of the Diagnostic Tool Feedback (`/Users/vedratnavelani/Documents/sc0redAdvisory/Diagnostic tool feedback-v1.pdf`). The Stream A quick wins shipped as PR #350, but a coherent set of feedback items remain that share a common thread: **the three analysis tools (strategy map, EBITDA tree, value chain) feel like three dashboards next to each other, not three lenses on the same business**. Zack's feedback lands the same critique six different ways:

- Confidence dots compete with the more useful "this objective has an opportunity targeting it" signal (#5b).
- Each tool shows opportunity links differently — EBITDA has colored dots (PR #305), value chain has a text list, strategy map shows nothing (#5a).
- Legends are inconsistent: EBITDA has two captions, the others have none (#5d).
- Strategy map opens with a four-row accordion before the user has read the Mission (#4).
- The strategy-map grid feels like Jira tickets in rows rather than a Balanced Scorecard read (#5e).
- The page closes on a long opportunity list with no way to spot the "quick wins" — the high-impact, short-timeline opportunities a PE reader actually wants to act on this quarter (#6).
- A user can hover a node and see the node's own detail, but cannot see which opportunities target it (#5c).

This change treats those seven items as one design pass and ships them together so the three tools feel like a coordinated story.

## What Changes

### Cross-tool design system

- **Add** a shared opportunity-overlay treatment across strategy map, EBITDA tree, and value chain — colored dots at the affected node/step (one per linked opportunity, dot color from the existing `LEVER_COLORS` map: Revenue / Cost / Both). Lifts EBITDA's PR #305 pattern to the other two tools.
- **Add** a shared legend component sitting above each tool's canvas, explaining the dots in one sentence. Sources its strings from a single module so the three tools can never drift.
- **Add** hover-to-opportunity highlighting on every node/step that carries `opportunity_indices`. On hover, the affected opportunities in the OpportunitiesList below scroll into view and pulse briefly. On the source side, the dot expands a per-opportunity tooltip with the title + impact rating.
- **Remove** confidence dots from strategy-map objective chips (the `confidence: 'HIGH'|'MEDIUM'|'LOW'` data stays in the pipeline; only the visual is dropped).
- **Remove** the EBITDA confidence chip + legend (same rationale — the new opportunity-dot legend takes its slot above the canvas).

### Strategy map layout overhaul

- **Modify** the strategy-map header to show only Mission + Vision (the four-row accordion of Mission / Value Proposition / Strategic Priorities / Core Values collapses into a single banner with Mission as the headline and Vision as the eyebrow).
- **Modify** the strategy-map body layout — drop the React-Flow free-form canvas, render as a Balanced Scorecard table: four perspective rows × N theme columns, each row with a subtitle prose label on the left ("What success looks like", "Who we serve & why us", "The themes we must master", "Who we are inside"), a clean grid of objective cells in the middle, and a Values strip at the bottom. Reference: TRJ/sc0red slide on page 5 of the feedback PDF.

### New visualisation

- **Add** a Quick Wins matrix below the OpportunitiesList. **Original scope (path C):** a 3×3 categorical matrix on `impact_rating` × `timeline`. **Revised scope (path B, post-P7 design review):** a 2D scatter plot on numeric ROI × Investment, requiring two new opportunity fields (`investment_value_usd: Optional[int]`, `roi_estimate_pct: Optional[float]`) populated by the AI. The path-C version shipped in P7 but missed Zack's literal "ROI × Investment 2×2" ask in Diagnostic Tool Feedback #6 — Section 14 of `tasks.md` flips to path B. Quadrants labelled "Quick Wins" / "Strategic Bets" / "Fill-Ins" / "Deprioritise" stay; the axes change.

## Capabilities

### New Capabilities

- `analysis-opportunity-overlays`: Cross-tool opportunity-link visual system — the shared dot treatment, the shared legend, and the hover-to-opportunity interaction across strategy map, EBITDA tree, and value chain. Covers feedback items #5a, #5c, #5d.
- `quick-wins-matrix`: The new 2x2 ROI × Investment plot rendered below the OpportunitiesList. Covers feedback item #6.
- `strategy-map-balanced-scorecard-layout`: The wawa-style table layout (Mission banner, four labelled rows, clean grid, Values strip). Covers feedback items #4 and #5e.

### Modified Capabilities

- `strategy-map`: Existing React-Flow canvas behavior is superseded — confidence dots removed (#5b), free-form layout swapped for the Balanced Scorecard table (#5e), header collapsed to Mission + Vision only (#4). The capability stays the same in scope (display the AI-generated strategy map); the rendering contract changes.
- `ebitda-tree-confidence`: Confidence-chip render is removed (#5b). The pipeline still produces `confidence_level` / `confidence_basis` data — the spec drops only the chip's visual requirement and the legend caption. Print-export visibility is also dropped.
- `analysis-detail-narrative`: Section render order gains the new Quick Wins matrix slot below OpportunitiesList and above DocumentUpload (#6).

## Impact

- **Frontend components** (rendered on `/analysis/[analysisId]` and in print):
  - `frontend/src/components/strategy-map/` — entire view rewrite (header, layout component, node component, legend). `StrategyMapCanvas` (React Flow) likely deleted.
  - `frontend/src/components/EbitdaNodeComponent.tsx` — drop the confidence chip; opportunity dots stay (already the new pattern).
  - `frontend/src/components/EbitdaTree.tsx` + `frontend/src/components/analysis/EbitdaSection.tsx` — drop the confidence legend, keep the opportunity-link legend.
  - `frontend/src/components/ValueChainDiagram.tsx` — add opportunity dots + legend, drop the inline text-list of linked opportunities.
  - New `frontend/src/components/analysis/AnalysisLegend.tsx` — shared legend component.
  - New `frontend/src/components/analysis/QuickWinsMatrix.tsx` — the 2x2 plot.
  - New `frontend/src/lib/hooks/useOpportunityHover.ts` — hover-coordination context shared by the three tools and OpportunitiesList.
  - `frontend/src/app/(authenticated)/analysis/[analysisId]/AnalysisDetail.tsx` — wraps the analysis sections in the hover provider; renders the Quick Wins matrix.
  - `frontend/src/components/print/` — print-export mirrors the screen changes (legend, drop confidence chip, drop value-chain text list, render the matrix as a static block).

- **Backend** (unchanged for the v1 path; potential follow-up for the matrix):
  - The AI pipeline already produces `opportunity_indices` on value-chain steps, `linked_opportunity_indices` on EBITDA leaves, and `impact_rating` + `timeline` on opportunities — all the data the v1 matrix needs.
  - Strategy-map objectives currently have no `linked_opportunity_indices`. Adding this would let the strategy map carry opportunity dots like the other two tools. The proposal includes adding this field to the AI prompt + schema; design.md owns the prompt mechanics.

- **Out of scope (deferred)**:
  - Numeric `investment_value` + `roi_estimate_pct` fields on opportunities (Path B for the matrix). Design.md captures the trade-off and recommends Path C (categorical) for v1.
  - The architectural choice of whether to delete `StrategyMapCanvas` outright vs gating it behind a feature flag — defer to design.md.

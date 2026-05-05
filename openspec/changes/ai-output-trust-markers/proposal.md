## Why

Two trust-signal issues flagged in the UX review (Audits 5 and 7) and queued from the BA-track follow-up plan:

**Audit 5 — risk-tier vs confidence color collision.** The same green/amber/red palette is used for two semantically opposite signals. On the analysis page:

- Overall AI Risk Score badge — green = low risk (good)
- Risk Dimensions chips — green = low risk (good)
- Risk Breakdown card numbers — green = low risk (good)
- **Strategy Map confidence chips — green = HIGH confidence (good)** ← collision

A reader scanning quickly sees a green chip on a strategy-map node and reads "low risk." It actually means "high confidence the inference is grounded in real data." The two concepts run in opposite directions but share a palette. PE buy-side readers — primary persona — care about both signals AND about the trustworthiness of the analysis. Conflating them undermines both.

**Audit 7 — provenance markers partial and inconsistent.** The strategy map's Vision and Mission carry `synthesised` flags rendered as bare parenthetical text "(synthesised)" / "(inferred)" — three different inline-style implementations across `StrategyMapHeader`, `CoreValuesStrip`, and the print path. No styled component. Three separate `style={{...}}` blocks duplicating the same uppercase-tracking-tertiary pattern.

Both axes are "trust signals" — the page tells the PE-triager *how to weight* what the AI claims. Confidence answers "should I believe this objective?"; provenance answers "did the AI extract this from a real source or infer it from absence?" Solving them together as one design move is more coherent than splitting.

This change is **frontend-only with the data the backend already emits.** The broader UX-review goal of provenance markers on Opportunities, EBITDA nodes, and ValueChain steps requires those types to gain `synthesised` / `confidence` fields in the backend AI pipeline (separate proposal — `extend-ai-output-provenance-fields` or similar). This proposal closes the gap on data we already have.

## What Changes

- **Add** `frontend/src/components/analysis/ConfidenceIndicator.tsx` — new component that replaces `ConfidenceChip`'s tier-palette pill with a 3-dot scale (`●●● / ●●○ / ●○○`) in a single neutral color. Per resolved persona discussion, the dot scale conveys ordering visually without recruiting the green/amber/red palette. Tooltip-on-hover preserves the existing long-form rationale ("Directly inferred from concrete public data" etc).
- **Migrate** `ConfidenceChip` consumers to `ConfidenceIndicator`: `StrategyMapNode`'s tooltip header (line 289). The 8-pixel confidence dot rendered separately on the chip's header (line 157, `CONFIDENCE_DOT`) consolidates into a small variant of the new indicator OR is removed in favor of the indicator inside the tooltip — design D2 picks the path.
- **Remove** `ConfidenceChip.tsx` after migration if no consumer remains. The barrel export at `components/strategy-map/index.ts` updates accordingly.
- **Add** `frontend/src/components/analysis/ProvenanceMarker.tsx` — new component that replaces the three inline-styled `(synthesised)` / `(inferred)` parentheticals with a single styled marker. `kind: 'inferred'` covers the current backend emission (`synthesised: true`). The component is forward-compatible with future kinds (`'extracted'`, `'from-upload'`) the backend may add later.
- **Migrate** the three inline-styled parentheticals to use `ProvenanceMarker`: `StrategyMapHeader.tsx` (Vision, Mission), `StrategyMapView.tsx` `CoreValuesStrip` (CoreValues), and `PrintStrategyMap.tsx` (Vision, Mission, CoreValues — print path).
- **Tests**: new tests for `ConfidenceIndicator` (renders correct dot count for each marker, neutral color, accessible name), new tests for `ProvenanceMarker` (renders correct icon/text, accessible name), updates to existing tests for `StrategyMapNode` and `StrategyMapHeader` to assert the new components are present (replacing `ConfidenceChip` queries).
- **No backend changes.** No data, API, or analytics changes.

## Capabilities

### New Capabilities

<!-- None. Both new components live within the analysis-detail-narrative capability surface; the trust-signal contract is a refinement of the existing strategy-map rendering, not a new capability. -->

### Modified Capabilities

- `analysis-detail-narrative`: extends with two new requirements covering (1) the consistent visual treatment of AI confidence (single neutral color, dot-scale) distinct from risk-tier color, and (2) the consistent visual treatment of provenance markers (single styled component, applied wherever `synthesised: true` appears in the data).

## Impact

**Code:**
- `frontend/src/components/analysis/ConfidenceIndicator.tsx` — NEW (~80 lines)
- `frontend/src/components/analysis/ProvenanceMarker.tsx` — NEW (~70 lines)
- `frontend/src/components/strategy-map/StrategyMapNode.tsx` — replace `ConfidenceChip` import + use; drop the standalone 8-px confidence dot if the indicator subsumes it (D2)
- `frontend/src/components/strategy-map/StrategyMapHeader.tsx` — replace inline-styled `(synthesised)` with `<ProvenanceMarker kind="inferred" />` for Vision and Mission
- `frontend/src/components/strategy-map/StrategyMapView.tsx` — replace `(inferred)` parenthetical in `CoreValuesStrip`
- `frontend/src/components/print/PrintStrategyMap.tsx` — replace 3 inline parentheticals; print path will use the same component (it doesn't depend on browser-only APIs)
- `frontend/src/components/strategy-map/index.ts` — remove `ConfidenceChip` export if component is deleted
- DELETE `frontend/src/components/strategy-map/ConfidenceChip.tsx` after migration
- `frontend/src/tests/components/analysis/ConfidenceIndicator.test.tsx` — NEW
- `frontend/src/tests/components/analysis/ProvenanceMarker.test.tsx` — NEW
- Updates to existing tests that asserted on `ConfidenceChip` text content or the inline `(synthesised)` text

**Surfaces affected:**
- Strategy map (every objective node tooltip, both screen and print)
- Strategy map header (Vision, Mission, CoreValues — both screen and print)

**Data / APIs / dependencies:** none

**Out of scope (explicitly deferred to separate proposals):**
- Adding `synthesised: boolean` and/or `confidence: ConfidenceMarker` to Opportunity, EbitdaNode, and ValueChainStep types in the backend Pydantic models + JSON schemas + AI prompts. This is a substantial backend change (new pipeline output fields, fixture updates, prompt engineering for confidence assignment) — own proposal.
- Distinguishing "from-upload" vs "from-scrape" vs "AI-only" provenance. Requires backend source tracking that doesn't exist today.
- Decoupling the risk-tier palette from any other shared use beyond confidence (e.g., the `Top 3 Immediate Actions` accent or `Sc0redCTABanner` blue treatment). The collision identified by Audit 5 is specifically risk-tier vs confidence; this proposal fixes that.
- ExpandableCard, card-density-variants, and section-spacing-tokens — separately queued in the UX-review priority order.

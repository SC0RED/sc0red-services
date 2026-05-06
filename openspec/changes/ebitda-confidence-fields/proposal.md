## Why

PE buyers don't take black-box numbers to their investment committee. They take numbers with provenance. Today the EBITDA tree surfaces revenue lines, cost lines, and margins as point estimates with no signal about *how the figure was derived* — a number anchored to a company's declared $40M ARR reads identically to one extrapolated from an industry-average revenue-per-employee benchmark. Both render as "$2M-$8M" and both look equally trustworthy.

This change makes derivation provenance visible at the node level. Each EBITDA tree node carries a confidence signal (high / medium / low) plus a one-line basis ("Derived from a SaaS template at a known mid-market size bracket" vs "Defaulted to a generic mid-market estimate — neither business model nor size signal was usable") so a PE analyst can see at a glance which figures are anchored to clean inputs and which are generic extrapolations. This is the highest-leverage trust signal we can ship: PE workflows already accept ranges, but only when they can audit the source.

## What Changes

- Backend: `build_programmatic_ebitda_tree` records derivation provenance per node as it builds the tree. The function already knows which path it took (template matched vs defaulted; size resolved vs defaulted); we just stop discarding that signal.
- Backend: `EbitdaNode` model gains two fields — `confidence_level: Literal["high", "medium", "low"] | None` and `confidence_basis: str | None` (1–2 sentence human-readable explanation of how the number was derived). Both `None` for non-leaf rollup nodes that inherit from children.
- Backend: confidence level rules are deterministic and documented in `build_ebitda_tree.py`. Both inputs to the build (`business_model` resolved against `_MODEL_KEYWORDS`, and `company_size` resolved against `_SIZE_TO_EMPLOYEES`) can each either match a known entry or fall back to a default; the level reflects how many resolved cleanly:
  - **high** = both `business_model` and `company_size` resolved cleanly to known entries
  - **medium** = exactly one of the two resolved cleanly; the other defaulted
  - **low** = both defaulted — no useful signal on either input (see `design.md` decision §2 for rationale and the note on forward evolution when a declared-revenue field is added later)
- Backend: schema for `EbitdaTreeResult` JSON output bumps to v2 (additive, backward-compatible with `null` defaults).
- Frontend: `EbitdaNodeComponent` renders a confidence chip next to each node's `value_range`, sourced from the new `confidenceLevel` field. Three-dot scale, neutral palette (matches the existing `ConfidenceIndicator` component used elsewhere on the page).
- Frontend: hovering or focusing the chip reveals a tooltip with `confidenceBasis`. Keyboard-accessible per the existing `HelpTooltip` pattern.
- Frontend: `EbitdaTree` legend documents the meaning of each level so first-time viewers don't guess.
- Frontend: print export (`PrintEbitdaOutline`) emits the confidence level inline (text form: "high / medium / low") so PDF readers see it too.

## Capabilities

### New Capabilities

- `ebitda-tree-confidence`: Per-node derivation provenance on the EBITDA tree — confidence level (high/medium/low) plus a 1–2 sentence basis rationale, surfaced as a chip on each node with a hover/focus tooltip and a documented legend.

### Modified Capabilities

<!-- None. The new capability `ebitda-tree-confidence` covers all per-node chip behavior. The existing `analysis-detail-narrative` spec scopes the EBITDA tree at the section level (ordering, presence/absence in the strap) and does not specify node-internal rendering, so adding chips to individual nodes does not modify any existing requirement. -->


## Impact

- **Backend models**: `EbitdaNode` gains two optional fields. Existing analyses that lack the fields render with `confidenceLevel: null` and the chip is suppressed (no "unknown" badge — silence is better than noise).
- **Backend pipeline**: `build_programmatic_ebitda_tree` adds provenance tagging logic. Pure addition; existing tree shape is unchanged.
- **Backend schemas / DynamoDB**: `EbitdaNode` is stored as JSON; new fields are additive and old records read fine (Pydantic defaults to `None`).
- **Frontend components**: `EbitdaNodeComponent`, `EbitdaTree` (legend), and `PrintEbitdaOutline` updated. No new component primitives needed (reuses `ConfidenceIndicator` + `HelpTooltip`).
- **Frontend types**: `src/lib/types/api.ts` `EbitdaNode` gains `confidenceLevel?: "high" | "medium" | "low"` and `confidenceBasis?: string`.
- **Tests**: backend unit tests for the provenance-tagging branches; frontend tests for chip rendering, tooltip a11y, and the suppress-when-null path.
- **No infrastructure changes**: no new tables, no new endpoints, no new env vars.
- **Re-analyse**: existing analyses gain confidence on next re-analysis. No backfill job required (graceful degradation via `null` default).

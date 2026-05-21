## REMOVED Requirements

### Requirement: Frontend renders a confidence chip on each leaf node

**Reason:** Diagnostic Tool Feedback #5b — Zack: "I think we can get rid of the confidence dots, it's not nearly as important as the ideas for improvement". The confidence chip competes visually with the opportunity-link dots (PR #305) that carry the more decision-relevant signal for a PE reader. Dropping it gives the opportunity dots room to read.

**Migration:** The `confidence_level` and `confidence_basis` fields remain in the AI pipeline output and in `EbitdaTreeResult`. `EbitdaNodeComponent` no longer renders the chip — the data is dormant at the visual layer. Any future surface (audit panel, debug overlay, programmatic export) that wants to render confidence can pull the field straight from the data without a pipeline change.

### Requirement: Hover or focus on the chip reveals the basis

**Reason:** No chip is rendered, so there is no hover target. The `confidence_basis` text remains on the data but is not surfaced anywhere in the v1 visual.

**Migration:** None — the chip's hover handler is deleted with the chip. Future surfaces that want to surface `confidence_basis` (e.g., a tooltip on the leaf node itself) can add their own handler without changing the data shape.

### Requirement: EBITDA tree legend documents confidence levels

**Reason:** The confidence legend was a one-line caption above the EBITDA canvas explaining the three-dot indicator. With the chip removed (above), the caption explains a visual that no longer exists. The slot above the canvas is now occupied by the new shared `AnalysisLegend` defined in the `analysis-opportunity-overlays` capability (which explains the opportunity-link dots, not confidence).

**Migration:** The `data-testid="ebitda-confidence-legend"` element is removed from `EbitdaTree`. The new `AnalysisLegend` component takes its position above the canvas.

### Requirement: Print export includes confidence inline

**Reason:** Print parity follows screen parity — with the chip removed from the on-screen visual, the print export also drops it.

**Migration:** `PrintEbitdaOutline.tsx` no longer renders the confidence-callout block. The opportunity-link callout block (which existed alongside the confidence one) remains.

## MODIFIED Requirements

### Requirement: EBITDA tree nodes carry derivation provenance

Each leaf `EbitdaNode` produced by `build_programmatic_ebitda_tree` SHALL carry two optional fields:

- `confidence_level: Literal["high", "medium", "low"] | None`
- `confidence_basis: str | None` — a 1–2 sentence human-readable explanation of how the node's `value_range` was derived.

Both fields default to `None` for nodes that do not have a deterministic provenance signal (e.g., rollup/subtotal nodes that aggregate children, or nodes produced by a code path that predates this change).

The fields are persisted, included in API responses, and available to the print export and any future audit/debug surface. The frontend visual does NOT render them as of the `redesign-analysis-visuals` change — see the REMOVED requirements above for the rationale.

#### Scenario: Both inputs resolved cleanly tagged high

- **WHEN** `build_programmatic_ebitda_tree` produces a leaf node from a `CompanyProfile` whose `business_model` matches an entry in `_MODEL_KEYWORDS` AND whose `company_size` matches a key in `_SIZE_TO_EMPLOYEES`
- **THEN** the node's `confidence_level` is `"high"` and `confidence_basis` references both inputs (e.g., "Derived from a SaaS template at a known mid-market size bracket")

#### Scenario: Exactly one input resolved tagged medium

- **WHEN** `build_programmatic_ebitda_tree` produces a leaf node from a `CompanyProfile` where exactly one of (`business_model` matches `_MODEL_KEYWORDS`, `company_size` matches `_SIZE_TO_EMPLOYEES`) is true
- **THEN** the node's `confidence_level` is `"medium"` and `confidence_basis` names the resolved input and the defaulted one

#### Scenario: Both inputs defaulted tagged low

- **WHEN** `build_programmatic_ebitda_tree` produces a leaf node from a `CompanyProfile` whose `business_model` does not match `_MODEL_KEYWORDS` AND whose `company_size` does not match `_SIZE_TO_EMPLOYEES`
- **THEN** the node's `confidence_level` is `"low"` and `confidence_basis` names both defaulted inputs

#### Scenario: API response continues to include the fields

- **WHEN** an analysis API response is returned for an analysis whose tree carries `confidence_level` on any leaf
- **THEN** the fields are present in the response payload exactly as they were before the visual was removed
- **AND** the analysis pipeline emits no migration deprecation warning for the fields

# ebitda-tree-confidence Specification

## Purpose

Per-node derivation provenance on the EBITDA tree — a confidence level (high/medium/low) plus a 1–2 sentence basis rationale. The level is deterministic and auditable: it reflects how cleanly the build inputs (`business_model` against `_MODEL_KEYWORDS`, `company_size` against `_SIZE_TO_EMPLOYEES`) resolved against the static template data. Both matched → high; one matched → medium; both defaulted → low. This is provenance, not AI self-rating — same inputs always produce the same label.

The fields are persisted, included in API responses, and available to the print export and any future audit / debug surface. The on-screen chip, hover tooltip, on-page legend, and print-inline marker were removed by the `redesign-analysis-visuals` change (Diagnostic Tool Feedback #5b) — the visuals competed with the more decision-relevant opportunity-link dots without adding signal a PE reader uses. The data layer is intentionally unchanged so any future surface (audit panel, debug overlay, programmatic export) can pull the fields without a pipeline change.

## Requirements

### Requirement: EBITDA tree nodes carry derivation provenance

Each leaf `EbitdaNode` produced by `build_programmatic_ebitda_tree` SHALL carry two optional fields:

- `confidence_level: Literal["high", "medium", "low"] | None`
- `confidence_basis: str | None` — a 1–2 sentence human-readable explanation of how the node's `value_range` was derived.

Both fields default to `None` for nodes that do not have a deterministic provenance signal (e.g., rollup/subtotal nodes that aggregate children, or nodes produced by a code path that predates this change).

The frontend visual does NOT render these fields as of the `redesign-analysis-visuals` change — the chip + legend + print-inline marker were removed in that change. The fields remain in the data pipeline + API responses for future surfaces.

#### Scenario: Both inputs resolved cleanly tagged high

- **WHEN** `build_programmatic_ebitda_tree` produces a leaf node from a `CompanyProfile` whose `business_model` matches an entry in `_MODEL_KEYWORDS` AND whose `company_size` matches a key in `_SIZE_TO_EMPLOYEES`
- **THEN** the node's `confidence_level` is `"high"` and `confidence_basis` references both inputs (e.g., "Derived from a SaaS template at a known mid-market size bracket")

#### Scenario: Exactly one input resolved tagged medium

- **WHEN** `build_programmatic_ebitda_tree` produces a leaf node from a `CompanyProfile` where exactly one of (`business_model` matches `_MODEL_KEYWORDS`, `company_size` matches `_SIZE_TO_EMPLOYEES`) is true
- **THEN** the node's `confidence_level` is `"medium"` and `confidence_basis` names the resolved input and the defaulted one (e.g., "SaaS template applied to a defaulted size bracket — no company-size signal" or "Defaulted to a generic SaaS template at a known small-company size bracket")

#### Scenario: Both inputs defaulted tagged low

- **WHEN** `build_programmatic_ebitda_tree` produces a leaf node from a `CompanyProfile` whose `business_model` does NOT match any `_MODEL_KEYWORDS` entry AND whose `company_size` is NOT in `_SIZE_TO_EMPLOYEES`
- **THEN** the node's `confidence_level` is `"low"` and `confidence_basis` indicates both fallbacks (e.g., "Defaulted to a generic mid-market estimate — neither business model nor size signal was usable")

#### Scenario: Cost-node confidence inherits from the inputs that drove it

- **WHEN** `build_programmatic_ebitda_tree` produces a leaf cost node (under COGS or OpEx) whose value derives from the template's `gross_margin` / `ebitda_margin` applied to the estimated revenue
- **THEN** the node's `confidence_level` matches the level computed for revenue nodes from the same `CompanyProfile` (i.e., a single confidence label is computed once per profile and propagates to every leaf node) and `confidence_basis` is phrased for cost provenance (e.g., "Industry-benchmark gross margin applied to a revenue estimate from a known SaaS template at a mid-market size bracket")

#### Scenario: Rollup nodes do not carry their own confidence

- **WHEN** `build_programmatic_ebitda_tree` produces a `subtotal` or `margin` node whose value is computed from its children
- **THEN** the node's `confidence_level` is `None` and `confidence_basis` is `None` (the children carry the signal individually; rollups inherit visually via their children's chips)

#### Scenario: API response continues to include the fields

- **WHEN** an analysis API response is returned for an analysis whose tree carries `confidence_level` on any leaf
- **THEN** the fields are present in the response payload exactly as they were before the visual was removed
- **AND** the analysis pipeline emits no migration deprecation warning for the fields

### Requirement: EbitdaTreeResult schema is additive and backward-compatible

The `EbitdaTreeResult` JSON schema SHALL accept records without the new fields and SHALL surface them as `None` when read back. Existing analyses stored in DynamoDB SHALL deserialize without error.

#### Scenario: Old record deserializes with null confidence

- **WHEN** an `EbitdaTreeResult` record stored before this change is fetched from DynamoDB and parsed
- **THEN** every node's `confidence_level` and `confidence_basis` are `None`; no `ValidationError` is raised

# ebitda-tree-confidence Specification

## Purpose

Per-node derivation provenance on the EBITDA tree — a confidence level (high/medium/low) plus a 1–2 sentence basis rationale. The level is deterministic and auditable: it reflects how cleanly the build inputs (`business_model` against `_MODEL_KEYWORDS`, `company_size` against `_SIZE_TO_EMPLOYEES`) resolved against the static template data. Both matched → high; one matched → medium; both defaulted → low. This is provenance, not AI self-rating — same inputs always produce the same label.

The fields are persisted, included in API responses, and available to the print export and any future audit / debug surface. The on-screen chip, hover tooltip, on-page legend, and print-inline marker were removed by the `redesign-analysis-visuals` change (Diagnostic Tool Feedback #5b) — the visuals competed with the more decision-relevant opportunity-link dots without adding signal a PE reader uses. The data layer is intentionally unchanged so any future surface (audit panel, debug overlay, programmatic export) can pull the fields without a pipeline change.
## Requirements
### Requirement: EBITDA tree nodes carry derivation provenance

Each `EbitdaNode` produced by the EBITDA assembler SHALL carry derivation-provenance fields:

- `confidence_level: Literal["high", "medium", "low"] | None`
- `confidence_basis: str | None` — a 1–2 sentence human-readable explanation of how the node's value was derived.

With this change the EBITDA tree is produced by the **decomposed AI-research pipeline**, not a keyword-selected industry template. Consequently the confidence label is no longer a function of `(template_matched, size_matched)`; it is a **deterministic function of the node's provenance tier** (`DISCLOSED` → high, `INDUSTRY_TYPICAL` → medium, `DERIVED_ESTIMATE` → low/medium), per the `fact-provenance-labeling` capability. The label is still deterministic and auditable — the same provenance tier and verification verdict always produce the same label, and adversarial verification may downgrade but never raise it. AI self-rating is NOT used.

Nodes whose value is `DISCLOSED` SHALL also carry their citation(s). Rollup/subtotal nodes that aggregate children MAY leave the fields `None` and inherit visually via their children. Records stored before these fields existed deserialize as `None`.

#### Scenario: Disclosed figure tagged high

- **WHEN** an EBITDA node's value comes from a citable source (site, uploaded document, or web-search source)
- **THEN** its `confidence_level` is `"high"`, its provenance is `DISCLOSED`, and it carries the citation

#### Scenario: Industry-typical value tagged medium

- **WHEN** a node's value comes from the model's general knowledge of the company type (e.g. a typical margin band) with no company-specific source
- **THEN** its `confidence_level` is `"medium"` and `confidence_basis` names the industry-typical basis

#### Scenario: Derived estimate tagged low/medium with its basis

- **WHEN** a node's value is computed/inferred (e.g. revenue range from scale signals × an industry assumption) with no citable source
- **THEN** its provenance is `DERIVED_ESTIMATE`, its confidence is not `"high"`, and `confidence_basis` states the one-line derivation

#### Scenario: Confidence is reproducible

- **WHEN** two nodes share the same provenance tier and verification verdict
- **THEN** they receive the same `confidence_level` (deterministic, not AI-self-rated)

#### Scenario: Adversarial verification can only downgrade

- **WHEN** a plausibility check returns "not plausible" for a node's basis
- **THEN** the node's confidence is downgraded (never raised)

### Requirement: EbitdaTreeResult schema is additive and backward-compatible

The `EbitdaTreeResult` JSON schema SHALL accept records without the new fields and SHALL surface them as `None` when read back. Existing analyses stored in DynamoDB SHALL deserialize without error.

#### Scenario: Old record deserializes with null confidence

- **WHEN** an `EbitdaTreeResult` record stored before this change is fetched from DynamoDB and parsed
- **THEN** every node's `confidence_level` and `confidence_basis` are `None`; no `ValidationError` is raised

### Requirement: EBITDA tree renders a placeholder when the business model matches no template

`build_programmatic_ebitda_tree` SHALL NOT fall back to a default (`"saas"`) template when `business_model` matches no entry in `_MODEL_KEYWORDS`. On no match (including a `"unknown"` business model) it SHALL return an EBITDA result in an explicit insufficient-data state carrying a human-readable reason, and SHALL NOT emit fabricated revenue, margin, or revenue-mix figures.

#### Scenario: Unmatched business model yields placeholder, not a SaaS P&L

- **WHEN** `build_programmatic_ebitda_tree` receives a `CompanyProfile` whose `business_model` (e.g. "debt settlement") matches no `_MODEL_KEYWORDS` entry
- **THEN** the returned `EbitdaTreeResult` is in the insufficient-data state with a reason
- **AND** it contains no fabricated revenue range, EBITDA margin, or "Subscriptions 80% / Professional Services 15%" revenue mix

#### Scenario: `"unknown"` business model is treated as no match

- **WHEN** the profile's `business_model` is the `"unknown"` sentinel
- **THEN** the EBITDA tree renders the insufficient-data placeholder state

### Requirement: EBITDA revenue range must not compound independent uncertainty bands

When a template matches and the EBITDA tree is built, the estimated revenue range SHALL NOT be produced by multiplying the low end of the employee-count band against the low end of the revenue-per-employee band while multiplying both high ends together. The emitted range's high/low ratio SHALL NOT exceed the larger of the two input bands' own high/low ratios — i.e. the two independent uncertainties are not multiplied into a misleadingly wide figure.

#### Scenario: Matched template yields a bounded range

- **WHEN** a matched template produces a revenue range from an employee band and a revenue-per-employee band
- **THEN** the resulting range's high/low ratio is no greater than the larger of the two input bands' high/low ratios (it does not compound to the ~13× `$30M–$400M` spread the old formula produced)


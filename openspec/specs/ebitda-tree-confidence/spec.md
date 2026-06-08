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

A rendered EBITDA tree always derives from a **matched** template: a `business_model` that matches no `_MODEL_KEYWORDS` entry no longer produces a low-confidence defaulted SaaS tree — it produces the insufficient-data placeholder state (see "EBITDA tree renders a placeholder when the business model matches no template"). Consequently, for any node that is actually rendered, the template input is always resolved, and the confidence level reflects only whether `company_size` resolved against `_SIZE_TO_EMPLOYEES` (`high` when size matched, `medium` when size defaulted). The previously-specified "both inputs defaulted → low" outcome is unreachable for a rendered tree because the template-default path that produced it has been removed.

The frontend visual does NOT render these fields as of the `redesign-analysis-visuals` change — the chip + legend + print-inline marker were removed in that change. The fields remain in the data pipeline + API responses for future surfaces.

#### Scenario: Both inputs resolved cleanly tagged high

- **WHEN** `build_programmatic_ebitda_tree` produces a leaf node from a `CompanyProfile` whose `business_model` matches an entry in `_MODEL_KEYWORDS` AND whose `company_size` matches a key in `_SIZE_TO_EMPLOYEES`
- **THEN** the node's `confidence_level` is `"high"` and `confidence_basis` references both inputs (e.g., "Derived from a SaaS template at a known mid-market size bracket")

#### Scenario: Template matched but size defaulted tagged medium

- **WHEN** `build_programmatic_ebitda_tree` produces a leaf node from a `CompanyProfile` whose `business_model` matches `_MODEL_KEYWORDS` but whose `company_size` is NOT in `_SIZE_TO_EMPLOYEES`
- **THEN** the node's `confidence_level` is `"medium"` and `confidence_basis` names the matched template and the defaulted size bracket (e.g., "SaaS template applied to a defaulted size bracket — no company-size signal")

#### Scenario: Unmatched template never yields a low-confidence tree

- **WHEN** a `CompanyProfile`'s `business_model` matches no `_MODEL_KEYWORDS` entry
- **THEN** no EBITDA nodes are produced at all (the result is the insufficient-data placeholder state), so no node is ever tagged `"low"` due to a defaulted template

#### Scenario: Cost-node confidence inherits from the inputs that drove it

- **WHEN** `build_programmatic_ebitda_tree` produces a leaf cost node (under COGS or OpEx) whose value derives from the template's `gross_margin` / `ebitda_margin` applied to the estimated revenue
- **THEN** the node's `confidence_level` matches the level computed for revenue nodes from the same `CompanyProfile` (i.e., a single confidence label is computed once per profile and propagates to every leaf node) and `confidence_basis` is phrased for cost provenance (e.g., "Industry-benchmark gross margin applied to a revenue estimate from a known SaaS template at a mid-market size bracket")

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


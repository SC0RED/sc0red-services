## ADDED Requirements

### Requirement: Every researched fact carries a provenance tier

Each fact produced by the research pipeline (every EBITDA node and value-chain step, and especially every quantitative figure) SHALL carry a provenance tier of exactly one of: `DISCLOSED` (backed by a citable source — scraped site, uploaded document, or web-search source), `INDUSTRY_TYPICAL` (the model's general world knowledge for the company type), or `DERIVED_ESTIMATE` (computed/inferred). A fact tagged `DISCLOSED` SHALL carry at least one citation; a `DISCLOSED` claim with no attached source SHALL be downgraded.

#### Scenario: Web-cited figure is DISCLOSED

- **WHEN** a revenue figure is produced from a web-search source
- **THEN** the fact's provenance is `DISCLOSED` and it carries the source citation (url + title)

#### Scenario: Unsourced figure is an estimate

- **WHEN** a revenue figure is computed from scale signals and an industry assumption with no citable source
- **THEN** the fact's provenance is `DERIVED_ESTIMATE`

#### Scenario: Claimed-disclosed without a source is downgraded

- **WHEN** the model self-declares a fact as disclosed but no citation is present
- **THEN** the fact is downgraded to `INDUSTRY_TYPICAL` or `DERIVED_ESTIMATE`

### Requirement: Confidence is deterministic from the provenance tier

A fact's confidence level SHALL be a deterministic function of its provenance tier (not AI-self-rated), consistent with the existing deterministic EBITDA confidence labelling. Adversarial verification MAY downgrade confidence but never raise it above the tier's ceiling.

#### Scenario: Same tier yields same confidence

- **WHEN** two facts share the same provenance tier and verification verdict
- **THEN** they receive the same confidence level (reproducible, auditable)

### Requirement: Quantitative facts are presented as honest, rigorous, labelled estimates

A quantitative figure that is not `DISCLOSED` SHALL be presented as an explicit estimate carrying: the value, its provenance tier, its confidence, and a one-line human-readable basis describing how it was reached. A `DISCLOSED` figure SHALL display its citation/source. The presentation SHALL make clear the figure is reasoned and effortful, not random, while remaining honest that an estimate is an estimate.

#### Scenario: Estimate shows its work

- **WHEN** the revenue range is a `DERIVED_ESTIMATE`
- **THEN** the report shows the range, an "estimated" label, a confidence level, and a one-line basis (e.g. how the figure was derived) — not a bare number presented as fact

#### Scenario: Disclosed figure shows its citation

- **WHEN** the revenue figure is `DISCLOSED`
- **THEN** the report shows the figure with its source citation

### Requirement: Provenance and citations persist end-to-end

The provenance tier, basis, and citations SHALL be additive optional fields on the EBITDA and value-chain models, persisted and returned through the analysis payload to the web report, PDF export, and MCP read tools. Records stored before these fields existed SHALL deserialize unchanged.

#### Scenario: Legacy record deserializes

- **WHEN** an analysis stored before this change is loaded
- **THEN** it deserializes without error (provenance/citation fields default to absent)

#### Scenario: Surfaces render provenance

- **WHEN** a researched analysis is rendered on the web report, PDF, or via MCP
- **THEN** each quantitative fact's provenance/confidence/basis (and citation when disclosed) is available on that surface

## MODIFIED Requirements

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

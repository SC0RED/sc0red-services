# value-chain-grounding Specification

## Purpose
TBD - created by archiving change enforce-fact-vs-forecast-data-integrity. Update Purpose after archive.
## Requirements
### Requirement: Value chain renders a placeholder when the business model matches no template

`build_programmatic_value_chain` SHALL NOT fall back to a default (`"saas"`) template when `business_model` matches no entry in `MODEL_KEYWORDS`. On no match it SHALL return a value-chain result in an explicit insufficient-data state carrying a human-readable reason, and SHALL NOT emit fabricated operating steps.

#### Scenario: Unmatched business model yields placeholder, not SaaS steps

- **WHEN** `build_programmatic_value_chain` receives a `CompanyProfile` whose `business_model` (e.g. "debt settlement") matches no `MODEL_KEYWORDS` entry
- **THEN** the returned `ValueChainResult` is in the insufficient-data state with a reason
- **AND** it contains no value-chain steps (no defaulted SaaS Lead Generation → Sales → Renewal chain)

#### Scenario: `"unknown"` business model is treated as no match

- **WHEN** the profile's `business_model` is the `"unknown"` sentinel
- **THEN** the value chain renders the insufficient-data placeholder state

#### Scenario: Matched business model still produces a grounded chain

- **WHEN** the profile's `business_model` matches a `MODEL_KEYWORDS` entry (e.g. "B2B SaaS")
- **THEN** the value chain is built from the matched template as today

### Requirement: Value chain carries a derivation-provenance signal

A rendered `ValueChainResult` SHALL carry a derivation-provenance signal equivalent to the EBITDA tree's confidence basis, recording which template was matched and that the chain is grounded in a matched business model.

#### Scenario: Matched chain records its provenance

- **WHEN** a value chain is built from a matched template
- **THEN** the result records the matched template and a provenance basis string consistent with the EBITDA tree's confidence vocabulary

#### Scenario: Provenance is available for audit/debug parity

- **WHEN** the value-chain result is serialized into the API response
- **THEN** the provenance signal is present alongside the steps, mirroring the EBITDA tree's `confidence_basis` data-layer parity


# report-data-integrity Specification

## Purpose
TBD - created by archiving change enforce-fact-vs-forecast-data-integrity. Update Purpose after archive.
## Requirements
### Requirement: Report surfaces are classified FACT or FORECAST

Every content surface in a generated report SHALL be classified as either a FACT surface (a statement about the company's existing reality — e.g. business model, financials, operating model, company profile) or a FORECAST surface (forward-looking judgement — e.g. risk scores, opportunities, value levers, strategy map). FACT surfaces are held to the grounding standard below; FORECAST surfaces MAY be approximate.

#### Scenario: Financial and operating-model surfaces are FACT

- **WHEN** the report includes the EBITDA/financial tree, the value chain, or company-profile attributes (business model, revenue model, company size)
- **THEN** those surfaces are treated as FACT surfaces and are subject to the grounding requirement

#### Scenario: Opportunity and strategy surfaces are FORECAST

- **WHEN** the report includes risk scores, opportunities/value levers, or the strategy map
- **THEN** those surfaces are treated as FORECAST surfaces and are exempt from the FACT grounding requirement

### Requirement: A FACT surface is rendered only when grounded

A FACT surface SHALL be rendered with concrete values only when those values are grounded in evidence (scraped site content, an uploaded document, or a matched deterministic template driven by a grounded input). A FACT surface SHALL NOT be produced by silently substituting a default template, defaulting an unresolved input, or asserting a value without basis.

#### Scenario: Ungroundable FACT surface shows a placeholder

- **WHEN** a FACT surface cannot be grounded (e.g. the driving input matches no template or resolved to an `"unknown"` sentinel)
- **THEN** the surface renders an explicit, clearly-labeled "insufficient public data to model this" placeholder
- **AND** it does NOT render fabricated concrete values (no defaulted revenue mix, margins, or operating steps)

#### Scenario: Placeholder is an explicit state, not an empty render

- **WHEN** a FACT surface is in the insufficient-data state
- **THEN** the result model carries an explicit flag and human-readable reason for that state (it is not represented by an empty/missing field that the frontend must infer)

### Requirement: Silent defaults on fact-bearing sections are forbidden by audit

The codebase audit (`make audit`) SHALL fail when a fact-bearing report builder relies on a silent default template (e.g. a module-level default-template-key constant) without an explicit insufficient-data / placeholder branch.

#### Scenario: Audit flags a new silent default

- **WHEN** a pipeline builder for a FACT surface declares a default-template fallback constant and has no no-match placeholder path
- **THEN** `make audit` reports a failure identifying the module and the missing placeholder path

#### Scenario: Audit passes when the placeholder path exists

- **WHEN** a fact-bearing builder resolves its template and returns the insufficient-data placeholder state on no match (no silent default)
- **THEN** `make audit` reports no finding for that builder


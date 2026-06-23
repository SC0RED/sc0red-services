# portfolio-company-list-upload Specification

## Purpose
TBD - created by archiving change customer-guided-portfolio-discovery. Update Purpose after archive.
## Requirements
### Requirement: Customer can supply a portfolio company list by upload

The customer SHALL be able to upload a CSV or PDF listing a firm's portfolio companies for a portfolio scan. A CSV SHALL be parsed with a required company-name column and an optional URL column; a PDF SHALL be parsed best-effort into company names. The parsed entries become discovery candidates that enter the existing validation and per-company scan path; when a URL is absent it is resolved by the existing per-company URL resolution.

#### Scenario: CSV with names and URLs

- **WHEN** the customer uploads a CSV with name and url columns
- **THEN** each row becomes a candidate with that name and URL, entering the validation/scan path

#### Scenario: CSV with names only

- **WHEN** the customer uploads a CSV with only a name column
- **THEN** each name becomes a candidate whose URL is resolved downstream

#### Scenario: PDF best-effort

- **WHEN** the customer uploads a PDF list
- **THEN** company names are extracted best-effort and surfaced as candidates, and the verdict reflects what was extracted so the customer can confirm or correct

#### Scenario: Upload supplements or replaces discovery

- **WHEN** the customer uploads a list after an incomplete automatic discovery
- **THEN** the uploaded companies are merged into the candidate set (deduplicated), not silently discarded


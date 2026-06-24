# portfolio-company-list-upload Specification

## Purpose
Lets a customer upload a CSV/PDF company list when automatic discovery under-returns; the parsed companies are merged into the scan as a reliable, customer-supplied source.
## Requirements
### Requirement: Customer can supply a portfolio company list by upload

The customer SHALL be able to upload a company list for a portfolio scan as a CSV or a text document (PDF/DOCX/TXT/MD). A CSV SHALL be parsed with a required company-name column and a URL column; a text document SHALL be parsed best-effort into company names. (Spreadsheets — XLSX/XLS — are intentionally rejected, since their extracted text yields junk candidates.) The parsed entries become discovery candidates that enter the existing validation and per-company scan path. A company can only be analyzed with a website URL, so entries lacking one are added to the list but flagged and excluded from analysis (surfaced, not silently dropped) — the upload UI SHALL set this expectation rather than presenting the URL as optional. Automatically resolving a URL from a name alone is future work (see the `resolve-uploaded-company-urls` change).

#### Scenario: CSV with names and URLs

- **WHEN** the customer uploads a CSV with name and url columns
- **THEN** each row becomes a candidate with that name and URL, entering the validation/scan path

#### Scenario: CSV with names only

- **WHEN** the customer uploads a CSV with only a name column (no URLs)
- **THEN** each name is added to the list but flagged as needing a URL and excluded
  from analysis until one is supplied — it is not silently dropped, and the upload
  does not present the URL as optional

#### Scenario: PDF best-effort

- **WHEN** the customer uploads a PDF list
- **THEN** company names are extracted best-effort and surfaced as candidates, and the verdict reflects what was extracted so the customer can confirm or correct

#### Scenario: Upload supplements or replaces discovery

- **WHEN** the customer uploads a list after an incomplete automatic discovery
- **THEN** the uploaded companies are merged into the candidate set (deduplicated), not silently discarded


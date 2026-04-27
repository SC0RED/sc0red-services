# analysis-navigation Specification

## Purpose
TBD - created by archiving change webapp-ux-foundations-tier1. Update Purpose after archive.
## Requirements
### Requirement: Analyses list portfolio badge links to the portfolio scan

On the `/analyses` page, the existing "Portfolio" / "Standalone" badge on each row SHALL be wrapped in a `<Link>` element when the row's `scanType === "portfolio"`, navigating to `/portfolio/{scanId}`. Standalone-type rows SHALL render the badge as plain text (no link), preserving the visual style.

#### Scenario: Portfolio badge navigates to scan view

- **WHEN** the user clicks the "Portfolio" badge on an analysis row whose `scanType === "portfolio"` and `scanId === "scan-123"`
- **THEN** they navigate to `/portfolio/scan-123`

#### Scenario: Standalone badge has no link

- **WHEN** the user clicks the "Standalone" badge on an analysis row whose `scanType === "single"`
- **THEN** no navigation occurs; the badge is non-interactive

#### Scenario: Click event does not propagate to row navigation

- **WHEN** the analysis row itself is also clickable (e.g., the entire row navigates to `/analysis/{id}`)
- **THEN** clicking the Portfolio badge navigates to `/portfolio/{scanId}` and does NOT also trigger the row's `/analysis/{id}` navigation (event propagation is stopped)

### Requirement: Analysis detail page renders scan provenance

On `/analysis/{id}`, when the analysis's parent scan is of type `portfolio`, the page SHALL render a "Part of: {scan_name}" line near the company name (top of the page). The text SHALL be a `<Link>` to `/portfolio/{scanId}`. For standalone analyses (`scanType === "single"`), no provenance line SHALL render — the analysis IS the scan.

#### Scenario: Portfolio analysis shows provenance line

- **WHEN** the user views `/analysis/{id}` for an analysis whose parent scan has `type === "portfolio"` and `name === "Q3 Diligence"`
- **THEN** a "Part of: Q3 Diligence" line renders near the company name, styled as small secondary text

#### Scenario: Provenance line links to portfolio

- **WHEN** the user clicks the "Q3 Diligence" link in the provenance line
- **THEN** they navigate to `/portfolio/{scanId}` of that scan

#### Scenario: Standalone analysis has no provenance line

- **WHEN** the user views `/analysis/{id}` for an analysis whose parent scan has `type === "single"`
- **THEN** no provenance line renders; the page header shows only the company name and existing metadata

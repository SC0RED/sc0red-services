# dashboard-company-count Specification

## Purpose
TBD - created by archiving change fix-dashboard-company-count. Update Purpose after archive.

## Requirements

### Requirement: Companies-cell precedence is status-aware

The dashboard's "Recent Scans" `Companies` cell SHALL render the displayed company count via a shared `displayedCompanyCount(scan)` helper that gates on whether the scan is in a terminal state:

- For terminal scans (`status` is `complete` or `failed`, or any future status not in `IN_FLIGHT_SCAN_STATUSES`): return `scan.totalCompanies ?? scan.completedCount ?? 0`. `total_companies` is set at confirm time and survives every later state, so it is the cascade truth for completed scans.
- For in-flight scans (`pending`, `discovering`, `awaiting_confirmation`, `running`): return `scan.completedCount ?? 0`. The user wants to see the running counter tick upward mid-stream — rendering the confirmed total would freeze the cell at the final value before any companies have actually finished.
- For unknown / missing status (defensive default): return `0` rather than guessing.

The helper SHALL be the single source of truth — the dashboard cell and `DeleteScanButton`'s `companyCount` prop SHALL both consume the helper, so the precedence cannot drift again.

#### Scenario: Complete scan with empty completedCount and confirmed totalCompanies renders the total

- **WHEN** a scan has `status='complete'`, `completedCount=0`, `totalCompanies=6`
- **THEN** the cell renders `6`

#### Scenario: Running scan renders the partial counter

- **WHEN** a scan has `status='running'`, `completedCount=3`, `totalCompanies=6`
- **THEN** the cell renders `3`

#### Scenario: Failed scan renders the total

- **WHEN** a scan has `status='failed'`, `completedCount=4`, `totalCompanies=6`
- **THEN** the cell renders `6`

#### Scenario: Discovering scan with no counts renders 0

- **WHEN** a scan has `status='discovering'`, `completedCount=0`, `totalCompanies=undefined`
- **THEN** the cell renders `0`

#### Scenario: Helper is shared with DeleteScanButton

- **WHEN** the dashboard renders both the `Companies` cell and the `DeleteScanButton`'s cascade-message scope
- **THEN** both consumers use the same `displayedCompanyCount(scan)` helper
- **AND** the rendered counts agree for every scan

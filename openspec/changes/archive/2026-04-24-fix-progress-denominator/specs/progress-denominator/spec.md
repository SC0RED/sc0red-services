## ADDED Requirements

### Requirement: Progress denominator uses total confirmed companies

`_compute_scan_progress` SHALL compute progress as a fraction of `total_companies` (the number of confirmed portfolio companies on the scan), not as a fraction of the number of `analyses` records currently persisted. When fewer records exist than were confirmed (because worker Lambdas are still starting up), the denominator remains stable at `total_companies` so progress never incorrectly displays 100%.

#### Scenario: 5 of 6 companies have records

- **WHEN** `total_companies=6`, 5 company records exist, all 5 have `analyzedAt`
- **THEN** computed progress is ~83%, not 100%

### Requirement: Frontend allResolved requires all records to exist

The frontend `allResolved` helper SHALL return `true` only when `analyses.length >= totalCompanies` AND every analysis has an `analyzedAt` timestamp. This prevents the dashboard from switching from the progress strip to the aggregate stats view before every confirmed company has produced a record.

#### Scenario: Fewer records than total

- **WHEN** `totalCompanies=6`, `analyses` has 5 entries all resolved
- **THEN** `allResolved` is false — progress strip visible, stats hidden

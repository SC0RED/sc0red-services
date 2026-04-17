## ADDED Requirements

### Requirement: Progress denominator uses total confirmed companies

#### Scenario: 5 of 6 companies have records

- **WHEN** `total_companies=6`, 5 company records exist, all 5 have `analyzedAt`
- **THEN** computed progress is ~83%, not 100%

### Requirement: Frontend allResolved requires all records to exist

#### Scenario: Fewer records than total

- **WHEN** `totalCompanies=6`, `analyses` has 5 entries all resolved
- **THEN** `allResolved` is false — progress strip visible, stats hidden

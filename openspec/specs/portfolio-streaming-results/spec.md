# portfolio-streaming-results Specification

## Purpose
TBD - created by archiving change portfolio-streaming-ux. Update Purpose after archive.
## Requirements
### Requirement: Portfolio scan navigates to portfolio page after first company completes

After confirming a portfolio scan, the UI SHALL continue showing the progress bar (`ScanProgressPhase`) until at least one company analysis has a non-null `analyzedAt`. At that point, the UI SHALL navigate to `/portfolio/{scanId}`.

#### Scenario: First company completes within 60 seconds

- **WHEN** the user confirms 69 portfolio companies and the first analysis completes 40 seconds later
- **THEN** the progress bar page displays for ~40 seconds, then navigates to the portfolio page where 1 completed card and 68 queued/analyzing cards are visible

#### Scenario: No company completes (all fail or timeout)

- **WHEN** every company analysis fails or the scan reaches `status=failed`
- **THEN** the progress bar page transitions to an error state (existing `onFailed` behavior) — the user is NOT navigated to an empty portfolio page

#### Scenario: Single-company scan is unaffected

- **WHEN** the user submits a single-company scan (not portfolio)
- **THEN** the existing progress bar → redirect to `/analysis/{id}` flow is unchanged

### Requirement: Portfolio page shows a progress strip while scan is running

While a portfolio scan has `status` other than `complete`, the portfolio page SHALL display a compact progress strip at the top showing the count of completed analyses out of total, with a thin progress bar.

#### Scenario: Progress strip shows live count

- **WHEN** the portfolio page renders with 12 of 69 analyses complete and scan status is `running`
- **THEN** a progress strip displays "12 of 69 done" with a progress bar filled to ~17%

#### Scenario: Progress strip updates on poll

- **WHEN** a new poll response arrives with 13 of 69 complete
- **THEN** the progress strip updates to "13 of 69 done" and the bar advances

### Requirement: Summary statistics are hidden until scan is complete

The portfolio page SHALL NOT display the summary statistics section (risk tier counts, average score) while the scan status is not `complete`. Summary stats SHALL appear only after the scan reaches `complete`.

#### Scenario: Running scan hides stats

- **WHEN** the scan status is `running` with 12 of 69 analyses done
- **THEN** the summary stats section is not rendered — the progress strip occupies that space

#### Scenario: Completed scan shows stats

- **WHEN** the scan status transitions to `complete`
- **THEN** the progress strip disappears and the summary statistics section renders with final tier counts and average risk score

### Requirement: Cards distinguish "Queued" from "Analyzing"

Portfolio grid cards SHALL distinguish between companies that are actively being analyzed (have `pipelineProgress > 0`) and companies waiting in the SQS queue (no progress, no error, no `analyzedAt`).

#### Scenario: Queued company card

- **WHEN** a company has no `analyzedAt`, no `error`, and `pipelineProgress` is 0 or absent
- **THEN** the card displays "Queued" (not "Analyzing...")

#### Scenario: Actively analyzing company card

- **WHEN** a company has no `analyzedAt`, no `error`, and `pipelineProgress > 0`
- **THEN** the card displays "Analyzing..." with the pipeline progress indicator


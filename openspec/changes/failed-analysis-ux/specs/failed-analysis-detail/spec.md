## ADDED Requirements

### Requirement: Company identity is persisted before pipeline execution

The SQS worker SHALL write `company_name`, `company_url`, `scan_id`, and `org_id` to the company record BEFORE invoking the analysis pipeline. This ensures failed analyses have identity for display and retry.

#### Scenario: Failed analysis has company name and URL

- **WHEN** a company analysis pipeline fails with an error
- **THEN** the company record contains `company_name`, `company_url`, `scan_id`, `org_id`, AND `error` — not just `error` alone

#### Scenario: Successful analysis overwrites initial identity with pipeline-resolved data

- **WHEN** a company analysis pipeline succeeds
- **THEN** `PersistResults` overwrites the initial `company_name` and `company_url` with the pipeline-resolved values (which may be more accurate)

### Requirement: Portfolio grid card displays real company name for failed analyses

The portfolio grid SHALL display the actual company name for failed analyses, not a loading placeholder. A visual indicator SHALL distinguish failed analyses from in-progress or successful ones.

#### Scenario: Failed card shows company name and error badge

- **WHEN** a company analysis has `error` set and no `analyzedAt`
- **THEN** the portfolio grid card shows the company name, a "Failed" badge, and remains clickable — navigating to the analysis detail page

#### Scenario: In-progress card still shows loading state

- **WHEN** a company analysis has no `error` and no `analyzedAt`
- **THEN** the portfolio grid card shows "Analyzing..." with a progress indicator (existing behavior unchanged)

### Requirement: Analysis detail page renders a failed state with retry

When the analysis record has `error` set and no `analyzedAt`, the analysis detail page SHALL render a failed-analysis view instead of a 404 or empty page. The view SHALL include:
- Company name and URL
- The error message
- An optional document upload zone
- A "Retry Analysis" button

#### Scenario: Failed analysis detail page renders

- **WHEN** a user navigates to `/analysis/{id}` for an analysis with `error="AI provider timeout"` and no `analyzedAt`
- **THEN** the page displays the company name, URL, error message, a document drop zone, and a "Retry Analysis" button — not a 404

#### Scenario: Retry button triggers single-company reanalysis

- **WHEN** a user clicks "Retry Analysis" on a failed analysis detail page
- **THEN** the page calls `POST /api/analysis/{id}/reanalyze`, shows a progress indicator, and the button is disabled to prevent double-send. The retry re-runs the pipeline for that single company only — not the entire portfolio.

#### Scenario: Retry with uploaded document

- **WHEN** a user uploads a document, then clicks "Retry Analysis"
- **THEN** the reanalysis pipeline runs with the uploaded document text as supplementary context. The document is stored via the existing upload mechanism before the reanalyze call fires.

#### Scenario: Retry succeeds — page transitions to full analysis

- **WHEN** a retry succeeds (the pipeline completes without error)
- **THEN** the same `/analysis/{id}` page transitions from the failed state to the full analysis view (risk scores, profile, opportunities). The portfolio grid card also updates to show the completed analysis.

#### Scenario: Retry fails again — error is updated

- **WHEN** a retry fails with a new error
- **THEN** the failed-analysis view updates to show the new error message. The company remains in the portfolio grid with the "Failed" badge.

### Requirement: Retry results remain within the portfolio scan context

A retried analysis SHALL preserve its association with the original portfolio scan. The portfolio scan's progress and completion state SHALL update when the retry completes (success or failure).

#### Scenario: Portfolio progress updates after successful retry

- **WHEN** a retry succeeds for company X within portfolio scan S
- **THEN** scan S's `completed_count` increments and `progress` recalculates. If all companies are now resolved, the scan status transitions to `complete`.

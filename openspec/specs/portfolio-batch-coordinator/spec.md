# portfolio-batch-coordinator Specification

## Purpose
TBD - created by archiving change step-functions-batch-coordinator. Update Purpose after archive.
## Requirements
### Requirement: Portfolio confirm starts a Step Function execution

When a user confirms portfolio companies, the API SHALL start a Step Functions execution with the company list and wave_size, instead of sending individual SQS messages.

#### Scenario: User confirms 69 companies

- **WHEN** `POST /api/scan/{id}/confirm` is called with 69 companies
- **THEN** one Step Functions execution starts with `{companies: [...69], wave_size: 4, scan_id, org_id, user_id}`. No SQS messages are sent for individual companies.

#### Scenario: Single-company scan is unchanged

- **WHEN** `POST /api/scan/start` with `type=single` is called
- **THEN** one SQS message is sent directly (existing path). Step Functions is not involved.

### Requirement: Step Function dispatches companies in waves via direct Lambda invocation

The state machine SHALL invoke Worker Lambdas directly (`lambda.invoke`) in parallel batches of `wave_size`, wait for each wave to complete, then dispatch the next wave.

#### Scenario: Wave of 4 companies dispatched

- **WHEN** the Step Function sends a wave of 4 companies
- **THEN** 4 Worker Lambda invocations are started in parallel via the Map state. Each receives the company payload directly (not via SQS).

#### Scenario: Throttled invocation retries automatically

- **WHEN** a `lambda.invoke` is throttled (`TooManyRequestsException`)
- **THEN** Step Functions retries with exponential backoff (30s initial, 2× backoff, up to 10 attempts). No DLQ, no ReceiveCount, no 10-minute invisible stall.

### Requirement: Wave size is auto-configured from reserved_concurrency

The wave size SHALL be derived from the Worker Lambda's `reserved_concurrency` in CDK. Changing concurrency from 4 to 6 SHALL automatically adjust the wave size to 6 without manual coordination.

#### Scenario: Concurrency changed from 4 to 6

- **WHEN** `reserved_concurrency` is updated to 6 in CDK and deployed
- **THEN** subsequent portfolio scans dispatch waves of 6 companies, not 4

### Requirement: Step Function marks scan complete after all waves

After all waves are processed, the Step Function SHALL update the scan record to `status=complete` and emit an AppSync notification.

#### Scenario: All 69 companies processed

- **WHEN** the final wave completes (all company records have `analyzedAt` or `error`)
- **THEN** the scan record is updated to `status=complete`, `progress=100`, and an AppSync `status=complete` event is emitted

### Requirement: Worker Lambda accepts both SQS and direct invocation events

The Worker Lambda SHALL detect the event shape and dispatch accordingly: SQS events use the existing handler; direct invocation events extract the company payload and call `_process_new_analysis`.

#### Scenario: Direct invocation from Step Functions

- **WHEN** the Worker Lambda receives `{"url": "...", "company_name": "...", "scan_id": "...", ...}` (no `Records` key)
- **THEN** it processes the company using the same `_process_new_analysis` path as SQS events


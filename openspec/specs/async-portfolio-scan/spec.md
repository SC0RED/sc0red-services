# async-portfolio-scan Specification

## Purpose
TBD - created by archiving change async-portfolio-discovery. Update Purpose after archive.
## Requirements
### Requirement: API dispatches portfolio discovery asynchronously

The API handler for `POST /api/scan/start` with `type=portfolio` SHALL NOT execute the discovery pipeline inline. It SHALL create the scan record with `status="discovering"` (matching the response it returns), publish a typed SQS message to the analysis queue, and return within 1 second with `{scanId, status: "discovering"}`. The response status and the DB record status SHALL be identical so that the first poll observes the same state the client already has.

#### Scenario: Portfolio scan request returns immediately

- **WHEN** a client submits `POST /api/scan/start` with body `{url: "https://perotjain.com", type: "portfolio"}`
- **THEN** the handler creates a scan record with `status="discovering"`, publishes an SQS message with `type="portfolio_discovery"`, and responds with HTTP 200 + `{scanId: "<uuid>", status: "discovering"}` in under 1 second

#### Scenario: Portfolio scan request does not time out on large firms

- **WHEN** a client submits a portfolio scan for a firm whose discovery would take 60+ seconds
- **THEN** the API response still returns within 1 second — the discovery work is handled by the worker Lambda after the response is sent

### Requirement: Worker processes portfolio discovery messages

The SQS worker SHALL recognise messages with `type="portfolio_discovery"` and invoke `FactoryManager.run_portfolio_discovery(...)` to execute the `DiscoverPortfolio` → `ValidatePortfolioCompanies` pipeline. On success, it SHALL update the scan record with `status="awaiting_confirmation"`, `portfolio_companies=[...]`, and `progress=20`.

#### Scenario: Worker runs discovery and persists results

- **WHEN** the worker receives a message `{type: "portfolio_discovery", url, org_id, user_id, scan_id}`
- **THEN** it runs the portfolio discovery pipeline and updates the scan record with `status="awaiting_confirmation"` and the discovered company list

#### Scenario: Worker ignores unknown message types

- **WHEN** the worker receives a message with `type="unknown_type"`
- **THEN** it raises and triggers SQS retry via `batchItemFailures`, so the bug is surfaced in CloudWatch rather than silently dropped

### Requirement: Failed discovery is surfaced on the scan record

When the worker catches a domain exception (`EngineError`, `ValueError`, `RuntimeError`) during discovery, it SHALL update the scan record with `status="failed"` and `error=<message>`, and it SHALL NOT trigger SQS retry.

#### Scenario: Domain failure writes error and does not retry

- **WHEN** `DiscoverPortfolio` raises `ValueError("No URL provided")` for a scan
- **THEN** the worker writes `{status: "failed", error: "No URL provided"}` to the scan record and returns successfully so SQS does not retry

#### Scenario: Programming error triggers retry

- **WHEN** the worker raises `KeyError` (bug) while processing a portfolio discovery message
- **THEN** the exception propagates, SQS marks the item as a batch failure, and the message is retried per the queue's redrive policy

### Requirement: Scan state lifecycle includes `discovering`

The scan record SHALL support the status values `discovering`, `awaiting_confirmation`, `running`, `complete`, and `failed`. The API handler sets `discovering` on creation for portfolio scans. The worker is idempotent — it re-asserts `discovering` on entry and then transitions to `awaiting_confirmation` (success) or `failed` (error) when finished.

#### Scenario: Status transitions during a successful portfolio scan

- **WHEN** a portfolio scan executes end-to-end successfully
- **THEN** the scan record passes through states in order: `discovering` (set by API) → `discovering` (re-asserted by worker) → `awaiting_confirmation` → (after user confirms) `running` → `complete`

#### Scenario: Status on discovery failure

- **WHEN** discovery fails with a domain error
- **THEN** the scan record reaches `failed` with a non-empty `error` field, and no further transitions occur

### Requirement: Frontend polling renders the `discovering` state

The scan progress page SHALL render a "Finding portfolio companies…" message (or equivalent) while the scan status is `discovering`, and SHALL continue polling `GET /api/scan/{id}` at the existing cadence until the status becomes `awaiting_confirmation` or `failed`.

#### Scenario: Frontend shows progress message while worker runs

- **WHEN** the scan status is `discovering`
- **THEN** the UI displays a loading indicator with the copy "Finding portfolio companies…" and continues polling

#### Scenario: Frontend transitions to confirmation view

- **WHEN** polling observes the status change from `discovering` to `awaiting_confirmation`
- **THEN** the UI navigates to the portfolio confirmation screen showing the discovered companies

### Requirement: Scan→company link records persist URL and submission order

When the API handler creates `scan_company` link records at confirm time, each link SHALL include `company_url` and `order_index` fields in addition to the existing `company_id` and `company_name`. The `order_index` SHALL be a zero-based integer matching the company's position in the user's submission order. Repository reads SHALL fall back gracefully when older link records lack these fields.

#### Scenario: Confirm writes URL and order on each link

- **WHEN** the user confirms a portfolio scan with 50 companies in a specific order
- **THEN** 50 `scan_company` link records exist in DynamoDB, each carrying `company_id`, `company_name`, `company_url`, and `order_index` values 0..49 in submission order

#### Scenario: Read tolerates legacy records without URL

- **WHEN** `get_scan_companies` reads a link record that lacks `company_url` (written before the deployment that introduced the field)
- **THEN** the returned dict has `company_url` absent (or set to `None`); the read does not raise

#### Scenario: Read tolerates legacy records without order_index

- **WHEN** `get_scan_companies` reads a link record that lacks `order_index`
- **THEN** the returned dict has `order_index` absent (or set to `None`); the read does not raise, and downstream sorting falls back to `company_id`

### Requirement: GET /scan/{id} returns a unified analyses array of length total_companies

The `GET /scan/{id}` response SHALL include an `analyses` array whose length equals `total_companies` from the moment the scan transitions to `running`. Each entry in the array SHALL correspond to exactly one `scan_company` link, hydrated with `companies`-table data when present and synthesized as a pending entry when not. Each entry SHALL carry an explicit `state` field with one of four values: `pending`, `scanning`, `done`, `failed`.

#### Scenario: All companies pending immediately after confirm

- **WHEN** the user has confirmed a 50-company scan and zero `companies`-table records exist yet
- **THEN** `GET /scan/{scan_id}` returns `analyses` of length 50, each with `state: "pending"`, populated `companyName` + `companyUrl` + `orderIndex`, and `null` for `overallRiskScore` / `riskTier` / `analyzedAt`

#### Scenario: Mid-scan with mixed states

- **WHEN** during a 50-company scan, 5 companies have `analyzed_at` set, 10 have `pipeline_progress > 0`, 8 have records but `pipeline_progress = 0`, and 27 have no `companies` record yet
- **THEN** the response analyses array contains 5 entries with `state: "done"`, 10 with `state: "scanning"`, and 35 with `state: "pending"` — collapsing the no-record-yet and progress=0 cases into a single pending state

#### Scenario: Failed company surfaces failed state

- **WHEN** a company has `error` set on its `companies`-table record
- **THEN** its analysis entry has `state: "failed"` and the existing `error` field is populated

#### Scenario: Pending entries have orderIndex from link record

- **WHEN** the response is serialized
- **THEN** every entry has `orderIndex` populated from the link record's `order_index`; entries from legacy link records lacking `order_index` use `null` and the frontend's fallback sort applies

### Requirement: Each analysis entry exposes pipeline label for scanning state

Analysis entries with `state: "scanning"` SHALL include the current `pipelineLabel` string (the human-readable step name from the `companies`-table record's `pipeline_label` field). Entries in other states MAY include `pipelineLabel` but the frontend SHALL only render it when `state` is `scanning`.

#### Scenario: Scanning entry includes the label

- **WHEN** a `companies`-table record has `pipeline_progress: 50` and `pipeline_label: "Detailing opportunities..."`
- **THEN** the corresponding analysis entry has `state: "scanning"` and `pipelineLabel: "Detailing opportunities..."`

#### Scenario: Scanning entry with empty label still renders

- **WHEN** a `companies`-table record has `pipeline_progress: 50` and an empty `pipeline_label`
- **THEN** the corresponding analysis entry has `state: "scanning"` and `pipelineLabel: ""` (or absent); the frontend tolerates empty labels gracefully


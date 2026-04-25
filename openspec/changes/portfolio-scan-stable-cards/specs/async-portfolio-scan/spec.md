## ADDED Requirements

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

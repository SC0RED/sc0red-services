# mcp-scan-tools Specification

## Purpose
TBD - created by archiving change mcp-write-tools. Update Purpose after archive.
## Requirements
### Requirement: Start a single-company scan from an MCP client
The MCP server SHALL expose a `start_company_scan(url)` tool that initiates a single-company analysis using the same backend code path as the web UI, scoped to the authenticated user's organization, and SHALL return the scan id with guidance to track progress via `get_scan`.

#### Scenario: Successful start
- **WHEN** an authenticated MCP client with the `write` scope calls `start_company_scan` with a company URL
- **THEN** a scan record is created for the caller's org, an analysis message is enqueued on the analysis queue, and the tool returns the scan id and status

#### Scenario: Missing URL
- **WHEN** `start_company_scan` is called with an empty or missing URL
- **THEN** the tool returns a validation message and no scan record or queue message is created

### Requirement: Start a portfolio discovery scan from an MCP client
The MCP server SHALL expose a `start_portfolio_scan(url)` tool that initiates PE portfolio discovery via the same backend code path as the web UI, and SHALL tell the client to confirm discovered companies with `confirm_portfolio_scan` once the scan reaches `awaiting_confirmation`.

#### Scenario: Successful discovery start
- **WHEN** an authenticated MCP client with the `write` scope calls `start_portfolio_scan` with a PE firm URL
- **THEN** a portfolio scan record is created in `discovering` status, a discovery message is enqueued, and the tool returns the scan id with confirm guidance

### Requirement: Confirm discovered portfolio companies from an MCP client
The MCP server SHALL expose a `confirm_portfolio_scan(scan_id, company_urls)` tool that confirms discovered companies for analysis using the same backend code path as the web UI. The tool SHALL only operate on scans belonging to the caller's organization.

#### Scenario: Successful confirmation
- **WHEN** `confirm_portfolio_scan` is called for an org-owned scan in `awaiting_confirmation` with a non-empty list of discovered company URLs
- **THEN** the confirmed companies are enqueued for analysis and the tool returns a confirmation summary

#### Scenario: Cross-org scan is not found
- **WHEN** `confirm_portfolio_scan` is called with a scan id belonging to a different organization
- **THEN** the tool returns a not-found message and nothing is enqueued

### Requirement: Write tools require the write scope
Write tools SHALL refuse to act when the caller's access token lacks the `write` scope, returning a message that names the missing scope. Read tools SHALL remain unaffected by this gate.

#### Scenario: Read-only token is refused
- **WHEN** a client whose token carries only the `read` scope calls any write tool
- **THEN** the tool performs no writes and returns a message stating the `write` scope is required

### Requirement: Read-tool guidance matches the real tool surface
Read-tool empty-state messages that reference scan tools SHALL name tools that actually exist on the server.

#### Scenario: Empty analyses list
- **WHEN** `list_analyses` returns no analyses
- **THEN** the guidance names `start_company_scan` and the tool exists and is callable on the server


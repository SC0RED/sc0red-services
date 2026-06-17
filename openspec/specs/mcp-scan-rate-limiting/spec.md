# mcp-scan-rate-limiting Specification

## Purpose
TBD - created by archiving change mcp-write-tools. Update Purpose after archive.
## Requirements
### Requirement: Per-org limits on MCP-initiated scans
The MCP server SHALL enforce per-organization rate limits on scan-initiating tool calls (`start_company_scan`, `start_portfolio_scan`, `confirm_portfolio_scan`): at most 5 per rolling hour window and 30 per rolling day window. Enforcement SHALL be atomic (no race that admits calls beyond the limit) and SHALL happen before any scan record or queue message is created.

#### Scenario: Within limits
- **WHEN** an org has made fewer than 5 scan calls this hour and fewer than 30 today
- **THEN** the scan call proceeds and both window counters increment

#### Scenario: Hourly limit reached
- **WHEN** an org has already made 5 scan calls within the current hour window
- **THEN** the next scan call performs no writes and returns a message naming the limit (5 scans/hour per organization) and when to retry

#### Scenario: Daily limit reached
- **WHEN** an org has already made 30 scan calls within the current day window
- **THEN** the next scan call performs no writes and returns a message naming the daily limit and when to retry

### Requirement: Rate-limit state expires automatically
Rate-limit counters SHALL be stored with a TTL so expired windows are cleaned up automatically and impose no manual maintenance.

#### Scenario: Window expiry
- **WHEN** an hour window passes
- **THEN** calls in the new window start from a fresh counter and the old counter row is eligible for TTL deletion

### Requirement: Rate limits do not affect the web UI
Rate limiting SHALL apply only to MCP-initiated scan calls; scans started through the web application SHALL be unaffected.

#### Scenario: Web scan during MCP lockout
- **WHEN** an org has exhausted its MCP hourly limit
- **THEN** starting a scan from the web UI still succeeds


## ADDED Requirements

### Requirement: Read tools
The MCP server SHALL provide read-only tools that query existing Janus data scoped to the authenticated user's org.

#### Scenario: list_analyses returns org-scoped results
- **WHEN** a user calls `list_analyses`
- **THEN** the server returns only analyses belonging to the user's org

#### Scenario: get_analysis returns full details
- **WHEN** a user calls `get_analysis` with a valid analysis_id
- **THEN** the server returns company name, risk score, risk tier, risk dimensions, opportunities, EBITDA tree, and value chain

#### Scenario: search_analyses by query
- **WHEN** a user calls `search_analyses` with a query string (company name, URL, or industry)
- **THEN** the server returns matching analyses with fuzzy matching

#### Scenario: compare_analyses side by side
- **WHEN** a user calls `compare_analyses` with 2+ analysis IDs
- **THEN** the server returns a structured comparison of risk scores, dimensions, and opportunities

#### Scenario: get_dashboard returns summary
- **WHEN** a user calls `get_dashboard`
- **THEN** the server returns total analyses, average risk, critical count, scan count, and recent items

### Requirement: Write tools
The MCP server SHALL provide tools that create new data (scans, documents) subject to rate limiting.

#### Scenario: start_company_scan initiates analysis
- **WHEN** a user calls `start_company_scan` with a URL
- **THEN** the server starts a scan and returns scan_id

#### Scenario: start_portfolio_scan discovers companies
- **WHEN** a user calls `start_portfolio_scan` with a PE firm URL
- **THEN** the server starts discovery and returns scan_id

#### Scenario: confirm_portfolio_scan after discovery
- **WHEN** a user calls `confirm_portfolio_scan` with scan_id and selected companies
- **THEN** the server queues analyses for selected companies

#### Scenario: poll_scan_until_complete waits for results
- **WHEN** a user calls `poll_scan_until_complete` with scan_id
- **THEN** the server polls internally until the scan completes or times out, and returns the final result

#### Scenario: upload_document adds file to analysis
- **WHEN** a user calls `upload_document` with analysis_id, filename, and base64 content
- **THEN** the server uploads to S3 and registers the document

#### Scenario: reanalyze_with_documents triggers re-analysis
- **WHEN** a user calls `reanalyze_with_documents` with analysis_id
- **THEN** the server queues a re-analysis incorporating uploaded documents

### Requirement: Destructive tools
The MCP server SHALL provide tools that delete data. Tool descriptions SHALL clearly state the action is permanent.

#### Scenario: delete_analysis removes analysis
- **WHEN** a user calls `delete_analysis` with analysis_id
- **THEN** the server deletes the analysis and all associated data

#### Scenario: delete_scan cascades to analyses
- **WHEN** a user calls `delete_scan` with scan_id
- **THEN** the server deletes the scan and all associated analyses

#### Scenario: delete_document removes document
- **WHEN** a user calls `delete_document` with analysis_id and document_id
- **THEN** the server removes the document from S3 and DynamoDB

### Requirement: Tool descriptions optimized for AI
All tool descriptions SHALL be written for LLM consumption: clear about when to use each tool, what it returns, and how it relates to other tools. Descriptions SHALL disambiguate similar tools (e.g., `start_company_scan` vs `start_portfolio_scan`).

#### Scenario: AI selects correct tool
- **WHEN** a user says "analyze stripe.com" in Claude Desktop
- **THEN** Claude selects `start_company_scan` (not `start_portfolio_scan`) based on tool descriptions

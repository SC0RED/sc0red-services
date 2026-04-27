## ADDED Requirements

### Requirement: Tools access DynamoDB directly via repositories
All MCP tool handlers SHALL read data from DynamoDB using the same repository classes (`DynamoDBAssessmentRepository`, `DynamoDBCompanyRepository`, `DynamoDBScanRepository`, `DynamoDBUserRepository`) that backend handlers use. Tools SHALL NOT make HTTP calls to the backend API.

#### Scenario: get_analysis reads from repositories
- **WHEN** a user calls `get_analysis` with an analysis_id
- **THEN** the tool calls `company_repo.get_by_id()`, `assessment_repo.find_by_company()`, `assessment_repo.get_risk_scores()`, `assessment_repo.get_opportunities()`, `assessment_repo.get_ebitda_tree()`, `assessment_repo.get_value_chain()`, and `assessment_repo.get_documents()` — the same sequence as `handle_get_analysis`

#### Scenario: get_dashboard reads from repositories
- **WHEN** a user calls `get_dashboard`
- **THEN** the tool calls `company_repo.find_by_org()` and `scan_repo.find_recent_by_org()` — the same sequence as `handle_dashboard`

### Requirement: Org scoping enforced via auth context
All tools that query org-level data SHALL read the `org_id` from `get_authenticated_user()` and pass it to repository methods that filter by org. A tool SHALL NOT return data from another org.

#### Scenario: list_analyses scoped to user's org
- **WHEN** user A (org_id=org-1) calls `list_analyses`
- **THEN** the tool calls `company_repo.find_by_org("org-1")` and only returns companies belonging to org-1

### Requirement: Shared StorageProvider initialized once
A single `DynamoDBStorageProvider` instance SHALL be created in `mcp_handler.py` and passed to all tool registration functions. Individual repositories SHALL be created from this provider at registration time.

#### Scenario: Storage provider shared across tools
- **WHEN** the MCP Lambda initializes
- **THEN** one `DynamoDBStorageProvider` is created, and all tools use repositories from it

### Requirement: No HTTP api_client
The `src/mcp/api_client.py` file SHALL be deleted. No MCP tool SHALL make HTTP requests to the backend API. The `INTERNAL_SIGNING_KEY` environment variable SHALL be removed from infrastructure.

#### Scenario: api_client does not exist
- **WHEN** the codebase is inspected after this change
- **THEN** `src/mcp/api_client.py` does not exist and no tool imports it

### Requirement: Data assembly matches backend handlers
Each tool's data assembly logic SHALL produce the same data structure as the corresponding backend handler. Field names, nesting, and transformations SHALL be identical.

#### Scenario: get_analysis returns same fields as backend
- **WHEN** `get_analysis` tool returns data for a company
- **THEN** it includes companyName, companyUrl, industry, overallRiskScore, riskTier, analysisSummary, topActions, riskScores, opportunities, ebitdaTree, valueChain, and documents — same as `GET /api/analysis/{id}`

### Requirement: Tool tests mock repositories
All tool tests SHALL mock repository methods (e.g., `company_repo.get_by_id`, `assessment_repo.get_risk_scores`) instead of mocking `call_backend`. Tests SHALL verify the tool calls the correct repository methods with the correct arguments.

#### Scenario: get_analysis test mocks repositories
- **WHEN** the test for `get_analysis` runs
- **THEN** it mocks `company_repo.get_by_id()` and `assessment_repo.find_by_company()` to return test data, and verifies the tool output contains the expected formatted text

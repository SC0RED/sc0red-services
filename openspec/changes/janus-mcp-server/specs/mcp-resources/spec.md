## ADDED Requirements

### Requirement: Resource listing
The MCP server SHALL respond to `resources/list` with all available resource URIs for the authenticated user's org.

#### Scenario: Client lists resources
- **WHEN** a client sends `resources/list`
- **THEN** the server returns URIs for all analyses, scans, and portfolio views belonging to the user's org

### Requirement: Analysis resources
The MCP server SHALL expose analysis data as resources addressable by URI.

#### Scenario: Fetch full analysis resource
- **WHEN** a client reads `analysis://{id}`
- **THEN** the server returns the complete analysis as structured text (company name, scores, risks, opportunities, EBITDA, value chain)

#### Scenario: Fetch analysis sub-resource
- **WHEN** a client reads `analysis://{id}/risk`, `analysis://{id}/opportunities`, `analysis://{id}/ebitda`, or `analysis://{id}/value-chain`
- **THEN** the server returns only that section of the analysis

### Requirement: Scan resources
The MCP server SHALL expose scan data as resources.

#### Scenario: Fetch scan resource
- **WHEN** a client reads `scan://{id}`
- **THEN** the server returns scan metadata, status, and linked company analyses

### Requirement: Portfolio resources
The MCP server SHALL expose aggregate portfolio views as resources.

#### Scenario: Fetch current portfolio
- **WHEN** a client reads `portfolio://current`
- **THEN** the server returns a summary of all analyses: company names, risk scores, tiers, and key stats

#### Scenario: Fetch critical risk portfolio
- **WHEN** a client reads `portfolio://critical-risk`
- **THEN** the server returns only analyses with critical or high risk tier

### Requirement: Resource content optimized for AI context
Resource content SHALL be formatted as concise structured text (not raw JSON) suitable for inclusion in an LLM prompt context. Content SHALL include key metrics, summaries, and actionable items while staying within reasonable token limits.

#### Scenario: Analysis resource fits in context
- **WHEN** a client includes `analysis://{id}` in prompt context
- **THEN** the resource content is under 2000 tokens and includes all essential information

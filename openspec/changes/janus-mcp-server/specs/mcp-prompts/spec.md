## ADDED Requirements

### Requirement: Prompt listing
The MCP server SHALL respond to `prompts/list` with all available prompt templates, their descriptions, and required arguments.

#### Scenario: Client lists prompts
- **WHEN** a client sends `prompts/list`
- **THEN** the server returns all registered prompts with name, description, and argument schemas

### Requirement: Investment memo prompt
The `/janus_investment_memo` prompt SHALL accept an analysis_id, fetch the analysis data, and return a structured prompt that guides the AI to produce a PE investment memo with executive summary, AI risk assessment, opportunity summary, value chain observations, and recommendation.

#### Scenario: Generate investment memo prompt
- **WHEN** a client invokes `/janus_investment_memo` with analysis_id
- **THEN** the server returns a prompt containing analysis data and memo structure template

### Requirement: Risk briefing prompt
The `/janus_risk_briefing` prompt SHALL accept an analysis_id and return a prompt for a concise 1-page risk summary highlighting the top risks, their scores, and mitigation considerations.

#### Scenario: Generate risk briefing prompt
- **WHEN** a client invokes `/janus_risk_briefing` with analysis_id
- **THEN** the server returns a prompt with risk data and briefing template

### Requirement: Diligence checklist prompt
The `/janus_diligence_checklist` prompt SHALL accept an analysis_id and return a prompt for generating an AI-specific due diligence checklist based on identified risks and opportunities.

#### Scenario: Generate diligence checklist prompt
- **WHEN** a client invokes `/janus_diligence_checklist` with analysis_id
- **THEN** the server returns a prompt with analysis data and checklist template

### Requirement: Portfolio review prompt
The `/janus_portfolio_review` prompt SHALL take no arguments and return a prompt for a cross-portfolio risk summary using all analyses in the user's org.

#### Scenario: Generate portfolio review prompt
- **WHEN** a client invokes `/janus_portfolio_review`
- **THEN** the server fetches all analyses for the org and returns a prompt with portfolio data and review template

### Requirement: Company comparison prompt
The `/janus_compare_companies` prompt SHALL accept two or more analysis IDs and return a prompt for structured side-by-side comparison.

#### Scenario: Generate comparison prompt
- **WHEN** a client invokes `/janus_compare_companies` with analysis IDs
- **THEN** the server returns a prompt with comparison data and comparison template

### Requirement: Opportunity deep dive prompt
The `/janus_opportunity_deep_dive` prompt SHALL accept an analysis_id and optional value_lever filter, returning a prompt for detailed exploration of AI opportunities.

#### Scenario: Generate opportunity deep dive prompt
- **WHEN** a client invokes `/janus_opportunity_deep_dive` with analysis_id and lever="automation"
- **THEN** the server returns a prompt with filtered opportunity data and deep dive template

### Requirement: Prompt templates externalized
All prompt template content SHALL be stored as external Markdown files in `src/mcp/prompts/` following the existing pattern of `src/pipeline/prompts/`. Templates SHALL NOT be inline in Python code.

#### Scenario: Template file exists for each prompt
- **WHEN** a new prompt is registered
- **THEN** its template content is loaded from an external `.md` file in `src/mcp/prompts/`

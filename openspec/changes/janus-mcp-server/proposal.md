## Why

Janus is a fully functional web app for PE AI risk intelligence. The next strategic step is making Janus available where PE analysts increasingly work — inside AI assistants (Claude Desktop, Cursor, ChatGPT, etc.). By exposing Janus as a hosted MCP (Model Context Protocol) server, analysts can query portfolio risk, run scans, compare companies, and draft investment memos without leaving their AI assistant.

This is a distribution play: the first AI risk platform natively available in AI assistants captures the workflow. The web app becomes the "deep dive" surface; MCP becomes the "always on" surface.

## What Changes

### New: OAuth 2.0 Authorization Server
- MCP-spec-compliant OAuth with Dynamic Client Registration (DCR)
- PKCE-based authorization code flow
- Consent UI page in Next.js frontend (matches design system)
- Token issuance (JWT signed by Janus, backed by Cognito user identity)
- Token refresh, revocation, and audit logging
- OAuth data stored in existing DynamoDB single-table (`OAUTH_CLIENT#`, `OAUTH_CODE#`, `OAUTH_TOKEN#`, `OAUTH_REFRESH#` prefixes)

### New: MCP Server (Python, separate Lambda)
- Hosted MCP server using `mcp` Python SDK
- SSE transport via Lambda Function URL (streaming support)
- Custom domain: `mcp.{env}.janus.sc0red.com` via CloudFront
- OAuth token validation middleware mapping to existing `AuthContext`

### New: MCP Tools (~22 tools)
- **Read tools**: `list_analyses`, `get_analysis`, `get_risk_breakdown`, `get_opportunities`, `get_ebitda_tree`, `get_value_chain`, `list_scans`, `get_scan`, `get_dashboard`, `list_team_members`, `list_documents`, `search_analyses`, `compare_analyses`
- **Write tools**: `start_company_scan`, `start_portfolio_scan`, `confirm_portfolio_scan`, `poll_scan_until_complete`, `reanalyze_with_documents`, `upload_document`
- **Destructive tools**: `delete_analysis`, `delete_scan`, `delete_document`

### New: MCP Resources
- `analysis://{id}` (full analysis + sub-resources for risk, opportunities, ebitda, value-chain)
- `scan://{id}`, `portfolio://current`, `portfolio://critical-risk`

### New: MCP Prompts
- `/janus_investment_memo`, `/janus_risk_briefing`, `/janus_diligence_checklist`, `/janus_portfolio_review`, `/janus_compare_companies`, `/janus_opportunity_deep_dive`
- Templates stored as external files following existing `src/pipeline/prompts/` pattern

### New: Infrastructure
- MCP Lambda (Python 3.12, dedicated)
- Lambda Function URL with CloudFront distribution
- CDK `MCPConstruct` for all MCP-related infrastructure
- Rate limiting per-user and per-org for write operations

### New: Auth middleware extension
- Detect OAuth Bearer tokens vs Cognito JWT tokens
- Validate Janus-issued OAuth tokens and map to `AuthContext`
- Dual-auth support: existing Cognito path unchanged, new OAuth path added

## Capabilities

### New Capabilities
- `oauth-server`: OAuth 2.0 Authorization Server with DCR, PKCE, consent UI, token management
- `mcp-server`: Hosted MCP server with SSE transport, tool/resource/prompt registration
- `mcp-tools`: Read, write, and destructive tools exposing all Janus functionality
- `mcp-resources`: URI-addressable data for AI assistant context injection
- `mcp-prompts`: Pre-built workflow templates for common PE tasks
- `mcp-infrastructure`: CDK construct for MCP Lambda, Function URL, CloudFront, custom domain

### Modified Capabilities

## Impact

- **New backend code**: OAuth handlers, MCP handler, tool/resource/prompt definitions, OAuth middleware
- **New frontend code**: Consent UI page (`/oauth/authorize`), connected apps settings page
- **New infrastructure**: MCP Lambda, Function URL, CloudFront distribution, custom domain
- **Modified**: Auth middleware (dual-auth support), DynamoDB table (new pk prefixes for OAuth data)
- **No existing API changes**: All current endpoints, auth flows, and web app behavior unchanged
- **Dependencies**: `mcp` Python SDK added to backend

## PR 1: OAuth Provider + Infrastructure

### Research & spike
- [x] 1.1 Spike: verify FastMCP `streamable_http_app()` + Mangum works on Lambda (minimal hello-world)
- [x] 1.2 Spike: verify `OAuthAuthorizationServerProvider` interface — confirm method signatures, test SDK auto-mounts endpoints

### Infrastructure
- [x] 1.3 Generate RSA key pair, store in Secrets Manager via CDK
- [x] 1.4 Create `MCPConstruct` in CDK (Lambda, Function URL, CloudFront, custom domain)
- [x] 1.5 Configure MCP Lambda environment variables (DYNAMODB_TABLE, API_URL, OAUTH_SIGNING_KEY_SECRET_ARN)

### OAuth provider implementation
- [x] 1.6 Create `src/mcp/oauth_provider.py` implementing `OAuthAuthorizationServerProvider`
- [x] 1.7 Implement `get_client()` — lookup from DynamoDB OAUTH_CLIENT#
- [x] 1.8 Implement `register_client()` — store in DynamoDB OAUTH_CLIENT#, generate client_id
- [x] 1.9 Implement `authorize()` — redirect to Janus consent UI with params
- [x] 1.10 Implement `exchange_authorization_code()` — PKCE validation, JWT signing, store tokens
- [x] 1.11 Implement `exchange_refresh_token()` — validate refresh, rotate tokens
- [x] 1.12 Implement `verify_access_token()` — JWT signature + expiry verification, return AuthInfo
- [x] 1.13 Implement `revoke_token()` — delete from DynamoDB
- [x] 1.14 Create `src/mcp/oauth_repository.py` — DynamoDB CRUD for OAuth records (clients, codes, tokens, refresh tokens)
- [x] 1.15 Create `src/mcp/token_utils.py` — RSA JWT signing/verification, PKCE helpers, code generation

### Frontend consent UI
- [x] 1.16 Create `/oauth/authorize` Next.js page with consent screen (client name, permissions, Allow/Cancel)
- [x] 1.17 Create backend endpoint `POST /api/oauth/approve` — generates authorization code, redirects to client
- [x] 1.18 Handle login redirect: if user not logged in, redirect to /login then back to consent

### MCP handler entry point
- [x] 1.19 Create `src/mcp/mcp_handler.py` — Lambda entry point using FastMCP + Mangum + OAuthAuthorizationServerProvider
- [x] 1.20 Register 1 tool (`get_analysis`) as proof of full stack

### Tests
- [x] 1.21 Unit tests for OAuth provider (17 tests)
- [x] 1.22 Unit tests for OAuth repository (14 tests)
- [x] 1.23 Unit tests for token utils (17 tests)
- [x] 1.24 Unit tests for OAuth handler (7 tests)
- [x] 1.25 Full test suite passes: 617 tests, 95.22% coverage
- [x] 1.26 Architecture review + audit (13 findings: 7 CRITICAL fixed, 4 MEDIUM addressed, 2 LOW deferred)

## PR 2: Read Tools

### Tool implementations
- [x] 2.1 `list_analyses` — list org analyses with optional filters
- [x] 2.2 `search_analyses` — fuzzy search by company name, URL, or industry
- [x] 2.3 `get_risk_breakdown` — risk scores by dimension for an analysis
- [x] 2.4 `get_opportunities` — opportunities with value levers for an analysis
- [x] 2.5 `get_ebitda_tree` — EBITDA model for an analysis
- [x] 2.6 `get_value_chain` — value chain analysis for an analysis
- [x] 2.7 `list_scans` — N/A (scans accessed via dashboard or get_scan)
- [x] 2.8 `get_scan` — scan details with linked analyses
- [x] 2.9 `get_dashboard` — dashboard summary stats
- [x] 2.10 `list_team_members` — org team members
- [x] 2.11 `list_documents` — documents for an analysis
- [x] 2.12 `compare_analyses` — side-by-side comparison of 2+ analyses

### Tests
- [x] 2.13 Unit tests per tool (22 tests covering data, empty states, edge cases)
- [ ] 2.14 Tool description validation: test with Claude Desktop (post-deployment)
- [x] 2.15 Architecture review + audit (4 CRITICAL fixed, 4 MEDIUM fixed)
- [ ] 2.15 Architecture review + audit

## PR 3: Write Tools

### Tool implementations
- [ ] 3.1 `start_company_scan` — initiate single company scan
- [ ] 3.2 `start_portfolio_scan` — initiate PE portfolio discovery
- [ ] 3.3 `confirm_portfolio_scan` — confirm discovered companies for analysis
- [ ] 3.4 `poll_scan_until_complete` — server-side polling with timeout
- [ ] 3.5 `upload_document` — accept base64 content, upload to S3, register
- [ ] 3.6 `reanalyze_with_documents` — trigger re-analysis pipeline
- [ ] 3.7 Implement rate limiting (100 reads/min, 5 scans/hour, 30 scans/day per org)

### Tests
- [ ] 3.8 Unit test per tool (success, validation errors, org scoping)
- [ ] 3.9 Rate limiting tests (within limit, exceeded, per-org)
- [ ] 3.10 Integration test: full scan flow via MCP (start → poll → view results)
- [ ] 3.11 Architecture review + audit

## PR 4: Destructive Tools + Audit Logging

### Tool implementations
- [ ] 4.1 `delete_analysis` — delete analysis and associated data
- [ ] 4.2 `delete_scan` — cascade delete scan and linked analyses
- [ ] 4.3 `delete_document` — remove document from S3 and DynamoDB

### Audit logging
- [ ] 4.4 Create audit log writer (DynamoDB or CloudWatch structured logs)
- [ ] 4.5 Log every MCP tool invocation: user_id, org_id, client_id, tool_name, args, timestamp, success/error
- [ ] 4.6 Add audit logging to all existing tools (read + write)

### Tests
- [ ] 4.7 Unit tests for destructive tools (deletion + cascade verification)
- [ ] 4.8 Audit log tests (records created for each invocation)
- [ ] 4.9 Architecture review + audit

## PR 5: Resources

### Resource implementations
- [ ] 5.1 Register resource handlers with MCP server
- [ ] 5.2 `analysis://{id}` — full analysis as structured text
- [ ] 5.3 `analysis://{id}/risk`, `analysis://{id}/opportunities`, `analysis://{id}/ebitda`, `analysis://{id}/value-chain` — sub-resources
- [ ] 5.4 `scan://{id}` — scan details as structured text
- [ ] 5.5 `portfolio://current` — aggregated portfolio summary
- [ ] 5.6 `portfolio://critical-risk` — filtered high/critical risk analyses
- [ ] 5.7 `resources/list` handler returning available resources for user's org
- [ ] 5.8 Create resource content formatter (JSON → concise structured text optimized for LLM context, under 2000 tokens)

### Tests
- [ ] 5.9 Unit tests per resource (content format, org scoping, sub-resources)
- [ ] 5.10 Token limit validation (resource content under 2000 tokens)
- [ ] 5.11 Architecture review + audit

## PR 6: Prompts

### Prompt template files
- [ ] 6.1 Create `src/mcp/prompts/` directory and template loader
- [ ] 6.2 Write `investment_memo.md` template
- [ ] 6.3 Write `risk_briefing.md` template
- [ ] 6.4 Write `diligence_checklist.md` template
- [ ] 6.5 Write `portfolio_review.md` template
- [ ] 6.6 Write `compare_companies.md` template
- [ ] 6.7 Write `opportunity_deep_dive.md` template

### Prompt handlers
- [ ] 6.8 Register prompt handlers with MCP server using @mcp.prompt()
- [ ] 6.9 Implement argument validation and data fetching for each prompt
- [ ] 6.10 `prompts/list` handler returning available prompts with descriptions

### Tests
- [ ] 6.11 Unit tests per prompt (argument validation, data fetching, template rendering)
- [ ] 6.12 Test prompt output quality with Claude Desktop (produces reasonable memos/briefings)
- [ ] 6.13 Architecture review + audit

## PR 7: Connected Apps UI + Documentation + Launch

### Connected apps UI
- [ ] 7.1 Create "Connected Apps" section in Janus settings (list connected MCP clients, revoke access)
- [ ] 7.2 Token revocation from UI calls backend to delete OAuth tokens

### Documentation
- [ ] 7.3 Create `docs/mcp-server.md` — comprehensive guide (architecture, setup, tools, resources, prompts)
- [ ] 7.4 Create quickstart section for Claude Desktop connection
- [ ] 7.5 Document all tools with examples and expected output
- [ ] 7.6 Document all resources with URI patterns
- [ ] 7.7 Document all prompts with argument descriptions

### Polish
- [ ] 7.8 Tool description review and iteration (test with Claude Desktop)
- [ ] 7.9 Error message review (user-friendly, actionable)
- [ ] 7.10 Rate limit tuning based on testing

### Launch
- [ ] 7.11 Deploy to staging and run full E2E verification
- [ ] 7.12 Deploy to production
- [ ] 7.13 Submit to MCP registries (Anthropic, Cursor)

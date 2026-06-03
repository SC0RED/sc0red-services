## Context

Janus is a PE AI Risk Intelligence Platform with a Python 3.12 backend (Lambda + API Gateway), Next.js 14 frontend (Amplify), DynamoDB single-table, Cognito authentication, and SQS-based async AI pipeline. The platform analyzes companies for AI risk exposure, producing risk scores, opportunities, EBITDA trees, and value chain analyses.

The MCP server exposes this functionality to AI assistants (Claude Desktop, Cursor, etc.) via the Model Context Protocol. It runs as a separate hosted service alongside the existing web app, sharing the same backend data and auth infrastructure.

**Key finding from research:** The MCP Python SDK (`mcp` package) provides `FastMCP` high-level API with decorator-based tool/resource/prompt registration, and an `OAuthAuthorizationServerProvider` interface for server-side OAuth. The SDK auto-mounts all standard OAuth endpoints when you implement this interface. The newer **Streamable HTTP** transport (`POST /mcp`) replaces SSE and works natively with Lambda + Mangum.

## Complete Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  AI Assistant (Claude Desktop / Cursor / ChatGPT / Custom)                  │
│                                                                             │
│  User: "Analyze stripe.com and draft a risk briefing"                       │
└──────────────────────────────┬──────────────────────────────────────────────┘
                               │
                               │ MCP over Streamable HTTP (POST /mcp)
                               │ Authorization: Bearer <oauth_access_token>
                               │
┌──────────────────────────────▼──────────────────────────────────────────────┐
│  mcp.janus.sc0red.com (Lambda Function URL + CloudFront)                    │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  MCP Lambda (Python 3.12)                                            │   │
│  │                                                                      │   │
│  │  ┌────────────────────────────────────────────────────────────────┐  │   │
│  │  │  FastMCP Server (mcp Python SDK)                               │  │   │
│  │  │                                                                │  │   │
│  │  │  OAuth (SDK-managed endpoints):                                │  │   │
│  │  │    /.well-known/oauth-protected-resource  (RFC 9728)           │  │   │
│  │  │    /.well-known/oauth-authorization-server (RFC 8414)          │  │   │
│  │  │    /register                              (RFC 7591 DCR)       │  │   │
│  │  │    /authorize                             (browser flow)       │  │   │
│  │  │    /token                                 (code + refresh)     │  │   │
│  │  │    /revoke                                (token revocation)   │  │   │
│  │  │                                                                │  │   │
│  │  │  MCP Protocol (SDK-managed):                                   │  │   │
│  │  │    POST /mcp                              (Streamable HTTP)    │  │   │
│  │  │                                                                │  │   │
│  │  │  ┌──────────────────────────────────────────────────────────┐  │  │   │
│  │  │  │  OAuthAuthorizationServerProvider (Janus implementation) │  │  │   │
│  │  │  │  - get_client()          → DynamoDB OAUTH_CLIENT#        │  │  │   │
│  │  │  │  - register_client()     → DynamoDB OAUTH_CLIENT#        │  │  │   │
│  │  │  │  - authorize()           → redirect to consent UI        │  │  │   │
│  │  │  │  - exchange_auth_code()  → DynamoDB OAUTH_CODE#          │  │  │   │
│  │  │  │  - exchange_refresh()    → DynamoDB OAUTH_REFRESH#       │  │  │   │
│  │  │  │  - verify_access_token() → JWT verification              │  │  │   │
│  │  │  │  - revoke_token()        → DynamoDB delete               │  │  │   │
│  │  │  └──────────────────────────────────────────────────────────┘  │  │   │
│  │  │                                                                │  │   │
│  │  │  ┌──────────────────────────────────────────────────────────┐  │  │   │
│  │  │  │  Rate Limiter (per-user/org)                             │  │  │   │
│  │  │  └──────────────────────────────────────────────────────────┘  │  │   │
│  │  │                                                                │  │   │
│  │  │  ┌──────────────────────────────────────────────────────────┐  │  │   │
│  │  │  │  Tool / Resource / Prompt Handlers                       │  │  │   │
│  │  │  │                                                          │  │  │   │
│  │  │  │  @mcp.tool()     — 22 tools (read, write, destructive)  │  │  │   │
│  │  │  │  @mcp.resource() — 8 resource URIs                      │  │  │   │
│  │  │  │  @mcp.prompt()   — 6 workflow templates                 │  │  │   │
│  │  │  └─────────────────────────┬────────────────────────────────┘  │  │   │
│  │  └────────────────────────────┼───────────────────────────────────┘  │   │
│  │                               │ HTTPS (internal)                     │   │
│  │  Mangum (ASGI → Lambda adapter)                                      │   │
│  └───────────────────────────────┼──────────────────────────────────────┘   │
│                                  │                                          │
│  ┌───────────────────────────────▼──────────────────────────────────────┐   │
│  │  Existing Janus Backend (API Gateway + Lambda)                       │   │
│  │  /api/dashboard, /api/analyses, /api/scan/*, /api/analysis/*, ...   │   │
│  │  Auth: Cognito RS256 JWT (unchanged)                                 │   │
│  └──────────────┬───────────────────────────────┬───────────────────────┘   │
│                 │                               │                           │
│        ┌────────▼─────────┐           ┌─────────▼──────────┐               │
│        │    DynamoDB       │           │    SQS + Worker    │               │
│        │  (single table)   │           │  (AI pipeline)     │               │
│        │  + OAuth records  │           └────────────────────┘               │
│        └──────────────────┘                                                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

## OAuth 2.0 Complete Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 1: Client connects to MCP server, gets 401                            │
│                                                                             │
│  Claude Desktop ──POST──▶ mcp.janus.sc0red.com/mcp                        │
│                  ◀─401─── WWW-Authenticate: Bearer                          │
│                           resource_metadata=                                │
│                             "https://mcp.janus.sc0red.com/                  │
│                              .well-known/oauth-protected-resource"          │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
┌─────────────────────────────────────▼───────────────────────────────────────┐
│  STEP 2: Client discovers Protected Resource Metadata (RFC 9728)            │
│                                                                             │
│  Claude Desktop ──GET──▶ /.well-known/oauth-protected-resource             │
│                  ◀─200── {                                                  │
│                            "resource": "https://mcp.janus.sc0red.com",     │
│                            "authorization_servers":                          │
│                              ["https://mcp.janus.sc0red.com"],             │
│                            "scopes_supported": ["read", "write"],          │
│                            "bearer_methods_supported": ["header"]           │
│                          }                                                  │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
┌─────────────────────────────────────▼───────────────────────────────────────┐
│  STEP 3: Client discovers Authorization Server Metadata (RFC 8414)          │
│                                                                             │
│  Claude Desktop ──GET──▶ /.well-known/oauth-authorization-server           │
│                  ◀─200── {                                                  │
│                            "issuer": "https://mcp.janus.sc0red.com",       │
│                            "authorization_endpoint": ".../authorize",       │
│                            "token_endpoint": ".../token",                   │
│                            "registration_endpoint": ".../register",        │
│                            "revocation_endpoint": ".../revoke",            │
│                            "response_types_supported": ["code"],           │
│                            "code_challenge_methods_supported": ["S256"],    │
│                            "grant_types_supported":                         │
│                              ["authorization_code", "refresh_token"],       │
│                            "token_endpoint_auth_methods_supported":         │
│                              ["none"]                                       │
│                          }                                                  │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
┌─────────────────────────────────────▼───────────────────────────────────────┐
│  STEP 4: Dynamic Client Registration — DCR (RFC 7591)                       │
│                                                                             │
│  Claude Desktop ──POST─▶ /register                                         │
│                  Body: { "client_name": "Claude Desktop",                   │
│                          "redirect_uris": ["http://localhost:..."],         │
│                          "grant_types": ["authorization_code",              │
│                                          "refresh_token"],                  │
│                          "response_types": ["code"],                        │
│                          "token_endpoint_auth_method": "none" }            │
│                                                                             │
│                  ◀─201── { "client_id": "dyn_abc123...",                    │
│                            "client_name": "Claude Desktop",                 │
│                            "redirect_uris": [...],                          │
│                            ... }                                            │
│                                                                             │
│  DynamoDB: pk=OAUTH_CLIENT#dyn_abc123  sk=CLIENT#METADATA                  │
│  Client caches client_id for future sessions.                               │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
┌─────────────────────────────────────▼───────────────────────────────────────┐
│  STEP 5: Authorization Code + PKCE (browser flow)                           │
│                                                                             │
│  Client generates:                                                          │
│    code_verifier = random(43-128 chars)                                     │
│    code_challenge = BASE64URL(SHA256(code_verifier))                        │
│                                                                             │
│  Claude Desktop opens browser:                                              │
│    https://mcp.janus.sc0red.com/authorize?                                 │
│      client_id=dyn_abc123                                                   │
│      &response_type=code                                                    │
│      &redirect_uri=http://localhost:PORT/callback                           │
│      &code_challenge=<challenge>                                            │
│      &code_challenge_method=S256                                            │
│      &state=random123                                                       │
│      &scope=read+write                                                      │
│                                                                             │
│  MCP server redirects to Janus consent UI:                                  │
│    https://janus.sc0red.com/oauth/authorize?<same params>                  │
│                                                                             │
│  ┌─────────────────────────────────────────────────────┐                    │
│  │  Janus Frontend (Next.js) — /oauth/authorize        │                   │
│  │                                                      │                   │
│  │  IF not logged in → redirect to /login first         │                   │
│  │  IF logged in → show consent screen:                 │                   │
│  │                                                      │                   │
│  │  ┌──────────────────────────────────────────────┐   │                   │
│  │  │  ┌──────┐                                     │   │                   │
│  │  │  │ Logo │  Claude Desktop wants to            │   │                   │
│  │  │  └──────┘  access your Janus account          │   │                   │
│  │  │                                               │   │                   │
│  │  │  Signed in as: ved@sc0red.com                 │   │                   │
│  │  │                                               │   │                   │
│  │  │  This will allow Claude Desktop to:           │   │                   │
│  │  │  ✓ View your analyses and risk scores         │   │                   │
│  │  │  ✓ Run new company and portfolio scans        │   │                   │
│  │  │  ✓ Manage documents                           │   │                   │
│  │  │  ✓ Delete analyses and scans                  │   │                   │
│  │  │                                               │   │                   │
│  │  │         [Cancel]    [Allow Access]            │   │                   │
│  │  └──────────────────────────────────────────────┘   │                   │
│  └──────────────────────────────────────────────────────┘                    │
│                                                                             │
│  User clicks "Allow Access":                                                │
│    Frontend calls backend → generates authorization code (10 min TTL)       │
│    DynamoDB: pk=OAUTH_CODE#<code>  sk=CODE#METADATA                        │
│    { user_id, org_id, client_id, code_challenge, redirect_uri, exp }       │
│                                                                             │
│    Redirects to: http://localhost:PORT/callback?code=<code>&state=random123 │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
┌─────────────────────────────────────▼───────────────────────────────────────┐
│  STEP 6: Token exchange (PKCE verified)                                     │
│                                                                             │
│  Claude Desktop ──POST─▶ /token                                            │
│                  Content-Type: application/x-www-form-urlencoded            │
│                  Body: grant_type=authorization_code                         │
│                        &code=<code>                                         │
│                        &client_id=dyn_abc123                                │
│                        &code_verifier=<original_verifier>                   │
│                        &redirect_uri=http://localhost:PORT/callback         │
│                                                                             │
│  Server validates:                                                          │
│    ✓ Code exists in DynamoDB and not expired                                │
│    ✓ client_id matches code's client                                        │
│    ✓ BASE64URL(SHA256(code_verifier)) == stored code_challenge (PKCE)      │
│    ✓ redirect_uri matches stored redirect_uri                               │
│                                                                             │
│  Server issues:                                                             │
│    access_token  (JWT, 1h TTL, signed by Janus RSA key)                    │
│      Claims: { sub, email, org_id, role, client_id, scope, iss, exp }      │
│    refresh_token (opaque, 30d TTL)                                         │
│                                                                             │
│  DynamoDB: pk=OAUTH_TOKEN#hash(token)    sk=TOKEN#METADATA   (TTL: 1h)    │
│            pk=OAUTH_REFRESH#hash(token)  sk=REFRESH#METADATA (TTL: 30d)   │
│  Deletes:  pk=OAUTH_CODE#<code>  (single use)                             │
│                                                                             │
│                  ◀─200── { "access_token": "eyJ...",                        │
│                            "token_type": "Bearer",                          │
│                            "expires_in": 3600,                              │
│                            "refresh_token": "ref_xyz..." }                 │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
┌─────────────────────────────────────▼───────────────────────────────────────┐
│  STEP 7: MCP communication (Streamable HTTP)                                │
│                                                                             │
│  Claude Desktop ──POST─▶ /mcp                                              │
│                  Authorization: Bearer eyJ...                                │
│                  Content-Type: application/json                              │
│                  Body: { "jsonrpc": "2.0",                                  │
│                          "method": "tools/call",                            │
│                          "params": { "name": "get_analysis",               │
│                                      "arguments": { "id": "abc123" } },    │
│                          "id": 1 }                                          │
│                                                                             │
│  MCP Server (FastMCP + OAuthAuthorizationServerProvider):                   │
│    1. SDK validates OAuth access_token via verify_access_token()            │
│    2. SDK extracts AuthInfo (user_id, org_id, role, client_id)             │
│    3. SDK dispatches to registered @mcp.tool() handler                      │
│    4. Handler calls Janus backend API internally                            │
│    5. Handler formats response as MCP content blocks                        │
│                                                                             │
│                  ◀─200── { "jsonrpc": "2.0",                                │
│                            "result": { "content": [                         │
│                              { "type": "text",                              │
│                                "text": "Stripe, Inc.\nRisk: 4.5/10..." }   │
│                            ] },                                             │
│                            "id": 1 }                                        │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
┌─────────────────────────────────────▼───────────────────────────────────────┐
│  STEP 8: Token refresh (when access_token expires after 1h)                 │
│                                                                             │
│  Claude Desktop ──POST─▶ /token                                            │
│                  Content-Type: application/x-www-form-urlencoded            │
│                  Body: grant_type=refresh_token                              │
│                        &refresh_token=ref_xyz...                            │
│                        &client_id=dyn_abc123                                │
│                                                                             │
│  Server validates refresh token → issues new access_token + refresh_token  │
│  Old refresh_token invalidated (rotation)                                   │
│                                                                             │
│                  ◀─200── { "access_token": "eyJ...(new)",                   │
│                            "expires_in": 3600,                              │
│                            "refresh_token": "ref_new..." }                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Goals / Non-Goals

**Goals:**
- Fully functional hosted MCP server with Tools, Resources, and Prompts
- OAuth 2.0 with DCR from day 1 (no throwaway auth)
- Same quality bar as existing codebase (95% coverage, ruff, pyright, architecture review)
- Each PR self-contained, testable, deployable independently
- Python MCP server in same backend codebase (no new language)

**Non-Goals:**
- Local/self-install MCP server (hosted only for v1)
- Team invite via MCP (awkward UX — kept in web UI)
- Cross-browser MCP testing (Chromium + Claude Desktop only)
- Mobile MCP support
- Self-service API key management UI (OAuth replaces this)

## Decisions

### 1. Python MCP server using FastMCP + OAuthAuthorizationServerProvider

**Decision: Use `mcp` Python SDK's `FastMCP` class with decorator-based tool/resource/prompt registration. Implement `OAuthAuthorizationServerProvider` interface — the SDK auto-mounts all OAuth endpoints.**

Rationale: The SDK handles MCP protocol compliance, JSON-RPC dispatch, OAuth endpoint mounting, and token validation. We implement the storage layer (DynamoDB) and business logic (consent flow, token issuance). This avoids building OAuth endpoints from scratch and ensures spec compliance as the MCP spec evolves.

Alternative considered: Building OAuth endpoints manually in separate handler files. Rejected because the SDK already handles this and keeps pace with spec changes.

### 2. Streamable HTTP transport via Lambda + Mangum

**Decision: Use Streamable HTTP transport (`POST /mcp`) instead of SSE. Deploy as Lambda with Mangum ASGI adapter.**

Rationale: Streamable HTTP is the newer MCP transport that replaces SSE. It uses standard request/response HTTP, which works natively with Lambda (no streaming required). Mangum (already in backend dependencies) adapts the ASGI app from FastMCP to Lambda. This eliminates the need for Lambda Function URL streaming support and simplifies the deployment.

Alternative considered: SSE transport via Lambda Function URL with streaming. Rejected because Streamable HTTP is the recommended transport going forward and is simpler to deploy on Lambda.

### 3. Lambda Function URL (not API Gateway) for MCP endpoint

**Decision: Use Lambda Function URL for the MCP Lambda, fronted by CloudFront for custom domain.**

Rationale: The MCP server is a separate service with different scaling characteristics than the API. Function URL is simpler than adding routes to the existing API Gateway. CloudFront provides custom domain (`mcp.{env}.janus.sc0red.com`) and TLS. If Streamable HTTP needs occasional long-running responses (e.g., `poll_scan_until_complete`), Function URL has no 30s timeout like API Gateway.

### 4. OAuth data in existing DynamoDB single-table

**Decision: Use existing `janus-{env}` table with new pk prefixes: `OAUTH_CLIENT#`, `OAUTH_CODE#`, `OAUTH_TOKEN#`, `OAUTH_REFRESH#`.**

Rationale: Follows existing single-table design. No new table to provision, backup, or monitor. OAuth records are small and TTL-based (codes: 10 min, access tokens: 1h, refresh tokens: 30d). Can extract to separate table later if needed.

### 5. Consent UI in Next.js frontend

**Decision: The MCP server's `/authorize` endpoint redirects to a Next.js page at `janus.sc0red.com/oauth/authorize` for the consent screen.**

Rationale: Matches existing design system. Uses existing Cognito login flow (if user isn't logged in, redirect to `/login` first, then back to consent). After user approves, the frontend calls a backend API to generate the authorization code, then redirects to the client's redirect_uri.

### 6. Janus-issued JWT for OAuth access tokens

**Decision: Janus signs its own JWTs for OAuth access tokens using an RSA key pair stored in Secrets Manager.**

Rationale: OAuth tokens need custom claims (client_id, scope) and different lifetimes (1h access, 30d refresh) than Cognito tokens (8h). The `verify_access_token()` method in the OAuth provider validates these JWTs locally (no external call needed). JWKS endpoint at `/.well-known/jwks.json` for public key distribution.

### 7. Rate limiting for write operations

**Decision: Per-user rate limits: 100 reads/min, 5 scans/hour, 30 scans/day per org.**

Rationale: Read operations are cheap (DynamoDB queries). Write operations (scans) incur AI API costs ($0.10-0.50 per scan). Rate limits prevent runaway AI agents from burning through credits. Limits enforced in tool handlers before forwarding to backend.

### 8. MCP transport — switch from Mangum to AWS Lambda Web Adapter (supersedes Decision 2)

**Status:** Decision captured 2026-06-03 during Phase A tactical scout. Implementation deferred — see `tasks.md` "Resume here" section.

**Decision:** Replace the Mangum-based Lambda integration with AWS Lambda Web Adapter (LWA). LWA proxies HTTP between the Lambda Function URL and a real uvicorn server running inside the Lambda container. Mangum (chosen in Decision 2) is architecturally incompatible with the MCP SDK's streamable-HTTP transport when run on Lambda.

**Why (the discovery chain):**

Phase A scout against the deployed staging Lambda (`sc0red-services-mcp-staging`, us-east-1) uncovered two bugs in sequence:

1. **Bug A — cold-start crash.** Lambda failed at module import with `KeyError: 'private_key'` because the Secrets Manager secret (`sc0red-services-mcp-signing-key-staging`) was created empty by `MCPConstruct` but never populated. Fixed operationally by generating an RSA-2048 key pair locally and pushing it via `aws secretsmanager put-secret-value`. **The CDK construct still creates an empty secret** — see Bug X.

2. **Bug B — lifespan-vs-request mismatch (the architectural one).** Once Bug A was fixed, the first request to each cold-started container returned 200. Every subsequent request to the same warm container returned 502 with:

   ```
   RuntimeError: StreamableHTTPSessionManager .run() can only be called once
   per instance. Create a new instance if you need to run again.
   ```

   The MCP SDK's `StreamableHTTPSessionManager` is designed for long-lived ASGI servers where lifespan startup runs once at server boot. Mangum, by contrast, calls lifespan startup on **every** Lambda invocation. The session manager's run-once guard fires on every invocation past the first.

   Effective production behaviour: each Lambda container serves **exactly one** request before becoming a 502 machine. Not viable.

**Why the original Decision 2 spike missed it:** Task 1.1 ("verify FastMCP `streamable_http_app()` + Mangum works on Lambda") was marked complete, but the spike was a hello-world cold-start test. Warm-invoke behaviour was never exercised. Unit tests for OAuth + tools_read mock the storage layer and never go through the Mangum lifespan path either — the bug was structurally invisible to both spike and CI. **Lesson for future spikes: any "X works on Lambda" verification must include at minimum two sequential requests to confirm warm-invoke survives.**

**Alternatives considered:**

| Option | Effort | Risk | Verdict |
|---|---|---|---|
| **A. AWS Lambda Web Adapter (LWA)** — run uvicorn inside the Lambda container, LWA proxies HTTP. Lifespan runs once per cold start, like a real ASGI server. | medium (~1 day, Docker-based Lambda + CDK rewrite) | low — AWS-blessed pattern for ASGI-on-Lambda | **CHOSEN** |
| B. Move MCP off Lambda to ECS Fargate / App Runner | large (~2-3 days, new infra + deploy pipeline) | medium — net-new ops surface | Right answer if sustained traffic is anticipated; over-spec for the read-only v1 launch |
| C. Custom Mangum subclass that resets session-manager state per request | small (~2-3 hrs) but ongoing maintenance | high — depends on MCP SDK internals, breaks on every SDK bump | Rejected as a maintenance burden |
| D. Provisioned concurrency = 1 + accept ~1-RPS limit | trivial | n/a | Doesn't fix anything — each container still serves exactly 1 request before becoming broken |

**Bug X (systemic, separate from Bug B):** `MCPConstruct` creates an empty signing-key secret without populating it. Lambda deploys "successfully" then crashes silently at first invocation. This is a fail-late pattern that contradicts CLAUDE.md's fail-fast standards. Fix during PR 2.5: either generate the key pair at CDK synth via a custom resource and populate the secret, or fail synth if the secret is empty for non-development environments.

**Migration scope:**
- Update `infrastructure/stacks/mcp_construct.py` to use Docker-based Lambda + LWA layer.
- Replace `backend/src/mcp/mcp_handler.py` Lambda entry point with a uvicorn boot script (`uvicorn.run(_app, host="0.0.0.0", port=...)`). Keep the FastMCP setup, OAuth provider wiring, and tool registrations unchanged.
- Add `backend/Dockerfile.mcp`.
- Add an integration test that calls the OAuth metadata endpoint **twice in succession** against a locally-running container — this is the test that would have caught Bug B in the first place.

**Latent bugs uncovered during Phase A but not addressed by this decision (carried to PR 2.6):**
- **Bug C** — Default `MCP_ISSUER_URL` is `https://mcp.{stage}.sc0red-services.sc0red.com`. That DNS doesn't exist. OAuth clients receive metadata pointing at a phantom domain.
- **Bug D** — `CONSENT_BASE_URL` env var on staging Lambda points at the **development** Amplify URL. Real customers using staging MCP would be sent to the dev consent screen.
- **Bug E** — Read-tool formatters were written 49 days ago and predate the Phase-14 schema additions. `get_opportunities` misses `investment_value_usd` and `roi_estimate_pct` (the matrix axes); `get_ebitda_tree` misses `confidence_*` + `linked_opportunity_indices`; `get_value_chain` misses `opportunity_indices`.
- **Bug F** — No `get_strategy_map` tool exists. Strategy map is invisible to AI assistant users.

### 9. MCP tool naming convention (placeholder — to decide during PR 2.6)

**Status:** Open question, deferred to PR 2.6.

**Question:** Should MCP tool names use a brand prefix (`sc0red_list_analyses`), stay bare (`list_analyses`), or keep the internal codename (`janus_list_analyses`)?

**Context:**
- Tool names appear in the AI assistant UI when users invoke them — they are customer-visible per CLAUDE.md's naming rule.
- Self-namespacing (prefix) is safer once users connect multiple MCP servers (`list_analyses` collides across servers).
- The brand we want users to recognise in Claude Desktop is "sc0red Services", not "janus".

**Lean (not yet decided):** `sc0red_` prefix across all tools + prompts. Read tools today are bare; prompts in the proposal say `janus_*`. The convention should be picked and applied once, before any external launch.

## Risks / Trade-offs

- **MCP SDK maturity**: The Python SDK is evolving. `OAuthAuthorizationServerProvider` interface may change. → Mitigation: Pin SDK version, test thoroughly, update incrementally.
- **OAuth spec evolution**: MCP OAuth added Protected Resource Metadata (RFC 9728) recently. More additions may come. → Mitigation: Use SDK-managed endpoints so spec updates come via SDK upgrades.
- **Single-table OAuth data**: May get noisy as OAuth records grow. → Mitigation: TTL on codes (10 min) and tokens (1h/30d) keeps the table clean. Can extract later.
- **Token-to-backend auth bridging**: MCP server has OAuth tokens but backend expects Cognito JWTs. → Mitigation: MCP server calls backend API with a service-level auth mechanism (shared secret or internal token). Design this carefully in PR 2.
- **Tool description quality**: AI agents select tools based on descriptions. Poor descriptions → wrong tool calls. → Mitigation: Iterate descriptions with real Claude Desktop testing. Treat descriptions as product copy.
- **Mangum + FastMCP compatibility**: Need to verify the ASGI app from FastMCP's `streamable_http_app()` works correctly through Mangum on Lambda. → Mitigation: Spike this in PR 2 before building tools.

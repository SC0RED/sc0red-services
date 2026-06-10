# ✅ PR 2.5 COMPLETE — end-to-end OAuth round-trip VALIDATED 2026-06-08

PR 1 + PR 2 shipped (Apr 14, 2026). A Phase A tactical scout (Jun 3) uncovered a chain of blocking bugs (B → C/D → G → I → J → K → L); **all are now fixed, deployed to staging, and the mcp-inspector OAuth round-trip completes end-to-end** (validated 2026-06-08 — see below). The next work is PR 2.6 (polish: read-tool drift, missing tools, rebrand, minimal UI).

## ✅ End-to-end validation (2026-06-08)

mcp-inspector v0.22.0 → staging MCP Function URL `…/mcp`, **Connection Type = Direct**, Transport = Streamable HTTP. Full chain succeeds: discovery → DCR → `/authorize` → consent "Allow Access" → callback → token exchange → **authenticated `/mcp` connection established** → MCP protocol calls work (`resources/list` returned `{resourceTemplates: []}`; tools/prompts/resources tabs all live). Inspector shows **Connected** to "sc0red Services" (server v1.27.2).

**⚠️ Inspector gotcha (operational note):** use **Connection Type = "Direct"**, NOT "Via Proxy". In Via-Proxy mode the inspector's local Express proxy (`:6277`) misrouted the DCR `POST /register` to itself and returned an Express `Cannot POST /register` HTML 404 (`ServerError: HTTP 404: Invalid OAuth error response`). Direct mode sends OAuth + transport straight to the Lambda; our CORS (#386) makes that work browser-side. Our `/register` was always correct (advertised endpoint = the Lambda; returns JSON) — the misroute was entirely inspector-side.

## Where we left off (updated 2026-06-08)

- ✅ PR 1 (OAuth Provider + Infrastructure) — shipped
- ✅ PR 2 (Read Tools, 12 tools) — shipped
- ✅ Phase A tactical scout — complete.
- ✅ **PR 2.5 (runtime fix) — CORE DONE + VALIDATED on staging.** The hard bug is fixed:
  - Bug B (run-once 502) → fixed via AWS Lambda Web Adapter (#379). Warm-invoke verified: 3 consecutive 200s (was 200→502→502).
  - Bug C (OAuth issuer = dead DNS) → fixed via SSM indirection (#382, after #380's circular-dep attempt was reverted in #381). Verified: metadata issuer = the real Function URL.
  - DCR (`POST /register` 201) + `GET /authorize` 302 → working. Server boots, survives warm invokes, serves OAuth metadata.
- ✅ **Bug G FIXED (#383)** — NextAuth now refreshes the Cognito idToken (refresh-token rotation in the jwt callback; tracked in change `fix-cognito-token-refresh`). The "Allow Access → Token expired/500" failure is gone.
- ✅ **Bug I FIXED (#384)** — once the token passed through, "Allow Access" hit a 502: the frontend `/api/oauth/approve` route double-encoded the body (`JSON.stringify` on top of `backendFetch`'s own stringify), so the backend's `json.loads(event["body"])` got a string and `handle_oauth_approve` threw `AttributeError: 'str' object has no attribute 'get'`. Fixed by passing the object. Inspector now gets through consent → callback → token exchange.
- ✅ **Bug J FIXED (#386, deployed)** — `/mcp` transport had no CORS, so the browser inspector's authed preflight 401'd with no `Access-Control-Allow-Origin` → `TypeError: Failed to fetch`. Fixed with an outermost `CORSMiddleware` (`src/mcp/cors.py`). Verified live post-deploy: `OPTIONS /mcp` → 200 + ACAO + `authorization` allowed; methods `GET, POST, DELETE, OPTIONS`.
- ✅ **Bug K FIXED (#387, deployed)** — `/token` 500: our `Stored*` dataclasses omitted `expires_at`, which the SDK token handler (`token.py:145`, no None guard) + bearer-auth backend read → `AttributeError`. Added + populated `expires_at` on all three (auth code / refresh / access) from the stored `ttl` / JWT `exp`. Token exchange now succeeds (inspector got a token and reached the `/mcp` connection).
- ✅ **Bug L FIXED (#388, deployed + validated)** — `/mcp` POST → 421 "Invalid Host header". FastMCP's default bind host is `127.0.0.1`, so with `transport_security` unset it auto-enabled DNS-rebinding protection (`allowed_hosts=["127.0.0.1:*","localhost:*","[::1]:*"]`); under LWA the Function URL Host failed that localhost list → 421 (behind `RequireAuthMiddleware`, so only surfaced once tokens worked). Disabled it via `transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False)` — inapplicable/redundant for a public TLS endpoint gated by an OAuth bearer token. Post-deploy round-trip in Direct mode succeeds.
- ✅ **Bug H FIXED — RFC 9728 path-suffixed metadata.** Root cause: `resource_server_url` was the Function URL root (path `/`), which the SDK treats as empty → served + advertised the BARE `/.well-known/oauth-protected-resource` and 404'd the path-suffixed `…/mcp` that spec-strict clients probe. Fixed by pointing `resource_server_url` at the actual protected resource (`…/mcp`): the SDK now registers the route at `/.well-known/oauth-protected-resource/mcp`, `metadata.resource = …/mcp`, and the `WWW-Authenticate` header points there. Issuer (authorization server) stays the root. Verified the URL derivation locally; verify post-deploy via curl.
- 🛑 PR 2.6 (Quick wins polish — drift fix + missing tools + rebrand + minimal UI) — **now unblocked**; this is the next chunk of work.
- 🛑 Original PR 3–7 — downstream.

## Resume here — next session (PR 2.6)

The OAuth + transport chain is DONE and validated; PR 2.5 is complete. Next is **PR 2.6 (polish)** — none of it blocks anything else, do in any order:

1. **Bug E — read-tool output drift.** Reconcile the read tools' output shape with the current API/model. (Independent; was flagged in Phase A. See the "Read-tool drift fix (Bug E)" section below for specifics.)
2. **Bug F — missing tools.** Add `get_strategy_map` and `list_scans` (see "Missing tools (Bug F + proposal gap)" section).
3. **Tool-name rebrand.** Align tool names with the sc0red Services brand.
4. **Minimal Connected Apps UI.** Surface MCP/OAuth connected apps in the frontend.
5. ✅ **Bug H — RFC 9728 path-suffixed metadata** — DONE (set `resource_server_url` to `…/mcp`).
6. **RFC 8707 resource indicators — DEFERRED (decision 2026-06-09, won't-do for now).** Investigated and consciously deferred: (a) the installed SDK doesn't enforce `resource` (the token handler parses it into the request model but never validates it against the auth code or passes it to issuance), so nothing is broken without it; (b) full threading needs FRONTEND work — `resource` arrives at `authorize()` but the consent flow bounces through the frontend consent page before the auth code is created, so the value is lost unless the consent page echoes it back; (c) the security substance (audience-restricted `aud`) is ~redundant here — RFC 8707 prevents token replay when one AS serves MULTIPLE resource servers, but we are both the issuer AND the only resource server, so the existing `iss` check already scopes tokens. Hard-validating `aud` would add redeploy risk to the validated `/mcp` flow for ~no gain. Revisit only if we add a second resource server or a client demands strict RFC 8707.

### Other deferred / known follow-ups
- ✅ **Bug X (signing key) — FIXED.** A CDK custom resource (`SigningKeyGenerator` Lambda → `signing_key_provider.handle`, wired via `custom_resources.Provider` in `MCPConstruct._add_signing_key_generator`) now generates the RSA keypair into the secret at deploy time, so each environment self-populates — no manual `put-secret-value`. **Idempotent**: it no-ops when the secret already holds a keypair, so staging's hand-populated key is preserved and redeploys never rotate (rotation would invalidate live tokens). This unblocks promotion to testing/production. Handler is 100%-tested; CDK wiring validated via isolated synth (custom resource + provider + read/write grants).
- **Promote beyond staging.** The MCP Lambda + all fixes (#379/#382/#383/#384/#386/#387/#388) are live on **staging (development) / us-east-1** only. Not yet promoted to testing/production (testing+prod use us-east-2). Promote via the development → testing → production PR flow when ready.
- **Validation health-check.** Quick re-run of the inspector round-trip after any future MCP Lambda deploy (Direct mode) is the canonical smoke test.

## State of staging environment (live, in AWS)

- **Account:** the sc0red-services AWS account (NOT 148256362911 — that's a different project's dev account).
- **Region:** `us-east-1`.
- **Lambda:** `sc0red-services-mcp-staging`. Active, last modified ~mid-May 2026 (rename-driven redeploy).
- **Function URL:** `https://wme4eulc26biz3ttnayifd6zsu0kinpn.lambda-url.us-east-1.on.aws/` — internal only. As of #382 it survives warm invocations (3× 200) and serves OAuth metadata with issuer = the Function URL.
- **Signing-key secret:** `sc0red-services-mcp-signing-key-staging` populated 2026-06-03 with an RSA-2048 keypair. The CDK construct still creates it empty (Bug X — partial fix shipped, full auto-gen deferred).
- **Issuer URL:** resolved at cold start from SSM param `/sc0red-services/mcp/staging/issuer-url` (= the Function URL). #382.
- **Status overall:** MCP runtime HEALTHY (run-once + issuer fixed). End-to-end OAuth still blocked by Bug G (frontend idToken refresh). Not yet promoted beyond staging.

## Bugs uncovered during Phase A — by status

| # | Bug | Status | Where |
|---|---|---|---|
| A | Signing-key secret empty → import-time `KeyError: 'private_key'` | ✅ Fixed operationally in staging (2026-06-03) | `backend/src/mcp/mcp_handler.py:38` |
| B | Mangum + `StreamableHTTPSessionManager` incompatibility — lifespan startup re-fires per invocation, run-once guard trips | ✅ Fixed via LWA (#379) | `backend/src/mcp/mcp_handler.py:102` |
| C | Default `MCP_ISSUER_URL` points at non-existent DNS `mcp.{stage}.sc0red-services.sc0red.com` | ✅ Fixed via SSM indirection (#382) | `backend/src/mcp/mcp_handler.py:50` |
| D | `CONSENT_BASE_URL` env var on staging Lambda points at the *development* Amplify URL | ⚠ Latent — fix in PR 2.6 | Lambda env var configuration |
| E | Read-tool formatters miss new Opportunity / EBITDA / value-chain fields shipped by `redesign-analysis-visuals` | ⚠ Latent — fix in PR 2.6 | `backend/src/mcp/tools_read.py` |
| F | No `get_strategy_map` tool exists; strategy map invisible to AI assistant users | ⚠ Latent — fix in PR 2.6 | `backend/src/mcp/tools_read.py` |
| X | `MCPConstruct` creates the signing-key secret empty; deploy succeeds but Lambda crashes silently at first invocation. | ✅ Fixed — fail-fast added (#379) + CDK custom resource auto-generates the keypair at deploy time (idempotent; preserves a hand-populated key). | `infrastructure/stacks/mcp_construct.py`, `backend/src/mcp/signing_key_provider.py` |
| G | **NextAuth does not refresh the Cognito idToken.** The server-read `getToken().idToken` goes stale after the 1h Cognito idToken expiry, so `backendFetch` (incl. the OAuth consent `/api/oauth/approve`) sends an expired token → API auth middleware returns `401 {"error":"Token expired"}`. **Reproduces right after re-login** (re-login may not rotate the JWT-stored idToken). Blocks the mcp-inspector OAuth round-trip AND any long-lived authenticated frontend session. | ✅ Fixed (#383) — refresh-token rotation in the NextAuth jwt callback. | `frontend/src/lib/api/serverToken.ts` (getBackendToken / idToken) + `frontend/src/lib/auth/authOptions.ts` |
| H | MCP server doesn't serve RFC 9728 Protected Resource Metadata — `GET /.well-known/oauth-protected-resource/mcp → 404`. mcp-inspector fell back fine, but stricter clients may require it. | ✅ Fixed — `resource_server_url` set to `…/mcp` so the SDK registers the path-suffixed route | `backend/src/mcp/mcp_handler.py` |
| I | Frontend `/api/oauth/approve` double-encoded the consent body → backend `AttributeError` → 502 | ✅ Fixed (#384) | `frontend/src/app/api/oauth/approve/route.ts` |
| J | `/mcp` transport had no CORS → browser preflight blocked (`Failed to fetch`) | ✅ Fixed (#386) | `backend/src/mcp/cors.py` |
| K | `Stored*` OAuth models missing `expires_at` → SDK token handler `AttributeError` → `/token` 500 | ✅ Fixed (#387) | `backend/src/mcp/oauth_provider.py` |
| L | Auto-enabled DNS-rebinding protection rejected the Function-URL Host → `/mcp` 421 | ✅ Fixed (#388) | `backend/src/mcp/mcp_handler.py` |

**Resolved: A (partial), B (#379), C (#382), G (#383), I (#384), J (#386), K (#387), L (#388), E (#399), F (#400), H (#401). D: re-assessed as non-bug. End-to-end OAuth round-trip VALIDATED 2026-06-08. Bug X (signing-key auto-gen) FIXED. PR 2.6 remaining: tool-name rebrand (recommendation: keep current names), Connected Apps UI. Promotion to testing/production now unblocked (Bug X cleared the per-env signing-key blocker). Deferred: RFC 8707 resource indicators (redundant for a single-resource server — see item 6). Use mcp-inspector Direct mode.**

## To re-establish context when resuming

```bash
# 1. Make sure AWS CLI points at the sc0red-services account:
export AWS_PROFILE=<your sc0red-services profile>
aws sts get-caller-identity   # confirm right account

# 2. Verify staging Lambda is still in the broken-but-deployed state described above:
aws logs tail /aws/lambda/sc0red-services-mcp-staging --region us-east-1 \
  --since 1h --format short 2>&1 | tail -50
# Expect: LifespanFailure / "run() can only be called once" stack traces.
# If you see "KeyError: 'private_key'", someone rotated the secret without
# repopulating — re-run the secret-population steps from the chat transcript
# (or below).

# 3. Re-read the discovery + decision:
#    openspec/changes/janus-mcp-server/design.md   → Decision 8
#    openspec/changes/janus-mcp-server/tasks.md    → this section + PR 2.5

# 4. Re-populate the signing-key secret if it's been rotated to empty
#    (only needed if Step 2 shows KeyError again):
cd /tmp
openssl genrsa -out mcp_staging_private.pem 2048
openssl rsa -in mcp_staging_private.pem -pubout -out mcp_staging_public.pem
python3 << 'PY'
import json
priv = open('/tmp/mcp_staging_private.pem').read()
pub  = open('/tmp/mcp_staging_public.pem').read()
with open('/tmp/mcp_secret.json', 'w') as f:
    json.dump({'private_key': priv, 'public_key': pub}, f)
PY
aws secretsmanager put-secret-value \
  --secret-id sc0red-services-mcp-signing-key-staging \
  --secret-string file:///tmp/mcp_secret.json --region us-east-1
rm -f /tmp/mcp_staging_*.pem /tmp/mcp_secret.json
```

## Resume here — the next three PRs in order

```
PR 2.5  (NEW, blocking)  — Runtime infrastructure fix: Mangum → AWS Lambda Web Adapter
                            Per design.md Decision 8. Also fixes Bug X (empty secret).
PR 2.6  (NEW, blocked)   — Quick wins polish: drift fix + get_strategy_map + rebrand
                            + minimal Connected Apps UI. Ships v1 read-only MCP.
PR 3–7                   — Original plan resumes. Write tools → destructive tools
                            → resources → prompts → full Connected Apps UI + launch.
```

---

## PR 2.5: Fix the run-once crash — cheap stateless config first, LWA only if needed (NEW)

Source of truth: `design.md` Decision 8 (revised 2026-06-03 — cheap config fix before any rewrite).

### Step 1 — cheap config fix (ATTEMPTED — FAILED on staging 2026-06-04)
- [x] 2.5.1 `backend/src/mcp/mcp_handler.py` — added `stateless_http=True, json_response=True`. (PR #378, merged.)
- [x] 2.5.2 Lint + typecheck passed.
- [x] 2.5.3 Deployed to staging via the development backend-deploy workflow. **RESULT: FAILED.** 1st request 200, 2nd + 3rd request **502** with the same `StreamableHTTPSessionManager .run() can only be called once` trace (via `mangum/adapter.py` lifespan). `stateless_http` changes session *handling* but `.run()` still lives in the ASGI lifespan that Mangum re-invokes per request → guard still trips.
- [x] 2.5.4 Inspector round-trip — **VALIDATED 2026-06-08.** Full OAuth + transport chain completes (mcp-inspector v0.22.0, Direct mode): discovery → DCR → authorize → consent → token → authed `/mcp` connect → `resources/list` returns. Required Bugs G/I/J/K/L all fixed + deployed.
- [x] 2.5.5 **Decision gate: Step 1 failed → proceed to Step 2 (LWA).**

### Step 1 — ship
- [x] 2.5.6 Shipped as PR #378 (merged to development; the merge is what deployed it to staging for the test). The stateless flags are KEPT — still correct posture under LWA, just insufficient alone.

---

### Step 2 — LWA via Lambda layer (IN PROGRESS — branch `fix/mcp-lambda-web-adapter`)
Chosen the **LWA-layer-on-zip** approach (Option 2a), not the full Docker `DockerImageFunction` rewrite — lighter, keeps the existing `pip install . -t /asset-output` bundling.
- [~] 2.5.7 Local Docker spike — skipped (can't iterate Docker/AWS from the dev sandbox; validation is the staging deploy). Will pivot to Docker (2b) only if the layer approach fails on staging.
- [x] 2.5.8 `infrastructure/stacks/mcp_construct.py` — added the architecture-aware LWA layer (`LambdaAdapterLayerX86`/`Arm64` v28), `handler="run_mcp.sh"`, env vars `AWS_LAMBDA_EXEC_WRAPPER=/opt/bootstrap`, `AWS_LWA_PORT=8080`, `AWS_LWA_READINESS_CHECK_PATH=/health`. (Layer approach — no `DockerImageFunction`.)
- [x] 2.5.9 `backend/run_mcp.sh` (new, +x) execs `uvicorn src.mcp.mcp_handler:app`. `infrastructure/stacks/lambda_factory.py` bundling copies it to the package root + chmods it (`pip install .` doesn't include loose files).
- [x] 2.5.10 `mcp_handler.py` — removed Mangum `handle_event`, exposed `app = mcp.streamable_http_app()`, added a `/health` `custom_route` for the LWA readiness probe.
- [~] 2.5.11 Local twice-in-succession test — NOT added: the bug only manifests under Mangum's per-invocation lifespan re-run; a local ASGI test (TestClient/uvicorn) runs lifespan once and can't reproduce it. The meaningful test is the staging warm-invoke (2.5.12).
- [x] 2.5.12 Deploy to staging — **LWA VALIDATED 2026-06-04.** Warm-invoke test passed: 3 consecutive requests all returned HTTP 200 (was 200→502→502 under Mangum). Server boots, survives warm invocations, and serves real OAuth discovery metadata. The run-once bug (Bug B) is fixed. (Inspector round-trip still pending Bug C fix — see below.)
- [x] 2.5.13 Architecture-reviewer on the diff — 0 CRITICAL, safe to commit. Addressed before PR: removed dead `mangum` dep (pyproject + uv.lock), fixed the stale "via Mangum" docstring in `mcp_construct.py`. **Deferred (with note):** the shared-bundling separation-of-concerns — `build_bundling_options()` copies `run_mcp.sh` into all 3 Lambda packages. Kept as a documented temporary coupling until staging validates the LWA-via-layer approach; if validated, move the copy to an MCP-specific bundling variant before merge; if it fails and we pivot to Docker (2b), the bundling is reworked anyway.

### Deferred to follow-up (orthogonal to the run-once fix)
- [x] 2.5.14 Bug X — **FULLY FIXED.** Fail-fast error in `_load_signing_keys` (#379) + a CDK custom resource (`SigningKeyGenerator`) that auto-generates the RSA keypair into the secret at deploy time. Idempotent (no-op if already populated → preserves a hand-populated key, never rotates on redeploy). Unblocks testing/production promotion.
- [x] 2.5.15 Bug C — **FIXED via SSM indirection** (chosen over custom domain). First attempt (#380, `add_environment("MCP_ISSUER_URL", function_url.url)`) failed at deploy with a CFN circular dependency (Lambda env → FunctionUrl → Lambda); reverted in #381. Durable fix (`fix/mcp-issuer-url-via-ssm`): `MCPConstruct` stores `function_url.url` in an SSM parameter (`/sc0red-services/mcp/{env}/issuer-url`); the Lambda's env carries only the static parameter NAME (a literal string — no resource reference, no cycle); the handler reads the parameter at cold start to set the issuer. IAM grant uses a **constructed string ARN** (not `param.grant_read`) so the execution role doesn't reference the SSM resource either (that would re-introduce role → param → FunctionUrl → Lambda). Dependency graph verified acyclic: Lambda is a leaf; FunctionUrl → Lambda; SSMParam → FunctionUrl; role policy → string ARN. Validation = staging deploy (synth must NOT report a circular dependency) + the mcp-inspector OAuth round-trip.
- [~] 2.5.16 Bug D — **re-assessed: not a functional bug.** `CONSENT_BASE_URL` IS set by the construct to the environment's frontend (dev Amplify URL for staging). Since the CDK `staging` env IS the `development` git branch / `dev.services.sc0red.ai` frontend, the consent redirect already points at the correct environment. The only imperfection is amplifyapp-URL vs custom-domain — the same cosmetic call accepted for `FRONTEND_BASE_URL` in the rename migration. The bogus handler *default* (never reached when deployed) was cleaned up alongside Bug C. No further action.

## PR 2.6: Quick wins polish — drift fix + missing tool + rebrand + minimal UI (NEW)

Pre-requisite: PR 2.5 merged and staging smoke-tested healthy across warm invokes.

### Read-tool drift fix (Bug E)
- [x] 2.6.1 `get_opportunities` now surfaces the full Opportunity contract — `strategic_category`, `timeline`, `investment_range` + `investment_value_usd`, `roi_estimate` + `roi_estimate_pct`, `implementation_steps` (extracted to `_format_opportunities` in `_tools_read_helpers.py` to stay under the 400-line limit).
- [x] 2.6.2 `get_ebitda_tree` resolves each node's `linked_opportunity_indices` to opportunity titles ("addresses: …"). (`confidence_level`/`confidence_basis` were already surfaced for the revenue node by the provenance work.)
- [x] 2.6.3 `get_value_chain` — **fixed the `name`→`label` bug** (every step had rendered as "?"; the test fixtures wrongly used `name` too, masking it), and now surfaces `risk_categories`, `opportunity_indices` (resolved to titles), per-step `confidence_level`/`confidence_basis`, and the chain-level `provenance_basis`.

### Missing tools (Bug F + proposal gap)
- [x] 2.6.4 Added `get_strategy_map(analysis_id)` — renders the BSC as sectioned Markdown (vision/mission/value-prop/priorities, then the four perspectives with per-objective title + first-sentence definition + linked opportunity titles, plus core values). Sectioned layout chosen over a cramped 4-row table — reads better for an LLM client. (`_format_strategy_map` in `_tools_read_helpers.py`.)
- [x] 2.6.5 Added `list_scans` — lists the org's scans (id, status, type, progress, created_at) via `scan_repo.find_recent_by_org`. Read-tool count is now 13 (matches the proposal).

### Rebrand for customer visibility
- [ ] 2.6.6 Decide naming convention per `design.md` Decision 9 (placeholder). Capture the decision before any rename sweep.
- [ ] 2.6.7 Apply the chosen convention across all tool registrations + planned prompt names. Update tests.

### Minimal Connected Apps UI (PR 7 subset)
- [~] 2.6.8 **Backend done** — `GET /api/connected-apps` (list the user's connected AI assistants — per-user OAuth consents, client name denormalized on the consent record) + `DELETE /api/connected-apps/{client_id}` (revoke consent). Per-user scoped (no IDOR). Revoke = consent revoke; active tokens lapse within their 1h TTL (immediate token revocation deferred to PR 7). **Frontend settings page is the remaining half** (separate PR).
- [ ] 2.6.9 Short "Connect to AI assistants" doc: Function URL (or custom domain when added) + the OAuth flow. (Ships with the frontend PR.)

### Tests + ship
- [~] 2.6.10 Unit tests for the new tools landed with 2.6.4/2.6.5 (get_strategy_map: perspectives/objectives, first-sentence trim, index→title resolution, no-map, cross-org; list_scans: render + empty). Formatter tests for the rebrand/UI items follow with their tasks.
- [ ] 2.6.11 Frontend gates: `npm run lint`, `npx tsc --noEmit`, `npm test`.
- [ ] 2.6.12 Architecture-reviewer pass.
- [ ] 2.6.13 Conventional commit + PR.
- [ ] 2.6.14 Ship to staging, eyeball end-to-end via mcp-inspector against staging URL, then promote to production. **v1 launch.**

---

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

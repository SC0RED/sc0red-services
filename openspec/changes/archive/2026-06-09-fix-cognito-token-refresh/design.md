# Design — Cognito idToken refresh

## Context

NextAuth (CredentialsProvider + JWT strategy) is the web session layer. Login calls `signInWithCognito` (`cognitoClient.ts`), which authenticates via Cognito `USER_PASSWORD_AUTH` and returns `{ idToken, accessToken, refreshToken }`. The Python API validates the **idToken** (RS256 against the Cognito JWKS) on every request, checking `exp`.

Current data flow and the gap:

```
login → authorize() → returns { …, idToken }            ← refreshToken DROPPED
      → jwt callback: token.idToken = user.idToken       ← only when `user` present (login)
      → session JWT: maxAge 8h                            ← but idToken exp = 1h
      ...1h later...
getBackendToken() → token.idToken (now EXPIRED) → API → 401 "Token expired"
```

`signInWithCognito` already returns the `refreshToken`; it is simply discarded in `authorize()`. Cognito refresh tokens are valid 30 days (pool default) and the app client is a public SPA client (no secret) with `REFRESH_TOKEN_AUTH` available.

## Goals / Non-Goals

**Goals:**
- A valid (unexpired) Cognito idToken is always available to `getBackendToken()` / `backendFetch`, refreshed transparently before/at expiry.
- No change to backend, API auth middleware, or `backendFetch` call sites.
- Clean fallback to re-login when the refresh token itself is expired/revoked.

**Non-Goals:**
- Changing the auth model (still Cognito idToken → RS256 at the API).
- Client-side (`useSession`) token exposure — the idToken stays server-side only.
- The MCP-side follow-ups (read-tool drift, `get_strategy_map`, rebrand, RFC 9728) — tracked in `janus-mcp-server`.

## Decisions

### 1. Refresh-token rotation in the NextAuth `jwt` callback (Option A)

**Decision:** Capture the refresh token at login and refresh the idToken in the `jwt` callback when it is at/near expiry.

**Alternatives considered:**

| Option | Scope | Why (not) chosen |
|---|---|---|
| **A — refresh-token rotation in `jwt` callback** | whole app | **Chosen.** Standard NextAuth pattern; fixes the app-wide hourly forced-relogin AND unblocks MCP consent; refresh token already returned by `signInWithCognito`. |
| B — consent page sends a client-side auto-refreshed idToken to `/api/oauth/approve` | MCP OAuth only | Unblocks MCP fast but leaves every other server-side `backendFetch` still failing after 1h. Treats the symptom, not the cause. |
| C — set NextAuth `maxAge` to ~1h | whole app | "Fixes" by logging users out every hour by design — negative UX, not a real fix. |

### 2. Refresh via Cognito `InitiateAuth: REFRESH_TOKEN_AUTH` (server-side)

**Decision:** Perform the refresh in the server-side `jwt` callback with a direct Cognito `InitiateAuth` call (`AuthFlow=REFRESH_TOKEN_AUTH`, `AuthParameters={REFRESH_TOKEN: <token>}`, the public `ClientId`). Returns a fresh `IdToken` (+ `AccessToken`); the refresh token is unchanged (no rotation configured), so the stored refresh token remains valid for its 30-day life.

Prefer this over `amazon-cognito-identity-js` `cognitoUser.refreshSession()` because the browser SDK assumes a browser storage/runtime; the `jwt` callback runs in Node. Implementation may use `@aws-sdk/client-cognito-identity-provider` (`InitiateAuthCommand`) or a plain `fetch` POST to `https://cognito-idp.{region}.amazonaws.com/` with header `X-Amz-Target: AWSCognitoIdentityProviderService.InitiateAuth` (no new dependency) — implementer picks the lighter path; both are unauthenticated public-client calls.

### 3. JWT token shape + refresh trigger

The NextAuth JWT carries:
- `idToken` — current Cognito idToken
- `refreshToken` — Cognito refresh token (captured at login)
- `idTokenExpiresAt` — epoch seconds, derived from the idToken `exp` (decoded at login + on each refresh)
- `error?` — set to `"RefreshAccessTokenError"` when a refresh fails

Trigger: in the `jwt` callback, if `now >= idTokenExpiresAt - SKEW` (e.g. SKEW = 60s), refresh. On success, replace `idToken` + `idTokenExpiresAt`, clear `error`. On failure, set `error` and leave the (expired) token; `getBackendToken()` returning a token with `error` set → treat as unauthenticated so the existing `error.tsx` / 401 path forces a clean re-login.

### 4. `getBackendToken()` stays the contract boundary

`getBackendToken()` continues to return `token.idToken`. Because the `jwt` callback refreshes before that read, the returned token is fresh. If `token.error === "RefreshAccessTokenError"`, return `null` (→ `backendFetch` throws 401 → existing re-login path). No `backendFetch` call site changes.

## Risks / Trade-offs

- **Refresh-token expiry (30d) / revocation.** A user idle > 30 days, or whose refresh token was revoked, gets a failed refresh → forced re-login. Handled via the `error` flag; this is the correct terminal behavior.
- **Concurrent refresh / thundering herd.** Multiple in-flight server requests near expiry may each trigger a refresh. Cognito tolerates repeated `REFRESH_TOKEN_AUTH` with the same refresh token (returns fresh idTokens), so this is benign; no distributed lock needed at current volumes. Note it in the spec so a future high-traffic surface can add single-flight if needed.
- **Migration-Lambda interaction.** The `USER_PASSWORD_AUTH` login path triggers the migration Lambda for legacy users; `REFRESH_TOKEN_AUTH` does not (the user already exists in the pool post-first-login). No interaction.
- **Clock skew.** The SKEW window (60s) absorbs minor skew between the Node runtime and Cognito; the API's own JWT validation has its own leeway.
- **idToken decode.** `idTokenExpiresAt` comes from base64url-decoding the idToken payload's `exp` (the codebase already does unverified payload decode in `authOptions.decodeIdTokenPayload`) — reuse that, no verification needed (the API verifies; the frontend only needs `exp` for scheduling).

## Validation Plan

1. Unit: `jwt` callback refreshes when `idTokenExpiresAt` is past; passes through when fresh; sets `error` on refresh failure. Mock the Cognito refresh call.
2. Unit: `getBackendToken()` returns null when `error` is set.
3. Manual (staging): log in, wait > 1h (or force a short expiry), load an authenticated page → no forced logout (refresh happened). Then the decisive one: **mcp-inspector OAuth round-trip completes** — consent "Allow Access" → `/api/oauth/approve` succeeds → code → token → `list_analyses` returns. That closes `janus-mcp-server`'s end-to-end gate.

# Tasks — Fix Cognito idToken refresh

## 1. Refresh helper (cognitoClient)

- [x] 1.1 Add `refreshCognitoSession(refreshToken: string): Promise<{ idToken: string; accessToken: string }>` to `frontend/src/lib/auth/cognitoClient.ts` using Cognito `InitiateAuth` with `AuthFlow=REFRESH_TOKEN_AUTH`, `AuthParameters={ REFRESH_TOKEN: refreshToken }`, and the public `ClientId`. Server-safe (no browser storage). Use `@aws-sdk/client-cognito-identity-provider` if already a dep, else a plain `fetch` POST to `https://cognito-idp.{NEXT_PUBLIC_COGNITO_REGION}.amazonaws.com/` with `X-Amz-Target: AWSCognitoIdentityProviderService.InitiateAuth`. Throw on failure.

## 2. Capture refresh token + expiry at login

- [x] 2.1 `authOptions.authorize()` — include `refreshToken: result.refreshToken` and `idTokenExpiresAt` (from `decodeIdTokenPayload(result.idToken).exp`) on the returned user object.
- [x] 2.2 `frontend/src/types/next-auth.d.ts` — extend the JWT (and `User`) types with `refreshToken?: string`, `idTokenExpiresAt?: number`, `error?: string`.

## 3. Refresh in the jwt callback

- [x] 3.1 `authOptions.callbacks.jwt` — on login (`user` present) store `idToken`, `refreshToken`, `idTokenExpiresAt`. On subsequent calls, if `Date.now()/1000 >= idTokenExpiresAt - 60`, call `refreshCognitoSession(token.refreshToken)`, update `idToken` + `idTokenExpiresAt`, clear `error`. On refresh failure, set `token.error = "RefreshAccessTokenError"` and return the token unchanged.
- [x] 3.2 Keep the idToken server-side only (do NOT expose on `session` via the `session` callback) — unchanged from today.

## 4. getBackendToken fallback

- [x] 4.1 `frontend/src/lib/api/serverToken.ts` — `getBackendToken()` returns `null` when `token.error === "RefreshAccessTokenError"` (so `backendFetch` throws 401 → existing `error.tsx` re-login path). Otherwise unchanged.

## 5. Tests

- [x] 5.1 Unit: jwt callback — (a) fresh token passes through untouched, (b) expired token triggers refresh + updates idToken/expiry, (c) refresh failure sets `error`. Mock `refreshCognitoSession`.
- [x] 5.2 Unit: `getBackendToken()` returns null when `error` set; returns the (refreshed) idToken otherwise.
- [x] 5.3 Unit: `refreshCognitoSession` — success maps the Cognito response to `{ idToken, accessToken }`; failure throws.

## 6. Quality gates + ship

- [x] 6.1 `cd frontend && npm run lint` clean; `npx tsc --noEmit` clean; `npm test` all green.
- [x] 6.2 Conventional commit + PR (branch off development, base development). Wait for CI + user merge approval. → PR #383, merged 2026-06-05.

## 7. Staging validation (the end-to-end gate)

- [x] 7.1 idToken refresh validated by implication — the consent "Allow Access" step (which goes through `getToken().idToken` → `backendFetch`) was the exact thing failing with "Token expired" before #383; the round-trip now completes that step cleanly (2026-06-08), confirming the refresh path works in practice. (Dedicated "idle past 1h → no forced logout" UI check not separately run; the mechanism is exercised + shipped.)
- [x] 7.2 **Decisive — DONE 2026-06-08.** mcp-inspector OAuth round-trip against the staging MCP Function URL completes end-to-end: consent "Allow Access" → `/api/oauth/approve` succeeds → code → token → authenticated `/mcp` connection → `resources/list` returns. Closes `janus-mcp-server`'s end-to-end OAuth gate (PR 2.5). Note: full chain also needed Bugs I (#384), J (#386), K (#387), L (#388); use mcp-inspector **Direct** connection mode (Via-Proxy misroutes `/register`).
- [x] 7.3 `janus-mcp-server` Bug G marked resolved in that change's tasks.md (#383).

## Out of scope (tracked in janus-mcp-server)

- Read-tool drift fix (Bug E), `get_strategy_map` / `list_scans` (Bug F), tool-name rebrand, RFC 9728 protected-resource metadata (Bug H), Connected Apps UI. None depend on this change.

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
- [ ] 6.2 Conventional commit + PR (branch off development, base development). Wait for CI + user merge approval.

## 7. Staging validation (the end-to-end gate)

- [ ] 7.1 After deploy, log into `dev.services.sc0red.ai`, leave the session idle past the idToken's 1h expiry (or temporarily shorten it), then load an authenticated page → confirm NO forced logout (refresh happened transparently).
- [ ] 7.2 **Decisive:** re-run the `mcp-inspector` OAuth round-trip against the staging MCP Function URL — consent "Allow Access" → `/api/oauth/approve` succeeds → code → token → `list_analyses` returns. This closes `janus-mcp-server`'s end-to-end OAuth gate.
- [ ] 7.3 Mark `janus-mcp-server` Bug G resolved in that change's tasks.md + bug table.

## Out of scope (tracked in janus-mcp-server)

- Read-tool drift fix (Bug E), `get_strategy_map` / `list_scans` (Bug F), tool-name rebrand, RFC 9728 protected-resource metadata (Bug H), Connected Apps UI. None depend on this change.

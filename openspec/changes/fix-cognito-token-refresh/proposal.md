# Proposal — Fix Cognito idToken refresh in the web session

## Why

The frontend's NextAuth session stores the Cognito **idToken** captured at login and never refreshes it. The session JWT lives **8 hours** (`authOptions.jwt.maxAge`), but a Cognito idToken expires after **1 hour**. There is no refresh path — `signInWithCognito` returns a `refreshToken`, but `authorize()` discards it and the `jwt` callback only sets `token.idToken` at initial sign-in.

Consequences, in order of severity:

1. **App-wide hourly forced re-login.** Every authenticated server-rendered page (`dashboard`, `analyses`, `analysis/[id]`, `team`, `portfolio/[id]`, …) and every server API route calls `backendFetch` → `getBackendToken()`, which reads the (stale-after-1h) idToken from the NextAuth JWT and sends it to the Python API. After an hour the API returns `401 {"error":"Token expired"}`. Pages survive only because the `error.tsx` boundary catches the 401 and force-signs-the-user-out → they log in again → fresh idToken for another hour. So users are silently kicked back to login roughly hourly.

2. **MCP OAuth consent is fully blocked.** The MCP server's OAuth flow (now working through discovery → DCR → authorize → consent page render, after the `janus-mcp-server` LWA + issuer fixes) dies at "Allow Access": the consent page posts to `/api/oauth/approve`, which calls the backend via `backendFetch` with the stale idToken → `401 Token expired`. Unlike a page, the API route has no `error.tsx` boundary, so the OAuth flow just fails — even immediately after a re-login, because re-login doesn't reliably rotate the idToken stored in the existing NextAuth JWT (NextAuth doesn't re-run `authorize` while a valid session JWT exists). This is the active blocker for a client-usable MCP v1 (verified 2026-06-05 against `mcp-inspector`).

This is a frontend session-management bug, not an MCP bug — but it surfaced as the final blocker for `janus-mcp-server`, which depends on it.

## What Changes

Implement standard NextAuth **refresh-token rotation** for the Cognito session:

- **Capture** the `refreshToken` (and the idToken's `exp`) at login — `signInWithCognito` already returns it; `authorize()` currently drops it.
- **Store** `idToken`, `refreshToken`, and `idTokenExpiresAt` on the NextAuth JWT.
- **Refresh** in the `jwt` callback: when the idToken is expired or within a small skew window of expiry, exchange the refresh token for a fresh idToken via Cognito `REFRESH_TOKEN_AUTH` and update the JWT. On refresh failure (refresh token expired/revoked after 30 days), mark the token so the next `getBackendToken()` / page load cleanly forces re-login.
- **`getBackendToken()`** then always returns a valid (auto-refreshed) idToken.

No change to the backend, to the API auth middleware, or to how `backendFetch` is called by consumers — the refresh is transparent.

## Capabilities

### New Capabilities

- `cognito-token-refresh`: the web session keeps a valid Cognito idToken available to server-side backend calls by refreshing it via the Cognito refresh token before expiry, transparently to all `backendFetch` callers.

### Modified Capabilities

- None (no existing spec covers the NextAuth session token lifecycle).

## Impact

- **Frontend only.** `frontend/src/lib/auth/authOptions.ts` (capture refresh token, refresh in `jwt` callback), `frontend/src/lib/auth/cognitoClient.ts` (add a `refreshCognitoSession` helper using `REFRESH_TOKEN_AUTH`), `frontend/src/types/next-auth.d.ts` (JWT type gains `refreshToken` + `idTokenExpiresAt`). `serverToken.ts` likely unchanged (it just reads `token.idToken`, now kept fresh).
- **No backend / infrastructure change.** The Cognito app client already supports `REFRESH_TOKEN_AUTH` (public SPA client, no secret).
- **Unblocks** `janus-mcp-server`'s end-to-end OAuth consent (the mcp-inspector round-trip) and removes the app-wide hourly forced-relogin.
- **Out of scope:** the MCP-side follow-ups tracked in `janus-mcp-server` (read-tool drift, `get_strategy_map`, rebrand, RFC 9728 metadata). Those are independent.

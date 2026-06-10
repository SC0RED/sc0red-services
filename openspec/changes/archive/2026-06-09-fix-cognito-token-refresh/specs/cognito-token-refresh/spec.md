# cognito-token-refresh Specification

## Purpose

The web session must keep a valid (unexpired) Cognito idToken available to every server-side backend call (`getBackendToken` / `backendFetch`). The Cognito idToken expires after 1 hour while the NextAuth session lives 8 hours, so the session must refresh the idToken using the Cognito refresh token before expiry — transparently, without changing backend behaviour or any `backendFetch` call site, and falling back to a clean re-login when the refresh token itself is no longer valid.

## Requirements

## ADDED Requirements

### Requirement: The web session refreshes the Cognito idToken before it expires

The NextAuth session SHALL retain the Cognito refresh token captured at login and SHALL refresh the idToken via the Cognito `REFRESH_TOKEN_AUTH` flow when the idToken is at or within a small skew window (≤ 60 s) of its expiry, so that `getBackendToken()` always returns an unexpired idToken. The refresh SHALL occur server-side in the NextAuth `jwt` callback and SHALL NOT require any change to `backendFetch` call sites or to the backend API.

#### Scenario: Fresh idToken passes through untouched

- **WHEN** the `jwt` callback runs and the stored idToken's expiry is more than the skew window in the future
- **THEN** the token is returned unchanged (no refresh call is made)

#### Scenario: Expired-or-near-expiry idToken is refreshed

- **WHEN** the `jwt` callback runs and the current time is at or past `idTokenExpiresAt - skew`
- **THEN** the stored refresh token is exchanged via Cognito `REFRESH_TOKEN_AUTH` for a fresh idToken
- **AND** the JWT's `idToken` and `idTokenExpiresAt` are updated to the new values
- **AND** any previous refresh `error` flag is cleared

#### Scenario: A long-lived session no longer forces hourly re-login

- **WHEN** an authenticated user keeps a session open past the 1-hour idToken expiry and loads a server-rendered authenticated page
- **THEN** the page renders without bouncing the user to the login screen (the idToken was refreshed transparently)

### Requirement: Refresh-token capture at login

The login flow SHALL persist the Cognito refresh token and the idToken expiry onto the NextAuth JWT. The refresh token SHALL remain server-side only (never exposed on the client-facing `session`), consistent with the idToken's existing handling.

#### Scenario: Login stores the refresh token and expiry

- **WHEN** a user signs in via Cognito `USER_PASSWORD_AUTH`
- **THEN** the NextAuth JWT carries `idToken`, `refreshToken`, and `idTokenExpiresAt` (derived from the idToken's `exp` claim)
- **AND** `useSession()` on the client does NOT expose `refreshToken` or `idToken`

### Requirement: Failed refresh falls back to re-login

When the refresh token is expired or revoked (e.g. after its 30-day lifetime), the refresh attempt SHALL fail gracefully: the session SHALL be marked with a refresh-error flag, and `getBackendToken()` SHALL return `null` so the next backend call surfaces a 401 and the existing re-login path runs. The application SHALL NOT serve a stale/expired idToken as if valid.

#### Scenario: Refresh-token expiry forces a clean re-login

- **WHEN** the `jwt` callback attempts a refresh and Cognito rejects the refresh token
- **THEN** the JWT is marked with a refresh-error flag and the (stale) idToken is not used
- **AND** `getBackendToken()` returns `null`, so `backendFetch` throws a 401 that the app's error boundary handles by signing the user out and redirecting to login

#### Scenario: OAuth consent approval succeeds with a refreshed token

- **WHEN** a user with a session older than the idToken's 1-hour expiry approves an MCP OAuth consent ("Allow Access"), which posts to `/api/oauth/approve`
- **THEN** the server route's `backendFetch` sends a freshly-refreshed idToken (not an expired one)
- **AND** the backend accepts it and issues the authorization code (the consent flow completes instead of failing with "Token expired")

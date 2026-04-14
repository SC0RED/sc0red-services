## ADDED Requirements

### Requirement: OAuth metadata discovery
The server SHALL expose `GET /.well-known/oauth-authorization-server` returning JSON metadata with issuer, authorization_endpoint, token_endpoint, registration_endpoint, supported response types, code challenge methods, and grant types.

#### Scenario: Client fetches metadata
- **WHEN** a client sends GET to `/.well-known/oauth-authorization-server`
- **THEN** the server returns 200 with JSON containing all required MCP OAuth metadata fields

### Requirement: Dynamic Client Registration
The server SHALL accept `POST /oauth/register` with client_name, redirect_uris, and grant_types. It SHALL return a unique client_id. Clients are public (no client_secret).

#### Scenario: New client registers
- **WHEN** a client sends POST to `/oauth/register` with valid client_name and redirect_uris
- **THEN** the server returns 201 with a client_id and stores the client in DynamoDB

#### Scenario: Registration with missing fields
- **WHEN** a client sends POST to `/oauth/register` without client_name
- **THEN** the server returns 400 with an error description

### Requirement: Authorization code flow with PKCE
The server SHALL support the authorization code grant with PKCE (S256 method). The authorization endpoint SHALL redirect unauthenticated users to login, then display a consent screen. Upon user approval, it SHALL issue an authorization code (10 min TTL) and redirect to the client's redirect_uri.

#### Scenario: User approves consent
- **WHEN** an authenticated user visits `/oauth/authorize` with valid client_id, code_challenge, and redirect_uri, and clicks "Allow"
- **THEN** the server generates an authorization code, stores it in DynamoDB with TTL, and redirects to redirect_uri with code and state

#### Scenario: User denies consent
- **WHEN** an authenticated user clicks "Cancel" on the consent screen
- **THEN** the server redirects to redirect_uri with error=access_denied

#### Scenario: Invalid redirect_uri
- **WHEN** the authorize request contains a redirect_uri not registered for the client
- **THEN** the server returns 400 without redirecting

### Requirement: Token exchange
The server SHALL accept `POST /oauth/token` with grant_type=authorization_code, code, client_id, code_verifier, and redirect_uri. It SHALL validate PKCE, issue a JWT access_token (1h TTL) and opaque refresh_token (30d TTL).

#### Scenario: Valid code exchange
- **WHEN** a client sends a valid authorization code with correct PKCE verifier
- **THEN** the server returns access_token (JWT), refresh_token, token_type, and expires_in

#### Scenario: Invalid PKCE verifier
- **WHEN** a client sends a code with incorrect code_verifier
- **THEN** the server returns 400 with error=invalid_grant

#### Scenario: Expired code
- **WHEN** a client sends a code that has expired (>10 min)
- **THEN** the server returns 400 with error=invalid_grant

### Requirement: Token refresh
The server SHALL accept `POST /oauth/token` with grant_type=refresh_token. It SHALL issue a new access_token and rotate the refresh_token.

#### Scenario: Valid refresh
- **WHEN** a client sends a valid refresh_token
- **THEN** the server returns a new access_token and new refresh_token, and invalidates the old refresh_token

#### Scenario: Expired or revoked refresh token
- **WHEN** a client sends an expired or revoked refresh_token
- **THEN** the server returns 400 with error=invalid_grant

### Requirement: Token revocation
The server SHALL support token revocation. Users SHALL be able to revoke tokens for specific clients from the Janus web UI.

#### Scenario: User revokes a connected app
- **WHEN** a user revokes access for a client in Janus settings
- **THEN** all access_tokens and refresh_tokens for that client+user are invalidated

### Requirement: Consent remembered per client
The server SHALL remember user consent per client_id. Subsequent authorization requests from the same client for the same user SHALL skip the consent screen.

#### Scenario: Returning client authorization
- **WHEN** a user has previously approved a client and the client requests authorization again
- **THEN** the server issues a new code without showing the consent screen

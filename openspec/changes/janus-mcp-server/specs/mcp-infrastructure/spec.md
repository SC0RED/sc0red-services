## ADDED Requirements

### Requirement: Dedicated MCP Lambda
A dedicated Lambda function SHALL be created for the MCP server, separate from the existing API Lambda. It SHALL use Python 3.12 runtime with Mangum as the ASGI-to-Lambda adapter.

#### Scenario: MCP Lambda deployed
- **WHEN** CDK deploys the stack
- **THEN** a `janus-mcp-{environment}` Lambda function exists with appropriate timeout (900s) and memory

### Requirement: Lambda Function URL
The MCP Lambda SHALL be exposed via a Lambda Function URL to serve the Streamable HTTP transport (`POST /mcp`) and OAuth endpoints.

#### Scenario: MCP endpoint accessible
- **WHEN** a client sends POST to the Function URL `/mcp`
- **THEN** the request is handled by the FastMCP server via Mangum

### Requirement: CloudFront custom domain
A CloudFront distribution SHALL front the Lambda Function URL and serve it at `mcp.{env}.janus.sc0red.com`.

#### Scenario: Custom domain resolves
- **WHEN** a client connects to `mcp.staging.janus.sc0red.com`
- **THEN** the request is routed through CloudFront to the Lambda Function URL

### Requirement: CDK MCPConstruct
All MCP-related infrastructure SHALL be encapsulated in an `MCPConstruct` CDK construct, following the existing pattern of `CognitoConstruct`, `AmplifyConstruct`, and `ObservabilityConstruct`.

#### Scenario: Stack includes MCP construct
- **WHEN** CDK synthesizes the stack
- **THEN** the MCPConstruct creates the Lambda, Function URL, and CloudFront distribution

### Requirement: Shared environment variables
The MCP Lambda SHALL receive the same core environment variables as the API Lambda (DynamoDB table, Cognito config) plus MCP-specific variables (OAuth signing key reference, API URL for internal calls, rate limit config).

#### Scenario: MCP Lambda has required env vars
- **WHEN** the MCP Lambda starts
- **THEN** it has access to DYNAMODB_TABLE, API_URL (internal backend), OAUTH_SIGNING_KEY_SECRET_ARN, and rate limit configuration

### Requirement: OAuth signing key in Secrets Manager
An RSA key pair for signing OAuth JWTs SHALL be stored in AWS Secrets Manager. The MCP Lambda reads the private key for signing; the `/.well-known/jwks.json` endpoint (managed by the MCP SDK) exposes the public key for verification.

#### Scenario: Key pair accessible
- **WHEN** the MCP Lambda starts and needs to sign a token
- **THEN** it reads the RSA private key from Secrets Manager

#### Scenario: JWKS endpoint serves public key
- **WHEN** a client fetches `/.well-known/jwks.json` from the MCP server
- **THEN** the server returns the RSA public key in JWKS format

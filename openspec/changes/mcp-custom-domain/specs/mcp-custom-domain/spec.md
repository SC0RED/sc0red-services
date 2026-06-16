# MCP Custom Domain

## ADDED Requirements

### Requirement: The MCP server is served on a branded per-environment hostname
The MCP server SHALL be reachable on the environment's branded hostname (`mcp.dev.services.sc0red.ai` for staging, `mcp.test.services.sc0red.ai` for testing, `mcp.services.sc0red.ai` for production) over HTTPS, covering the Streamable HTTP transport and every OAuth/discovery endpoint on the same host.

#### Scenario: Transport and discovery on the branded host
- **WHEN** a client requests `https://mcp.dev.services.sc0red.ai/.well-known/oauth-authorization-server` and `…/mcp`
- **THEN** both are served by the MCP server (discovery 200; transport 401 without a token), identical in behavior to the Function URL

### Requirement: Advertised URLs use the branded hostname only
When a custom domain is configured, all server-advertised URLs — the OAuth issuer, token/registration/authorization endpoints, the RFC 9728 `resource`, and the `WWW-Authenticate` `resource_metadata` hint — SHALL use the branded hostname. The raw Lambda Function URL SHALL NOT appear in any advertised metadata.

#### Scenario: Metadata advertises the branded host
- **WHEN** a client fetches the authorization-server metadata via the branded host
- **THEN** the issuer and every endpoint URL in the response use `https://mcp.<env-domain>` and no `lambda-url` host appears

### Requirement: Environments without a configured domain are unaffected
The custom domain SHALL be optional per environment: with no domain configured, the server keeps advertising the Function URL (SSM-resolved issuer) exactly as before.

#### Scenario: No domain configured
- **WHEN** an environment is deployed without `mcp_domain` config
- **THEN** no CloudFront distribution is created and the issuer resolves via the SSM Function URL parameter

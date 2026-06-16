# MCP Custom Domain

## Why

The MCP server is reachable only via its raw Lambda Function URL (`https://wme4….lambda-url.us-east-1.on.aws/mcp`) — ugly for customers, and worse, it is the customer contract: every connected AI assistant breaks if it ever changes. Branding the endpoint (`mcp.dev.services.sc0red.ai` / `mcp.test.services.sc0red.ai` / `mcp.services.sc0red.ai`) before promotion means customers only ever see a stable, owned URL. The issuer hook already exists (`MCP_ISSUER_URL` env wins over SSM — built for exactly this in the Bug C fix).

## What Changes

- Per environment, a CloudFront distribution in front of the whole Lambda Function URL (all paths: `/mcp`, `/token`, `/register`, `/authorize`, `/.well-known/*` — OAuth discovery lives on the same origin as the transport, so a path-proxy on the frontend domain is not viable).
- ACM certificates are requested **out-of-band via CLI** and referenced **by ARN** in per-env config — this avoids the CI deploy hanging on DNS validation (20-min job ceiling) and sidesteps the us-east-1-only CloudFront cert constraint for the us-east-2 testing/prod stacks.
- `MCP_ISSUER_URL` set from config when a domain is configured — flips all advertised URLs (issuer, token endpoint, RFC 9728 `resource`, `WWW-Authenticate`) to the branded host in one move.
- DNS (decision: **Option A — manual records**): two records per environment in the production account's Route 53 (cert-validation CNAME at issuance; `mcp.<env-domain>` CNAME → the CloudFront domain after deploy). Matches the precedent of how the Amplify frontend domains were attached.
- **BREAKING (staging only, accepted):** switching the issuer invalidates existing dev tokens/client registrations — connected clients (inspector, Claude) re-consent once. That is the point of doing this before promotion.

## Capabilities

### New Capabilities
- `mcp-custom-domain`: the MCP server is served and advertised on a branded per-environment hostname, with the raw Function URL no longer appearing in any advertised metadata.

### Modified Capabilities

<!-- none — OAuth/transport behavior is unchanged; only the host changes -->

## Impact

- **Infrastructure**: new CloudFront distribution + cert-by-ARN wiring in `MCPConstruct` (or a sibling construct); `MCP_ISSUER_URL` env; per-env config (`mcp_domain`, `mcp_certificate_arn`) in `app.py`.
- **Operations**: one-time per env — request cert (CLI), add 2 DNS records in the production account's Route 53.
- **Clients**: staging clients re-connect once. Customers (testing/prod) only ever see the branded URL.
- **No backend code changes** — the issuer resolution already supports this.

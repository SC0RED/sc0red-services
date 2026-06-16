# Tasks — MCP Custom Domain

## 1. Certificate (out-of-band, per D1) — staging now

- [x] 1.1 Request the staging cert (dev account, MUST be us-east-1): `aws acm request-certificate --domain-name mcp.dev.services.sc0red.ai --validation-method DNS --region us-east-1` → note the ARN.
- [x] 1.2 Get the validation record: `aws acm describe-certificate --certificate-arn <arn> --region us-east-1 --query 'Certificate.DomainValidationOptions[0].ResourceRecord'` → hand the CNAME (name + value) to the prod-account Route 53 admin.
- [x] 1.3 Cert ISSUED (2026-06-12) — validation CNAME added in the prod-account Route 53. (usually minutes after the record lands).

## 2. CDK (config-gated, per D2–D4)

- [x] 2.1 `app.py`: optional per-env `mcp_domain` + `mcp_certificate_arn` config (staging: `mcp.dev.services.sc0red.ai` + the ARN from 1.1; testing/prod: empty until promotion). Thread through `Sc0redServicesStack` → `MCPConstruct`.
- [x] 2.2 `MCPConstruct`: when domain config present — CloudFront distribution (origin = Function URL hostname via `Fn.select(2, Fn.split("/", url))`, `AllViewerExceptHostHeader` origin-request policy, `CachingDisabled`, ALL methods, redirect-to-HTTPS, alias = domain, cert by ARN) + `MCP_ISSUER_URL=https://{domain}` env + `CfnOutput` of the CloudFront domain name (the CNAME target for DNS).
- [x] 2.3 Isolated synth check of the CloudFront wiring (full local synth is blocked by the bundling deploy key — same as prior infra changes); ruff clean on infra.
- [x] 2.4 Architecture review — 0 critical/medium; CloudFront-for-OAuth behavior verified (query strings, Authorization, OPTIONS, POST bodies pass; caching disabled); fixed the LOW docstring staleness.

## 3. Ship + DNS

- [x] 3.1 PR (base development). NOTE: merge only after the GitHub→AWS secrets access is restored — the merge triggers the backend deploy.
- [x] 3.2 Deployed; `MCPCloudFrontDomain` = d17pf11lx7inko.cloudfront.net → CNAME added in the prod-account Route 53 (DNS resolves). → admin adds `mcp.dev.services.sc0red.ai CNAME <dxxxx.cloudfront.net>` in the prod-account Route 53.

## 4. Staging validation

- [x] 4.1 `curl https://mcp.dev.services.sc0red.ai/health` → 200; `…/.well-known/oauth-authorization-server` → issuer + all endpoints on the branded host, no `lambda-url` anywhere; `…/.well-known/oauth-protected-resource/mcp` → `resource` on the branded host.
- [ ] 4.2 mcp-inspector round-trip against `https://mcp.dev.services.sc0red.ai/mcp` (Direct mode): fresh consent → tools list (16) → a read tool returns. (Existing connections invalidated by the issuer flip — expected, reconnect.)
- [x] 4.3 Update the janus-mcp-server tracking (staging URL references) + Connected Apps "How to connect" guidance if it names a URL.

## 5. Testing/production (during promotion — not now)

- [ ] 5.1 Repeat 1.x per account (us-east-1 certs in the testing/prod accounts), fill their env config, deploy, add the 2 records each, validate.

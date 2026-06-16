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
- [x] 4.2 mcp-inspector round-trip on the branded host — fresh consent (incl. the login/signup→consent redirect fix #409), 17 tools, read + write tools verified by the user.
- [x] 4.3 Update the janus-mcp-server tracking (staging URL references) + Connected Apps "How to connect" guidance if it names a URL.

## 5. Testing promotion

- [x] 5.0 TEST_AWS keys restored as **testing environment** secrets (admin); `deploy-testing.yml` declares `environment: testing`, so they resolve.
- [x] 5.1 Testing cert ISSUED (`...66937018...`, testing account us-east-1); validation CNAME added in the prod-account Route 53.
- [x] 5.2 Testing config added to app.py (PR #410, merged).
- [x] 5.3 Promoted development → testing (PR #411); `Sc0redServices-testing` deployed.
- [x] 5.4 `MCPCloudFrontDomain` = d2xossqs1x5e9j.cloudfront.net → `mcp.test.services.sc0red.ai` CNAME added in the prod-account Route 53.
- [x] 5.5 Validated `https://mcp.test.services.sc0red.ai`: health 200, metadata + WWW-Authenticate on the branded host (0 lambda-url leaks), inspector round-trip (17 tools) user-confirmed.

## 6. Production promotion (later)

- [x] 6.0 PROD_AWS keys present as **production environment** secrets (admin); `deploy-production.yml` declares `environment: production` (no approval gate → merge auto-deploys).
- [ ] 6.1 **Cert (production account, us-east-1):** `mcp.services.sc0red.ai` requested (`...5cb75da8...`); add validation CNAME in the prod Route 53 → confirm ISSUED.
- [ ] 6.2 Add production `mcp_domain`/`mcp_certificate_arn` to app.py → PR to development.
- [ ] 6.3 Sync development → testing.
- [ ] 6.4 Promote testing → production; deploy runs `cdk deploy Sc0redServices-production`.
- [ ] 6.5 Grab the production `MCPCloudFrontDomain` output → add `mcp.services.sc0red.ai CNAME <cloudfront>` in the prod Route 53.
- [ ] 6.6 Validate `https://mcp.services.sc0red.ai`.

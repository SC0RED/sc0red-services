# Design — MCP Custom Domain

## Context

The MCP server runs as a Lambda Function URL (LWA + FastMCP) per environment: staging in the dev account (us-east-1), testing/production in their own accounts (us-east-2). DNS for `services.sc0red.ai` lives in Route 53 **in the production account only** — so staging and testing DNS records are cross-account no matter what. The issuer resolution order in `mcp_handler._resolve_issuer_url` is `MCP_ISSUER_URL` env → SSM (Function URL) → localhost, so flipping every advertised URL to a custom domain is a config change, not a code change.

Decisions already made with the user: **Option A** (manual DNS records in the prod-account zone; matches the Amplify-domain precedent), hostnames `mcp.dev.services.sc0red.ai` / `mcp.test.services.sc0red.ai` / `mcp.services.sc0red.ai`.

## Goals / Non-Goals

**Goals:**
- Branded, stable MCP endpoint per environment covering the transport AND all OAuth/discovery endpoints.
- Zero waiting-on-humans inside the CI deploy (the 20-minute job ceiling must hold).
- One construct that works for all three environments, including the us-east-2 ones.

**Non-Goals:**
- Blocking direct access to the raw Function URL (Lambda OAC requires clients to send `x-amz-content-sha256` on POSTs — no MCP client does; the raw URL stays reachable but is advertised nowhere, and everything behind it still requires a bearer token).
- Automating Route 53 (Option B's delegated subzones) — revisit if record churn ever becomes recurring.
- Custom domains for the API Gateway / frontend (out of scope; already handled via Amplify).

## Decisions

### D1 — Certificates by ARN, requested out-of-band

CDK-managed DNS-validated certs would pause the stack mid-deploy until a human adds the validation CNAME in another AWS account — guaranteed to blow the 20-minute CI ceiling on first deploy. Instead: the cert is requested once per environment via CLI (`aws acm request-certificate … --region us-east-1`), the validation CNAME is added to the prod-account zone, and the **issued cert's ARN goes into `app.py` env config** (`mcp_certificate_arn` — an ARN is not a secret). CDK imports it with `Certificate.from_certificate_arn`.

Bonus: CloudFront only accepts **us-east-1** certs, but the testing/prod stacks are us-east-2 — by-ARN import needs no cross-region CDK stack machinery at all (the cert is simply requested in us-east-1 of each account).

*Alternative considered:* `acm.Certificate` + cross-region cert stack — rejected: deploy-blocking validation + extra stack complexity for zero gain under Option A.

### D2 — CloudFront in front of the whole Function URL

One distribution per environment:
- Origin: the Function URL **hostname** (derived in-stack: `Fn.select(2, Fn.split("/", function_url.url))` — CF → FunctionUrl is a one-way reference, no cycle).
- Origin request policy: managed **`AllViewerExceptHostHeader`** — Function URLs route by their own Host header; forwarding the viewer Host would break them. (CloudFront sets the origin Host to the origin domain.)
- Cache policy: managed **`CachingDisabled`** (every request is dynamic + authenticated).
- Allowed methods: ALL (the transport uses GET/POST/DELETE; OAuth uses GET/POST).
- Viewer protocol: redirect-to-HTTPS; aliases: the env's `mcp_domain`; cert: D1's ARN.

### D3 — Issuer flip via config

When `mcp_domain` is configured, `MCPConstruct` sets `MCP_ISSUER_URL=https://{mcp_domain}` (a static string — exactly the no-circular-dependency hook built in the Bug C fix). The SSM fallback stays for environments without a domain. `resource_server_url` derives from the issuer, so RFC 9728 metadata and `WWW-Authenticate` flip automatically.

### D4 — Rollout: staging first, config-gated

`mcp_domain`/`mcp_certificate_arn` are optional per-env config: absent → today's behavior (Function URL + SSM issuer), present → CloudFront + branded issuer. Staging ships first and validates the pattern; testing/prod get their values during promotion.

## Risks / Trade-offs

- [Issuer flip invalidates existing staging tokens/registrations] → accepted; clients re-consent once. Done before promotion so customers never experience it.
- [Raw Function URL stays reachable] → accepted (see Non-Goals); advertised nowhere after the flip.
- [Manual DNS = humans in the loop per env] → 2 records, one-time, matches the Amplify precedent; values are surfaced as stack outputs / CLI output.
- [CloudFront default 30s origin-response timeout] → fine for read tools and scan-start (fast writes); long-running work is queued, not synchronous.
- [GET /mcp SSE streaming through CloudFront] → `json_response=True` keeps responses plain JSON; SSE notifications stream as bytes arrive (CloudFront supports streaming responses). Validate in the round-trip.

## Migration Plan

Per environment: (1) request cert via CLI → validation CNAME added in prod-account Route 53 → ISSUED; (2) put domain + cert ARN in env config; (3) deploy (creates CloudFront, flips issuer); (4) add `mcp.<domain>` CNAME → CloudFront domain; (5) validate discovery + inspector round-trip on the new URL; clients re-connect. Rollback: remove the two config values and redeploy (issuer falls back to the Function URL via SSM).

## Open Questions

- None blocking.

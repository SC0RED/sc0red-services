# Frontend Migration: Vercel → AWS — Implementation Plan

## Motivation

Single source of truth. Backend (Lambda, DynamoDB, SQS, Cognito) and frontend on the same AWS account, deployed from the same pipeline. Simplifies maintenance, scaling, environment management, and eliminates Vercel as a separate vendor.

---

## Current Architecture

```
                    Vercel                              AWS
               ┌─────────────┐              ┌──────────────────────┐
User ──HTTPS──▶│  Next.js    │──HTTP/JWT───▶│  API Gateway         │
               │  (SSR +     │              │    ↓                  │
               │   API routes)│              │  Lambda (API)        │
               │             │              │    ↓                  │
               │  Deployed   │              │  DynamoDB / SQS /    │
               │  via CLI    │              │  Cognito / S3        │
               └─────────────┘              └──────────────────────┘

Frontend env vars: set in Vercel Dashboard
Deployment: manual `vercel --prod` from local
Domain: Vercel auto-generated URL
```

## Target Architecture

Both options place the frontend on AWS, behind CloudFront CDN.

---

## Option A: AWS Amplify Hosting

### What It Is

AWS Amplify Hosting is a managed service for deploying full-stack web apps. It natively supports Next.js SSR (server-side rendering, API routes, middleware) without any custom infrastructure. Think "Vercel on AWS."

### Architecture

```
                         AWS
     ┌─────────────────────────────────────────────┐
     │  CloudFront (managed by Amplify)            │
     │    ↓                                         │
     │  Amplify Hosting                             │
     │    ├─ Static assets → S3 (managed)          │
     │    ├─ SSR → Lambda (managed)                │
     │    └─ API routes → Lambda (managed)         │
     │                                              │
User │  API Gateway                                 │
 ──▶ │    ↓                                         │
     │  Lambda (API handler)                        │
     │    ↓                                         │
     │  DynamoDB / SQS / Cognito / S3              │
     └─────────────────────────────────────────────┘

One AWS account. Frontend and backend.
```

### How It Works

1. Amplify connects to GitHub repo (or triggered by GitHub Actions)
2. On push, Amplify runs `npm ci && npm run build` inside its managed build environment
3. Deploys static assets to S3, SSR routes to Lambda, all behind CloudFront
4. Environment variables set in Amplify Console (or via CDK `aws-amplify` construct)
5. Custom domain via Route53 + Amplify managed SSL

### CDK Integration

Amplify has CDK constructs but they're **separate from the existing Lambda/API Gateway stack**. Amplify manages its own Lambda functions and CloudFront distribution.

```python
# infrastructure/stacks/amplify_frontend.py (new stack)
from aws_cdk import aws_amplify as amplify

class AmplifyFrontendStack(Stack):
    def __init__(self, ...):
        app = amplify.App(
            self, "JanusFrontend",
            source_code_provider=amplify.GitHubSourceCodeProvider(
                owner="SC0RED",
                repository="janus",
                oauth_token=SecretValue.secrets_manager("github-token"),
            ),
            build_spec=codebuild.BuildSpec.from_object({
                "version": "1.0",
                "frontend": {
                    "phases": {
                        "preBuild": {"commands": ["cd frontend && npm ci"]},
                        "build": {"commands": ["npm run build"]},
                    },
                    "artifacts": {
                        "baseDirectory": "frontend/.next",
                        "files": ["**/*"],
                    },
                },
            }),
            environment_variables={
                "NEXT_PUBLIC_COGNITO_USER_POOL_ID": pool_id,
                "NEXT_PUBLIC_COGNITO_CLIENT_ID": client_id,
                "NEXT_PUBLIC_COGNITO_REGION": region,
                "NEXTAUTH_SECRET": nextauth_secret,
                "BACKEND_URL": api_gateway_url,
            },
        )

        main_branch = app.add_branch("development")

        # Custom domain (when ready)
        # domain = app.add_domain("janus.yourdomain.com")
        # domain.map_root(main_branch)
```

### Pros
- Simplest migration path — most similar to Vercel experience
- Managed builds, managed CDN, managed SSL
- Native Next.js SSR support (Amplify uses OpenNext under the hood)
- Built-in preview deployments for PRs
- CDK construct available for IaC

### Cons
- Amplify manages its own Lambda/CloudFront — not the same as our existing CDK stack
- Two "stacks" to manage: Amplify (frontend) + CDK (backend)
- Build times can be slower than Vercel
- Less control over CloudFront configuration
- Amplify CDK construct is less mature than other AWS CDK constructs

### Migration Steps

| Step | What | Effort |
|---|---|---|
| 1 | Create `AmplifyFrontendStack` in CDK | Small |
| 2 | Configure Amplify build spec for Next.js + monorepo (`frontend/` subdir) | Small |
| 3 | Set environment variables (Cognito, NextAuth, backend URL) | Small |
| 4 | Connect GitHub repo → Amplify auto-deploy on push to `development` | Small |
| 5 | Test SSR, API routes, auth flow, AppSync WebSocket on Amplify | Medium |
| 6 | Set up custom domain (Route53 + Amplify) when ready | Small |
| 7 | Update GitHub Actions to trigger Amplify deploy (or use Amplify's built-in) | Small |
| 8 | Remove Vercel configuration and dependencies | Small |

### Estimated Timeline: 2-3 days

---

## Option B: SST / OpenNext (CDK-Native)

### What It Is

SST (Serverless Stack Toolkit) is an open-source framework that deploys Next.js to AWS using standard services (Lambda + CloudFront + S3). It uses **OpenNext** — an adapter that converts Next.js output into Lambda-compatible handlers. Everything is defined in CDK, in the same infrastructure stack as the backend.

### Architecture

```
                         AWS (single CDK stack)
     ┌─────────────────────────────────────────────┐
     │  CloudFront Distribution                    │
     │    ├─ Static assets → S3 bucket             │
     │    ├─ SSR routes → Lambda (server function) │
     │    ├─ API routes → Lambda (server function) │
     │    └─ Image optimization → Lambda           │
     │                                              │
User │  API Gateway                                 │
 ──▶ │    ↓                                         │
     │  Lambda (API handler)                        │
     │    ↓                                         │
     │  DynamoDB / SQS / Cognito / S3              │
     └─────────────────────────────────────────────┘

Everything in one CDK app. One `cdk deploy` deploys everything.
```

### How It Works

1. OpenNext runs `next build` and converts the output into Lambda-compatible packages
2. Static assets are uploaded to S3
3. SSR routes are deployed as Lambda functions behind CloudFront
4. API routes run in the same Lambda (or separate, configurable)
5. CloudFront handles routing: static → S3, dynamic → Lambda
6. All resources defined in CDK — same `infrastructure/` directory as backend

### CDK Integration

This lives in the **same CDK app** as the backend. Can be a separate stack or part of the existing `JanusStack`.

```python
# infrastructure/stacks/frontend_stack.py (new stack)
# Uses cdk-nextjs-standalone or manual OpenNext CDK construct

from cdk_nextjs_standalone import Nextjs

class FrontendStack(Stack):
    def __init__(self, scope, id, *, backend_url, cognito_pool_id, ...):
        super().__init__(scope, id)

        frontend = Nextjs(
            self, "JanusFrontend",
            nextjs_path="../frontend",
            environment={
                "NEXT_PUBLIC_COGNITO_USER_POOL_ID": cognito_pool_id,
                "NEXT_PUBLIC_COGNITO_CLIENT_ID": cognito_client_id,
                "NEXT_PUBLIC_COGNITO_REGION": region,
                "NEXTAUTH_SECRET": nextauth_secret,
                "BACKEND_URL": backend_url,
            },
        )

        # Custom domain
        # frontend.add_domain("janus.yourdomain.com")

        CfnOutput(self, "FrontendUrl", value=frontend.url)
```

Alternative: use OpenNext CLI directly + manual CDK constructs:

```python
# Manual approach (more control, more code)
class FrontendStack(Stack):
    def __init__(self, ...):
        # S3 bucket for static assets
        bucket = s3.Bucket(self, "StaticAssets", ...)

        # Lambda for SSR
        ssr_function = lambda_.Function(
            self, "SSRFunction",
            handler="index.handler",
            code=lambda_.Code.from_asset("../frontend/.open-next/server-function"),
            ...
        )

        # CloudFront distribution
        distribution = cloudfront.Distribution(
            self, "CDN",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.HttpOrigin(...),  # Lambda function URL
            ),
            additional_behaviors={
                "/_next/static/*": cloudfront.BehaviorOptions(
                    origin=origins.S3Origin(bucket),
                ),
            },
        )
```

### Pros
- **Single CDK app** — frontend + backend deployed together
- **Single CI/CD pipeline** — one `cdk deploy` in GitHub Actions
- Full control over CloudFront, Lambda, S3 configuration
- No vendor-specific platform (pure AWS services)
- Can share CDK constructs between frontend and backend (Cognito pool ID, API Gateway URL)
- OpenNext is actively maintained by the community (used by SST, Amplify internally)

### Cons
- More initial setup than Amplify (CDK constructs for CloudFront + Lambda + S3)
- OpenNext/cdk-nextjs-standalone is a community package — not AWS-managed
- Need to handle image optimization Lambda separately
- Build step requires OpenNext CLI before `cdk deploy`
- Preview deployments require custom setup (Amplify gives this free)

### Migration Steps

| Step | What | Effort |
|---|---|---|
| 1 | Add `open-next` dev dependency to frontend (`npm install -D open-next`) | Small |
| 2 | Add build script: `open-next build` (converts Next.js output for Lambda) | Small |
| 3 | Create `FrontendStack` in CDK (S3 + Lambda + CloudFront) or use `cdk-nextjs-standalone` | Medium |
| 4 | Wire environment variables from backend stack outputs (Cognito IDs, API URL) | Small |
| 5 | Update GitHub Actions: `open-next build` → `cdk deploy FrontendStack` | Medium |
| 6 | Test SSR, API routes, auth flow, static assets, AppSync WebSocket | Medium |
| 7 | Set up custom domain (Route53 + CloudFront + ACM certificate) | Small |
| 8 | Remove Vercel configuration and dependencies | Small |

### Estimated Timeline: 3-5 days

---

## Comparison Summary

| Aspect | Amplify Hosting | SST / OpenNext |
|---|---|---|
| **Deployment model** | Separate Amplify + CDK backend | Single CDK app for everything |
| **CDK integration** | Separate construct, separate stack | Same stack / sibling stack |
| **CI/CD** | Amplify built-in or GitHub Actions trigger | GitHub Actions → `cdk deploy` |
| **One `cdk deploy`** | No — Amplify deploy is separate | **Yes** |
| **Preview deploys** | Built-in | Custom setup needed |
| **SSR support** | Native (uses OpenNext internally) | Native (OpenNext) |
| **Control** | Low (managed) | High (you own all resources) |
| **Maintenance** | Low | Medium |
| **Setup effort** | 2-3 days | 3-5 days |
| **Maturity** | GA, AWS-supported | Community-maintained |
| **Fits "single source of truth"** | Partially (still two deploy systems) | **Fully** (one CDK, one pipeline) |
| **Scales with team** | Yes (managed) | Yes (IaC) |

---

## Environment Variables (both options)

| Variable | Source | How to set |
|---|---|---|
| `NEXT_PUBLIC_COGNITO_USER_POOL_ID` | CDK CfnOutput from CognitoConstruct | Pass as cross-stack reference |
| `NEXT_PUBLIC_COGNITO_CLIENT_ID` | CDK CfnOutput from CognitoConstruct | Pass as cross-stack reference |
| `NEXT_PUBLIC_COGNITO_REGION` | Stack region | `self.region` |
| `NEXTAUTH_SECRET` | SSM Parameter Store | `ssm.StringParameter.value_for_string_parameter()` |
| `BACKEND_URL` | CDK CfnOutput from JanusStack (API Gateway URL) | Pass as cross-stack reference |
| `NEXT_PUBLIC_APPSYNC_ENDPOINT` | CDK CfnOutput from JanusStack | Pass as cross-stack reference |
| `NEXT_PUBLIC_APPSYNC_API_KEY` | CDK CfnOutput from JanusStack | Pass as cross-stack reference |

---

## GitHub Actions Pipeline (after migration)

```yaml
# .github/workflows/deploy.yml
name: Deploy
on:
  push:
    branches: [development]

jobs:
  ci:
    # existing CI checks (lint, test, security, audit)

  deploy:
    needs: ci
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
      - uses: actions/setup-python@v5

      # Build frontend
      - run: cd frontend && npm ci && npx open-next build  # (for SST option)

      # Deploy everything
      - run: cd infrastructure && cdk deploy --all --require-approval never
```

---

## Recommendation

**For your situation (consolidation priority, not urgent, pre-funding, small team):**

**Start with Amplify Hosting.** Here's why:

1. **Fastest to production** — 2-3 days vs 3-5. You're pre-funding and need to ship features (like Value Chain), not spend a week on infra.

2. **"Single source of truth" achieved** — both on AWS, same account, same billing. Yes, Amplify has its own deploy system, but it's still AWS-managed and you're not paying another vendor.

3. **Migrate to SST later if needed** — Amplify uses OpenNext internally. If you outgrow Amplify (need more CloudFront control, want true single-stack CDK), you can migrate to SST with minimal frontend code changes since the underlying adapter is the same.

4. **Preview deployments for free** — when you have more team members reviewing PRs, Amplify gives you preview URLs automatically. With SST, you'd build this yourself.

5. **Less to maintain** — pre-funding means fewer engineers. Amplify manages the infra; SST means you own it.

**If after funding you have a larger team and want full IaC control, migrate from Amplify to SST.** The frontend code doesn't change — only the infrastructure.

---

## Implementation Plan (Amplify — Chosen Approach)

### Decision: Amplify Hosting via CDK L1 Constructs

- Use `CfnApp` + `CfnBranch` (L1) — no extra dependencies, stable in CDK v2
- GitHub PAT for repo access (passed at deploy time via `AMPLIFY_GITHUB_TOKEN`)
- Two-phase construct to resolve circular dependency (Amplify needs API URL, API needs Amplify URL for CORS)

### Circular Dependency Resolution

Amplify needs `BACKEND_URL` (API Gateway URL) for branch env vars. API Gateway needs `FRONTEND_DOMAIN` (Amplify URL) for CORS. Solution: split Amplify construct into two phases:

1. **Phase 1 — Create `CfnApp` early** (only needs GitHub token + repository). This gives us `attr_default_domain` as a CDK token.
2. Use `branch_url` (`https://{branch}.{default_domain}`) as `FRONTEND_DOMAIN` for S3 CORS, Cognito, API Gateway.
3. Create API Gateway (now has the Amplify URL for CORS).
4. **Phase 2 — Create `CfnBranch`** with `BACKEND_URL` = API Gateway URL.

### New File: `infrastructure/stacks/amplify_construct.py`

```python
class AmplifyConstruct(Construct):
    def __init__(self, scope, id, *, environment, nextauth_secret,
                 github_token, repository, branch_name):
        # Creates CfnApp + IAM role immediately
        # Exposes default_domain and branch_url properties

    def create_branch(self, *, api_url, cognito_pool_id, cognito_client_id):
        # Creates CfnBranch with BACKEND_URL and NEXT_PUBLIC_* vars
        # Called after API Gateway is created
```

### Modified Files

| File | Change |
|------|--------|
| `infrastructure/stacks/janus_stack.py` | Reorder init (Amplify app → resources → Amplify branch), refactor 3x `FRONTEND_DOMAIN` reads into single resolution |
| `infrastructure/app.py` | Add `enable_amplify`, `github_repository`, `amplify_branch` to env configs |
| `frontend/next.config.js` | Add `output: 'standalone'` (required for Amplify SSR) |
| `.github/workflows/deploy-backend.yml` | Add `AMPLIFY_GITHUB_TOKEN` secret, rename to `deploy.yml` |

### Init Order in JanusStack (after refactor)

```
1. amplify_app (CfnApp only, if enabled)     ← NEW
2. resolve frontend_domain                     ← NEW (single place)
3. table, queues
4. documents_bucket(frontend_domain)           ← parameter instead of os.environ
5. bundling, cognito(frontend_domain)          ← parameter instead of os.environ
6. lambdas
7. api(frontend_domain)                        ← parameter instead of os.environ
8. amplify_branch(api.url)                     ← NEW (Phase 2)
9. appsync, monitoring, outputs
```

### Environment Variables on Amplify

**App-level (shared across branches):**
- `NEXTAUTH_SECRET` — from deploy-time env var
- `_CUSTOM_IMAGE` = `amplify:al2023` — required for Next.js 14 SSR

**Branch-level:**
- `BACKEND_URL` — API Gateway URL (CDK token)
- `NEXTAUTH_URL` — auto-detected by NextAuth from Host header
- `NEXT_PUBLIC_COGNITO_USER_POOL_ID` — from Cognito construct
- `NEXT_PUBLIC_COGNITO_CLIENT_ID` — from Cognito construct

### What's NOT Changing

- No auth rewrite (NextAuth + Cognito stays)
- No PR preview deployments (add later)
- No custom domain (Amplify-generated URL for now)
- No docker-compose changes (local dev unchanged)
- No E2E test changes
- No frontend code changes (beyond next.config.js)

---

## What to Remove After Migration

| Item | Action |
|---|---|
| `vercel.json` (if exists) | Delete |
| `.vercel/` directory | Delete, add to `.gitignore` |
| Vercel environment variables | Migrate to Amplify/SSM, then delete from Vercel |
| Vercel project | Archive or delete |
| `vercel --prod` deployment command | Replace with GitHub Actions |
| Vercel DNS (if custom domain) | Move to Route53 |

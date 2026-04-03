# Multi-Environment Deployment Plan

## Overview

Deploy Janus to three AWS accounts (one per environment), each with its own full stack: Lambda, DynamoDB, SQS, S3, Cognito, Amplify, AppSync.

| Environment | Git Branch | AWS Account | CDK Environment |
|---|---|---|---|
| Development | `development` | Development account | `staging` |
| Testing | `testing` | Testing account | `testing` |
| Production | `production` | Production account | `production` |

---

## Secrets Inventory

### Org-level (shared across all repos/environments)

| Secret | Purpose | Status |
|---|---|---|
| `DEV_AWS_ACCESS_KEY_ID` | Dev account IAM key | Exists |
| `DEV_AWS_SECRET_ACCESS_KEY` | Dev account IAM secret | Exists |
| `DEV_AWS_ACCOUNT_ID` | Dev account ID | Exists |
| `DEV_AWS_REGION` | Dev region | Exists |
| `TEST_AWS_ACCESS_KEY_ID` | Test account IAM key | Exists |
| `TEST_AWS_SECRET_ACCESS_KEY` | Test account IAM secret | Exists |
| `TEST_AWS_ACCOUNT_ID` | Test account ID | Exists |
| `TEST_AWS_REGION` | Test region | Exists |
| `PROD_AWS_ACCESS_KEY_ID` | Prod account IAM key | Exists |
| `PROD_AWS_SECRET_ACCESS_KEY` | Prod account IAM secret | Exists |
| `PROD_AWS_ACCOUNT_ID` | Prod account ID | Exists |
| `PROD_AWS_REGION` | Prod region | Exists |
| `DEV_OPENAI_API_KEY` | OpenAI key (dev) | Exists |
| `TEST_OPENAI_API_KEY` | OpenAI key (testing) | Exists |
| `PROD_OPENAI_API_KEY` | OpenAI key (production) | Exists |
| `ANTHROPIC_API_KEY` | Anthropic key (not in use) | Exists |
| `AMPLIFY_DEPLOYMENT` | GitHub PAT for Amplify repo access | Exists |

### Repo-level (shared across all environments)

| Secret | Purpose | Status |
|---|---|---|
| `SIGNALFIELD_CORE_DEPLOY_KEY` | SSH key for signalfield-core | Exists |
| `APP_ID` | GitHub App ID (unused) | Exists (legacy) |
| `APP_PRIVATE_KEY` | GitHub App key (unused) | Exists (legacy) |
| `NEXTAUTH_SECRET` | **Currently repo-level — must move to per-env** | Action needed |

### Per-environment (GitHub environment secrets)

| Secret | Staging | Testing | Production |
|---|---|---|---|
| `NEXTAUTH_SECRET` | **Move from repo** | **Create** | **Create** |

### Cleanup

| Action | Reason |
|---|---|
| Remove `NEXTAUTH_SECRET` from repo-level | Moving to per-env for isolation |
| Remove `FRONTEND_DOMAIN` from staging env | Dead — Amplify CDK token handles CORS |
| Remove `DEV_AWS_*` from staging env | Redundant — org-level already has them |

---

## Code Changes

### New Files

| File | Purpose |
|---|---|
| `.github/workflows/deploy-testing.yml` | Auto-deploy on push to `testing` branch |
| `.github/workflows/deploy-production.yml` | Auto-deploy on push to `production` branch |

### Modified Files

| File | Change |
|---|---|
| `.github/workflows/deploy-backend.yml` | Use org-level `DEV_*` secrets, read `NEXTAUTH_SECRET` from staging env |
| `scripts/deploy-aws.sh` | Accept `testing` as valid environment |

### No Changes Needed

- `infrastructure/app.py` — already has testing + production configs
- `infrastructure/stacks/*.py` — environment-agnostic
- `backend/` — no code changes
- `docker-compose*.yml` — local dev only
- E2E tests — run in CI on PRs, not per-environment

---

## GitHub Environments to Create

### Testing

- Create in: Settings → Environments → New environment → `testing`
- Protection rules: Optional (require 1 approval recommended)
- Secret: `NEXTAUTH_SECRET` (unique value)

### Production

- Create in: Settings → Environments → New environment → `production`
- Protection rules: Required (2 approvals, branch restricted to `production`)
- Secret: `NEXTAUTH_SECRET` (unique value)

---

## Deployment Workflows

### Development (existing, updated)

```
Push to development → CI checks → deploy-backend.yml
  → CDK deploy Janus-staging to DEV AWS account
  → Amplify auto-builds development branch
```

### Testing (new)

```
Merge PR to testing → CI checks → deploy-testing.yml
  → CDK deploy Janus-testing to TEST AWS account
  → Amplify auto-builds testing branch
```

### Production (new)

```
Merge PR to production (2 approvals) → CI checks → deploy-production.yml
  → CDK deploy Janus-production to PROD AWS account
  → Amplify auto-builds production branch
```

---

## CDK Environment Configs (already in app.py)

| Setting | Development | Testing | Production |
|---|---|---|---|
| Removal policy | DESTROY | SNAPSHOT | RETAIN |
| Log retention | 7 days | 30 days | 90 days |
| Monitoring | Off | On | On |
| PITR | Off | Off | On |
| Lambda arch | arm64 | x86_64 | x86_64 |
| API rate limit | 50/100 | 50/100 | 100/200 |
| Amplify branch | `development` | `testing` | `production` |

---

## Frontend Considerations

### Amplify (per environment)

Each CDK deploy creates a separate Amplify app in its AWS account. The Amplify app:
- Connects to GitHub via `AMPLIFY_DEPLOYMENT` PAT
- Auto-builds when its configured branch receives a push
- Gets its own unique URL: `https://{branch}.d{id}.amplifyapp.com`

### Environment Variables (auto-wired by CDK)

All frontend env vars are set automatically by the AmplifyConstruct:

| Variable | Source | Notes |
|---|---|---|
| `BACKEND_URL` | API Gateway URL from same CDK stack | Different per account |
| `NEXTAUTH_SECRET` | Per-env GitHub secret | Unique per environment |
| `NEXTAUTH_URL` | Amplify branch URL | Auto-generated |
| `NEXT_PUBLIC_COGNITO_USER_POOL_ID` | Cognito in same CDK stack | Different per account |
| `NEXT_PUBLIC_COGNITO_CLIENT_ID` | Cognito in same CDK stack | Different per account |

### What's Baked at Build Time (`.env.production`)

The Amplify build spec writes these to `.env.production`:
- `NEXTAUTH_SECRET`, `NEXTAUTH_URL` — server-side, needed at SSR runtime
- `BACKEND_URL` — server-side, needed at SSR runtime
- `NEXT_PUBLIC_COGNITO_USER_POOL_ID`, `NEXT_PUBLIC_COGNITO_CLIENT_ID` — client-side, inlined at build

### No Frontend Code Changes

The frontend is fully environment-agnostic. All environment-specific values come from env vars injected by CDK → Amplify. No hardcoded URLs, no environment checks in code.

### Cognito Users Are Per-Environment

Each environment has its own Cognito User Pool. Users created in development don't exist in testing or production. After first deploy to testing/production, you'll need to:
1. Create the first admin user via Cognito Console or CLI
2. Or use the signup flow on the deployed frontend

### Custom Domains (future)

For production, you'll likely want a custom domain (e.g., `app.sc0red.com`) instead of the Amplify-generated URL. This is configured via Amplify Console → Custom domains → Route53. Not needed for initial deployment.

---

## Implementation Order

| Step | What | Who |
|---|---|---|
| 1 | Create `testing` + `production` GitHub environments | You (GitHub UI) |
| 2 | Set unique `NEXTAUTH_SECRET` per environment | You (I generate values) |
| 3 | Create deploy workflow files + update existing | Me (PR) |
| 4 | Move `NEXTAUTH_SECRET` from repo to staging env | You (GitHub UI) |
| 5 | Clean up dead staging secrets | You (GitHub UI) |
| 6 | Deploy to testing (merge to testing branch) | You |
| 7 | Verify testing environment works | You |
| 8 | Deploy to production (merge to production branch) | You |
| 9 | Set up production branch protection | You (GitHub UI) |

---

## Cost Estimate (Monthly)

| Environment | Estimate | Notes |
|---|---|---|
| Testing | $5-18 | Mostly free tier, light usage |
| Production | $25-100 | Depends on traffic, PITR adds ~20% to DynamoDB |
| **Additional total** | **$30-120** | On top of existing development costs |

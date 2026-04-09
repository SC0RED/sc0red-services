# Playwright E2E Test Automation

**Impact**: High | **Effort**: Medium-High (~2-3 days) | **Priority**: Next

## Problem

No manual QA team. 951 unit tests cover component behavior and API logic, but nothing tests the app as a user sees it — SSR rendering, middleware redirects, real authentication, multi-page flows, and real AI pipeline execution. Bugs that only appear when all layers interact (Amplify SSR → NextAuth → API routes → Lambda → DynamoDB → Cognito) are invisible until a human manually clicks through the app.

## Proposal

Add Playwright browser-based E2E tests at three levels: local (PR gate), smoke (post-deploy dev), and full deployed (post-deploy testing — final gate before production).

## Architecture

### Three Test Projects

**1. Local E2E (docker-compose) — runs on every PR to testing/production**
- Uses existing docker-compose.e2e.yml stack (LocalStack, mock AI, mock JWKS)
- Mock authentication (no real Cognito)
- All user flows tested: register, login, scan, results, team management
- Fast (~3-5 min), deterministic, blocks merge on failure
- Retries: 2

**2. Smoke (deployed dev) — runs after every deploy to dev**
- Tests against real Amplify URL + real Cognito
- Read-heavy: register test user, login, navigate pages, verify content loads
- No scan (save AI credits)
- Cleanup: delete test user + data after run
- Alerts on failure (doesn't block anything)
- Retries: 2

**3. Full Deployed (deployed testing) — runs after every deploy to testing**
- Tests against real Amplify URL + real Cognito + real AI pipeline
- Full flows: register, login, start scan, wait for AI results, verify analysis
- Team management: invite, list, revoke
- Session expiry: verify redirect to login
- Burns AI credits (~$0.10-0.50 per run — acceptable)
- Cleanup: delete all test data (Cognito user + DynamoDB records)
- THIS IS THE FINAL GATE BEFORE PRODUCTION
- Retries: 2

### No Tests on Production

Production is fully gated by the testing environment. If full E2E passes on testing, it deploys to production without additional tests. This avoids test data pollution and AI cost on production.

### Visual Regression — Deferred

Screenshot comparison will be explored separately after functional E2E is stable.

## Test Suite

### Local E2E (7 spec files)

| Spec | What it tests |
|---|---|
| `auth.spec.ts` | Register new account, login, logout |
| `dashboard.spec.ts` | Empty state, stats cards, recent tables |
| `standalone-scan.spec.ts` | Enter URL → progress bar → analysis results |
| `portfolio-scan.spec.ts` | Enter PE URL → discover companies → confirm → portfolio view |
| `analysis-detail.spec.ts` | Risk breakdown, opportunities, EBITDA tree, value chain |
| `team-management.spec.ts` | Invite member, list members, revoke invitation |
| `navigation.spec.ts` | Breadcrumbs, sidebar nav, session expiry redirect |

### Smoke — Deployed Dev (3 spec files)

| Spec | What it tests |
|---|---|
| `health.spec.ts` | Landing page loads, login page loads |
| `auth.spec.ts` | Register → login → see dashboard → cleanup |
| `navigation.spec.ts` | Navigate authenticated pages, verify content |

### Full Deployed — Testing (6 spec files)

| Spec | What it tests |
|---|---|
| `auth.spec.ts` | Register → login → dashboard |
| `standalone-scan.spec.ts` | Full scan with real AI → verify risk scores + opportunities |
| `analysis-detail.spec.ts` | EBITDA tree present, value chain present, opportunities listed |
| `team-management.spec.ts` | Invite → list → revoke |
| `session-expiry.spec.ts` | Expired token → redirect to login (no infinite loop) |
| `cleanup.spec.ts` | Delete test org, user, data from Cognito + DynamoDB |

## Test Data Lifecycle

### Local (mock environment)
- Register user via API at test start
- All data in LocalStack (ephemeral, docker-compose down -v clears everything)
- No cleanup needed

### Deployed (real environment)
```
Setup:
  1. Register: POST /api/auth/register
     email: e2e-{timestamp}@janus-test.com
     orgName: "E2E Test Org {timestamp}"
  2. Login via Cognito USER_PASSWORD_AUTH
  3. Save auth cookies (Playwright storage state)

Tests run...

Cleanup (always runs, even on failure):
  4. Delete companies: DELETE /api/analysis/{id} for each
  5. Delete scans: DELETE /api/scan/{id} for each  
  6. Delete Cognito user: boto3 admin_delete_user
  7. Delete DynamoDB records: org, user, invitations
  → Implemented as cleanup.spec.ts (runs last via Playwright project dependencies)
  → Also as standalone script: scripts/e2e-cleanup.py (failsafe)
```

## CI Integration

### PR to testing/production
```yaml
# In pull-request.yml — new job
playwright-local:
  runs-on: ubuntu-latest
  steps:
    - docker compose -f docker-compose.e2e.yml up -d
    - npx playwright install --with-deps chromium
    - npx playwright test --project=local
    - docker compose -f docker-compose.e2e.yml down -v
```

### Post-deploy to dev
```yaml
# In deploy-backend.yml — new job after deploy
smoke-test:
  needs: deploy
  runs-on: ubuntu-latest
  steps:
    - npx playwright install --with-deps chromium
    - PLAYWRIGHT_BASE_URL=<amplify-dev-url> npx playwright test --project=smoke
```

### Post-deploy to testing
```yaml
# In deploy-testing.yml — new job after deploy
e2e-deployed:
  needs: deploy
  runs-on: ubuntu-latest
  steps:
    - npx playwright install --with-deps chromium
    - PLAYWRIGHT_BASE_URL=<amplify-testing-url> npx playwright test --project=deployed
    - python scripts/e2e-cleanup.py  # failsafe cleanup
```

## File Structure

```
frontend/
├── playwright.config.ts
├── e2e/
│   ├── local/
│   │   ├── auth.spec.ts
│   │   ├── dashboard.spec.ts
│   │   ├── standalone-scan.spec.ts
│   │   ├── portfolio-scan.spec.ts
│   │   ├── analysis-detail.spec.ts
│   │   ├── team-management.spec.ts
│   │   └── navigation.spec.ts
│   ├── smoke/
│   │   ├── health.spec.ts
│   │   ├── auth.spec.ts
│   │   └── navigation.spec.ts
│   ├── deployed/
│   │   ├── auth.spec.ts
│   │   ├── standalone-scan.spec.ts
│   │   ├── analysis-detail.spec.ts
│   │   ├── team-management.spec.ts
│   │   ├── session-expiry.spec.ts
│   │   └── cleanup.spec.ts
│   └── setup/
│       ├── local-auth.setup.ts
│       └── deployed-auth.setup.ts
├── playwright/
│   └── .auth/                      ← Saved auth state (gitignored)
scripts/
└── e2e-cleanup.py                  ← Failsafe cleanup (boto3)
```

## Playwright Config Highlights

```typescript
// playwright.config.ts
{
  retries: 2,
  projects: [
    {
      name: 'local-setup',
      testDir: './e2e/setup',
      testMatch: 'local-auth.setup.ts',
    },
    {
      name: 'local',
      testDir: './e2e/local',
      dependencies: ['local-setup'],
      use: { baseURL: 'http://localhost:3000' },
    },
    {
      name: 'deployed-setup',
      testDir: './e2e/setup',
      testMatch: 'deployed-auth.setup.ts',
    },
    {
      name: 'smoke',
      testDir: './e2e/smoke',
      dependencies: ['deployed-setup'],
      use: { baseURL: process.env.PLAYWRIGHT_BASE_URL },
    },
    {
      name: 'deployed',
      testDir: './e2e/deployed',
      dependencies: ['deployed-setup'],
      use: { baseURL: process.env.PLAYWRIGHT_BASE_URL },
    },
  ],
}
```

## What We DON'T Do

- No tests on production (fully gated by testing env)
- No visual regression (deferred — separate effort)
- No mobile browser testing (desktop Chromium only for now)
- No cross-browser testing (Chromium only — can add Firefox/WebKit later)
- No load/performance testing (separate concern)
- No API-only Playwright tests (existing E2E script + pytest cover this)

## Success Criteria

- [ ] Playwright installed and configured with 3 projects
- [ ] Local E2E: 7 spec files covering all critical user journeys
- [ ] Smoke: 3 spec files for post-deploy dev verification
- [ ] Full deployed: 6 spec files with real AI scan on testing env
- [ ] Cleanup script: Cognito + DynamoDB test data removal
- [ ] CI integration: local blocks PR merge, deployed runs post-deploy
- [ ] Retries: 2 per test for flakiness tolerance
- [ ] All existing 951 unit tests continue to pass

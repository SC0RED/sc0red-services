# E2E Testing Guide

End-to-end tests verify Janus as a user sees it — real browser interactions across SSR rendering, authentication, API calls, and AI pipeline execution.

---

## Architecture

```
                    ┌─────────────────────────────────────────┐
                    │            Test Pyramid                  │
                    ├─────────────────────────────────────────┤
                    │                                         │
                    │      ┌──────────────────────┐          │
                    │      │  Deployed E2E (14)    │ ← testing│
                    │      │  Real Cognito + AI    │   env    │
                    │      ├──────────────────────┤          │
                    │      │  Smoke (10)           │ ← dev    │
                    │      │  Real Cognito         │   env    │
                    │    ┌─┴──────────────────────┴─┐        │
                    │    │  Local E2E (28)           │ ← PR   │
                    │    │  Mock AI, Mock Auth       │   gate  │
                    │  ┌─┴──────────────────────────┴─┐      │
                    │  │  Unit Tests (390+)            │      │
                    │  │  Vitest + RTL                 │      │
                    │  └──────────────────────────────┘      │
                    └─────────────────────────────────────────┘
```

| Mode | Environment | Auth | AI | When | Tests |
|------|------------|------|----|------|-------|
| `local` | docker-compose (LocalStack + mock AI) | Mock JWKS + crafted cookies | Mock OpenAI | Every PR (CI) + manual | 28 |
| `smoke` | Deployed dev (Amplify + Lambda) | Real Cognito (signup via UI) | None (read-only) | Post-deploy dev (CI) + manual | 10 |
| `deployed` | Deployed testing (Amplify + Lambda) | Real Cognito (signup via UI) | Real OpenAI | Post-deploy testing (CI) + manual | 14 |

---

## First-Time Setup

Before running any Playwright tests, install dependencies and browsers from the `frontend/` directory:

```bash
cd frontend
npm install
npx playwright install chromium
cd ..
```

---

## Quick Start

```bash
# Run all local tests (starts docker, runs tests, tears down)
./scripts/playwright.sh --mode=local

# Watch tests in a visible Chrome browser
./scripts/playwright.sh --mode=local --headed

# Run smoke tests against deployed dev
./scripts/playwright.sh --mode=smoke --url=https://dev.advisory.sc0red.com

# Run full E2E against deployed (uses real AI)
./scripts/playwright.sh --mode=deployed --url=https://dev.advisory.sc0red.com
```

Or use npm shortcuts from the `frontend/` directory:

```bash
npm run e2e:local          # Same as --mode=local
npm run e2e:headed         # Same as --mode=local --headed
npm run e2e:ui             # Same as --mode=local --ui
npm run e2e:visual         # Same as --mode=local --visual
npm run e2e:visual-update  # Same as --mode=local --visual-update
```

---

## Running Locally

### Prerequisites

| Requirement | Needed for | Install |
|-------------|-----------|---------|
| Docker Desktop | `--mode=local` | https://www.docker.com/products/docker-desktop |
| Node.js 20+ | All modes | https://nodejs.org |
| Python 3.12 | `--mode=local` (infra setup) | https://www.python.org |
| `boto3` | `--mode=local` (infra setup), all modes (cleanup) | `pip install boto3` |
| AWS credentials | `--mode=smoke`, `--mode=deployed` (cleanup) | `aws configure` or env vars |
| GitHub CLI | `--mode=local` (docker build) | `brew install gh` |
| Playwright browsers | All modes | `npx playwright install chromium` |

### Local Mode

Runs against docker-compose with mock AI and mock auth. The script manages the full lifecycle:

```
Start docker-compose.e2e.yml
    → Wait for backend health check
    → Create DynamoDB table + SQS queue + S3 bucket
    → Start Next.js dev server
    → Run Playwright tests (28 tests)
    → Tear down everything (even on failure)
```

```bash
# Ensure Docker is running, then:
./scripts/playwright.sh --mode=local
```

The script automatically:
- Builds and starts the docker stack (backend, worker, LocalStack, mock AI)
- Provisions DynamoDB, SQS, and S3 on LocalStack
- Starts the Next.js dev server with correct env vars
- Runs all local Playwright projects (local, local-post-scan, local-expiry)
- Tears down docker and kills Next.js on completion or failure

### Smoke Mode

Runs against a real deployed environment. Tests signup, login, navigation — no scans (saves AI credits).

```bash
./scripts/playwright.sh --mode=smoke --url=https://dev.advisory.sc0red.com
```

Requires:
- `--url` pointing to a deployed sc0red Advisory frontend
- The deployed backend must be running (Amplify + Lambda)
- Real Cognito user pool must be available (tests register via the signup UI)

**Cleanup:** Smoke tests create a real Cognito user and DynamoDB org. Cleanup runs automatically after tests (requires AWS credentials). The script auto-discovers the Cognito user pool and DynamoDB table by naming convention (`janus-users-*` and `janus-*`). Pass `--skip-cleanup` to disable:

```bash
# Cleanup runs by default
./scripts/playwright.sh --mode=smoke --url=https://dev.advisory.sc0red.com

# Skip cleanup if needed
./scripts/playwright.sh --mode=smoke --url=https://dev.advisory.sc0red.com --skip-cleanup
```

### Deployed Mode

Full E2E with real Cognito and real AI. Creates a scan against `stripe.com` and verifies results.

```bash
./scripts/playwright.sh --mode=deployed --url=https://dev.advisory.sc0red.com
```

This mode:
- Registers a real user via the signup page
- Runs a full scan with real AI (takes 1–3 minutes)
- Verifies analysis results (risk scores, EBITDA, value chain)
- Cleans up test data after completion (auto-discovers Cognito pool + DynamoDB table)

Requires:
- `--url` pointing to a deployed sc0red Advisory frontend
- AWS credentials configured (for cleanup — pass `--skip-cleanup` if unavailable)

---

## Browser Modes

Playwright supports several ways to watch and debug tests:

| Flag | Description |
|------|-------------|
| `--headed` | Launches a visible Chrome window — watch tests execute in real-time |
| `--ui` | Opens the Playwright Test UI — interactive runner with time-travel debugging, step through each action |
| `--debug` | Opens Playwright Inspector — step through tests line by line with breakpoints |

Examples:

```bash
# Watch tests run in Chrome
./scripts/playwright.sh --mode=local --headed

# Interactive debugger with time-travel
./scripts/playwright.sh --mode=local --ui

# Step-by-step debugging with inspector
./scripts/playwright.sh --mode=local --debug

# Watch smoke tests on deployed dev
./scripts/playwright.sh --mode=smoke --url=https://dev.example.com --headed
```

---

## Visual Regression

Visual regression captures screenshots of key pages and compares against baselines. It's triggered only by explicit flags — never runs in CI.

### First-time setup

Generate baseline screenshots:

```bash
./scripts/playwright.sh --mode=local --visual-update
```

This creates baseline PNGs in `frontend/e2e/__screenshots__/`. Commit these to git.

### Running comparisons

```bash
./scripts/playwright.sh --mode=local --visual
```

If a page's appearance changed beyond the 1% pixel threshold, the test fails and produces a diff image showing what changed.

### Updating baselines

After intentional UI changes, regenerate baselines:

```bash
./scripts/playwright.sh --mode=local --visual-update
git add frontend/e2e/__screenshots__/
git commit -m "chore: update visual regression baselines"
```

### What's captured

| Page | Screenshot name | Project |
|------|----------------|---------|
| Login | `login-page.png` | local-visual |
| Signup | `signup-page.png` | local-visual |
| Dashboard (empty) | `dashboard-empty.png` | local-visual |
| Scan input | `scan-input.png` | local-visual |
| Team management | `team-page.png` | local-visual |
| Analysis detail | `analysis-detail.png` | local-visual-post-scan |
| Dashboard (with data) | `dashboard-with-data.png` | local-visual-post-scan |

### Smoke visual

Visual regression also works against deployed environments:

```bash
./scripts/playwright.sh --mode=smoke --url=https://dev.example.com --visual
./scripts/playwright.sh --mode=smoke --url=https://dev.example.com --visual-update
```

---

## CI Integration

Visual regression is **not** part of CI. Here's what runs automatically:

### PR Gate (every pull request)

**Workflow:** `pull-request.yml` → Playwright job

```
Projects: local + local-post-scan + local-expiry
Tests: 28 (functional only, no visual)
Blocks merge on failure
```

### Post-deploy to dev (development branch)

**Workflow:** `deploy-backend.yml` → Smoke job + Cleanup job

```
Projects: smoke
Tests: 10
Alerts on failure (does not block)
Cleanup: e2e-cleanup.py deletes test users from Cognito + DynamoDB
```

### Post-deploy to testing (testing branch)

**Workflow:** `deploy-testing.yml` → E2E job + Cleanup job

```
Projects: deployed + deployed-post-scan + deployed-cleanup
Tests: 14
Final gate before production
Cleanup: e2e-cleanup.py deletes test users from Cognito + DynamoDB
```

---

## Test Data Lifecycle

### Local mode
- User registered via backend API (no real Cognito)
- All data in LocalStack (ephemeral)
- `docker-compose down -v` clears everything — no manual cleanup needed

### Deployed modes
- User registered via real signup UI → creates Cognito user + DynamoDB org
- `cleanup.spec.ts` deletes analyses/scans via UI delete buttons
- `scripts/e2e-cleanup.py` runs automatically after tests — deletes `e2e-*` Cognito users + their full DynamoDB data graph (user, org, scans, companies, assessments)
- Also detects orphaned DynamoDB records (where Cognito user was already deleted)
- Cleanup runs even when tests fail (`if: always()` in CI)

---

## Adding New Tests

### 1. Choose the right directory

| Directory | Mode | Auth state | Use when |
|-----------|------|-----------|----------|
| `e2e/local/` | local | `./playwright/.auth/local.json` | Testing with mock AI/auth |
| `e2e/smoke/` | smoke | `./playwright/.auth/deployed.json` | Read-only deployed checks |
| `e2e/deployed/` | deployed | `./playwright/.auth/deployed.json` | Full flows with real AI |
| `e2e/visual/` | any | Depends on project | Screenshot comparisons |

### 2. Create the spec file

```typescript
// e2e/local/my-feature.spec.ts
import { test, expect } from '@playwright/test'

test.describe('my feature', () => {
    test('does the thing', async ({ page }) => {
        await page.goto('/my-page')
        await expect(page.getByText('Expected Content')).toBeVisible({ timeout: 10000 })
    })
})
```

### 3. Run it

```bash
# Run just your new test
cd frontend && npx playwright test e2e/local/my-feature.spec.ts --project=local

# Or run the full local suite
./scripts/playwright.sh --mode=local
```

### Tips

- Use `{ timeout: 10000 }` or higher for assertions that depend on API calls
- Use `page.getByRole()`, `page.getByLabel()`, `page.getByText()` over CSS selectors
- Use `.first()` when a locator might match multiple elements
- Use `{ exact: true }` on `getByText()` when substring matches cause strict mode violations
- For tests that need scan data, put them in a separate spec and use the `local-post-scan` project dependency
- For tests that need expired auth, use the `local-expiry` project

# Tasks: Playwright E2E Test Automation

## PR 1: Setup + Local E2E Tests

### Setup
- [x] Install Playwright + configure playwright.config.ts with 3 projects
- [x] Create local auth setup (register via UI, save storage state)
- [x] Add .gitignore entries for Playwright artifacts

### Local E2E Tests
- [x] auth.spec.ts — register, login, logout, redirect
- [x] dashboard.spec.ts — empty state, stats, sidebar navigation
- [x] standalone-scan.spec.ts — URL → progress → results
- [x] portfolio-scan.spec.ts — discover → confirm → progress → results
- [x] analysis-detail.spec.ts — risk breakdown, opportunities, value chain
- [x] team-management.spec.ts — page load, invite form, validation
- [x] navigation.spec.ts — sidebar nav, breadcrumbs, landing page

### CI Integration (local)
- [x] Add playwright-local job to pull-request.yml with summary integration

## PR 2: Deployed Tests + Smoke + Cleanup

### Deployed Auth Setup
- [x] Create deployed auth setup (real Cognito register/login)

### Smoke Tests (dev)
- [x] health.spec.ts — landing + login pages load
- [x] auth.spec.ts — register → login → dashboard → cleanup
- [x] navigation.spec.ts — navigate authenticated pages

### Full Deployed Tests (testing)
- [x] auth.spec.ts — register → login → dashboard
- [x] standalone-scan.spec.ts — full scan with real AI → verify results
- [x] analysis-detail.spec.ts — verify risk scores, EBITDA, value chain present
- [x] team-management.spec.ts — invite → list → revoke
- [x] cleanup.spec.ts — delete all test data

### Cleanup Script
- [x] scripts/e2e-cleanup.py — boto3 Cognito + DynamoDB cleanup

### CI Integration (deployed)
- [x] Add smoke job to deploy-backend.yml (post-deploy dev)
- [x] Add full E2E job to deploy-testing.yml (post-deploy testing)

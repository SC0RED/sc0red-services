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
- [ ] Create deployed auth setup (real Cognito register/login)

### Smoke Tests (dev)
- [ ] health.spec.ts — landing + login pages load
- [ ] auth.spec.ts — register → login → dashboard → cleanup
- [ ] navigation.spec.ts — navigate authenticated pages

### Full Deployed Tests (testing)
- [ ] auth.spec.ts — register → login → dashboard
- [ ] standalone-scan.spec.ts — full scan with real AI → verify results
- [ ] analysis-detail.spec.ts — verify risk scores, EBITDA, value chain present
- [ ] team-management.spec.ts — invite → list → revoke
- [ ] session-expiry.spec.ts — expired token → redirect to login
- [ ] cleanup.spec.ts — delete all test data

### Cleanup Script
- [ ] scripts/e2e-cleanup.py — boto3 Cognito + DynamoDB cleanup

### CI Integration (deployed)
- [ ] Add smoke job to deploy-backend.yml (post-deploy dev)
- [ ] Add full E2E job to deploy-testing.yml (post-deploy testing)

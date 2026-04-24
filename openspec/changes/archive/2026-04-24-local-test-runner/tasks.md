## 1. Runner Script

- [x] 1.1 Create `scripts/playwright.sh` with argument parsing (`--mode`, `--url`, `--headed`, `--ui`, `--debug`, `--visual`, `--visual-update`)
- [x] 1.2 Implement local mode: docker-compose lifecycle (build, up, health wait, infra setup, Next.js start, run, teardown)
- [x] 1.3 Implement smoke mode: validate `--url`, run smoke project with `PLAYWRIGHT_BASE_URL`
- [x] 1.4 Implement deployed mode: validate `--url`, run deployed + deployed-post-scan + deployed-cleanup projects
- [x] 1.5 Implement `--visual` / `--visual-update` flag: append visual project to the run, pass `--update-snapshots` when updating
- [x] 1.6 Implement Playwright flag passthrough (`--headed`, `--ui`, `--debug`)
- [x] 1.7 Add trap handler for cleanup on failure/interrupt in local mode

## 2. Visual Regression

- [x] 2.1 Add `local-visual` and `smoke-visual` projects to `playwright.config.ts` (depend on respective setup projects)
- [x] 2.2 Create `frontend/e2e/visual/local.spec.ts` with `toHaveScreenshot()` for key pages (login, signup, dashboard, scan input, team)
- [x] 2.3 Create `frontend/e2e/visual/post-scan.spec.ts` with `toHaveScreenshot()` for analysis detail page (depends on local project for data)
- [x] 2.4 Create `frontend/e2e/visual/smoke.spec.ts` with `toHaveScreenshot()` for deployed pages
- [x] 2.5 Configure screenshot settings: `maxDiffPixelRatio: 0.01`, `animations: 'disabled'`, viewport `1280x720`
- [x] 2.6 Generate initial baseline screenshots using `--visual-update`
- [x] 2.7 Add `frontend/e2e/__screenshots__/` to git (baselines) and add diff output dirs to `.gitignore`

## 3. npm Convenience Scripts

- [x] 3.1 Add `e2e`, `e2e:local`, `e2e:headed`, `e2e:ui`, `e2e:visual` scripts to `frontend/package.json`

## 4. Documentation

- [x] 4.1 Create `docs/e2e-testing.md` with test architecture overview and diagram
- [x] 4.2 Add quick start section with one command per mode
- [x] 4.3 Add running locally section: prerequisites, local mode walkthrough, smoke mode, deployed mode
- [x] 4.4 Add headed/UI/debug mode section with all Playwright flags
- [x] 4.5 Add visual regression section: how to run, update baselines, interpret diffs
- [x] 4.6 Add CI integration section: what runs where (PR gate, post-deploy dev, post-deploy testing)
- [x] 4.7 Add "Adding New Tests" section with examples
- [x] 4.8 Update `docs/developer-guide.md` E2E section to reference new doc

## 5. Verification

- [x] 5.1 Run `./scripts/playwright.sh --mode=local` end-to-end (all 28 tests pass)
- [x] 5.2 Run `./scripts/playwright.sh --mode=local --headed` (browser visible) — verified
- [x] 5.3 Run `./scripts/playwright.sh --mode=local --visual-update` (baselines generated)
- [x] 5.4 Run `./scripts/playwright.sh --mode=local --visual` (comparisons pass)
- [x] 5.5 Verify npm scripts work (`npm run e2e:local`, `npm run e2e:headed`) — verified

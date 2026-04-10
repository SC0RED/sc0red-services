## Why

Running Playwright E2E tests locally requires tribal knowledge — which docker-compose to start, which env vars to set, which `--project=` flags to pass, and manual DynamoDB/SQS setup. There's no single entry point, no way to watch tests in a real browser, and no visual regression capability. Developers need a one-command experience that handles all of this, with explicit mode selection to avoid accidentally running against the wrong environment.

## What Changes

- **New runner script** (`scripts/playwright.sh`): Single entry point for all Playwright E2E tests with `--mode=local|smoke|deployed` (required flag), full docker lifecycle management for local mode (start, setup infra, run, tear down), and passthrough for `--headed`/`--ui`/`--debug` flags.
- **Visual regression**: New `--visual` and `--visual-update` flags that add screenshot comparison tests. Works with any mode. Baselines committed to git. Not run in CI — manual local check only.
- **Visual regression specs**: New spec files using `toHaveScreenshot()` for 7 key pages (login, signup, dashboard empty/with-data, analysis detail, scan input, team).
- **npm convenience scripts**: `npm run e2e`, `npm run e2e:local`, `npm run e2e:headed` shortcuts in package.json.
- **Comprehensive documentation** (`docs/e2e-testing.md`): Full guide covering test architecture, all modes, prerequisites, commands, visual regression, debugging tips, CI integration, and how to add new tests.
- **Update developer-guide.md**: Replace brief E2E section with pointer to new comprehensive doc.

## Capabilities

### New Capabilities
- `test-runner`: Unified shell script that orchestrates docker lifecycle, infra setup, Next.js server, and Playwright execution across all test modes
- `visual-regression`: Screenshot comparison testing using Playwright's `toHaveScreenshot()` with baseline management, triggered only via explicit `--visual` flag
- `e2e-documentation`: Comprehensive standalone documentation for the full E2E testing strategy

### Modified Capabilities

## Impact

- **New files**: `scripts/playwright.sh`, `docs/e2e-testing.md`, `frontend/e2e/visual/*.spec.ts`
- **Modified files**: `frontend/package.json` (new scripts), `frontend/playwright.config.ts` (visual projects), `docs/developer-guide.md` (updated E2E section)
- **No CI changes**: Visual regression is manual-only. Existing CI pipelines unchanged.
- **No production code changes**: This is purely test infrastructure.

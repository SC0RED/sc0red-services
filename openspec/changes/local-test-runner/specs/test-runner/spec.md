## ADDED Requirements

### Requirement: Explicit mode selection
The runner script SHALL require a `--mode` flag with one of `local`, `smoke`, or `deployed`. The script SHALL exit with usage help and a non-zero exit code if `--mode` is not provided.

#### Scenario: No mode provided
- **WHEN** the user runs `./scripts/playwright.sh` without `--mode`
- **THEN** the script prints usage help showing all modes and flags, and exits with code 1

#### Scenario: Invalid mode provided
- **WHEN** the user runs `./scripts/playwright.sh --mode=invalid`
- **THEN** the script prints an error message and usage help, and exits with code 1

### Requirement: Local mode orchestrates full docker lifecycle
In `--mode=local`, the script SHALL start docker-compose.e2e.yml, wait for backend health, provision DynamoDB table + SQS queue + S3 bucket, start the Next.js dev server, run the local Playwright projects, then tear down docker-compose (with volumes) and kill the Next.js process.

#### Scenario: Successful local run
- **WHEN** the user runs `./scripts/playwright.sh --mode=local` with Docker running
- **THEN** the script starts docker-compose, provisions infra, starts Next.js, runs `local` + `local-post-scan` + `local-expiry` projects, then tears down all services

#### Scenario: Docker not running
- **WHEN** the user runs `./scripts/playwright.sh --mode=local` without Docker running
- **THEN** the script prints an error message asking the user to start Docker, and exits with code 1

#### Scenario: Teardown on test failure
- **WHEN** Playwright tests fail in local mode
- **THEN** the script still tears down docker-compose and kills Next.js before exiting with the Playwright exit code

### Requirement: Smoke mode requires URL
In `--mode=smoke`, the script SHALL require `--url` to specify the deployed frontend URL. It SHALL run the `smoke` project against that URL.

#### Scenario: Smoke mode with URL
- **WHEN** the user runs `./scripts/playwright.sh --mode=smoke --url=https://dev.example.com`
- **THEN** the script runs the `smoke` Playwright project with `PLAYWRIGHT_BASE_URL` set to the provided URL

#### Scenario: Smoke mode without URL
- **WHEN** the user runs `./scripts/playwright.sh --mode=smoke` without `--url`
- **THEN** the script prints an error message and exits with code 1

### Requirement: Deployed mode requires URL
In `--mode=deployed`, the script SHALL require `--url` and run the `deployed`, `deployed-post-scan`, and `deployed-cleanup` projects.

#### Scenario: Deployed mode with URL
- **WHEN** the user runs `./scripts/playwright.sh --mode=deployed --url=https://testing.example.com`
- **THEN** the script runs `deployed` + `deployed-post-scan` + `deployed-cleanup` projects with `PLAYWRIGHT_BASE_URL` set to the provided URL

### Requirement: Playwright flag passthrough
The script SHALL pass `--headed`, `--ui`, and `--debug` flags through to the `npx playwright test` command when provided.

#### Scenario: Headed mode
- **WHEN** the user runs `./scripts/playwright.sh --mode=local --headed`
- **THEN** Playwright launches a visible Chrome browser window for each test

#### Scenario: UI mode
- **WHEN** the user runs `./scripts/playwright.sh --mode=local --ui`
- **THEN** Playwright launches the interactive test runner with time-travel debugging

### Requirement: npm convenience scripts
The frontend package.json SHALL include scripts that delegate to the runner script for common operations.

#### Scenario: npm run e2e:local
- **WHEN** the user runs `npm run e2e:local` from the frontend directory
- **THEN** it executes `../scripts/playwright.sh --mode=local`

#### Scenario: npm run e2e:headed
- **WHEN** the user runs `npm run e2e:headed` from the frontend directory
- **THEN** it executes `../scripts/playwright.sh --mode=local --headed`

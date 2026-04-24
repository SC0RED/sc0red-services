# visual-regression Specification

## Purpose
TBD - created by archiving change local-test-runner. Update Purpose after archive.
## Requirements
### Requirement: Visual regression triggered by explicit flag
Visual regression tests SHALL only run when the `--visual` or `--visual-update` flag is passed. They SHALL NOT run in CI or when flags are omitted.

#### Scenario: Normal run without visual flag
- **WHEN** the user runs `./scripts/playwright.sh --mode=local` (no `--visual`)
- **THEN** only functional tests run, no screenshot comparisons are performed

#### Scenario: Run with visual flag
- **WHEN** the user runs `./scripts/playwright.sh --mode=local --visual`
- **THEN** functional tests run AND visual regression tests run, comparing against baselines

#### Scenario: Update baselines
- **WHEN** the user runs `./scripts/playwright.sh --mode=local --visual-update`
- **THEN** visual regression tests run and overwrite baseline screenshots with current captures

### Requirement: Visual regression works with any mode
The `--visual` flag SHALL work with `--mode=local`, `--mode=smoke`, and `--mode=deployed`.

#### Scenario: Visual on local mode
- **WHEN** the user runs `./scripts/playwright.sh --mode=local --visual`
- **THEN** the `local-visual` Playwright project runs after functional local tests

#### Scenario: Visual on smoke mode
- **WHEN** the user runs `./scripts/playwright.sh --mode=smoke --url=https://... --visual`
- **THEN** the `smoke-visual` Playwright project runs after smoke tests

### Requirement: Key pages captured
Visual regression SHALL capture screenshots of these pages: login, signup, dashboard (empty state), analysis detail, scan input page, team management page.

#### Scenario: All pages captured in local visual run
- **WHEN** the user runs visual regression in local mode
- **THEN** screenshots are captured for login, signup, dashboard, analysis detail, scan input, and team pages

### Requirement: Screenshot baselines stored in git
Baseline screenshots SHALL be stored in `frontend/e2e/__screenshots__/` and committed to the repository. The `--visual-update` flag SHALL overwrite these baselines.

#### Scenario: First-time visual run
- **WHEN** the user runs `--visual` and no baselines exist
- **THEN** the test fails with a message indicating baselines need to be created using `--visual-update`

#### Scenario: Baseline update
- **WHEN** the user runs `--visual-update`
- **THEN** new screenshots are saved as baselines in `frontend/e2e/__screenshots__/`

### Requirement: Pixel diff tolerance
Screenshot comparisons SHALL allow a small tolerance for rendering differences (anti-aliasing, subpixel rendering) using a `maxDiffPixelRatio` threshold.

#### Scenario: Minor rendering difference
- **WHEN** a screenshot differs by less than 1% of pixels from the baseline
- **THEN** the comparison passes

#### Scenario: Significant visual change
- **WHEN** a screenshot differs by more than 1% of pixels from the baseline
- **THEN** the comparison fails and produces a diff image


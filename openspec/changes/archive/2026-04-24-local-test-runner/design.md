## Context

Janus has 28 local Playwright tests, 10 smoke tests, and 14 deployed tests across 3 test modes (local/smoke/deployed). Running these requires knowing which docker-compose to start, env vars to set, infra to provision, and which `--project=` flags to pass. There's no single entry point, no headed browser support exposed, and no visual regression capability.

The Playwright config already defines all projects with correct dependencies. The gap is an orchestration layer that manages the environment and provides a clean CLI.

## Goals / Non-Goals

**Goals:**
- One script (`scripts/playwright.sh`) as the single entry point for all E2E testing
- Explicit `--mode` flag (required) — no accidental runs against wrong environment
- Full docker lifecycle for local mode: build → start → setup infra → run → tear down
- Passthrough for Playwright flags: `--headed`, `--ui`, `--debug`
- Visual regression via `--visual` / `--visual-update` flags (any mode, manual only)
- npm convenience scripts for common combinations
- Comprehensive `docs/e2e-testing.md` documentation

**Non-Goals:**
- CI changes (visual regression is manual-only, CI pipelines stay as-is)
- Cross-browser testing (Chromium only)
- Mobile viewport testing
- Performance/load testing
- Automatic mode detection from env vars

## Decisions

### 1. Shell script vs. Node.js script

**Decision: Bash shell script (`scripts/playwright.sh`)**

Rationale: The script orchestrates docker-compose, curl health checks, python setup scripts, and npx commands. All of these are shell operations. A Node.js wrapper would just exec shell commands anyway. The existing `scripts/e2e-test.sh` follows the same pattern.

Alternative considered: Node.js with `execa` — adds a dependency for no benefit since the logic is orchestration, not computation.

### 2. Mode flag is required (no default)

**Decision: `--mode` must be explicitly provided. Script exits with usage help if omitted.**

Rationale: Running smoke/deployed tests creates real users in real Cognito and burns AI credits. An accidental run without `--mode` should never default to something destructive. Making it required forces the developer to be intentional.

### 3. Docker lifecycle: fully managed in local mode

**Decision: The script starts docker-compose, waits for health, provisions infra, runs tests, then tears everything down (including volumes).**

Rationale: "Start fresh every time" is predictable. The developer doesn't need to remember if the stack is running or which state it's in. The full cycle takes ~30s for docker + ~10s for tests, which is acceptable for a manual local run.

Alternative considered: "Check if running, start if not, leave running after" — more complex, stale state issues if docker containers are from a different branch.

### 4. Visual regression as separate Playwright projects

**Decision: Add `local-visual` and `smoke-visual` projects to playwright.config.ts. The runner script adds these projects only when `--visual` or `--visual-update` is passed.**

Rationale: Keeps visual tests completely separate from functional tests. They use the same auth state (depend on the same setup projects) but run `toHaveScreenshot()` instead of functional assertions. Playwright's built-in screenshot comparison handles diff generation and threshold configuration.

### 5. Screenshot baselines committed to git

**Decision: Store baseline screenshots in `frontend/e2e/__screenshots__/` and commit to git.**

Rationale: Baselines must be shared across developers to be useful. Git handles binary diffs reasonably for small PNGs (10-50KB each). 7 screenshots × 50KB = 350KB total — negligible.

Alternative considered: Git LFS — overkill for <1MB of screenshots.

### 6. Visual regression spec structure

**Decision: One visual spec file per mode (`visual/local.spec.ts`, `visual/smoke.spec.ts`) that navigates to each page and calls `toHaveScreenshot()`.**

Rationale: Visual tests are simple (navigate → screenshot → compare). Grouping by mode rather than by page avoids duplication of auth setup. Each spec captures screenshots of all key pages in sequence.

## Risks / Trade-offs

- **Screenshot flakiness**: CSS animations, loading spinners, or timing can cause pixel diffs. → Mitigation: Use `toHaveScreenshot({ maxDiffPixelRatio: 0.01 })` threshold and add `waitForLoadState('networkidle')` before captures.
- **Platform differences**: Screenshots on macOS vs. Linux CI will differ. → Mitigation: Visual tests are local-only (not in CI), and baselines are per-developer. Use `--visual-update` to regenerate on a new platform.
- **Docker startup time**: Full cycle adds ~30s to each local run. → Mitigation: This is acceptable for manual runs. Developers iterating on a specific test can use `npx playwright test` directly with a pre-running stack.

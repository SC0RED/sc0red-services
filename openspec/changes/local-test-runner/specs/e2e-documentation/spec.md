## ADDED Requirements

### Requirement: Standalone E2E testing guide
A comprehensive document (`docs/e2e-testing.md`) SHALL cover the full E2E testing strategy including test architecture, all modes, prerequisites, commands, visual regression, debugging, CI integration, and how to add new tests.

#### Scenario: Developer wants to run E2E tests
- **WHEN** a developer reads `docs/e2e-testing.md`
- **THEN** they find step-by-step instructions for running tests in every mode with all available options

### Requirement: Documentation covers test architecture
The documentation SHALL include a visual overview of the test pyramid showing unit tests, local E2E, smoke tests, and deployed tests with their triggers and environments.

#### Scenario: Developer wants to understand test strategy
- **WHEN** a developer reads the architecture section
- **THEN** they see a diagram showing which tests run where (PR, post-deploy dev, post-deploy testing) and what each mode uses (mock vs real services)

### Requirement: Documentation covers all runner commands
The documentation SHALL list every combination of `--mode`, `--headed`, `--ui`, `--debug`, `--visual`, and `--visual-update` with examples.

#### Scenario: Developer wants command reference
- **WHEN** a developer looks for how to run headed tests
- **THEN** they find the exact command with explanation

### Requirement: Documentation covers prerequisites per mode
The documentation SHALL specify what each mode requires (Docker, Node.js, GH_TOKEN, deployed URL, etc.).

#### Scenario: Developer setting up for local mode
- **WHEN** a developer reads the local mode prerequisites
- **THEN** they know they need Docker Desktop running and GH_TOKEN available

### Requirement: Developer guide updated with pointer
The existing `docs/developer-guide.md` SHALL update its E2E section to reference the new comprehensive doc rather than duplicating content.

#### Scenario: Developer reads developer guide
- **WHEN** a developer reads the E2E section in developer-guide.md
- **THEN** they see a brief summary and a link to `docs/e2e-testing.md` for full details

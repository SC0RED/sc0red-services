# sc0red Services — Developer Guide

This guide covers everything you need to run sc0red Services locally, understand the test suites, and work within the code quality pipeline.

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Local Development (Docker)](#local-development-docker)
- [Local Development (Without Docker)](#local-development-without-docker)
- [CDK Deployment to LocalStack](#cdk-deployment-to-localstack)
- [Backend Tests](#backend-tests)
- [Frontend Tests](#frontend-tests)
- [End-to-End Tests](#end-to-end-tests)
- [Code Quality Checks](#code-quality-checks)
- [Git Workflow](#git-workflow)
- [Project Conventions](#project-conventions)
- [DynamoDB Data Model](#dynamodb-data-model)
- [AI Pipeline Deep Dive](#ai-pipeline-deep-dive)

---

## Prerequisites

| Tool | Version | Install |
|---|---|---|
| Docker Desktop | Latest | https://www.docker.com/products/docker-desktop |
| Node.js | 20+ | https://nodejs.org |
| Python | 3.12 | https://www.python.org |
| uv | Latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| GitHub CLI | Latest | `brew install gh` |
| npm (aws-cdk) | — | bundled with Node.js |

---

## Local Development (Docker)

The simplest way to run the full stack. All services start in the correct order with health checks.

```bash
# 1. Authenticate with GitHub (needed to pull signalfield-core)
export GH_TOKEN=$(gh auth token)

# 2. Configure your API key (optional — app works without it but AI calls will fail)
echo "ANTHROPIC_API_KEY=sk-ant-..." >> .env

# 3. Start everything
docker compose up --build -d

# 4. Follow logs
docker compose logs -f

# 5. Stop
docker compose down
```

**Service URLs**

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8001/api/health |
| DynamoDB Admin UI | http://localhost:8002 |

**Rebuilding a single service**

```bash
docker compose up backend --build -d --force-recreate
```

**Rotating the Anthropic API key without a full rebuild**

```bash
ANTHROPIC_API_KEY=sk-ant-new-key docker compose up backend -d --force-recreate
```

---

## Local Development (Without Docker)

### Backend

```bash
cd backend

# Install dependencies (reads pyproject.toml)
uv sync

# Start DynamoDB Local (needed for the backend)
docker run -d -p 8000:8000 amazon/dynamodb-local:latest \
    -jar DynamoDBLocal.jar -sharedDb -inMemory

# Copy and edit environment
cp .env.example .env.local
# Set DYNAMODB_ENDPOINT=http://localhost:8000, NEXTAUTH_SECRET=..., etc.

# Run the FastAPI dev server
uv run uvicorn src.local_server:app --reload --port 8001
```

### Frontend

```bash
cd frontend

# Install dependencies
npm install --legacy-peer-deps

# Copy and edit environment
cp .env.local.example .env.local
# Set BACKEND_URL=http://localhost:8001, NEXTAUTH_SECRET=..., NEXTAUTH_URL=http://localhost:3000

# Start Next.js dev server
npm run dev
```

---

## CDK Deployment to LocalStack

For testing the Lambda + API Gateway infrastructure locally.

### One-command deploy

```bash
./scripts/deploy-local.sh
```

This script:
1. Checks prerequisites (Docker, npm, uv, GH_TOKEN)
2. Installs `aws-cdk` and `aws-cdk-local` globally if missing
3. Runs `uv sync` in `infrastructure/`
4. Starts LocalStack via `docker compose --profile localstack up localstack -d`
5. Waits for LocalStack to be ready
6. Bootstraps and deploys the CDK stack
7. Prints the API Gateway URL

### Manual deploy

```bash
cd infrastructure

# Install CDK Python deps
uv sync

# Set AWS credentials for LocalStack
export AWS_ACCESS_KEY_ID=local
export AWS_SECRET_ACCESS_KEY=local
export AWS_DEFAULT_REGION=us-east-1
export CDK_ENVIRONMENT=development
export GH_TOKEN=$(gh auth token)

# Bootstrap (first time only)
cdklocal bootstrap aws://000000000000/us-east-1

# Deploy
cdklocal deploy Sc0redServices-development --require-approval never --outputs-file /tmp/sc0red-services-outputs.json
```

### Known LocalStack limitations

| Issue | Workaround |
|---|---|
| `cdklocal update` stuck at `CREATE_COMPLETE` | Run `cdklocal destroy Sc0redServices-development --force && cdklocal deploy ...` |
| `log_retention` creates unsupported nodejs22.x Lambda | Use explicit `logs.LogGroup` construct — already fixed in `sc0red_services_stack.py` |
| Stack-level tags fail on `EventSourceMapping` | Tags are skipped for `development` environment — already fixed in `app.py` |

### CDK environments

Configured in `infrastructure/app.py`:

| Environment | Removal Policy | Log Retention | Monitoring |
|---|---|---|---|
| `development` | DESTROY | 7 days | Off |
| `staging` | SNAPSHOT | 30 days | On |
| `production` | RETAIN | 90 days | On |

---

## Backend Tests

```bash
cd backend

# Run all tests
uv run pytest

# With coverage report
uv run pytest --cov=src --cov-report=term-missing

# Run a specific test file
uv run pytest tests/unit/handlers/test_api_gateway_handler.py -v

# Run a specific test
uv run pytest tests/unit/handlers/test_api_gateway_handler.py::TestLogin::test_valid_credentials -v
```

Or via make:

```bash
make test          # pytest with coverage
make test-fast     # pytest without coverage (faster)
```

### Test structure

```
backend/tests/
├── unit/
│   ├── handlers/              # API Gateway routing, auth middleware
│   ├── pipeline_steps/        # Each AI step tested with mocked LLM calls
│   ├── pipeline_factories/    # CompanyAnalysisFactory, PortfolioDiscoveryFactory
│   ├── pipeline/              # Sc0redServicesFactoriesFactory, RequestExecutor
│   ├── repositories/          # DynamoDB repos (mocked with moto)
│   ├── data_strategies/       # URLResolutionStrategy, WebScraperStrategy
│   └── facades/               # CompanyAccessor
└── conftest.py                # Shared fixtures (DynamoDB table, auth context, etc.)
```

### Coverage requirements

- **Floor**: 95% (enforced by `--cov-fail-under=95` in CI)
- **Current**: ~98%
- Coverage report: `htmlcov/index.html` after running with `--cov-report=html`

### Mocking strategy

- **DynamoDB**: [moto](https://github.com/getmoto/moto) creates an in-memory DynamoDB with the real AWS API
- **AI calls**: Mocked via `MagicMock` — pipeline step tests never make real LLM calls
- **HTTP**: `httpx` is mocked in scraping tests

---

## Frontend Tests

```bash
cd frontend

# Run all tests once
npm run test

# Watch mode (re-runs on file change)
npm run test:watch

# With coverage report
npm run test:coverage
```

### Test structure

```
frontend/src/tests/
├── api/
│   └── analysis/route.test.ts       # Analysis API proxy route
├── components/
│   ├── DeleteAnalysisButton.test.tsx # Delete confirmation flow
│   └── RiskBadge.test.tsx           # Risk tier badge rendering
├── errors.test.ts                    # BackendError class
└── riskUtils.test.ts                 # Risk tier helpers and score formatting
```

### Testing libraries

| Library | Purpose |
|---|---|
| Vitest | Test runner (replaces Jest) |
| @testing-library/react | Component rendering and interaction |
| @testing-library/user-event | Realistic user interaction simulation |
| MSW (Mock Service Worker) | Network request mocking |
| jsdom | DOM environment for server components |

### Coverage thresholds

Configured in `vitest.config.ts`:
- Lines: 80%
- Branches: 80%

### Type checking

```bash
cd frontend
npm run typecheck    # tsc --noEmit (strict mode)
```

### Linting and formatting

```bash
cd frontend
npm run lint         # ESLint — zero warnings allowed
npm run lint:fix     # ESLint with auto-fix
npm run format       # Prettier (write)
npm run format:check # Prettier (check only — used in CI)
```

---

## End-to-End Tests

sc0red Services has two E2E test systems:

**1. Playwright browser tests** — test the full app as a user sees it (SSR, auth, navigation, scans). This is the primary E2E system.

```bash
# Run all local browser E2E tests (manages docker lifecycle automatically)
./scripts/playwright.sh --mode=local

# Or from frontend directory:
npm run e2e:local
```

**2. Backend API tests** — test REST endpoints directly via curl (no browser).

```bash
python3 -m pip install boto3 PyJWT
export GH_TOKEN=$(gh auth token)
docker compose up --build -d
./scripts/e2e-test.sh
```

For the full guide including all test modes, headed browser, visual regression, debugging, and CI integration, see **[docs/e2e-testing.md](e2e-testing.md)**.

---

## Code Quality Checks

### Pre-commit hooks (run automatically on `git commit`)

Install once after cloning:

```bash
pip install pre-commit
pre-commit install
pre-commit install --hook-type commit-msg
pre-commit install --hook-type pre-push
```

Run manually against all files:

```bash
pre-commit run --all-files
```

#### What runs on `git commit` (pre-commit)

| Hook | What it checks |
|---|---|
| `trailing-whitespace` | No trailing spaces |
| `end-of-file-fixer` | Files end with a newline |
| `check-yaml` / `check-json` / `check-toml` | Valid syntax |
| `check-merge-conflict` | No unresolved conflict markers |
| `check-added-large-files` | No files > 1 MB |
| `detect-private-key` | No private keys accidentally committed |
| `no-commit-to-branch` | Blocks direct commits to `development`, `testing`, `production` |
| **Gitleaks** | Secret scanning (API keys, tokens, credentials) |
| **Ruff (lint)** | Python linting with auto-fix |
| **Ruff (format)** | Python formatting (Black-compatible) |
| **Naming check** | No abbreviations in Python code (msg→message, req→request, cfg→config) |
| **Import check** | Imports must be at the top of files |
| **ESLint** (frontend) | TypeScript/React linting via lint-staged |
| **Prettier** (frontend) | Code formatting via lint-staged |

#### What runs on `git commit-msg`

| Hook | What it checks |
|---|---|
| **Commitizen** | Enforces conventional commit format |

#### What runs on `git push` (pre-push)

| Hook | What it checks |
|---|---|
| **Branch name** | Must follow `type/TICKET-description` format |
| **pip-audit** | Python dependency vulnerability scan |
| **Frontend tests** | `npm run test` — all tests must pass |

### Running individual checks manually

```bash
# Python linting
cd backend && uv run ruff check src/ --fix

# Python formatting
cd backend && uv run ruff format src/

# Python type checking
cd backend && uv run pyright src/

# Dead code detection
cd backend && uv run vulture src/

# Security scan
cd backend && uv run bandit -r src/ --severity-level high

# Dependency vulnerability check
cd backend && uv run pip-audit

# Secret scanning
gitleaks detect --source . --verbose
```

---

## Git Workflow

### Branch naming

```
type/TICKET-short-description

# Examples
feat/SF-001-add-portfolio-scan
fix/SF-042-risk-score-calculation
chore/SF-100-update-dependencies
```

Valid types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `ci`, `style`, `perf`

### Commit messages

Conventional commits format is enforced by Commitizen:

```
type(optional-scope): imperative short description

Optional longer body explaining why, not what.
```

```bash
# Examples
feat: add portfolio scan confirmation step
fix: handle missing company URL gracefully
refactor: extract risk tier logic into shared utility
test: add coverage for auth middleware edge cases
docs: update API reference with dashboard endpoint
```

### Pull request flow

1. Create a branch from `development`
2. Make changes
3. Push — pre-push hooks run tests
4. Open PR against `development`
5. All CI checks must pass
6. Squash and merge

---

## Project Conventions

### Naming

- **No abbreviations** — `message` not `msg`, `request` not `req`, `configuration` not `cfg`, `context` not `ctx`
- **Functions start with verbs** — `get_scan()`, `create_user()`, `build_response()`, `handle_event()`
- **Boolean variables** — `is_`, `has_`, `can_`, `should_` prefix
- **Private functions** — `_underscore_prefix`

### Python style

- Line length: 100 characters (ruff)
- Type annotations: required everywhere (pyright strict)
- Docstrings: required on all public functions and classes
- No `noqa` or `type: ignore` without a comment explaining why

### TypeScript/React style

- Line length: 110 characters (Prettier)
- No `any` — use proper types or `unknown`
- No `console.log` — use structured logging patterns
- Semi-colons: off
- Quotes: single
- Server components by default; `'use client'` only when state/effects are needed

### Environment variables

- Backend secrets: never `NEXT_PUBLIC_` prefix (they'd be exposed to the browser)
- Frontend env: `BACKEND_URL` is server-side only (no `NEXT_PUBLIC_` prefix)
- All defaults must be safe for local development (non-production values)

---

## DynamoDB Data Model

sc0red Services uses a single-table design with 4 GSIs. All entities share the same table (`sc0red-services-{environment}`).

### Primary key pattern

| Entity | pk | sk |
|---|---|---|
| User | `USER#{user_id}` | `USER#{user_id}` |
| Organisation | `ORG#{org_id}` | `ORG#{org_id}` |
| Scan | `SCAN#{scan_id}` | `SCAN#{scan_id}` |
| Company | `COMPANY#{company_id}` | `COMPANY#{company_id}` |
| Assessment | `COMPANY#{company_id}` | `ASSESSMENT#{assessment_id}` |
| Risk Score | `COMPANY#{company_id}` | `RISK#{category}` |
| Opportunity | `COMPANY#{company_id}` | `OPP#{opportunity_id}` |

### GSI usage

| GSI | GSI{i}PK | GSI{i}SK | Used for |
|---|---|---|---|
| GSI1 | `ORG#{org_id}` | `USER#{user_id}` | List users in org |
| GSI2 | `ORG#{org_id}` | `COMPANY#{created_at}` | List analyses by org |
| GSI3 | `ORG#{org_id}` | `SCAN#{created_at}` | List scans by org |
| GSI4 | `SCAN#{scan_id}` | `COMPANY#{company_id}` | List companies in scan |

---

## AI Pipeline Deep Dive

The pipeline is implemented as a `signalfield_core.PipelineExecutor` and executes 5 steps sequentially for each company. Steps 1–2 run multiple AI calls in parallel internally.

```
URL
 │
 ▼
Step 1: ScrapeAndResolveURL                     [1 AI call]
  ├─ Scrape the provided URL (BeautifulSoup + httpx)
  ├─ If portfolio page: AI resolves the actual company URL
  └─ Scrape the resolved URL if different
 │
 ▼
Step 2: ParallelProfileRiskAndIdeation          [11 AI calls in parallel]
  ├─ 1 profile extraction (company_name, industry, business_model, ...)
  ├─ 2 risk assessment batches (4 categories each, split by theme)
  │   Batch A: competitive_displacement, technology_obsolescence,
  │            customer_behavior, margin_compression
  │   Batch B: talent_workforce, regulatory_compliance,
  │            supply_chain, data_ip
  ├─ 8 opportunity ideation calls (one per risk category)
  ├─ Risk aggregates computed programmatically (mean score → tier)
  ├─ Quality gate: filters Low-impact ideations from low-risk categories
  └─ Deduplication + ranking → top N ideations for detail phase
 │
 ▼
Step 3: DetailOpportunities                     [N AI calls in parallel]
  ├─ One detail call per ranked ideation (typically 3–5)
  └─ Adds: 3 implementation steps, timeline, investment range,
     ROI estimate, vendor recommendations
 │
 ▼
Step 4: ComputeEbitdaTree                       [0 AI calls — programmatic]
  ├─ Builds P&L tree from company profile using industry templates
  ├─ 5 business model templates (SaaS, Services, E-commerce,
  │   Manufacturing, Financial Services)
  └─ Links opportunities to EBITDA nodes by value_lever
 │
 ▼
Step 5: PersistResults                          [0 AI calls]
  ├─ Saves company record (risk score, tier, industry, analyzed_at)
  ├─ Saves risk scores (one DynamoDB item per category)
  ├─ Saves opportunities
  ├─ Saves EBITDA tree
  └─ Pipeline progress updates written to company record throughout
```

Total AI calls per analysis: **~15** (1 URL + 1 profile + 2 risk + 8 ideation + ~3 detail)

### AI calibration guides

Two guides are appended to system prompts to improve consistency:
- `risk_scoring_guide.py` → appended to risk assessment calls (score range anchors, category-specific calibration, anti-patterns)
- `ideation_guide.py` → appended to ideation calls (specificity standards, quality gate, observable proxy patterns)

### Adding a new pipeline step

1. Create `backend/src/pipeline/pipeline_steps/my_step.py` extending `signalfield_core.pipeline.step.RequestStep`
2. Add it to `backend/src/pipeline/pipeline_factories/company_analysis_factory.py` in `get_pipeline()`
3. Add a progress entry in `backend/src/pipeline/request_executor.py` `_PROGRESS_MAP`
4. Write tests in `backend/tests/unit/pipeline/test_my_step.py` with a mocked AI client

### AI client configuration

The pipeline uses `signalfield_core.AIClientFactory`. All AI calls use:

| Step | Verbosity | Reasoning | Precision |
|---|---|---|---|
| URL Resolution | LOW | LOW | STANDARD |
| Profile / Risk / Ideation / Detail | MEDIUM | LOW | STANDARD |

# sc0red Advisory (codebase: `janus`)

The customer-facing product is **sc0red Advisory** — a SaaS platform that helps private equity firms assess AI disruption risk across their portfolio companies. Given a portfolio URL or a single company URL, sc0red Advisory scrapes the company, runs a 6-step AI analysis pipeline, and produces a scored risk report with actionable investment opportunities.

## Naming convention: sc0red Advisory (customer) vs. janus (internal)

Customer-facing brand: **sc0red Advisory**. Internal codebase, repo, AWS resources, CDK stack names, Python / Node package names, Docker containers, the local dev DynamoDB table, and the `localStorage.janus.theme` storage key all retain the **`janus-*`** naming. This is intentional — renaming infrastructure resources would require risky data migrations for zero customer value. See `openspec/changes/rename-janus-to-sc0red-advisory/` for the full rationale.

If you're editing customer-visible text, use **sc0red Advisory**. If you're editing infrastructure or internal symbols, the `janus-*` family stays.

---

## Table of Contents

- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Application Walkthrough](#application-walkthrough)
- [Configuration](#configuration)
- [Documentation](#documentation)
- [Project Structure](#project-structure)

---

## Architecture

```
┌─────────────────┐     HTTPS      ┌─────────────────────────────────┐
│  Next.js 14     │ ─────────────► │  Python Backend (FastAPI/Lambda) │
│  (Frontend)     │ ◄───────────── │                                  │
│  Port 3000      │   JSON REST    │  API Gateway → Lambda Handler    │
└─────────────────┘                │  └─► 5-Step AI Pipeline          │
                                   │       ├─ Scrape & Resolve URL     │
                                   │       ├─ Extract Company Profile  │
                                   │       ├─ Assess AI Risk (8 cats) │
                                   │       ├─ Generate Opportunities   │
                                   │       └─ Persist to DynamoDB      │
                                   └──────────────┬──────────────────┘
                                                  │
                                         ┌────────▼────────┐
                                         │    DynamoDB      │
                                         │  Single-table    │
                                         │  4 GSIs          │
                                         └─────────────────┘
```

| Layer | Technology |
|---|---|
| Frontend | Next.js 14, React 18, TypeScript, NextAuth v4 |
| Backend | Python 3.12, FastAPI (local) / AWS Lambda (cloud) |
| Database | DynamoDB — single-table design with 4 GSIs |
| AI | Anthropic Claude (via `signalfield-core`) |
| Queue | AWS SQS — async portfolio batch processing |
| Infrastructure | AWS CDK — Lambda, API Gateway, DynamoDB, SQS |
| Local Dev | Docker Compose, DynamoDB Local, LocalStack |

---

## Quick Start

### Prerequisites

- Docker Desktop (running)
- Node.js 20+ and npm
- Python 3.12+ and [uv](https://docs.astral.sh/uv/)
- A GitHub token with access to `SignalField/signalfield-core` (`GH_TOKEN`)
- An Anthropic API key for AI analysis (`ANTHROPIC_API_KEY`)

### 1. Clone and configure

```bash
git clone git@github.com:SignalField/janus.git
cd janus
```

Create a `.env` file at the repo root:

```bash
# Required for AI analysis (get from https://console.anthropic.com/settings/keys)
ANTHROPIC_API_KEY=sk-ant-...

# Optional — defaults to a development secret (change for staging/production)
NEXTAUTH_SECRET=your-random-32-character-secret-here
```

### 2. Start the full stack

```bash
# Get your GitHub token (required to build the backend — pulls private signalfield-core)
export GH_TOKEN=$(gh auth token)

docker compose up --build -d
```

This starts four services:

| Service | URL | Description |
|---|---|---|
| Frontend | http://localhost:3000 | Next.js application |
| Backend API | http://localhost:8001 | Python FastAPI server |
| DynamoDB Admin | http://localhost:8002 | Visual DynamoDB browser |
| DynamoDB Local | localhost:8000 | Local DynamoDB instance |

### 3. Open the app

Visit **http://localhost:3000** and create an account to get started.

### Stopping

```bash
docker compose down
```

---

## Application Walkthrough

### Sign Up

Navigate to **http://localhost:3000/signup**.

- Select your account type: **PE Firm** (to analyze portfolio companies) or **Company** (standalone analysis)
- Fill in your name, organisation name, email, and password
- You are automatically signed in and redirected to the dashboard

### Dashboard

The dashboard gives you an at-a-glance overview of your risk intelligence:

- **Stats bar** — Total companies analyzed, average risk score, critical risk count, total scans
- **Recent Analyses** — The last 8 companies analyzed, with risk score and tier, click any row to open the full report
- **Recent Scans** — The last 10 scan jobs with status and progress

### Running a Scan

Click **New Scan** in the sidebar.

#### Portfolio Scan

1. Paste your PE firm's portfolio page URL (e.g. `https://www.sequoiacap.com/companies`)
2. Select **Portfolio**
3. Click **Analyse** — Janus scrapes the page and extracts all portfolio companies
4. Review the discovered company list and deselect any you want to skip
5. Click **Confirm** — Janus runs the full AI pipeline on each company in parallel

#### Standalone Scan

1. Paste a single company URL
2. Select **Standalone**
3. Click **Analyse** — The full pipeline runs immediately and you are taken straight to the report

### Risk Report

Each analysis report shows:

- **Overall Risk Score** (1–10) with colour-coded tier: Low / Moderate / High / Critical
- **8 Risk Categories** — scored individually with an AI-written explanation:
  - Competitive Displacement, Talent Retention, Operational Efficiency, Market Dynamics
  - Regulatory Change, Supply Chain, Customer Consolidation, Technology Obsolescence
- **Strategic Opportunities** — 3–5 AI-generated investment recommendations, each with impact rating, timeline, investment range, estimated ROI, implementation steps, and suggested vendors
- **Export to PDF** — generates a formatted report you can share

### Analyses List

The **Analyses** page lists every completed report across all scans, filterable by company, industry, and risk tier.

---

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | Yes (for AI) | `sk-placeholder` | Anthropic Claude API key |
| `NEXTAUTH_SECRET` | Yes | `dev-secret-minimum-32-characters-long` | JWT signing secret (≥32 chars) |
| `GH_TOKEN` | Build-time | — | GitHub token to pull `signalfield-core` |
| `BACKEND_URL` | Frontend only | `http://backend:8001` | Backend base URL (server-side) |
| `NEXTAUTH_URL` | Frontend only | `http://localhost:3000` | NextAuth callback URL |
| `DYNAMODB_TABLE` | Backend only | `janus-dev` | DynamoDB table name |
| `DYNAMODB_ENDPOINT` | Local only | — | DynamoDB Local endpoint |

> Without a real `ANTHROPIC_API_KEY`, the app starts and auth/navigation works, but any scan that triggers the AI pipeline returns a 401 error from Anthropic.

---

## Documentation

| Document | Description |
|---|---|
| [docs/api.md](docs/api.md) | Backend REST API — all endpoints with request/response schemas |
| [docs/developer-guide.md](docs/developer-guide.md) | Local development, testing, code quality checks, CDK deployment |

---

## Project Structure

```
janus/
├── backend/                  # Python 3.12 backend
│   ├── src/
│   │   ├── handlers/         # Lambda entry point, API routing, auth middleware
│   │   ├── pipeline/         # 5-step AI analysis pipeline
│   │   ├── repositories/     # DynamoDB data access (single-table)
│   │   ├── models/           # Pydantic domain models
│   │   ├── data_strategies/  # Web scraping, URL resolution
│   │   └── local_server.py   # FastAPI app for local development
│   └── tests/                # 296 tests, ~99% coverage
│
├── frontend/                 # Next.js 14 TypeScript frontend
│   ├── src/
│   │   ├── app/              # App Router pages and Next.js API proxy routes
│   │   ├── components/       # Shared React components
│   │   ├── lib/              # Auth, API client, types, utilities
│   │   └── tests/            # 56 Vitest unit tests
│   └── public/               # Static assets
│
├── infrastructure/           # AWS CDK Python stack
│   ├── app.py                # CDK entry point (dev / staging / production)
│   └── stacks/janus_stack.py # DynamoDB + SQS + Lambda + API Gateway
│
├── scripts/
│   ├── deploy-local.sh       # One-command LocalStack CDK deployment
│   └── e2e-test.sh           # End-to-end integration tests
│
├── docs/
│   ├── api.md                # REST API reference
│   └── developer-guide.md    # Developer guide
│
└── docker-compose.yml        # Local full-stack environment
```

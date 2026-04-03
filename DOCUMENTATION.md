# Janus (PE Scan) — Project Documentation

## Overview

**Janus** is a SaaS AI risk intelligence platform built for private equity firms and their portfolio companies. Its core purpose is to analyze companies for AI-driven disruption risks and generate tactical opportunity roadmaps to defend against and capitalize on AI trends.

---

## Core Workflows

### 1. PE Portfolio Scan

1. User enters a PE firm's URL
2. The app auto-discovers all portfolio companies by crawling pages like `/portfolio`, `/companies`, `/investments`
3. User reviews and confirms discovered companies
4. AI risk analysis runs on each company sequentially
5. Results are displayed on a portfolio-level dashboard

### 2. Standalone Company Scan

1. User enters any company's URL
2. The app scrapes the website content
3. A full AI risk & opportunity analysis is performed
4. A detailed report is displayed with radar chart and opportunity cards

---

## The 5-Step AI Analysis Pipeline

Each company goes through 5 sequential pipeline steps using Anthropic Claude via `signalfield_core.AIClientFactory`:

| Stage | Name | Purpose |
|---|---|---|
| 0 | ScrapeAndResolveURL | Scrapes the provided URL; if it's a PE portfolio listing page, uses AI to identify the actual company website URL and scrapes that too |
| 1 | ExtractProfile | Extracts structured profile (industry, business model, products, AI maturity, etc.) from scraped content |
| 2 | AssessRisk | Scores 8 risk categories (1–10) with explanations, evidence, and an overall risk tier |
| 3 | GenerateOpportunities | Produces 3–5 actionable opportunity cards with implementation steps, timelines, ROI estimates, and vendor recommendations |
| 4 | PersistResults | Saves company record, risk scores, and opportunities to DynamoDB |

### Risk Tiers

| Tier | Score Range |
|---|---|
| Low | 1–3 |
| Moderate | 4–6 |
| High | 7–8 |
| Critical | 9–10 |

---

## The 8 Risk Dimensions

| Category | Key | What It Measures |
|---|---|---|
| Competitive Displacement | `competitive_displacement` | AI-native competitors capturing market share |
| Technology Obsolescence | `technology_obsolescence` | Core products becoming obsolete due to AI |
| Talent Retention | `talent_retention` | Ability to hire/retain engineers in an AI-first market |
| Operational Efficiency | `operational_efficiency` | AI adoption in internal operations |
| Market Dynamics | `market_dynamics` | ICP and buyer behaviour shifts driven by AI |
| Regulatory Change | `regulatory_change` | AI regulation exposure (EU AI Act, GDPR, etc.) |
| Supply Chain | `supply_chain` | API/vendor dependency and concentration risk |
| Data & IP | `data_ip` | Proprietary data/IP losing value to AI models |

Risk scoring is industry-aware — for example, financial services weights regulatory and competitive risks higher, while SaaS weights tech obsolescence and competitive displacement higher.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14 (App Router) + React 18 + TypeScript |
| Styling | Vanilla CSS with CSS custom properties — dark glassmorphism design |
| Charts | Recharts (radar/spider charts for risk visualization) |
| Icons | Lucide React |
| Auth | NextAuth.js v4 with CredentialsProvider (email + password), JWT sessions |
| Backend | Python 3.12, FastAPI (local) / AWS Lambda (cloud) |
| Database | DynamoDB — single-table design with 4 GSIs |
| AI | Anthropic Claude via `signalfield_core.AIClientFactory` |
| Web Scraping | BeautifulSoup + httpx |
| PDF Export | Server-rendered HTML (print-to-PDF from browser) |
| Infrastructure | AWS CDK — Lambda, API Gateway, DynamoDB, SQS |
| Deployment | Vercel (frontend), AWS Lambda (backend) |

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

---

## Database Schema

DynamoDB single-table design (`janus-{environment}`). All entities share one table with 4 GSIs.

### Primary key pattern

| Entity | pk | sk |
|---|---|---|
| User | `USER#{user_id}` | `USER#{user_id}` |
| Organisation | `ORG#{org_id}` | `ORG#{org_id}` |
| Scan | `SCAN#{scan_id}` | `SCAN#METADATA` |
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

## API Routes

| Method | Route | Purpose |
|---|---|---|
| POST | `/api/auth/register` | Register new user + organisation |
| POST | `/api/auth/login` | Authenticate user, returns JWT-ready user profile |
| POST | `/api/scan/start` | Start a new scan (standalone or portfolio) |
| GET | `/api/scan/{scanId}` | Get scan status and progress |
| POST | `/api/scan/{scanId}/confirm` | Confirm portfolio companies and run analysis |
| GET | `/api/analysis/{analysisId}` | Get full analysis with risk scores and opportunities |
| DELETE | `/api/analysis/{analysisId}` | Delete analysis (cascading cleanup) |
| GET | `/api/analyses` | List all analyses for the authenticated organisation |
| GET | `/api/dashboard` | Aggregated stats and recent activity |

See [docs/api.md](docs/api.md) for full request/response schemas.

---

## Authentication & Multi-Tenancy

- **NextAuth.js v4** with `CredentialsProvider` (email + bcrypt-hashed password)
- **JWT sessions** — `org_id`, `user_id`, and `role` are embedded in the token
- All API queries are scoped to `org_id` from the session, enforcing full multi-tenancy
- Roles: `admin`, `analyst`, `viewer`

---

## Key Features

- **Portfolio discovery** — crawls PE firm websites across up to 6 URL variants, identifies company links, filters out social/generic domains, caps at 30 companies
- **Interactive scan wizard** — multi-phase form with company review/confirmation step for portfolio scans
- **Radar chart visualization** — 8-dimension spider chart for risk scores using Recharts
- **Opportunity cards** — actionable recommendations with implementation steps, timelines, cost estimates, and real vendor names/URLs
- **PDF export** — dark-themed server-rendered HTML report for print-to-PDF
- **Progress polling** — frontend polls scan status every 2–3 seconds with cosmetic progress animation
- **Cascading delete** — deleting an analysis removes associated opportunities and risk scores, and cleans up empty parent scans

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes (for AI) | Anthropic Claude API key |
| `NEXTAUTH_SECRET` | Yes | JWT signing secret (≥32 chars) |
| `GH_TOKEN` | Build-time | GitHub token to pull `signalfield-core` |
| `BACKEND_URL` | Frontend only | Backend base URL (server-side, default `http://backend:8001`) |
| `NEXTAUTH_URL` | Frontend only | NextAuth callback URL (default `http://localhost:3000`) |
| `DYNAMODB_TABLE` | Backend only | DynamoDB table name (default `janus-dev`) |
| `DYNAMODB_ENDPOINT` | Local only | DynamoDB Local endpoint |

---

## UI Design

- **Dark-first theme** with deep navy/slate background (`#060A12`)
- **Glassmorphism** cards with `backdrop-filter: blur(16px)`
- **Electric blue** (`#3B7BF6`) accent color
- **Risk-tier color scale**: green (low) → yellow (moderate) → orange (high) → red (critical)
- **Fixed 240px sidebar** with navigation links, user info, and sign-out
- Server components for data-heavy pages (dashboard, portfolio, analyses list)
- Client components for interactive pages (scan wizard, analysis detail)

---

## Deployment

### Frontend — Vercel

- Configured via `vercel.json`
- Connects to the Python backend via `BACKEND_URL`

### Backend — AWS Lambda (CDK)

- Infrastructure defined in `infrastructure/stacks/janus_stack.py`
- Lambda + API Gateway + SQS + DynamoDB provisioned via AWS CDK
- Local testing via LocalStack: `./scripts/deploy-local.sh`
- See [docs/developer-guide.md](docs/developer-guide.md) for full CDK deployment instructions

---

## AI Provider

The backend uses **Anthropic Claude** via the signalfield-core AI abstraction layer (`AIClientFactory` / `AIClient`). The `ANTHROPIC_API_KEY` environment variable is required for the analysis pipeline.

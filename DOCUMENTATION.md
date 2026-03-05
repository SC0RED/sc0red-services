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

## The 4-Stage AI Analysis Pipeline

Each company goes through 4 sequential GPT-4o calls (temperature 0.3, JSON mode):

| Stage | Name | Purpose |
|---|---|---|
| 0 | URL Resolution | If the URL is a PE portfolio listing page, identifies the actual company website URL and scrapes it |
| 1 | Company Profile Extraction | Extracts structured profile (industry, business model, products, AI maturity, etc.) from up to 12,000 chars of scraped text |
| 2 | Risk Assessment | Scores 8 risk categories (1–10) with explanations, evidence, and an overall risk tier |
| 3 | Opportunity Generation | Produces 4–6 actionable opportunity cards with implementation steps, timelines, ROI estimates, and vendor recommendations |

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
| Talent & Workforce | `talent_workforce` | AI automating key workforce functions |
| Margin Compression | `margin_compression` | Competitors using AI to operate at lower cost |
| Customer Behavior | `customer_behavior` | Customers adopting AI-powered alternatives |
| Regulatory Compliance | `regulatory_compliance` | AI regulations creating compliance burden |
| Supply Chain | `supply_chain` | Key suppliers being disrupted by AI |
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
| Database | libSQL/Turso (SQLite-compatible) — file-based locally, Turso cloud in production |
| LLM | OpenAI SDK calling GPT-4o |
| Web Scraping | Cheerio (HTML parsing) + native `fetch` |
| PDF Export | Server-rendered HTML (print-to-PDF from browser) |
| Deployment | Vercel (primary), Render (secondary) |

---

## Project Structure

```
pe-scan/
├── src/
│   ├── app/
│   │   ├── page.tsx                              # Landing page (public)
│   │   ├── layout.tsx                            # Root layout with SessionWrapper
│   │   ├── globals.css                           # Full design system (CSS vars, components)
│   │   ├── login/page.tsx                        # Login form
│   │   ├── signup/page.tsx                       # Registration form
│   │   ├── dashboard/
│   │   │   ├── layout.tsx + providers.tsx         # Dashboard layout with SessionProvider
│   │   │   └── page.tsx                          # Main dashboard (server component)
│   │   ├── scan/new/page.tsx                     # New scan wizard (client component)
│   │   ├── analysis/[analysisId]/page.tsx        # Individual company report
│   │   ├── portfolio/[scanId]/page.tsx           # Portfolio view
│   │   ├── analyses/page.tsx                     # All analyses list
│   │   └── api/
│   │       ├── auth/[...nextauth]/route.ts       # NextAuth handler
│   │       ├── auth/register/route.ts            # User registration
│   │       ├── scan/start/route.ts               # Start scan (main analysis trigger)
│   │       ├── scan/[scanId]/route.ts            # Get scan status
│   │       ├── scan/[scanId]/confirm/route.ts    # Confirm and run portfolio analysis
│   │       ├── analysis/[analysisId]/route.ts    # GET/DELETE analysis
│   │       └── export/pdf/[analysisId]/route.ts  # PDF/HTML export
│   ├── components/
│   │   ├── DashboardSidebar.tsx                  # Fixed sidebar nav
│   │   ├── DeleteAnalysisButton.tsx              # Delete with confirm UI
│   │   └── SessionWrapper.tsx                    # SessionProvider wrapper
│   └── lib/
│       ├── ai/
│       │   ├── analyzeCompany.ts                 # 4-stage LLM analysis pipeline
│       │   └── prompts.ts                        # All LLM prompts + TypeScript interfaces
│       ├── auth/authOptions.ts                   # NextAuth config
│       ├── db/client.ts                          # libSQL client + schema initialization
│       ├── scraper/index.ts                      # Web scraping + portfolio discovery
│       └── utils/riskUtils.ts                    # Risk category definitions, scoring helpers
├── scripts/e2e-flow.mjs                          # Puppeteer E2E test
├── public/janus-logo.png                         # Brand logo
├── PE scan PRD.md                                # Product requirements document
├── render.yaml                                   # Render.com deployment config
├── vercel.json                                   # Vercel config
├── fix-env.js                                    # Utility to push .env.local vars to Vercel
└── next.config.js                                # Next.js config
```

---

## Database Schema

Six tables, all auto-initialized on first connection:

### `organizations`

| Column | Type | Description |
|---|---|---|
| id | TEXT (UUID) | Primary key |
| name | TEXT | Organization name |
| type | TEXT | `pe_firm` or `company` |
| url | TEXT | Organization URL |
| created_at | DATETIME | Creation timestamp |

### `users`

| Column | Type | Description |
|---|---|---|
| id | TEXT (UUID) | Primary key |
| org_id | TEXT | FK → organizations |
| email | TEXT (UNIQUE) | User email |
| password_hash | TEXT | bcrypt-hashed password |
| name | TEXT | Display name |
| role | TEXT | `admin`, `analyst`, or `viewer` |
| created_at | DATETIME | Creation timestamp |

### `scans`

| Column | Type | Description |
|---|---|---|
| id | TEXT (UUID) | Primary key |
| org_id | TEXT | FK → organizations |
| created_by | TEXT | FK → users |
| type | TEXT | `portfolio` or `standalone` |
| source_url | TEXT | URL that was scanned |
| status | TEXT | Scan status (e.g., `complete`, `awaiting_confirmation`) |
| progress | INTEGER | Progress percentage (0–100) |
| portfolio_companies | TEXT | JSON array of discovered companies |
| created_at | DATETIME | Creation timestamp |

### `company_analyses`

| Column | Type | Description |
|---|---|---|
| id | TEXT (UUID) | Primary key |
| scan_id | TEXT | FK → scans |
| company_name | TEXT | Analyzed company name |
| company_url | TEXT | Analyzed company URL |
| industry | TEXT | Detected industry |
| description | TEXT | JSON blob: `{summary, topActions, shortDescription}` |
| overall_risk_score | REAL | Aggregate risk score (1–10) |
| risk_tier | TEXT | `low`, `moderate`, `high`, or `critical` |
| error | TEXT | Error message if analysis failed |
| analyzed_at | DATETIME | Analysis timestamp |

### `risk_scores`

| Column | Type | Description |
|---|---|---|
| id | TEXT (UUID) | Primary key |
| analysis_id | TEXT | FK → company_analyses |
| category | TEXT | One of the 8 risk categories |
| score | REAL | Score (1–10) |
| explanation | TEXT | Explanation of the score |
| evidence | TEXT | Supporting evidence |

### `opportunities`

| Column | Type | Description |
|---|---|---|
| id | TEXT (UUID) | Primary key |
| analysis_id | TEXT | FK → company_analyses |
| title | TEXT | Opportunity title |
| risk_mitigated | TEXT | Which risk this addresses |
| impact_rating | TEXT | Impact level |
| strategic_category | TEXT | Strategy category |
| description | TEXT | Detailed description |
| implementation_steps | TEXT | JSON array of 5 steps |
| timeline | TEXT | Estimated timeline |
| investment_range | TEXT | Cost estimate |
| roi_estimate | TEXT | Expected ROI |
| related_services | TEXT | JSON array of vendor recommendations |
| sort_order | INTEGER | Display order |

---

## API Routes

| Method | Route | Purpose |
|---|---|---|
| POST | `/api/auth/register` | Register new user + organization |
| GET/POST | `/api/auth/[...nextauth]` | NextAuth sign-in/sign-out/session |
| POST | `/api/scan/start` | Start a new scan (standalone or portfolio) |
| GET | `/api/scan/[scanId]` | Get scan status and progress |
| POST | `/api/scan/[scanId]/confirm` | Confirm portfolio companies and run analysis |
| GET | `/api/analysis/[analysisId]` | Get full analysis with risk scores and opportunities |
| DELETE | `/api/analysis/[analysisId]` | Delete analysis (cascading cleanup) |
| GET | `/api/export/pdf/[analysisId]` | Export analysis as printable HTML |

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

| Variable | Purpose |
|---|---|
| `OPENAI_API_KEY` | GPT-4o API calls for the analysis pipeline |
| `NEXTAUTH_SECRET` | JWT signing secret for authentication |
| `NEXTAUTH_URL` | NextAuth callback URL |
| `TURSO_DATABASE_URL` | Turso cloud database URL (production) |
| `TURSO_AUTH_TOKEN` | Turso authentication token (production) |

For local development, the database defaults to `file:./data/pescan.db` (local SQLite file).

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

### Vercel (Primary)

- Configured via `vercel.json`
- Function timeouts: 120s for standalone scans, 300s for portfolio scans
- Use `fix-env.js` to push local env vars to Vercel

### Render (Secondary)

- Configured via `render.yaml`
- Runs as a Node.js web service

---

## Known Discrepancy

The PRD (`PE scan PRD.md`) specifies **Claude Sonnet** as the LLM and references `ANTHROPIC_API_KEY`, but the actual implementation uses **OpenAI GPT-4o** via the `openai` npm package with `OPENAI_API_KEY`.

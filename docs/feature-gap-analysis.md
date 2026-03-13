# Feature Gap Analysis: Zack's Prototype vs Janus

**Date:** 2026-03-13
**Source:** Zack's prototype at `~/Documents/github/pe-scan` + PE friend feedback via Slack
**Purpose:** Identify new features in Zack's prototype that are not yet in Janus, prioritize them based on real PE user feedback, and outline implementation considerations.

---

## Background

Zack reached out to a PE friend who provided direct feedback on Janus:

1. Overall thinks it's great — they're far along in their AI adoption journey
2. Already implemented an AI solution that increased worker productivity by 8x at a drywall-focused portco — would love a site like Janus to help identify things like that
3. **Wants diligence mode** — analysis for due diligence scenarios (pre-acquisition), not just existing portcos
4. **Revenue + Cost classification** — wants AI opportunities identified on both the revenue and cost side
5. **Document upload** — wants to provide a diligence or investment memorandum for more precise analysis
6. **Business Model Agent / EBITDA Tree** — wants an agent that distills the business model, maps an EBITDA tree, and figures out which parts of the tree can be impacted through risks or opportunities

Zack has since prototyped several of these features. This document captures the gaps.

---

## New Features in Zack's Prototype

### 1. EBITDA Tree / Business Model Agent

**Status in Janus:** Not present
**PE Feedback Alignment:** Directly requested — *"a business model agent who distills the business and maps an EBITDA tree and figures out which parts of the tree can be impacted"*

#### What It Does

A new AI pipeline stage (Stage 4 in Zack's prototype, after opportunity generation) that decomposes a company's economics into a P&L tree and links AI opportunities to specific line items.

#### AI Output

| Field | Description |
|-------|-------------|
| `summary` | 2-3 sentence business model overview |
| `revenue_estimate` | Annual revenue range (e.g., "$10M-$50M") |
| `ebitda_estimate` | EBITDA range or margin % (e.g., "$2M-$8M" or "15-25% margin") |
| `nodes` | Hierarchical tree from Revenue down to EBITDA |

#### Tree Node Structure

Each node contains:
- `id` — unique identifier
- `label` — display name (e.g., "SaaS Subscriptions", "R&D Expense")
- `type` — one of: `revenue`, `cost`, `margin`, `subtotal`
- `value_range` — estimated dollar range
- `percentage_of_parent` — relative weight in parent category
- `parent_id` — hierarchy link
- `description` — what this line item represents
- `linked_opportunity_indices[]` — which opportunity recommendations (by index) impact this P&L line

#### Example Tree Structure

```
Revenue
├── SaaS Subscriptions (60% of revenue)
├── Professional Services (25% of revenue)
└── Licensing (15% of revenue)
- COGS
├── Cloud Infrastructure
├── Customer Success Team
└── Third-Party APIs
= Gross Profit
- Operating Expenses
├── R&D
├── Sales & Marketing
└── G&A
= EBITDA
```

#### Frontend Visualization

- **Library:** ReactFlow + Dagre (automatic hierarchical layout)
- **Node colors:** Green (revenue), Red (cost), Blue (margin), Amber (EBITDA/subtotal)
- **Interactive features:** Hover tooltips showing node description + linked AI opportunities
- **Opportunity indicators:** Colored dots on nodes — green (Revenue Side), purple (Cost Side), cyan (Both)
- **Controls:** Pan, zoom, responsive sizing

#### Zack's Implementation Reference

| File | Purpose |
|------|---------|
| `pe-scan/frontend/src/lib/ai/prompts.ts` (lines 275-330) | EBITDA tree AI prompt |
| `pe-scan/frontend/src/lib/ai/analyzeCompany.ts` (lines 171-182) | Pipeline execution |
| `pe-scan/src/components/EbitdaTree.tsx` | ReactFlow visualization |
| `pe-scan/src/lib/db/client.ts` | `ebitda_trees` table schema |

---

### 2. Document Upload & Re-analysis

**Status in Janus:** Not present
**PE Feedback Alignment:** Directly requested — *"Would be great if they could give a diligence or investment memorandum then could be more precise"*

#### What It Does

Users can upload supporting documents (investment memos, diligence reports, financial statements) that are text-extracted and injected into the AI prompts for a more precise, context-aware analysis.

#### Supported File Types

| Format | Extensions |
|--------|-----------|
| Documents | PDF, DOCX, TXT, MD |
| Spreadsheets | XLSX, XLS, CSV |
| Presentations | PPTX |

**Max file size:** 10MB per file

#### User Flow

1. User runs initial analysis (URL-based, same as today)
2. On the analysis report page, a **Document Upload** section appears
3. User drags/drops or clicks to upload files
4. System extracts text from each file, stores it with character count
5. User clicks **"Re-analyze with Documents"**
6. System re-runs the AI pipeline with document text appended to prompts (capped at 25K chars)
7. Updated analysis replaces the previous one

#### Data Model

```
documents table:
- id (primary key)
- analysis_id (foreign key)
- filename
- file_type
- extracted_text
- char_count
- uploaded_at
```

#### Prompt Integration

Document text is appended to the profile extraction prompt:
```
SUPPLEMENTARY DOCUMENTS (investment memos, diligence docs, etc.):
${documentText}
```

This gives the AI richer context about the company's financials, strategy, and competitive position — resulting in more precise risk scores and more relevant opportunity recommendations.

#### Zack's Implementation Reference

| File | Purpose |
|------|---------|
| `pe-scan/src/components/DocumentUpload.tsx` | Drag-and-drop upload UI |
| `pe-scan/src/app/api/analysis/[analysisId]/documents/route.ts` | Upload/list/delete API |
| `pe-scan/src/app/api/analysis/[analysisId]/reanalyze/route.ts` | Re-analysis trigger |

---

### 3. Value Lever Classification

**Status in Janus:** Not present
**PE Feedback Alignment:** Directly requested — *"Would be good to identify AI opportunities on both the revenue and cost side"*

#### What It Does

Each AI-generated opportunity is tagged with a `value_lever` field indicating whether it primarily drives revenue growth, reduces costs, or both.

#### Value Lever Options

| Value | Meaning |
|-------|---------|
| `Revenue Side` | Drives top-line growth (new revenue streams, pricing optimization, market expansion) |
| `Cost Side` | Reduces operating expenses (automation, efficiency, vendor consolidation) |
| `Both` | Impacts both revenue and cost (e.g., AI platform that cuts support costs AND enables upsell) |

#### Frontend Additions

1. **Value Lever Summary Section** — 3 cards on the analysis page:
   - Revenue Side: count of opportunities + total investment range
   - Cost Side: count of opportunities + total investment range
   - Both: count of opportunities + total investment range

2. **Opportunity Filtering** — opportunities can be filtered by value lever in addition to the existing strategic category filter

#### Implementation Scope

- Add `value_lever` field to the opportunity generation AI prompt
- Add `value_lever` to the `Opportunity` data model
- Store in DynamoDB (already nested in assessment JSON — just add the field)
- Add Value Lever Summary section to analysis detail page
- Add filter toggle to opportunity list

#### Zack's Implementation Reference

| File | Purpose |
|------|---------|
| `pe-scan/frontend/src/lib/ai/prompts.ts` (opportunity prompt) | Prompt includes value_lever in JSON schema |
| `pe-scan/src/app/analysis/[analysisId]/page.tsx` | Value Lever Summary UI + filter |

---

### 4. Portfolio Risk Heatmap

**Status in Janus:** Not present (Janus has table + stats, but no heatmap)
**PE Feedback Alignment:** Indirect — improves portfolio-level visibility

#### What It Does

On the portfolio page, displays a visual grid of company cards (in addition to the table) where each card is color-coded by risk tier for at-a-glance portfolio risk distribution.

#### Features

- **Responsive grid:** Auto-fill layout with min 220px per card
- **Color-coded top borders:** Green (low), yellow (moderate), orange (high), red (critical)
- **Card content:** Company name, industry, risk score
- **Status indicators:** "Analyzing..." for in-progress, reduced opacity for pending
- **Clickable:** Links to individual analysis report

#### Implementation Scope

- Frontend-only change on the portfolio page
- No backend changes needed
- Add a grid section above or alongside the existing table

---

### 5. Diligence Mode (Implied but Not Fully Prototyped)

**Status in Jack's Prototype:** Not explicitly built as a separate mode
**PE Feedback Alignment:** Directly requested — *"Would like to see an option to do this analysis for diligence scenarios as well as existing portcos"*

#### What It Would Do

A toggle on the scan page: **"Existing Portfolio"** vs **"Due Diligence"**

When in diligence mode:
- AI prompts shift focus to pre-acquisition risk assessment
- Emphasis on deal-breaker risks, hidden liabilities, integration complexity
- Opportunities framed as "post-acquisition value creation" rather than "defend against disruption"
- Document upload becomes more prominent (diligence memos, CIMs, financial models)
- EBITDA tree emphasizes value creation potential post-deal

This feature was requested by the PE friend but not fully implemented in Zack's prototype. It would primarily be a prompt-engineering change with a mode flag propagated through the pipeline.

---

## Features Already in Both Codebases

These exist in both Janus and Zack's prototype — no gap:

| Feature | Notes |
|---------|-------|
| 8-dimension risk framework | Same 8 categories, same 1-10 scoring |
| Portfolio discovery from PE firm URL | Crawl + extract portfolio companies |
| Portfolio confirmation UI | Select/deselect companies before analysis |
| Standalone single-company scan | Direct URL analysis |
| Radar chart for risk visualization | Recharts-based 8-axis spider chart |
| Opportunity generation | Implementation steps, ROI, timelines, investment ranges, vendor recommendations |
| Dashboard with aggregate stats | Total analyses, avg score, critical count, scan count |
| PDF export | Server-rendered dark-themed HTML report |
| Auth (NextAuth + credentials) | Email/password with org-level isolation |
| Delete analysis | With confirmation UI |

---

## Features Only in Janus (Not in Zack's Prototype)

| Feature | Why It Matters |
|---------|---------------|
| Production-grade Python backend | Lambda + SQS async pipeline (Zack runs AI inline in Next.js API routes — would timeout on Vercel) |
| signalfield-core SDK | Structured pipeline with entity accessors, data strategies, factory patterns |
| DynamoDB single-table design | Scalable, production-ready (vs Turso/SQLite) |
| SQS async processing | Portfolio companies analyzed in parallel via queue |
| E2E test suite | 32 automated integration tests |
| 98.5% backend test coverage | 296+ unit tests |
| AWS CDK infrastructure | Deployable Lambda + API Gateway + SQS + DynamoDB |
| Scan deletion with cascade | Full cleanup of linked companies, assessments, opportunities |
| Dashboard scan management | View/delete failed and abandoned scans |
| Comprehensive pre-commit hooks | 14 hooks including ruff, pyright, commitlint |

---

## Tech Stack Comparison

| Aspect | Zack's Prototype | Janus |
|--------|-----------------|-------|
| LLM Provider | OpenAI GPT-4o | Anthropic Claude (via signalfield-core) |
| Database | Turso/libSQL (SQLite cloud) | DynamoDB single-table |
| AI Pipeline Location | Frontend (Next.js API routes, inline) | Backend (Python Lambda + SQS worker) |
| Tree Visualization | ReactFlow + Dagre | Not present |
| Document Processing | Built-in text extraction | Not present |
| Infrastructure | Vercel-only | AWS CDK (Lambda + API GW + SQS + DynamoDB) + Vercel |
| Testing | Minimal | 296+ backend tests, 81 frontend tests, 32 E2E tests |

---

## Recommended Priority

| Priority | Feature | Effort | Rationale |
|----------|---------|--------|-----------|
| **P0** | Value Lever on Opportunities | **Small** | Add one field to prompt + model + UI. Quick win that directly addresses PE feedback. |
| **P1** | EBITDA Tree / Business Model | **Large** | Biggest differentiator. New pipeline step, new DynamoDB entity, ReactFlow frontend. Directly requested by PE user. |
| **P1** | Document Upload & Re-analysis | **Large** | Core ask from PE user. Needs: S3 storage (or DynamoDB), text extraction library, re-analysis endpoint, upload UI. |
| **P2** | Portfolio Risk Heatmap | **Small** | Frontend-only visual enhancement. Nice addition to portfolio page. |
| **P3** | Diligence Mode | **Medium** | Mode flag + prompt variants. Builds on document upload (P1). More impactful after docs are supported. |

---

## Implementation Considerations

### For EBITDA Tree
- **Backend:** New pipeline step (Stage 5: `GenerateEbitdaTree`) after `GenerateOpportunities`, before `PersistResults`
- **Storage:** New DynamoDB entity type (`COMPANY#{id}` / `EBITDA_TREE#{id}`) or nested in assessment JSON
- **Frontend:** Add `reactflow` and `dagre` packages, new `EbitdaTree` component
- **Prompt:** Receives company profile + risk scores + opportunities array (indexed) to link nodes to opportunities

### For Document Upload
- **Storage:** S3 for raw files, DynamoDB for metadata + extracted text
- **Text extraction:** Python library (e.g., `pypdf`, `python-docx`, `openpyxl`) in the backend
- **API:** New endpoints: `POST/GET/DELETE /api/analysis/{id}/documents`, `POST /api/analysis/{id}/reanalyze`
- **Prompt integration:** Append extracted text to profile extraction and risk assessment prompts
- **Size limit:** Cap extracted text at 25K characters per analysis to stay within LLM context limits

### For Value Lever
- **Backend:** Add `value_lever` field to opportunity generation prompt schema and `Opportunity` model
- **Storage:** Already nested in assessment JSON — just add the field
- **Frontend:** Add 3-card summary section + filter toggle on analysis page
- **Migration:** Existing analyses won't have `value_lever` — handle gracefully with null/undefined checks

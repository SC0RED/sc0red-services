# sc0red Services — Backend API Reference

Base URL (local): `http://localhost:8001`
Base URL (LocalStack CDK): `https://<api-id>.execute-api.localhost.localstack.cloud:4566/development`

---

## Authentication

All endpoints except `/api/auth/register` and `/api/auth/login` require a signed JWT in the `Authorization` header:

```
Authorization: Bearer <token>
```

Tokens are HS256-signed using `NEXTAUTH_SECRET`. The frontend generates server-side tokens automatically via `serverToken.ts`. For direct API access (scripts, testing) generate a token with:

```python
import jwt, time
token = jwt.encode(
    {"sub": user_id, "orgId": org_id, "exp": time.time() + 300},
    NEXTAUTH_SECRET,
    algorithm="HS256"
)
```

**Auth error response** (all protected endpoints):
```json
HTTP 401
{ "error": "Missing or invalid Authorization header" }
```

---

## Endpoints

### Auth

#### `POST /api/auth/register`

Create a new user and organisation. Public — no auth required.

**Request**
```json
{
    "name": "Alex Johnson",
    "email": "alex@firm.com",
    "password": "SecurePass123!",
    "orgName": "Accel Partners",
    "orgType": "pe_firm"
}
```

| Field | Type | Required | Values |
|---|---|---|---|
| `name` | string | Yes | Full name |
| `email` | string | Yes | Must be unique |
| `password` | string | Yes | Hashed with bcrypt |
| `orgName` | string | Yes | Organisation display name |
| `orgType` | string | Yes | `pe_firm` or `company` |

**Response 200**
```json
{ "success": true }
```

**Response 400**
```json
{ "error": "Email already registered" }
{ "error": "All fields are required" }
```

---

#### `POST /api/auth/login`

Authenticate a user and return their profile. Public — no auth required.

**Request**
```json
{
    "email": "alex@firm.com",
    "password": "SecurePass123!"
}
```

**Response 200**
```json
{
    "success": true,
    "user": {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "email": "alex@firm.com",
        "name": "Alex Johnson",
        "orgId": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
        "role": "admin"
    }
}
```

**Response 401**
```json
{ "error": "Invalid credentials" }
```

---

### Scans

#### `POST /api/scan/start`

Start a new scan. For portfolio URLs, discovers companies and returns them for confirmation. For standalone URLs, queues a single company analysis via SQS.

**Request**
```json
{
    "url": "https://www.sequoiacap.com/companies",
    "type": "portfolio"
}
```

| Field | Type | Values |
|---|---|---|
| `url` | string | Any company or portfolio page URL |
| `type` | string | `portfolio` or `standalone` |

**Response 200 — Portfolio** (user must confirm companies before analysis runs)
```json
{
    "scanId": "550e8400-e29b-41d4-a716-446655440000",
    "status": "awaiting_confirmation",
    "portfolioCompanies": [
        { "name": "Company A", "url": "https://company-a.com" },
        { "name": "Company B", "url": "https://company-b.com" }
    ]
}
```

**Response 200 — Standalone** (analysis queued via SQS, poll for progress)
```json
{
    "scanId": "550e8400-e29b-41d4-a716-446655440000",
    "status": "running",
    "analysisId": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"
}
```

**Response 400**
```json
{ "error": "URL and type are required" }
```

---

#### `GET /api/scan/{scanId}`

Retrieve the current state of a scan, including progress and all linked company analyses. Progress is computed from per-company pipeline progress for real-time updates.

**Response 200**
```json
{
    "status": "running",
    "progress": 45,
    "progressLabel": "Running AI risk assessment...",
    "type": "portfolio",
    "portfolioCompanies": [
        { "name": "Company A", "url": "https://company-a.com" }
    ],
    "analyses": [
        {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "companyName": "Company A",
            "companyUrl": "https://company-a.com",
            "industry": "B2B SaaS",
            "overallRiskScore": 7.2,
            "riskTier": "high",
            "error": null,
            "analyzedAt": "2026-03-08T10:00:00Z",
            "pipelineProgress": 100,
            "pipelineLabel": ""
        }
    ]
}
```

| Field | Values |
|---|---|
| `status` | `running`, `awaiting_confirmation`, `complete`, `failed` |
| `progress` | 0–100 integer (computed from per-company pipeline progress) |
| `progressLabel` | Current pipeline stage label (e.g. "Running AI risk assessment...") |
| `pipelineProgress` | Per-company pipeline progress (0–100), 0 if not started |
| `riskTier` | `low`, `moderate`, `high`, `critical` |

**Response 404**
```json
{ "error": "Not found" }
```

---

#### `POST /api/scan/{scanId}/confirm`

Confirm the list of portfolio companies to analyse. Queues each company as a separate SQS message for parallel processing by worker Lambdas.

**Request**
```json
{
    "companies": [
        { "name": "Company A", "url": "https://company-a.com" },
        { "name": "Company B", "url": "https://company-b.com" }
    ]
}
```

**Response 202**
```json
{
    "ok": true,
    "queued": [
        { "name": "Company A", "analysisId": "550e8400-e29b-41d4-a716-446655440000" },
        { "name": "Company B", "analysisId": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11" }
    ]
}
```

**Response 404**
```json
{ "error": "Scan not found" }
```

---

### Analyses

#### `GET /api/analysis/{analysisId}`

Retrieve the full AI risk report for a single company.

**Response 200**
```json
{
    "companyName": "Acme Corp",
    "companyUrl": "https://acme.com",
    "industry": "B2B SaaS — Sales Intelligence",
    "overallRiskScore": 7.2,
    "riskTier": "high",
    "analysisSummary": "Acme Corp faces high AI disruption risk (overall: 7.2/10). Highest risk areas: competitive_displacement (8/10), technology_obsolescence (7/10), talent_workforce (7/10).",
    "topActions": [
        "Deploy AI-powered competitive intelligence platform",
        "Modernise analytics engine with LLM integration",
        "AI-driven customer success automation"
    ],
    "riskScores": [
        {
            "category": "competitive_displacement",
            "score": 8,
            "rationale": "AI-native competitors with demonstrably superior products visible in market..."
        },
        {
            "category": "technology_obsolescence",
            "score": 7,
            "rationale": "Some components at risk but company shows modernisation signals..."
        },
        {
            "category": "customer_behavior",
            "score": 5,
            "rationale": "Some customer segments exploring alternatives but core base appears stable..."
        },
        {
            "category": "margin_compression",
            "score": 6,
            "rationale": "Some pricing pressure but company maintains premium positioning..."
        },
        {
            "category": "talent_workforce",
            "score": 7,
            "rationale": "Core workforce functions partially automatable by current AI..."
        },
        {
            "category": "regulatory_compliance",
            "score": 3,
            "rationale": "Minimal regulatory exposure to AI-specific rules..."
        },
        {
            "category": "supply_chain",
            "score": 3,
            "rationale": "Minimal supply chain complexity, software-only model..."
        },
        {
            "category": "data_ip",
            "score": 5,
            "rationale": "Some data assets at risk but company has unique data sources..."
        }
    ],
    "opportunities": [
        {
            "title": "Deploy AI-powered competitive intelligence platform",
            "description": "Deploy real-time AI monitoring of competitor moves to stay ahead of AI-native entrants.",
            "impact_rating": "High",
            "strategic_category": "Competitive Moat",
            "value_lever": "Revenue Side",
            "timeline": "Medium-term (3-9 months)",
            "investment_range": "$100K-$500K",
            "roi_estimate": "30% improvement in competitive win rate within 12 months",
            "implementation_steps": [
                "Audit current competitor tracking workflows",
                "Deploy LLM-based monitoring on competitor product pages and job postings",
                "Integrate alerts into existing sales and strategy dashboards"
            ]
        }
    ],
    "ebitdaTree": {
        "summary": "Acme Corp operates a SaaS business model with estimated annual revenue of $30M-$400M.",
        "revenueEstimate": "$30M-$400M",
        "ebitdaEstimate": "$4M-$140M (15-35% margin)",
        "nodes": [
            {
                "id": "revenue",
                "label": "Total Revenue",
                "type": "revenue",
                "valueRange": "$30M-$400M",
                "children": [
                    {
                        "id": "subscriptions",
                        "label": "Subscriptions",
                        "type": "revenue",
                        "valueRange": "$24M-$320M",
                        "percentageOfParent": 80
                    }
                ]
            }
        ]
    }
}
```

**Risk Categories**

| Category | Description |
|---|---|
| `competitive_displacement` | Risk of AI-native competitors capturing market share |
| `technology_obsolescence` | Risk that core products/services become obsolete due to AI |
| `customer_behavior` | Risk that customers adopt AI-powered alternatives |
| `margin_compression` | Risk that AI enables competitors to operate at dramatically lower costs |
| `talent_workforce` | Risk that AI automates key workforce functions |
| `regulatory_compliance` | Risk from emerging AI regulations |
| `supply_chain` | Risk that key suppliers are disrupted by AI |
| `data_ip` | Risk that proprietary data or IP loses value |

**Risk Tiers**

| Tier | Score Range |
|---|---|
| `critical` | 8.5–10.0 |
| `high` | 6.5–8.4 |
| `moderate` | 3.5–6.4 |
| `low` | 1.0–3.4 |

**Response 404**
```json
{ "error": "Analysis not found" }
```

---

#### `DELETE /api/analysis/{analysisId}`

Delete a company analysis and all associated data (risk scores, opportunities). If the parent scan has no remaining analyses, the scan is also deleted.

**Response 200**
```json
{ "ok": true }
```

**Response 404**
```json
{ "error": "Analysis not found" }
```

---

### Lists & Dashboard

#### `GET /api/analyses`

Return all completed company analyses for the authenticated organisation, sorted newest first.

**Response 200**
```json
{
    "analyses": [
        {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "companyName": "Acme Corp",
            "companyUrl": "https://acme.com",
            "industry": "B2B SaaS",
            "overallRiskScore": 7.2,
            "riskTier": "high",
            "error": null,
            "analyzedAt": "2026-03-08T10:00:00Z",
            "scanType": "portfolio"
        }
    ]
}
```

---

#### `GET /api/dashboard`

Return aggregated stats and the most recent activity for the authenticated organisation.

**Response 200**
```json
{
    "totalAnalyses": 12,
    "avgRiskScore": 6.8,
    "criticalCount": 3,
    "scanCount": 5,
    "recentAnalyses": [
        {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "companyName": "Acme Corp",
            "companyUrl": "https://acme.com",
            "overallRiskScore": 7.2,
            "riskTier": "high",
            "analyzedAt": "2026-03-08T10:00:00Z",
            "scanType": "portfolio"
        }
    ],
    "recentScans": [
        {
            "id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
            "sourceUrl": "https://sequoiacap.com/companies",
            "type": "portfolio",
            "status": "complete",
            "progress": 100,
            "completedCount": 8,
            "createdAt": "2026-03-08T09:00:00Z"
        }
    ]
}
```

`recentAnalyses` returns up to 8 records; `recentScans` returns up to 10.

---

## Error Responses

All error responses follow the same shape:

```json
{ "error": "<human-readable message>" }
```

| HTTP Status | Meaning |
|---|---|
| 400 | Bad request — missing or invalid fields |
| 401 | Unauthorised — missing, expired, or invalid JWT |
| 403 | Forbidden — resource belongs to a different organisation |
| 404 | Not found |
| 500 | Internal server error |

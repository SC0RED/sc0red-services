# Janus — Backend API Reference

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

Start a new scan. For portfolio URLs, returns a list of discovered companies for confirmation. For standalone URLs, runs the full pipeline immediately and returns the analysis ID.

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

**Response 200 — Standalone** (analysis runs synchronously)
```json
{
    "scanId": "550e8400-e29b-41d4-a716-446655440000",
    "status": "complete",
    "analysisId": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"
}
```

**Response 400**
```json
{ "error": "URL and type are required" }
```

---

#### `GET /api/scan/{scanId}`

Retrieve the current state of a scan, including all linked company analyses.

**Response 200**
```json
{
    "status": "complete",
    "progress": 100,
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
            "analyzedAt": "2026-03-08T10:00:00Z"
        }
    ]
}
```

| Field | Values |
|---|---|
| `status` | `running`, `awaiting_confirmation`, `complete`, `failed` |
| `progress` | 0–100 integer |
| `riskTier` | `low`, `moderate`, `high`, `critical` |

**Response 404**
```json
{ "error": "Scan not found" }
```

---

#### `POST /api/scan/{scanId}/confirm`

Confirm the list of portfolio companies to analyse. Triggers the AI pipeline for each company sequentially. Progress updates are stored in DynamoDB as each company completes.

**Request**
```json
{
    "companies": [
        { "name": "Company A", "url": "https://company-a.com" },
        { "name": "Company B", "url": "https://company-b.com" }
    ]
}
```

**Response 200**
```json
{
    "ok": true,
    "results": [
        {
            "name": "Company A",
            "status": "complete",
            "analysisId": "550e8400-e29b-41d4-a716-446655440000"
        },
        {
            "name": "Company B",
            "status": "failed",
            "error": "Could not scrape website"
        }
    ]
}
```

**Response 403**
```json
{ "error": "Scan does not belong to your organisation" }
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
    "analysisSummary": "Acme faces significant AI disruption risk, particularly from next-generation AI-native competitors entering their core market...",
    "topActions": [
        "Invest in AI-powered product features to retain competitive position",
        "Upskill sales and engineering teams on AI capabilities",
        "Evaluate strategic acquisitions in the AI tooling space"
    ],
    "riskScores": [
        {
            "category": "competitive_displacement",
            "score": 8,
            "explanation": "Multiple AI-native competitors (Outreach AI, Gong 2.0) are capturing market share with 10x lower CAC..."
        },
        {
            "category": "talent_retention",
            "score": 6,
            "explanation": "Engineers are being poached by AI-first startups offering equity..."
        },
        {
            "category": "operational_efficiency",
            "score": 5,
            "explanation": "Current ops stack has partial AI adoption but key workflows remain manual..."
        },
        {
            "category": "market_dynamics",
            "score": 7,
            "explanation": "ICP is shifting toward smaller teams using AI-powered self-serve tools..."
        },
        {
            "category": "regulatory_change",
            "score": 3,
            "explanation": "EU AI Act compliance is manageable; no immediate regulatory headwinds..."
        },
        {
            "category": "supply_chain",
            "score": 4,
            "explanation": "Vendor concentration risk is moderate; primary API dependencies have alternatives..."
        },
        {
            "category": "customer_consolidation",
            "score": 6,
            "explanation": "Mid-market customers are consolidating vendors; risk of churn to all-in-one platforms..."
        },
        {
            "category": "technology_obsolescence",
            "score": 7,
            "explanation": "Core NLP models will be commoditised by open-source alternatives within 18 months..."
        }
    ],
    "opportunities": [
        {
            "title": "AI-Powered Prospecting Engine",
            "description": "Integrate LLM-based signal detection into the prospecting workflow to surface intent signals 3x faster than rule-based systems.",
            "impact_rating": "High",
            "timeline": "3–6 months",
            "investment_range": "$500K–$1M",
            "roi_estimate": "40–60% reduction in time-to-qualified-lead",
            "implementation_steps": [
                "Audit current prospecting data pipeline",
                "Select LLM provider and evaluate fine-tuning requirements",
                "Build signal classification layer on top of existing CRM data",
                "Run A/B test against current rule-based system",
                "Roll out to full sales team"
            ],
            "related_services": [
                {
                    "service_type": "LLM Provider",
                    "vendors": [
                        { "name": "Anthropic", "url": "https://anthropic.com" },
                        { "name": "OpenAI", "url": "https://openai.com" }
                    ]
                },
                {
                    "service_type": "Implementation Partner",
                    "vendors": [
                        { "name": "Accenture AI", "url": "https://accenture.com/ai" }
                    ]
                }
            ]
        }
    ]
}
```

**Risk Categories**

| Category | Description |
|---|---|
| `competitive_displacement` | AI-native competitors eating market share |
| `talent_retention` | Ability to hire/retain engineers in an AI-first market |
| `operational_efficiency` | AI adoption in internal operations |
| `market_dynamics` | ICP and buyer behaviour shifts driven by AI |
| `regulatory_change` | AI regulation exposure (EU AI Act, GDPR, etc.) |
| `supply_chain` | API/vendor dependency and concentration risk |
| `customer_consolidation` | Customer consolidation onto AI-first platforms |
| `technology_obsolescence` | Core technology being commoditised by AI |

**Risk Tiers**

| Tier | Score Range |
|---|---|
| `low` | 1.0–3.9 |
| `moderate` | 4.0–5.9 |
| `high` | 6.0–7.9 |
| `critical` | 8.0–10.0 |

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

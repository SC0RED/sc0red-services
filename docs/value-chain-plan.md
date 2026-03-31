# Value Chain Analysis — Implementation Plan

## Overview

Add a programmatic value chain visualization below the EBITDA tree on the single-company analysis detail page. Each step of the company's value chain shows which AI risks and opportunities apply, giving PE analysts an operational view alongside the financial view.

No AI call needed — uses business model templates (like EBITDA tree) and programmatically maps existing risk scores + opportunities to value chain steps.

---

## Architecture

```
Existing pipeline:
  ScrapeAndResolve → ProfileRiskIdeation → DetailOpportunities → ComputeEbitdaTree → PersistResults

After:
  ScrapeAndResolve → ProfileRiskIdeation → DetailOpportunities → ComputeEbitdaTree → ComputeValueChain → PersistResults
                                                                                      ↑ new step (~0ms)
```

`ComputeValueChain` runs after `ComputeEbitdaTree` (needs profile + risk scores + opportunities). Pure Python, no AI call, <1ms.

---

## Data Model

### ValueChainStep

```python
class ValueChainStep(BaseModel):
    id: str                          # e.g. "lead_generation"
    label: str                       # e.g. "Lead Generation"
    description: str                 # 1-sentence description
    category: str                    # "primary" | "support"
    risk_categories: list[str]       # linked risk category IDs
    risk_scores: list[RiskScore]     # populated from existing risk assessment
    opportunity_indices: list[int]   # indices into opportunity_result.opportunities
```

### ValueChainResult

```python
class ValueChainResult(BaseModel):
    steps: list[ValueChainStep]
    summary: str                     # "SaaS value chain with 6 primary activities"
```

Stored on `Company.value_chain: ValueChainResult | None` alongside `ebitda_tree`.

---

## Business Model Templates

### Template Structure

Each template defines:
- Primary activities (the operational flow)
- Support activities (cross-cutting)
- Risk category mapping per step
- Opportunity linking rules per step

### SaaS Template

```
Primary Activities:
1. Lead Generation & Marketing
   - Risks: competitive_displacement, customer_behavior
   - Opportunities: Revenue Capture, Market Expansion

2. Sales & Conversion
   - Risks: competitive_displacement, margin_compression
   - Opportunities: Revenue Capture, Competitive Moat

3. Onboarding & Implementation
   - Risks: technology_obsolescence, talent_workforce
   - Opportunities: Operational Efficiency

4. Product Delivery & Platform
   - Risks: technology_obsolescence, data_ip
   - Opportunities: Competitive Moat, Operational Efficiency

5. Customer Success & Support
   - Risks: customer_behavior, talent_workforce
   - Opportunities: Operational Efficiency, Revenue Capture

6. Renewal & Expansion
   - Risks: competitive_displacement, margin_compression, customer_behavior
   - Opportunities: Revenue Capture, Competitive Moat

Support Activities:
7. R&D / Engineering
   - Risks: technology_obsolescence, talent_workforce
   - Opportunities: Competitive Moat, Talent Strategy

8. Data & Infrastructure
   - Risks: data_ip, supply_chain, regulatory_compliance
   - Opportunities: Operational Efficiency
```

### Professional Services Template

```
Primary:
1. Business Development
2. Proposal & Scoping
3. Project Delivery
4. Quality Assurance
5. Client Relationship Management

Support:
6. Knowledge Management
7. Talent & Training
```

### E-commerce Template

```
Primary:
1. Product Sourcing / Curation
2. Marketing & Acquisition
3. Storefront / UX
4. Order Fulfillment
5. Customer Service
6. Returns & Logistics

Support:
7. Technology / Platform
8. Supply Chain Management
```

### Manufacturing Template

```
Primary:
1. Raw Material Procurement
2. Inbound Logistics
3. Production / Assembly
4. Quality Control
5. Outbound Logistics / Distribution
6. Sales & Marketing
7. After-Sales Service

Support:
8. R&D / Product Design
9. Supply Chain Planning
```

### Financial Services Template

```
Primary:
1. Client Acquisition
2. Onboarding & KYC
3. Product Delivery / Advisory
4. Risk Management
5. Client Servicing
6. Reporting & Compliance

Support:
7. Technology / Infrastructure
8. Regulatory Affairs
```

---

## Linking Logic

### Risk Categories → Value Chain Steps

Static mapping per template (defined above). Each step lists which of the 8 risk categories apply. When rendering, we look up the actual score from the risk assessment.

### Opportunities → Value Chain Steps

Match by `strategic_category`:
- **Competitive Moat** → Sales, Product Delivery, R&D steps
- **Revenue Capture** → Lead Gen, Sales, Renewal steps
- **Market Expansion** → Lead Gen, Marketing steps
- **Operational Efficiency** → Delivery, Support, Infrastructure steps
- **Talent Strategy** → all labor-intensive steps (Support, Delivery, R&D)

Additionally, match by `value_lever`:
- **Revenue Side** → revenue-generating steps (Sales, Marketing, Renewal)
- **Cost Side** → cost-heavy steps (Delivery, Support, Infrastructure)
- **Both** → all steps

The final mapping is the intersection of strategic_category match AND value_lever match.

---

## Files to Create

| File | Purpose |
|---|---|
| `backend/src/pipeline/pipeline_steps/build_value_chain.py` | Templates + `build_programmatic_value_chain(profile, risk_assessment, opportunities)` |
| `backend/src/pipeline/pipeline_steps/compute_value_chain.py` | `ComputeValueChain(RequestStep)` — pipeline step wrapper |
| `backend/src/models/model_company.py` | Add `ValueChainStep`, `ValueChainResult`, `value_chain` field on `Company` |
| `backend/src/facades/company_accessor.py` | Add `set_value_chain()` / `get_value_chain()` |
| `frontend/src/components/ValueChainDiagram.tsx` | Horizontal flow visualization |
| `backend/tests/unit/pipeline/test_build_value_chain.py` | Template tests |
| `backend/tests/unit/pipeline/test_compute_value_chain.py` | Pipeline step tests |
| `frontend/src/tests/components/ValueChainDiagram.test.tsx` | Frontend tests |

## Files to Modify

| File | Change |
|---|---|
| `backend/src/pipeline/pipeline_factories/company_analysis_factory.py` | Add `ComputeValueChain` step after `ComputeEbitdaTree` |
| `backend/src/pipeline/request_executor.py` | Add `compute_value_chain` to progress map |
| `backend/src/pipeline/pipeline_steps/persist_results.py` | Persist value chain to assessment |
| `backend/src/repositories/dynamodb/assessment_repository.py` | Add `save_value_chain()` / `get_value_chain()` |
| `backend/src/handlers/analysis_handlers.py` | Include value chain in analysis response |
| `frontend/src/app/analysis/[analysisId]/AnalysisDetail.tsx` | Render `ValueChainDiagram` below EBITDA tree |
| `frontend/src/lib/types/api.ts` | Add `ValueChainStep` type |
| `scripts/mock_ai_server.py` | No change (no AI call) |

---

## Frontend Visualization

### Layout

Below EBITDA tree, full-width card:

```
┌─────────────────────────────────────────────────────────┐
│ Value Chain Analysis                                     │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────┐   ┌──────┐   ┌──────┐   ┌──────┐   ┌──────┐ │
│  │Lead  │──▶│Sales │──▶│Onbrd │──▶│Prodct│──▶│Supprt│  │
│  │Gen   │   │      │   │      │   │Dlvry │   │      │  │
│  │      │   │      │   │      │   │      │   │      │  │
│  │🔴 7.2│   │🟠 5.8│   │🟡 4.1│   │🔴 6.9│   │🟡 4.5│  │
│  │2 opps│   │1 opp │   │1 opp │   │3 opps│   │1 opp │  │
│  └──────┘   └──────┘   └──────┘   └──────┘   └──────┘  │
│                                                          │
│  Support: R&D (🟠 6.2, 2 opps) · Data & Infra (🟡 3.8) │
└─────────────────────────────────────────────────────────┘
```

Each step card shows:
- Step name
- Highest risk score among linked categories (color-coded)
- Number of linked opportunities
- Click to expand: shows individual risk scores + opportunity titles

Support activities shown as a compact row below the primary flow.

---

## Implementation Order

| Step | Files | Effort |
|---|---|---|
| 1 | Data model: `ValueChainStep`, `ValueChainResult` on `Company` | Small |
| 2 | `build_value_chain.py` — templates + linking logic | Medium |
| 3 | `compute_value_chain.py` — pipeline step | Small |
| 4 | Wire into factory + progress map | Small |
| 5 | Persist + include in analysis response | Small |
| 6 | Frontend `ValueChainDiagram` component | Medium |
| 7 | Tests (backend + frontend) | Medium |

Estimated total: 1-2 days of focused work.

---

## What We're NOT Doing (v1)

- No AI-generated value chain steps (programmatic templates only)
- No portfolio-level value chain aggregation
- No custom/editable value chain steps
- No per-step detailed analysis (just risk scores + opportunity links)
- No value chain comparison between companies

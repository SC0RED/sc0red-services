# Janus Pipeline — Complete Analysis of Every Step and AI Request

## Pipeline Overview

```
ScrapeAndResolve → ExtractProfile → AssessRisk → GenerateOpportunities → GenerateEbitdaTree → PersistResults
     ~15s            ~30-45s         ~45-60s        ~50-70s                  ~60-90s             ~2s
```

**Total wall-clock: ~2.5-3.5 minutes** (after Phase 1 optimizations)

- **Model**: `claude-sonnet-4-20250514` (Precision.STANDARD) for all AI calls
- **Provider**: Anthropic (Messages API with `tool_use` for structured JSON output)
- **Extended thinking**: Enabled on all calls (budget varies by ReasoningEffort)
- **Retry**: 3 retries with exponential backoff (factor=2) on AIProviderError

### Token Budget Configuration (Anthropic Provider)

| ReasoningEffort | Thinking Budget | Used By |
|-----------------|----------------|---------|
| MINIMAL | 1,024 tokens | — (not used) |
| LOW | 4,096 tokens | All 5 AI calls |
| MEDIUM | 10,240 tokens | — (was AssessRisk, changed to LOW) |
| HIGH | 32,768 tokens | — (not used) |

| Verbosity | max_tokens (output) | Used By |
|-----------|-------------------|---------|
| LOW | 4,096 | URL Resolution (AI Call #1) |
| MEDIUM | 8,192 | ExtractProfile, AssessRisk, GenOpps (×2), GenEbitdaTree |
| HIGH | 16,384 | — (not used) |

**Effective max_tokens sent to API** = `max_tokens + thinking_budget`
- LOW verbosity + LOW reasoning = 4,096 + 4,096 = **8,192**
- MEDIUM verbosity + LOW reasoning = 8,192 + 4,096 = **12,288**

---

## Step 1: ScrapeAndResolve

**File**: `backend/src/pipeline/pipeline_steps/scrape_and_resolve.py`
**Timing**: ~15s total (dominated by HTTP requests)
**AI Calls**: 1 (conditional — URL resolution)

### Sub-step 1a: Initial HTTP Scrape (~5-10s)

**No AI call.** Pure HTTP scraping via `WebScraperStrategy`.

- **Timeout**: 15s per request
- **Max text length**: 20,000 chars
- **Extracts**: title, description, text, links, meta_keywords
- **Library**: httpx + BeautifulSoup4
- **Fails if**: scraped text < 50 characters

### Sub-step 1b: URL Resolution — AI Call #1 (~5-10s)

**Purpose**: Determine if the URL is a PE portfolio listing page and find the actual company website.

**AI Settings**:
| Setting | Value |
|---------|-------|
| Verbosity | LOW |
| ReasoningEffort | LOW |
| Precision | STANDARD |
| max_tokens | 4,096 + 4,096 = 8,192 |
| Thinking budget | 4,096 |

**System Prompt** (combined with user prompt into single `input_text`):
```
You are a data extraction assistant. Your task is to find the actual website URL of the primary company described in the provided web page content.
If the provided URL is already the company's actual operating website (not a private equity firm's portfolio listing), return that same URL.
If the provided URL is a portfolio listing or directory, look at the provided text and links to find the actual external website of the company.
```

**User Prompt Template**:
```
Provided URL: {url}
Page Title: {scraped_title}

Text Preview:
{scraped_text[:3000]}

Links found on page:
{json.dumps(scraped_links[:100])}

Return the actual company website URL.
```

**JSON Schema**:
```json
{
  "type": "object",
  "properties": {
    "actual_url": {
      "type": "string",
      "description": "The actual company website URL"
    }
  },
  "required": ["actual_url"],
  "additionalProperties": false
}
```

**Output**: Single field — `actual_url` string

**Notes**:
- System + user prompt are concatenated into one string (not separate system message)
- If AI returns non-HTTP URL or call fails, silently falls back to original URL
- This is the simplest AI call — 1 required field, ~3KB input

### Sub-step 1c: Resolved URL Scrape (conditional, ~5-10s)

**No AI call.** Only runs if URL resolution found a different URL. Same HTTP scrape as 1a.
Combines both content sources into a single string:
```
[Context from portfolio listing ({original_url}):
{first_2000_chars_of_original}]

[Content from actual company website ({actual_url}):
{actual_text}]
```

---

## Step 2: ExtractProfile

**File**: `backend/src/pipeline/pipeline_steps/extract_profile.py`
**Timing**: ~30-45s
**AI Calls**: 1

### AI Call #2: Company Profile Extraction

**Purpose**: Extract a structured company profile from raw scraped website content.

**AI Settings**:
| Setting | Value |
|---------|-------|
| Verbosity | MEDIUM |
| ReasoningEffort | LOW |
| Precision | STANDARD |
| max_tokens | 8,192 + 4,096 = 12,288 |
| Thinking budget | 4,096 |

**System Prompt**:
```
You are a senior business intelligence analyst specializing in technology companies and private equity portfolio analysis. Your job is to extract structured, accurate information about a company from raw web content.

Always respond with valid JSON only. No markdown, no explanation text outside the JSON.
```

**User Prompt Template**:
```
Analyze this company website content and extract a structured company profile.

URL: {actual_url}

Website Content:
{scraped_text[:12000]}
{document_section}
Extract the company profile with all available fields.
```

Where `{document_section}` is (if supplementary documents exist):
```
SUPPLEMENTARY DOCUMENTS (investment memos, diligence docs, etc.):
{document_text[:50000]}
```

**JSON Schema** (13 required fields):
```json
{
  "type": "object",
  "properties": {
    "company_name": {
      "type": "string",
      "description": "Official company name"
    },
    "industry": {
      "type": "string",
      "description": "Primary industry (be specific, e.g. 'B2B SaaS - HR Technology' not just 'Software')"
    },
    "industry_sector": {
      "type": "string",
      "description": "Broader sector (Technology, Healthcare, Financial Services, Manufacturing, Retail, Real Estate, Media, Professional Services, Energy, Transportation, etc.)"
    },
    "business_model": {
      "type": "string",
      "description": "How they make money (SaaS, marketplace, services, product, etc.)"
    },
    "description": {
      "type": "string",
      "description": "2-3 sentence description of what they do"
    },
    "products_services": {
      "type": "array",
      "items": {"type": "string"},
      "description": "Specific products or services"
    },
    "target_market": {
      "type": "string",
      "description": "Who their customers are"
    },
    "company_size": {
      "type": "string",
      "description": "Estimated size (Startup <50, Small 50-200, Mid-market 200-1000, Enterprise 1000+)"
    },
    "revenue_model": {
      "type": "string",
      "description": "Subscription, transaction, professional services, etc."
    },
    "tech_signals": {
      "type": "array",
      "items": {"type": "string"},
      "description": "Technology signals from job postings, tech stack mentions, integrations"
    },
    "competitive_positioning": {
      "type": "string",
      "description": "How they differentiate"
    },
    "ai_maturity": {
      "type": "string",
      "description": "Current AI adoption level (None evident, Early exploration, Partial adoption, AI-forward)"
    },
    "key_risks_visible": {
      "type": "array",
      "items": {"type": "string"},
      "description": "Obvious risk signals visible on the site"
    }
  },
  "required": [
    "company_name", "industry", "industry_sector", "business_model",
    "description", "products_services", "target_market", "company_size",
    "revenue_model", "tech_signals", "competitive_positioning",
    "ai_maturity", "key_risks_visible"
  ],
  "additionalProperties": false
}
```

**Input size**: ~12,000 chars of scraped content + optional up to 50,000 chars of supplementary docs
**Output size**: 13 fields, mostly short strings and small arrays

---

## Step 3: AssessRisk

**File**: `backend/src/pipeline/pipeline_steps/assess_risk.py`
**Timing**: ~45-60s
**AI Calls**: 1
**Depends on**: Step 2 output (CompanyProfile)

### AI Call #3: 8-Category Risk Assessment

**Purpose**: Score the company across 8 AI disruption risk categories.

**AI Settings**:
| Setting | Value |
|---------|-------|
| Verbosity | MEDIUM |
| ReasoningEffort | LOW |
| Precision | STANDARD |
| max_tokens | 8,192 + 4,096 = 12,288 |
| Thinking budget | 4,096 |

**System Prompt**:
```
You are a senior AI strategy consultant at a top-tier management consulting firm, specializing in AI disruption risk assessment for private equity portfolios. You have deep knowledge of how AI is transforming industries and creating existential risks for incumbent business models.

Your analysis is:
- Evidence-based: Always cite specific signals from the company's actual situation
- Industry-calibrated: Consider what risks matter most for this specific industry
- Honest: Don't soften scores — use the full 1-10 scale appropriately
- Forward-looking: Consider 2-5 year AI trajectory, not just today

Score scale:
1-2: Minimal risk, company is well-positioned or AI is a tailwind
3-4: Low-moderate risk, some vulnerability but manageable
5-6: Moderate risk, meaningful exposure requiring attention in 12 months
7-8: High risk, significant disruption likely, immediate action needed
9-10: Critical/existential risk, business model fundamentally threatened

Always respond with valid JSON only. No markdown, no explanation text outside the JSON.
```

**User Prompt Template**:
```
Perform a comprehensive AI disruption risk assessment for this company.

COMPANY PROFILE:
{json.dumps(profile_dict, indent=2)}

RISK CATEGORIES TO ASSESS:
- competitive_displacement: Competitive Displacement — Risk of AI-native competitors capturing market share
- technology_obsolescence: Technology Obsolescence — Risk that core products/services become obsolete due to AI
- talent_workforce: Talent & Workforce — Risk that AI automates key workforce functions
- margin_compression: Margin Compression — Risk that AI enables competitors to operate at dramatically lower costs
- customer_behavior: Customer Behavior Shift — Risk that customers adopt AI-powered alternatives
- regulatory_compliance: Regulatory & Compliance — Risk from emerging AI regulations
- supply_chain: Supply Chain & Vendor — Risk that key suppliers are disrupted by AI
- data_ip: Data & IP Vulnerability — Risk that proprietary data or IP loses value

INDUSTRY CONTEXT: The company operates in "{industry_sector}". Apply industry-specific weighting:
- If Financial Services: Weight regulatory_compliance and competitive_displacement higher
- If Healthcare: Weight regulatory_compliance and data_ip higher
- If Manufacturing: Weight supply_chain and talent_workforce higher
- If Technology/SaaS: Weight technology_obsolescence and competitive_displacement higher
- If Professional Services: Weight talent_workforce and technology_obsolescence higher
- If Retail/Consumer: Weight customer_behavior and margin_compression higher

For each risk category, consider:
1. What specific AI technologies are threatening this company's position?
2. Who are the AI-native competitors entering this space?
3. What is the timeline of disruption risk?
4. Are there any moats protecting against this risk?

Assess all risk categories and provide the overall analysis.
```

**JSON Schema**:
```json
{
  "type": "object",
  "properties": {
    "risk_scores": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "category": {"type": "string", "description": "Risk category ID"},
          "score": {"type": "number", "description": "Risk score 1-10"},
          "explanation": {
            "type": "string",
            "description": "2-3 sentences explaining this specific score"
          },
          "evidence": {
            "type": "string",
            "description": "Specific signals supporting this assessment"
          }
        },
        "required": ["category", "score", "explanation", "evidence"],
        "additionalProperties": false
      }
    },
    "overall_score": {"type": "number", "description": "Overall risk score 1-10"},
    "tier": {
      "type": "string",
      "enum": ["low", "moderate", "high", "critical"],
      "description": "Risk tier"
    },
    "top_risks": {
      "type": "array",
      "items": {"type": "string"},
      "description": "Top 3 most critical risk category IDs"
    },
    "analysis_summary": {
      "type": "string",
      "description": "3-4 sentence executive summary"
    }
  },
  "required": ["risk_scores", "overall_score", "tier", "top_risks", "analysis_summary"],
  "additionalProperties": false
}
```

**Input size**: Full company profile JSON (~1-2KB) + category descriptions + industry instructions
**Output size**: 8 risk scores (each with category + score + explanation + evidence) + overall_score + tier + top_risks + summary. This is one of the larger outputs.

---

## Step 4: GenerateOpportunities (Parallelized)

**File**: `backend/src/pipeline/pipeline_steps/generate_opportunities.py`
**Timing**: ~50-70s (two parallel calls, wall-clock = max of both)
**AI Calls**: 2 (parallel via ThreadPoolExecutor)
**Depends on**: Step 2 output (CompanyProfile) + Step 3 output (RiskAssessment)

### Shared Context Block (included in both prompts)

```
COMPANY PROFILE:
{json.dumps(profile_dict, indent=2)}

RISK ASSESSMENT:
Overall Score: {overall_score}/10 ({tier} risk)
Top Risks: {top_risks_comma_separated}
Risk Summary: {analysis_summary}

DETAILED RISK SCORES:
{json.dumps(risk_scores, indent=2)}
```

### Shared Strategic Categories Instructions (included in both prompts)

```
Strategic categories to use:
- "Competitive Moat" - Strengthen defensibility (data flywheels, switching costs, network effects)
- "Revenue Capture" - New AI-powered products/services to sell
- "Market Expansion" - Enter adjacent markets enabled by AI
- "Operational Efficiency" - Internal AI to cut costs and improve margins
- "Talent Strategy" - Workforce transformation, AI hiring, upskilling
```

### AI Call #4a: High-Priority Opportunities

**Purpose**: Generate 2-3 opportunities targeting the top 3 risk categories + top 3 immediate actions.

**AI Settings**:
| Setting | Value |
|---------|-------|
| Verbosity | MEDIUM |
| ReasoningEffort | LOW |
| Precision | STANDARD |
| max_tokens | 8,192 + 4,096 = 12,288 |
| Thinking budget | 4,096 |

**System Prompt**:
```
You are a senior management consultant and AI transformation advisor who specializes in helping private equity portfolio companies capture AI opportunities and defend against disruption. You combine strategic thinking with practical implementation expertise.

Your recommendations are:
- Specific and actionable: Real implementation steps, not vague suggestions
- Industry-appropriate: Tailored to what's actually feasible in this sector
- Commercial: Focused on ROI, competitive advantage, and revenue impact
- Resourced: Include realistic investment ranges and timeline estimates

For vendor recommendations, suggest real companies that specialize in each service area.

Always respond with valid JSON only. No markdown, no explanation text outside the JSON.
```

**User Prompt**:
```
Generate specific, tactical AI opportunity recommendations for this company, focusing on the highest-priority risks.

{shared_context_block}

TARGET RISK CATEGORIES (highest priority): {top_3_risk_categories}

Generate 2-3 high-priority opportunities targeting the risk categories listed above. For each opportunity:
- Make implementation steps specific to THIS company (3-5 steps)
- Keep descriptions concise (2-3 sentences)
- ROI estimates should be realistic for company size and industry
- For related_services, list relevant vendors as simple strings (e.g. "Datadog - Observability")
- Classify each opportunity's value_lever: "Revenue Side" (drives top-line growth, new revenue streams, pricing optimization, market expansion), "Cost Side" (reduces operating expenses, automation, efficiency gains), or "Both" (impacts revenue and cost simultaneously)

Strategic categories to use:
- "Competitive Moat" - Strengthen defensibility (data flywheels, switching costs, network effects)
- "Revenue Capture" - New AI-powered products/services to sell
- "Market Expansion" - Enter adjacent markets enabled by AI
- "Operational Efficiency" - Internal AI to cut costs and improve margins
- "Talent Strategy" - Workforce transformation, AI hiring, upskilling

Also provide top_three_immediate_actions: the 3 most impactful actions this company can start within 30 days.
```

**JSON Schema**:
```json
{
  "type": "object",
  "properties": {
    "opportunities": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "title": {"type": "string", "description": "Specific, action-oriented title"},
          "risk_mitigated": {"type": "string", "description": "Category ID this primarily addresses"},
          "impact_rating": {"type": "string", "enum": ["High", "Medium", "Low"]},
          "strategic_category": {"type": "string", "description": "One of: Competitive Moat, Revenue Capture, Market Expansion, Operational Efficiency, Talent Strategy"},
          "description": {"type": "string", "description": "2-3 sentence description"},
          "implementation_steps": {"type": "array", "items": {"type": "string"}, "description": "3-5 specific implementation steps"},
          "timeline": {"type": "string", "description": "Quick Win (1-3 months)|Medium-term (3-9 months)|Long-term (9-18 months)"},
          "investment_range": {"type": "string", "description": "$50K-$100K|$100K-$500K|$500K-$1M|$1M+"},
          "roi_estimate": {"type": "string", "description": "Specific ROI description"},
          "related_services": {"type": "array", "items": {"type": "string"}, "description": "Relevant vendor or service names"},
          "value_lever": {"type": "string", "enum": ["Revenue Side", "Cost Side", "Both"], "description": "Whether this opportunity primarily drives revenue growth, reduces costs, or both"}
        },
        "required": ["title", "risk_mitigated", "impact_rating", "strategic_category", "description", "implementation_steps", "timeline", "investment_range", "roi_estimate", "related_services", "value_lever"],
        "additionalProperties": false
      }
    },
    "top_three_immediate_actions": {
      "type": "array",
      "items": {"type": "string"},
      "description": "Top 3 immediate actions doable in 30 days"
    }
  },
  "required": ["opportunities", "top_three_immediate_actions"],
  "additionalProperties": false
}
```

**Output**: 2-3 opportunities (11 fields each) + top_three_immediate_actions array

### AI Call #4b: Strategic Opportunities

**Purpose**: Generate 1-2 opportunities targeting the remaining 5 risk categories.

**AI Settings**: Same as Call #4a.

**System Prompt**: Same as Call #4a.

**User Prompt**:
```
Generate specific, tactical AI opportunity recommendations for this company, focusing on strategic risk categories.

{shared_context_block}

TARGET RISK CATEGORIES (strategic): {remaining_5_risk_categories}

Generate 1-2 strategic opportunities targeting the risk categories listed above. For each opportunity:
- Make implementation steps specific to THIS company (3-5 steps)
- Keep descriptions concise (2-3 sentences)
- ROI estimates should be realistic for company size and industry
- For related_services, list relevant vendors as simple strings (e.g. "Datadog - Observability")
- Classify each opportunity's value_lever: "Revenue Side" (drives top-line growth, new revenue streams, pricing optimization, market expansion), "Cost Side" (reduces operating expenses, automation, efficiency gains), or "Both" (impacts revenue and cost simultaneously)

Strategic categories to use:
- "Competitive Moat" - Strengthen defensibility (data flywheels, switching costs, network effects)
- "Revenue Capture" - New AI-powered products/services to sell
- "Market Expansion" - Enter adjacent markets enabled by AI
- "Operational Efficiency" - Internal AI to cut costs and improve margins
- "Talent Strategy" - Workforce transformation, AI hiring, upskilling

Generate the opportunities. Do NOT include top_three_immediate_actions.
```

**JSON Schema**:
```json
{
  "type": "object",
  "properties": {
    "opportunities": {
      "type": "array",
      "items": { ... same opportunity item schema as #4a ... }
    }
  },
  "required": ["opportunities"],
  "additionalProperties": false
}
```

**Output**: 1-2 opportunities (11 fields each)

### Merge Logic

- Opportunities from Call #4a come first, then Call #4b
- `top_three_immediate_actions` taken from Call #4a only
- Results combined into a single `OpportunityResult` model

---

## Step 5: GenerateEbitdaTree

**File**: `backend/src/pipeline/pipeline_steps/generate_ebitda_tree.py`
**Timing**: ~60-90s
**AI Calls**: 1
**Depends on**: Step 2 (profile) + Step 3 (risk assessment) + Step 4 (opportunities)

### AI Call #5: EBITDA Decomposition Tree

**Purpose**: Build a hierarchical P&L tree showing where AI opportunities impact the company's economics.

**AI Settings**:
| Setting | Value |
|---------|-------|
| Verbosity | MEDIUM |
| ReasoningEffort | LOW |
| Precision | STANDARD |
| max_tokens | 8,192 + 4,096 = 12,288 |
| Thinking budget | 4,096 |

**System Prompt**:
```
You are a senior financial analyst and business model strategist who specialises in decomposing company economics into P&L trees for private equity portfolio companies. You understand how AI opportunities map to specific revenue and cost line items.

Your analysis is:
- Structured: Build a clear top-down tree from Revenue → Gross Profit → EBITDA
- Specific: Use industry-typical line items relevant to this company's business model
- Actionable: Link AI opportunities to specific P&L nodes where they'd have impact
- Realistic: Provide reasonable estimates based on company size and industry benchmarks

Always respond with valid JSON only. No markdown, no explanation text outside the JSON.
```

**User Prompt Template**:
```
Build an EBITDA decomposition tree for this company showing where AI opportunities would impact the P&L.

COMPANY PROFILE:
{json.dumps(profile_dict, indent=2)}

RISK ASSESSMENT:
Overall Score: {overall_score}/10 ({tier} risk)
Summary: {analysis_summary}

AI OPPORTUNITIES (indexed 0-{N-1}):
[0] {title} ({value_lever}) - {strategic_category}
[1] {title} ({value_lever}) - {strategic_category}
...

Build a tree from Revenue down to EBITDA. The tree should reflect this company's actual business model and industry.

Tree structure guidelines:
- Start with total Revenue at the top
- Break revenue into 2-4 revenue streams specific to this company
- Show COGS / Cost of Revenue
- Show Gross Profit (subtotal)
- Show 3-5 key operating expense categories relevant to this business
- Show EBITDA (subtotal)
- For each node, indicate which AI opportunities (by index) could impact that line item

Generate the EBITDA decomposition tree.
```

**JSON Schema** (recursive with `$ref`):
```json
{
  "type": "object",
  "$defs": {
    "node": {
      "type": "object",
      "properties": {
        "id": {"type": "string"},
        "label": {"type": "string"},
        "type": {"type": "string", "enum": ["revenue", "cost", "margin", "subtotal"]},
        "value_range": {"type": "string", "description": "Estimated value range (e.g. '$10M-$50M')"},
        "percentage_of_parent": {"type": ["number", "null"], "description": "Percentage of parent node value"},
        "parent_id": {"type": ["string", "null"]},
        "description": {"type": "string"},
        "linked_opportunity_indices": {
          "type": "array",
          "items": {"type": "integer"},
          "description": "Indices of AI opportunities that impact this line item"
        },
        "children": {"type": "array", "items": {"$ref": "#/$defs/node"}}
      },
      "required": ["id", "label", "type", "value_range", "percentage_of_parent", "parent_id", "description", "linked_opportunity_indices", "children"],
      "additionalProperties": false
    }
  },
  "properties": {
    "summary": {"type": "string", "description": "2-3 sentence overview of business model economics and where AI has the most P&L impact"},
    "revenue_estimate": {"type": "string", "description": "Estimated annual revenue range (e.g. '$10M-$50M')"},
    "ebitda_estimate": {"type": "string", "description": "Estimated EBITDA range or margin (e.g. '$2M-$8M' or '15-25% margin')"},
    "nodes": {"type": "array", "items": {"$ref": "#/$defs/node"}, "description": "Top-level tree nodes (typically starts with Revenue)"}
  },
  "required": ["summary", "revenue_estimate", "ebitda_estimate", "nodes"],
  "additionalProperties": false
}
```

**Output**: Recursive tree with ~15-25 nodes, each with 9 required fields. This produces the **largest structured output** of any single AI call.

---

## Step 6: PersistResults

**File**: `backend/src/pipeline/pipeline_steps/persist_results.py`
**Timing**: ~2s
**AI Calls**: 0

Pure DynamoDB writes:
1. Save company document (name, url, industry, description, risk score, tier, scan_id, org_id, timestamp)
2. Save assessment (overall_score, tier, top_risks, analysis_summary)
3. Save 8 individual risk scores
4. Save 3-5 opportunities (11 fields each)
5. Save top_three_immediate_actions
6. Save EBITDA tree (recursive node data + estimates + summary)

---

## Summary: All AI Calls

| # | Step | Purpose | Verbosity | Reasoning | Thinking | max_tokens | Input Size | Output Size | Timing |
|---|------|---------|-----------|-----------|----------|------------|------------|-------------|--------|
| 1 | ScrapeAndResolve | URL resolution | LOW | LOW | 4,096 | 8,192 | ~3KB | 1 field | ~5-10s |
| 2 | ExtractProfile | Company profile | MEDIUM | LOW | 4,096 | 12,288 | ~12KB (+50KB docs) | 13 fields | ~30-45s |
| 3 | AssessRisk | 8-category risk scoring | MEDIUM | LOW | 4,096 | 12,288 | ~2KB profile + categories | 8 scores + summary | ~45-60s |
| 4a | GenOpps (high-priority) | 2-3 top-risk opportunities | MEDIUM | LOW | 4,096 | 12,288 | ~4KB context | 2-3 opps × 11 fields + actions | ~50-70s |
| 4b | GenOpps (strategic) | 1-2 strategic opportunities | MEDIUM | LOW | 4,096 | 12,288 | ~4KB context | 1-2 opps × 11 fields | ~40-60s |
| 5 | GenEbitdaTree | P&L decomposition tree | MEDIUM | LOW | 4,096 | 12,288 | ~3KB context | ~15-25 recursive nodes | ~60-90s |

**Total AI calls**: 5 (1 conditional + 4 required, with calls 4a+4b running in parallel)
**Total thinking budget per scan**: 4,096 × 5 = **20,480 thinking tokens**
**Total max output tokens per scan**: 8,192 + (12,288 × 4) = **57,344 tokens**

---

## Data Flow Between Steps

```
Input: company URL
         │
         ▼
[ScrapeAndResolve]
   Produces: scraped_text, scraped_links, scraped_title, actual_url
         │
         ▼
[ExtractProfile]
   Consumes: scraped_text[:12000], actual_url, document_text
   Produces: CompanyProfile (13 fields)
         │
         ▼
[AssessRisk]
   Consumes: CompanyProfile (full JSON dump)
   Produces: RiskAssessment (8 risk_scores, overall_score, tier, top_risks, analysis_summary)
         │
         ├───────────────────────────┐
         ▼                           ▼
[GenOpps-HighPriority]      [GenOpps-Strategic]       ← PARALLEL
   Consumes: profile +         Consumes: profile +
     full assessment +           full assessment +
     top 3 risk categories       remaining 5 categories
   Produces: 2-3 opps +       Produces: 1-2 opps
     top_three_actions
         │                           │
         └───────┬───────────────────┘
                 ▼ (merge)
[GenerateEbitdaTree]
   Consumes: profile + assessment summary + indexed opportunity list
   Produces: EbitdaTreeResult (recursive node tree + estimates)
         │
         ▼
[PersistResults]
   Consumes: ALL of the above
   Produces: DynamoDB records
```

---

## Token/Cost Analysis Per Scan

Assuming typical Anthropic pricing for claude-sonnet-4:

| Call | Est. Input Tokens | Est. Output Tokens | Est. Thinking Tokens |
|------|------------------|--------------------|---------------------|
| URL Resolution | ~1,500 | ~50 | ~500-1,000 |
| ExtractProfile | ~4,000-15,000 | ~500-800 | ~1,000-2,000 |
| AssessRisk | ~2,000-3,000 | ~2,000-3,000 | ~2,000-4,000 |
| GenOpps-High | ~3,000-4,000 | ~2,000-3,000 | ~2,000-4,000 |
| GenOpps-Strategic | ~3,000-4,000 | ~1,000-2,000 | ~1,500-3,000 |
| GenEbitdaTree | ~3,000-4,000 | ~3,000-5,000 | ~2,000-4,000 |
| **Total** | **~16,500-30,000** | **~8,550-13,850** | **~9,000-18,000** |

---

## Where Time Is Spent (Breakdown)

| Activity | Time | % of Total |
|----------|------|------------|
| HTTP scraping (1-2 requests) | ~10-15s | ~5% |
| AI thinking tokens (extended thinking) | ~30-60s cumulative | ~25% |
| AI output token generation | ~60-120s cumulative | ~45% |
| Network latency to Anthropic API (5 calls) | ~5-15s | ~5% |
| DynamoDB writes | ~2s | ~1% |
| Sequential waiting (steps that can't overlap) | ~30-40s | ~20% |

**Key insight**: Output token generation (structured JSON) dominates. Extended thinking adds ~25% overhead. The pipeline is I/O-bound (waiting on Anthropic API), not CPU-bound.

---

## Part 2: Provider Efficiency Analysis and Optimization Findings

### How Each Provider Handles Structured Output

#### Anthropic (Claude — current production provider)

```
AnthropicProvider._build_request_params() builds:
{
  "model": "claude-sonnet-4-20250514",
  "messages": [{"role": "user", "content": "<system_prompt>\n\n<user_prompt>"}],
  "max_tokens": max_tokens + thinking_budget,     // e.g. 8192 + 4096 = 12288
  "thinking": {"type": "enabled", "budget_tokens": 4096},
  "tools": [{
    "name": "structured_response",
    "description": "Return the structured response matching the required schema.",
    "input_schema": <our_json_schema>
  }],
  "tool_choice": {"type": "any"}   // forces tool use
}
```

**Mechanism**: Tool-use. The model generates a `tool_use` content block where the `input` field
is constrained to match our JSON schema. Thinking tokens are generated first, then the tool call.

**Key characteristics**:
- Extended thinking runs BEFORE structured output — adds latency proportional to thinking budget
- `tool_choice: any` forces a tool call — the model cannot produce free-text
- System prompts placed in `system` parameter get **automatic prompt caching** (90% input cost reduction on cache hits, reduced TTFT)
- Tool definitions count as input tokens
- Retry: 3 attempts with exponential backoff (factor=2) on AIProviderError

#### OpenAI (GPT — alternate provider)

```
OpenAIProvider._build_structured_request() builds:
{
  "model": "gpt-5.1",
  "input": "<system_prompt>\n\n<user_prompt>",
  "reasoning": {"effort": "low"},
  "text": {
    "verbosity": "medium",
    "format": {
      "type": "json_schema",
      "name": "structured_response",
      "schema": <our_json_schema>,
      "strict": true
    }
  },
  "store": false
}
```

**Mechanism**: Native `json_schema` structured output with strict mode. The model is constrained
at the decoding level to produce valid JSON matching the schema — no tool-use wrapper needed.

**Key characteristics**:
- `strict: true` guarantees valid JSON matching schema at decode time
- No tool_use overhead — schema is enforced directly on output
- `reasoning.effort` controls internal reasoning (no explicit thinking budget)
- OpenAI auto-adds `additionalProperties: false` and `required` fields for strict compliance
- Instructions via `instructions` parameter (not used by our pipeline)

#### Efficiency Comparison

| Factor | Anthropic (tool_use) | OpenAI (json_schema) |
|--------|---------------------|---------------------|
| Structured output mechanism | Tool call wrapper | Native decoding constraint |
| Thinking overhead | Explicit budget (visible, controllable) | Internal reasoning (opaque) |
| Schema as input tokens | Yes (tool definition) | Yes (format.schema) |
| System prompt caching | Yes (system parameter) | Partial (instructions) |
| Guaranteed valid JSON | Yes (tool_use schema) | Yes (strict mode) |
| Token overhead | Higher (tool_use framing) | Lower (direct output) |

---

### Finding 1: System Prompts Are in the Wrong Location (ALL 5 CALLS)

**Problem**: Every pipeline step concatenates system + user prompt into one string:

```python
# What we do (every pipeline step):
prompt = f"{_SYSTEM_PROMPT}\n\n{user_prompt}"
client.query_structured(input_text=prompt, json_schema=schema)
```

This sends the system prompt as **user message content**, not in the dedicated system field.

**What the providers expect**:

```python
# Anthropic — system prompt should go in params["system"]
# Currently goes into messages[0]["content"] as user text

# OpenAI — system prompt should go in params["instructions"]
# Currently goes into params["input"] as user text
```

**What we should do**: Use the `instructions` parameter on `get_client()`:

```python
# Proposed — system prompt in dedicated field:
client = factory.get_client(
    verbosity=Verbosity.MEDIUM,
    reasoning_effort=ReasoningEffort.LOW,
    precision=Precision.STANDARD,
    instructions=_SYSTEM_PROMPT,     # ← goes to proper system field
)
response = client.query_structured(input_text=user_prompt, json_schema=schema)
```

The `AIClientFactory.get_client()` already supports `instructions` — it's in the cache key and
passed to the provider constructor. We just never use it.

**Impact**:
- **Anthropic**: Enables automatic prompt caching. System prompts >1024 tokens get cached, giving
  90% input token cost reduction and reduced TTFT on subsequent calls. Our system prompts are
  ~200-400 tokens individually, but could be restructured with a shared preamble to cross the threshold.
- **OpenAI**: Moves system context to the `instructions` parameter, which is processed at higher
  attention priority than user input.
- **All providers**: Cleaner separation of concerns — the model knows what's instruction vs. data.

---

### Finding 2: "Respond with valid JSON only" Is Redundant (ALL 5 CALLS)

**Problem**: Every system prompt includes:
```
Always respond with valid JSON only. No markdown, no explanation text outside the JSON.
```

**Why it's redundant**:
- **Anthropic**: `tool_choice: {"type": "any"}` forces the model to produce a tool_use block.
  The output IS the tool arguments — there's no way to produce free text.
- **OpenAI**: `strict: true` in `json_schema` format constrains decoding to valid JSON.
  The model literally cannot produce non-JSON output.

**Impact**: Wastes ~30 input tokens per call (×5 = 150 tokens/scan). More importantly, it can
confuse the model — it's being told to do something the API already enforces, which can cause
the model to spend thinking tokens "planning" JSON output instead of reasoning about the task.

---

### Finding 3: CompanyProfile Extracts 10 Fields the Frontend Never Displays

**Frontend usage audit** (from AnalysisDetail.tsx and EbitdaTree.tsx):

| Profile Field | Displayed in UI? | Used by Downstream AI? |
|--------------|-----------------|----------------------|
| company_name | YES (header) | YES (all prompts) |
| industry | YES (badge) | YES (all prompts) |
| industry_sector | NO | YES (risk weighting) |
| business_model | NO | YES (risk + opps context) |
| description | NO | YES (company context) |
| products_services | NO | Marginal (array of strings) |
| target_market | NO | Marginal (short string) |
| company_size | NO | YES (investment sizing) |
| revenue_model | NO | Marginal (short string) |
| tech_signals | NO | Marginal (array, AI rediscovers these) |
| competitive_positioning | NO | YES (risk context) |
| ai_maturity | NO | Marginal (AI reassesses this) |
| key_risks_visible | NO | Marginal (AI discovers its own risks) |

**Assessment**: 6 fields are genuinely useful for downstream AI quality. 4 fields (`products_services`,
`target_market`, `revenue_model`, `tech_signals`) add marginal value — the downstream AI will
identify these patterns itself from the risk assessment context. 3 fields (`ai_maturity`,
`key_risks_visible`, and arguably `tech_signals`) are **actively redundant** — AssessRisk and
GenOpps will independently assess AI maturity and discover risks.

**Potential optimization**: Reduce to 8-9 fields. Removes 4-5 fields from extraction output,
saving ~200-400 output tokens on ExtractProfile and ~200-400 input tokens on every downstream
call that passes the profile.

---

### Finding 4: EBITDA Tree Schema Has Redundant + Expensive Structure

**Problem 1 — Dual parent-child encoding**: Each node has BOTH:
- `parent_id` — reference to parent node
- `children` — nested array of child nodes

This is redundant. The recursive `children` nesting forces deeply nested JSON output which is
significantly slower to generate than a flat array.

**Problem 2 — Frontend flattens anyway**: The EbitdaTree.tsx component flattens the tree for
rendering and uses `parent_id` for graph construction.

**Problem 3 — Unused fields**: The frontend doesn't render `id` or `parent_id` directly
(they're structural). The `description` is only shown in a hover tooltip.

**Current schema output** (per node, 9 required fields):
```json
{
  "id": "revenue_saas",
  "label": "SaaS Revenue",
  "type": "revenue",
  "value_range": "$5M-$15M",
  "percentage_of_parent": 60,
  "parent_id": "total_revenue",
  "description": "Recurring subscription revenue from enterprise clients...",
  "linked_opportunity_indices": [0, 2],
  "children": [...]   // ← forces recursive nesting
}
```

**Proposed flat schema** (per node, 7 fields — drop `id`, drop `children`):
```json
{
  "label": "SaaS Revenue",
  "type": "revenue",
  "value_range": "$5M-$15M",
  "percentage_of_parent": 60,
  "parent_id": "total_revenue",
  "description": "One sentence.",
  "linked_opportunity_indices": [0, 2]
}
```

Use `label` as the node identifier (unique within a tree). Use `parent_id` referencing parent's
`label`. Flat array instead of recursive nesting. Constrain `description` to "1 sentence".

**Impact**: Eliminates recursive JSON generation. With 15-25 nodes, each saving ~30-50 output
tokens from removed nesting + `id` + shorter descriptions = **~500-1,200 fewer output tokens**.
Flat arrays are also faster for AI to generate than recursive structures because the model doesn't
need to track nesting depth. Estimated: **15-25s savings**.

---

### Finding 5: Thinking Budget Is Uniform but Task Complexity Varies

**Problem**: All 5 calls use `ReasoningEffort.LOW` = 4,096 thinking tokens.

For Anthropic, thinking tokens are generated BEFORE the response starts. Each thinking token
costs roughly the same time as an output token. So 4,096 thinking tokens ≈ 2-4 seconds of
latency per call.

| Call | Cognitive Task | Ideal Budget | Current | Waste |
|------|---------------|-------------|---------|-------|
| URL Resolution | Pattern match: "is this a portfolio page?" | MINIMAL (1,024) | LOW (4,096) | 3,072 tokens |
| ExtractProfile | Named entity extraction from text | MINIMAL (1,024) | LOW (4,096) | 3,072 tokens |
| AssessRisk | Analytical scoring with justification | LOW (4,096) | LOW (4,096) | 0 |
| GenOpps ×2 | Creative strategic recommendations | LOW (4,096) | LOW (4,096) | 0 |
| GenEbitdaTree | Financial decomposition | LOW (4,096) | LOW (4,096) | 0 |

**Provider compatibility caveat**: `ReasoningEffort.MINIMAL` ("minimal") is **Anthropic-only**.
OpenAI's Responses API `reasoning.effort` parameter only accepts `"low"`, `"medium"`, `"high"` —
sending `"minimal"` would cause an API error. The Anthropic provider maps MINIMAL → 1,024
thinking budget tokens, but the OpenAI provider passes the raw value `"minimal"` to the API
with no clamping.

**Options**:
- **Safe (no SDK change)**: Keep LOW as the minimum. Accept the 4,096 thinking budget for
  extraction tasks. No provider compatibility risk.
- **Better (requires signalfield_core change)**: Add clamping in `OpenAIProvider` to map
  MINIMAL → "low". This lets us express intent (minimal reasoning) while each provider
  handles it appropriately. Anthropic gets 1,024 tokens, OpenAI gets "low" effort.

**Impact if MINIMAL is usable**: Reduces 6,144 thinking tokens = **~3-5 seconds** on Anthropic.
On OpenAI, clamped to "low" so no change from current behavior.

---

### Finding 6: AssessRisk Has Two Redundant Text Fields Per Risk Score

**Current schema** (per risk score):
```json
{
  "category": "competitive_displacement",
  "score": 7,
  "explanation": "2-3 sentences explaining this specific score",
  "evidence": "Specific signals supporting this assessment"
}
```

**Problem**: `explanation` and `evidence` overlap significantly. A typical output:
- explanation: "High risk of competitive displacement. AI-native startups are entering the market
  with automated solutions that could undercut traditional service delivery."
- evidence: "Companies like Jasper, Copy.ai, and Writer are offering AI-powered content services
  at 10x lower cost. The company's manual workflow is vulnerable to automation."

These two fields together produce ~4-6 sentences per category × 8 categories = **32-48 sentences
of risk text**. The frontend renders both in the risk detail view, but they're largely saying
the same thing with different framing.

**Proposed**: Merge into a single `rationale` field:
```json
{
  "category": "competitive_displacement",
  "score": 7,
  "rationale": "1-2 sentences: score justification with specific evidence"
}
```

**Impact**: Cuts risk assessment text output roughly in half. 8 × (explanation + evidence) →
8 × rationale. Saves ~800-1,500 output tokens = **~10-15 seconds**.

**Frontend change required**: Update `AnalysisDetail.tsx` to render `rationale` instead of
separate `explanation` + `evidence` blocks.

---

### Finding 7: Opportunity `risk_mitigated` Field Is Never Displayed

**Problem**: The frontend types include `risk_mitigated` but it's never rendered in the UI.
Each opportunity (3-5 per scan) requires the model to determine which risk category it addresses
and output the category ID string.

**Impact**: Removing saves ~15-25 output tokens + reduces thinking overhead (model no longer
needs to map each opportunity to a risk category). Small but free.

---

### Finding 8: Input Token Waste from `json.dumps(indent=2)`

**Problem**: All prompts use pretty-printed JSON:
```python
json.dumps(profile_dict, indent=2)    # ~800 tokens
json.dumps(assessment_dict, indent=2)  # ~1,200 tokens
```

vs. compact JSON:
```python
json.dumps(profile_dict)              # ~500 tokens
json.dumps(assessment_dict)           # ~750 tokens
```

Indented JSON adds ~40-60% more whitespace tokens. It appears in:
- AssessRisk prompt: 1× profile
- GenOpps prompts: 2× (profile + assessment, duplicated across both parallel calls)
- GenEbitdaTree prompt: 1× profile

**Impact**: ~400-800 wasted input tokens per scan. At Anthropic's pricing ($3/MTok input),
this is negligible cost-wise, but every input token adds to processing time. Savings: **~1-2s**.

AI models parse compact JSON just as accurately as indented JSON — the tokenizer doesn't need
whitespace for comprehension.

---

### Finding 9: URL Resolution Passes Excessive Input

**Current**:
```python
scraped_text[:3000]          # 3,000 chars ≈ 750-1,000 tokens
scraped_links[:100]          # 100 link objects ≈ 1,500-3,000 tokens (URLs are token-expensive)
```

**For URL resolution, the model needs**:
- Page title (already provided separately)
- Whether the page looks like a portfolio listing vs. company website
- A few links to find the actual company URL

**Proposed**:
```python
scraped_text[:1000]          # 1,000 chars ≈ 250-350 tokens
scraped_links[:20]           # 20 links ≈ 300-600 tokens
```

**Impact**: Saves ~1,500-2,500 input tokens on this call. For a call that produces 1 output
field, this is a disproportionate amount of input context. Savings: **~1-2s TTFT improvement**.

---

### Finding 10: Parallel GenOpps Calls Duplicate ~3,000 Input Tokens

**Problem**: Both GenOpps calls include identical context:
- Full profile JSON (~500-1,000 tokens)
- Full assessment with all 8 risk scores and their explanation/evidence (~1,000-2,000 tokens)
- Same strategic categories instructions (~100 tokens)

This is inherent to parallel calls (each needs full context), but the assessment context could
be **summarized** for the strategic call since it focuses on lower-priority risks:

```python
# High-priority call: full assessment (needs detailed risk scores for top 3)
# Strategic call: could use summary only (overall_score, tier, top_risks, analysis_summary)
#   — skip the detailed risk_scores JSON for non-focus categories
```

**Impact**: Saves ~500-1,000 input tokens on the strategic call. Minor: **~0.5-1s**.

---

## Optimization Roadmap (Ranked by Impact)

### Tier 1 — High Impact: Reduce Output Tokens (~30-50s savings)

These target the dominant cost: **output token generation time**.

| # | Change | Est. Savings | Risk |
|---|--------|-------------|------|
| 1 | Flatten EBITDA tree: remove `children` nesting, drop `id`, constrain `description` to 1 sentence | 15-25s | Low — frontend already flattens; needs frontend type update |
| 2 | Merge AssessRisk `explanation` + `evidence` → single `rationale` (1-2 sentences with evidence) | 10-15s | Low — frontend renders both, update to render one |
| 3 | Drop `risk_mitigated` from opportunity schema | 1-2s | None — never displayed |
| 4 | Constrain opportunity `related_services` to "1-2 vendors" | 1-2s | Low — only used in PDF export |
| 5 | Reduce `analysis_summary` to "1-2 sentences" (from "3-4") | 1-2s | None — minor text reduction |

### Tier 2 — Medium Impact: Reduce Thinking + Input Tokens (~8-15s savings)

| # | Change | Est. Savings | Risk |
|---|--------|-------------|------|
| 6 | URL Resolution + ExtractProfile → MINIMAL thinking (1,024) | 3-5s | Low — extraction, not reasoning |
| 7 | Use proper system prompt location (`instructions` param) | 5-10s on cache hits | None — existing API support |
| 8 | Remove "respond with valid JSON" from all system prompts | 1-2s | None — API enforces this |
| 9 | Compact JSON: `json.dumps(data)` instead of `indent=2` | 1-2s | None — AI reads compact JSON fine |
| 10 | Reduce URL resolution input: text[:1000], links[:20] | 1-2s | Low — plenty for URL detection |

### Tier 3 — Architectural: Rethink Pipeline Parallelism (~60-120s savings)

These require design changes but offer the biggest absolute wins.

| # | Change | Est. Savings | Risk | Complexity |
|---|--------|-------------|------|------------|
| 11 | **Parallelize ExtractProfile ∥ AssessRisk**: Pass raw scraped text to AssessRisk instead of structured profile. Both run after ScrapeAndResolve, not sequentially. | 30-45s (eliminates waiting for ExtractProfile) | Medium — AssessRisk gets raw text instead of structured profile; may slightly reduce risk score quality | Medium |
| 12 | **Merge AssessRisk + GenOpps into 1 call**: Single AI call produces risk scores + opportunities together. Eliminates one full AI round-trip. | 30-50s (eliminates entire AI call + thinking cycle) | Medium — very large output may offset time savings; needs careful schema design | High |
| 13 | **Use faster model for extraction**: URL Resolution and ExtractProfile on a Haiku-class model (faster, cheaper, sufficient for extraction). | 20-30s (extraction calls drop to ~5-10s each) | Medium — requires PRECISION tier below STANDARD in factory; extraction quality may dip slightly | Medium |
| 14 | **Cache profile + assessment for re-scans**: If same URL scanned within 24h, skip Steps 1-3 entirely. | Up to 120s (skip to GenOpps) | Low — cache invalidation is simple (URL + time) | Low |
| 15 | **Stream-and-forward**: Start GenEbitdaTree as soon as opportunities begin streaming (don't wait for full response). | 10-20s | High — requires streaming API + partial result handling | High |

---

## Realistic Timeline Projections

### Current State
```
Scrape(15s) → ExtractProfile(30-45s) → AssessRisk(45-60s) → GenOpps(50-70s) → EbitdaTree(60-90s) → Persist(2s)
Total: ~3.5-4.5 min wall-clock (with GenOpps parallelized)
```

### After Tier 1 + Tier 2 (prompt/schema changes only)
```
Scrape(12s) → ExtractProfile(25-35s) → AssessRisk(30-40s) → GenOpps(40-55s) → EbitdaTree(35-55s) → Persist(2s)
Total: ~2.5-3.0 min wall-clock
Savings: ~30-60s from current
```

### After Tier 3 Option A: Parallel ExtractProfile ∥ AssessRisk
```
                ┌→ ExtractProfile(25-35s) ─┐
Scrape(12s) → ─┤                           ├→ GenOpps(40-55s, parallel) → EbitdaTree(35-55s) → Persist(2s)
                └→ AssessRisk(30-40s) ──────┘
Total: ~2.0-2.5 min wall-clock
Savings: ~30-45s more (ExtractProfile no longer on critical path)
```

### After Tier 3 Option B: Merge AssessRisk + GenOpps
```
                ┌→ ExtractProfile(25-35s) ─┐
Scrape(12s) → ─┤                           ├→ AssessRisk+GenOpps(60-80s) → EbitdaTree(35-55s) → Persist(2s)
                └→ (parallel path)  ────────┘
Total: ~1.8-2.8 min wall-clock
```

### After Tier 3 Options A + C (parallel + faster extraction model)
```
                ┌→ ExtractProfile-fast(8-12s) ─┐
Scrape(12s) → ─┤                                ├→ GenOpps(40-55s) → EbitdaTree(35-55s) → Persist(2s)
                └→ AssessRisk(30-40s) ───────────┘
Total: ~1.5-2.5 min wall-clock
```

### Theoretical Best (all Tier 3 options + aggressive parallelism)
```
                ┌→ ExtractProfile-fast(8s) ──────┐
Scrape(10s) → ─┤                                  ├→ combined-GenOpps+EbitdaTree(50-70s) → Persist(2s)
                └→ AssessRisk-from-raw-text(25s) ─┘
Total: ~1.2-1.5 min wall-clock
```

### To reach 15-30 seconds (the stated goal)
This requires fundamentally different architecture:
- Pre-computed profiles (cache scrape + extraction results)
- Single mega-call that produces risk + opportunities + EBITDA in one shot
- Or: move to a faster model tier (Haiku-class) for ALL calls, accepting some quality trade-off
- Or: hybrid approach — fast preliminary results in 15s, then background refinement

---

## Frontend Fields Actually Used (Audit Results)

For reference — this drives which output fields we can safely remove or constrain:

| Model | Total Fields | Used in UI | Unused | Notes |
|-------|-------------|-----------|--------|-------|
| CompanyProfile | 13 | 3 | 10 | Only company_name, industry, company_url displayed |
| RiskAssessment | 5 | 5 | 0 | All fields rendered |
| RiskScore | 4 | 4 | 0 | explanation + evidence both rendered (merge candidate) |
| Opportunity | 11 | 10 | 1 | risk_mitigated never rendered |
| EbitdaNode | 9 | 6 | 3 | id, parent_id, children not directly rendered |
| EbitdaTree (top) | 4 | 3-4 | 0 | businessModelSummary conditionally shown |

Note: Even though 10 profile fields aren't displayed in the frontend, most are consumed by
downstream AI steps as input context. The optimization is to reduce these to the 8-9 that
genuinely improve downstream AI quality.

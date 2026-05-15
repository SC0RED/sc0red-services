# AI Model Benchmark Comparison

**Baseline:** gpt-5.1 (2026-05-15)
**Candidate:** gpt-5.4-mini (2026-05-15)
**Prompts:** 10

## Aggregate Metrics

| Metric | gpt-5.1 | gpt-5.4-mini | Delta |
|--------|---------|-----------|-------|
| Total cost | $0.0779 | $0.0275 | -64.7% 🟢 significant savings |
| Avg latency | 11.4s | 3.2s | -72.2% 🟢 much faster |
| Schema compliance | 100% | 100% | 0.0% |
| Errors | 0 | 0 | |

## Per-Task-Type Breakdown

| Task Type | Count | Cost Δ | Latency Δ | Content Diffs |
|-----------|-------|--------|-----------|---------------|
| arrow_yesno | 1 | -47.7% | -47.0% | 1/1 |
| arrows_priorities | 1 | -49.0% | -44.0% | 1/1 |
| detail_opportunity | 1 | -86.5% | -66.6% | 1/1 |
| financial_titles | 1 | -54.9% | -58.2% | 1/1 |
| ideation | 1 | -69.3% | -87.7% | 1/1 |
| internal_objective_detail | 1 | -47.8% | -30.7% | 1/1 |
| mission_text | 1 | -39.1% | -43.3% | 1/1 |
| profile_extraction | 1 | -66.5% | -64.5% | 1/1 |
| risk_batch | 1 | -79.4% | -88.2% | 1/1 |
| vp_primary | 1 | -49.1% | +3.6% | 0/1 |

## Per-Prompt Comparison

### 🟡 strategy_map_arrow_yesno_01: Strategy-map arrow yes/no — one candidate cause-effect link among 60+ parallel calls

| | gpt-5.1 | gpt-5.4-mini |
|---|---|---|
| Cost | $0.0063 | $0.0033 |
| Latency | 4.4s | 2.4s |
| Tokens | 3903 | 3848 |
| Schema OK | ✅ | ✅ |

**Content differences:**
- hypothesis: length 342 → 196 (ratio: 0.57x)

### 🟡 strategy_map_arrows_priorities_01: Strategy-map holistic priorities synthesis — the historic tail-latency outlier

| | gpt-5.1 | gpt-5.4-mini |
|---|---|---|
| Cost | $0.0061 | $0.0031 |
| Latency | 4.3s | 2.4s |
| Tokens | 3426 | 3373 |
| Schema OK | ✅ | ✅ |

**Content differences:**

### 🟡 strategy_map_internal_detail_01: Strategy-map Round-3 internal-objective elaboration (definition, category, confidence)

| | gpt-5.1 | gpt-5.4-mini |
|---|---|---|
| Cost | $0.0060 | $0.0031 |
| Latency | 4.6s | 3.2s |
| Tokens | 2960 | 2944 |
| Schema OK | ✅ | ✅ |

**Content differences:**
- definition: length 680 → 582 (ratio: 0.86x)
- rationale_source: length 180 → 158 (ratio: 0.88x)

### 🟡 strategy_map_financial_titles_01: Strategy-map Round-1 financial-perspective title list (3 short objective titles)

| | gpt-5.1 | gpt-5.4-mini |
|---|---|---|
| Cost | $0.0054 | $0.0024 |
| Latency | 3.8s | 1.6s |
| Tokens | 2910 | 2798 |
| Schema OK | ✅ | ✅ |

**Content differences:**

### 🟡 strategy_map_mission_text_01: Strategy-map mission-statement generation from scrape

| | gpt-5.1 | gpt-5.4-mini |
|---|---|---|
| Cost | $0.0043 | $0.0026 |
| Latency | 2.8s | 1.6s |
| Tokens | 3162 | 3186 |
| Schema OK | ✅ | ✅ |

**Content differences:**
- statement: length 140 → 166 (ratio: 1.19x)

### 🟢 strategy_map_vp_primary_01: Strategy-map value-proposition primary classifier (operational_excellence / customer_intimacy / product_leadership / hybrid)

| | gpt-5.1 | gpt-5.4-mini |
|---|---|---|
| Cost | $0.0054 | $0.0027 |
| Latency | 3.8s | 3.9s |
| Tokens | 3442 | 3375 |
| Schema OK | ✅ | ✅ |

Content: ✅ identical

### 🟡 profile_extract_01: ParallelProfileRisk — extract structured company profile from scrape

| | gpt-5.1 | gpt-5.4-mini |
|---|---|---|
| Cost | $0.0096 | $0.0032 |
| Latency | 13.3s | 4.7s |
| Tokens | 2094 | 1794 |
| Schema OK | ✅ | ✅ |

**Content differences:**
- ai_maturity: length 16 → 17 (ratio: 1.06x)
- industry: length 67 → 84 (ratio: 1.25x)
- description: length 396 → 382 (ratio: 0.96x)
- target_market: length 202 → 153 (ratio: 0.76x)
- business_model: length 105 → 108 (ratio: 1.03x)
- competitive_positioning: length 549 → 337 (ratio: 0.61x)
- industry_sector: length 10 → 13 (ratio: 1.3x)
- revenue_model: length 316 → 131 (ratio: 0.41x)

### 🟡 risk_batch_01: ParallelProfileRisk — assess 4 risk categories with rationale (audit-trail quality matters)

| | gpt-5.1 | gpt-5.4-mini |
|---|---|---|
| Cost | $0.0175 | $0.0036 |
| Latency | 44.2s | 5.2s |
| Tokens | 3047 | 2038 |
| Schema OK | ✅ | ✅ |

**Content differences:**

### 🟡 ideation_01: ParallelProfileRisk — generate one specific AI opportunity addressing margin compression (creativity matters)

| | gpt-5.1 | gpt-5.4-mini |
|---|---|---|
| Cost | $0.0058 | $0.0018 |
| Latency | 19.8s | 2.4s |
| Tokens | 1627 | 1393 |
| Schema OK | ✅ | ✅ |

**Content differences:**
- value_lever: length 12 → 9 (ratio: 0.75x)
- description: length 859 → 405 (ratio: 0.47x)
- strategic_category: length 15 → 22 (ratio: 1.47x)
- title: length 85 → 75 (ratio: 0.88x)

### 🟡 detail_01: DetailOpportunities — implementation steps + timeline + investment range + ROI (specificity matters)

| | gpt-5.1 | gpt-5.4-mini |
|---|---|---|
| Cost | $0.0114 | $0.0015 |
| Latency | 12.9s | 4.3s |
| Tokens | 1373 | 563 |
| Schema OK | ✅ | ✅ |

**Content differences:**
- roi_estimate: length 1167 → 278 (ratio: 0.24x)

## Recommendation

✅ **Good candidate.** -64.7% cost change with 0 high-severity content differences. Manual review of flagged prompts recommended.

---

## Human-review verdict (2026-05-15)

Applied the OpenSpec quality gate from `upgrade-strategy-map-to-mini-model/design.md` §3:

### Strategy-map (6/6 prompts) — 🟢 PASS

All six pass cleanly. Notable wins:
- `arrows_priorities` (the historic 184s tail-latency outlier): 2.4s on mini vs 4.3s on gpt-5.1.
- `vp_primary`: identical content.
- `arrow_yesno`: hypothesis 342→196 chars, well within the 20-500 schema bound.
- `internal_objective_detail`: definition 0.86x, rationale 0.88x — barely shorter.
- `financial_titles`, `mission_text`: no content regression.

Migration cleared for all strategy-map AI calls.

### Other 4 surfaces — verdicts

| Surface | Verdict | Reasoning |
|---|---|---|
| `profile_extract_01` | 🔴 | Mini misclassified `industry_sector` as "Manufacturing" (should be Technology). `revenue_model` lost specific anchor numbers ($48K/robot/yr, $200M ARR target). `competitive_positioning` lost quantitative metrics (31% throughput median, <5% churn vs 8-15% industry). `ai_maturity` underestimated ("Early exploration" vs gpt-5.1's "Partial adoption"). |
| `risk_batch_01` | 🟡 accept | Rationales shorter (2-3 sentences vs 3-4) but no factual regression. Schema-compliant. Huge latency win: 44.2s → 5.2s (gpt-5.1 hit a tail spike here). |
| `ideation_01` | 🟡 accept | Different but equally valid opportunities (revenue-side pricing engine vs cost-side diagnostics copilot). Both schema-compliant, specific, actionable. |
| `detail_01` | 🔴 | ROI estimate 1167→278 chars (0.24x). Mini lost the explicit financial bridge that PE diligence users consume — revenue → COGS → BOM → addressable → 3-year EBITDA uplift → valuation impact at EBITDA multiple. Mini's ROI is correct but high-level; gpt-5.1's reads as a deliverable. |

### Migration plan

8 of 10 call sites migrate to `gpt-5.4-mini` via SDK upgrade. 2 stay on `gpt-5.1` via per-site `Precision.ADVANCED` override:

- `ParallelProfileRiskAndIdeation` `extract_profile` — factual misclassification on mini
- `DetailOpportunities._run_ai_call` — ROI specificity for PE users

Expected production impact: ~-55% to -60% cost, ~-50% to -60% wall clock, tail-latency spikes on strategy-map largely eliminated.
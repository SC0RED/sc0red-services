# Pipeline Performance Analysis & Optimization Decisions

## Current State (as of 2026-03-17)

### Pipeline Architecture

```
ScrapeAndResolve → ParallelProfileAndRisk → ParallelOpportunitiesAndEbitda → PersistResults
```

### Measured Timings (Lambda, production)

| Step | Wall-clock | Bottleneck |
|------|-----------|------------|
| ScrapeAndResolve | 2.24s | URL resolution AI call |
| ParallelProfileAndRisk | 48.70s | assess_risk (48.70s) vs extract_profile (11.13s) |
| ParallelOpportunitiesAndEbitda | 70.09s | ebitda_tree (70.08s) vs high_priority (39.98s) vs strategic (54.75s) |
| PersistResults | 0.10s | — |
| **Total** | **~121s** | |

### Sub-step Breakdown

```
ScrapeAndResolveURL.initial_scrape:                    0.44s
ScrapeAndResolveURL.url_resolution:                    1.80s
ParallelProfileAndRisk.ai_call_extract_profile:       11.13s
ParallelProfileAndRisk.ai_call_assess_risk:           48.70s   ← bottleneck #2
ParallelOpportunitiesAndEbitda.ai_call_high_priority: 39.98s
ParallelOpportunitiesAndEbitda.ai_call_strategic:     54.75s
ParallelOpportunitiesAndEbitda.ai_call_ebitda_tree:   70.08s   ← bottleneck #1
PersistResults.total:                                  0.10s
```

### Root Cause Analysis

The two bottlenecks are:

1. **EBITDA tree (70s)** — recursive `$ref` JSON schema forces the model to generate deeply nested output with ~15 nodes × 7 fields each (~1000-1200 output tokens)
2. **Risk assessment (49s)** — single call generates 8 risk scores with rationales + overall_score + tier + top_risks + analysis_summary (~600-800 output tokens)

---

## Optimizations Evaluated

### 1. Split Risk Assessment into 8 Parallel Calls (1 category each)

**Idea:** Run 8 independent AI calls, each scoring a single risk category.

**Speed impact:** 49s → ~12s (each call generates ~50-80 output tokens, wall-clock = max of 8)

**Quality impact — SIGNIFICANT DEGRADATION:**

- **Cross-category reasoning is lost.** When the AI sees all 8 categories together, it makes connections: "supply chain risk is high *because* of the same technology obsolescence driving their core product risk." With individual calls, each rationale is written in isolation — the AI can't cross-reference or rank risks comparatively.

- **Score calibration drifts toward the center.** When scoring 1 category in isolation, the AI tends toward the middle (5-7 range) because it has no reference frame. When scoring all 8 together, it naturally uses the full range — some get 3s, some get 8s — because it's implicitly ranking them. Independent calls lose this relative calibration. A company that should get `[8, 7, 3, 2, 6, 4, 5, 3]` might get `[7, 6, 5, 4, 6, 5, 5, 4]` — everything drifts toward the center.

- **Rationales lose comparative depth.** PE users value rationales that say "competitive displacement is the dominant risk, significantly outweighing regulatory concerns." Individual calls can only assess each category in a vacuum.

**Decision: REJECTED** — quality degradation too significant for marginal speed gain over 2×4 split.

---

### 2. Split Risk Assessment into 2 Parallel Calls (4 categories each)

**Idea:** Run 2 AI calls, each scoring 4 risk categories. Compute overall_score, tier, top_risks, and analysis_summary programmatically.

**Speed impact:** 49s → ~25-30s (each call generates ~300-400 output tokens)

**Quality impact — MINIMAL:**

- 4 categories per call provides enough context for relative calibration ("competitive displacement is more severe than regulatory risk *for this company*")
- Cross-category reasoning preserved within each batch of 4
- Rationales can still reference comparisons within the batch
- Programmatic overall_score (weighted average) is deterministic and consistent
- Programmatic tier (threshold-based) matches what the AI would produce
- Programmatic top_risks (sort by score, take top 3) is exact
- Programmatic analysis_summary (template) is less nuanced than AI-generated but adequate for PE users who focus on the scores and rationales

**Splitting strategy:**

| Call | Categories | Rationale for grouping |
|------|-----------|----------------------|
| A | competitive_displacement, technology_obsolescence, customer_behavior, margin_compression | External market threats — naturally cross-reference |
| B | talent_workforce, regulatory_compliance, supply_chain, data_ip | Internal/operational risks — naturally cross-reference |

**Decision: APPROVED** — good speed improvement with minimal quality impact.

---

### 3. Flatten EBITDA Tree Schema (remove recursive `$ref`)

**Idea:** Replace the recursive tree schema with a flat `line_items` array using `parent_id` references. Reconstruct the nested tree programmatically before sending to the frontend.

**Speed impact:** 70s → ~25-35s from output token reduction alone.

**Why recursive schemas are slow (prompt engineering perspective):**

1. **Constrained decoding state machine complexity.** Recursive `$ref` creates a state machine where at every node's `children` array, the decoder must track nesting depth, which required fields have been emitted at each level, and whether to open a new child or close the array. This branching state machine grows exponentially with nesting depth.

2. **Token overhead from nesting.** Each level adds structural tokens — `{`, `}`, `[`, `]`, key names, commas. For a 15-node tree with 3 levels, structural tokens are ~30-40% of total output.

3. **Sequential bottleneck.** Every output token depends on the previous one — no parallelism within a single generation. Recursive tree: ~1000-1200 tokens. Flat list: ~300-400 tokens. 3x fewer tokens = 3x faster.

**Quality impact — NONE.** A flat list with `parent_id` references encodes the exact same tree structure. The AI generates the same content in a different JSON shape. Programmatic reconstruction is trivial (group by parent_id, attach children to parents).

**Decision: APPROVED** — significant speed improvement with zero quality loss.

---

### 4. Remove `description` and `percentage_of_parent` from EBITDA Nodes

**Idea:** Drop `description` and `percentage_of_parent` from the EBITDA node schema to reduce output tokens.

**Speed impact:** ~2-3 seconds saved on top of the flattening. With the flat schema already reducing node count to ~8-10:
- `description`: ~10-15 tokens × 10 nodes = ~100-150 tokens
- `percentage_of_parent`: ~3-5 tokens × 10 nodes = ~30-50 tokens
- Total: ~130-200 tokens at ~50-100 tokens/sec = **~1.5-4 seconds**

**Quality impact:**
- `description` is shown only on hover tooltip; `label` already conveys the key info
- `percentage_of_parent` is shown conditionally; derivable from value ranges

**Decision: REJECTED** — the ~2-3 second savings is negligible relative to the ~35-40s already saved by flattening. Not worth losing hover tooltips and percentage display for PE users who value detailed financial breakdowns.

---

### 5. Split EBITDA Tree into 2 Parallel Calls (Revenue vs Costs)

**Idea:** Run 2 parallel calls — one for revenue breakdown, one for cost breakdown — then merge programmatically.

**Speed impact:** 25-35s → ~12-18s (each call generates ~150-200 output tokens)

**Quality impact — SIGNIFICANT DEGRADATION:**

The EBITDA tree requires internal P&L consistency:
- Revenue streams should sum to total revenue
- COGS should reflect industry-appropriate gross margins relative to revenue
- Operating expenses should be reasonable relative to gross profit
- EBITDA = Revenue - COGS - OpEx must be plausible

When one call generates the full tree, the AI maintains this consistency naturally — it picks a revenue estimate and works downward, ensuring the math roughly holds.

With two separate calls:
- Call A picks revenue = "$10M-$50M" and generates streams
- Call B independently estimates COGS = "$8M-$40M" (80% of revenue for a SaaS company?)
- Gross Profit becomes implausibly small because the two calls didn't coordinate
- Operating expenses might exceed Gross Profit, making EBITDA negative

**Cannot fix with anchoring:** Giving Call B the revenue estimate from Call A makes them sequential, defeating the purpose.

**PE users will immediately spot inconsistent P&L numbers.** This is the exact audience that reads income statements daily.

**Decision: REJECTED** — P&L consistency cannot be maintained across independent calls.

---

### 7. Move EBITDA Tree Generation to Step 2 (parallel with risk assessment)

**Idea:** Since EBITDA is being flattened and simplified, remove its dependency on risk assessment and run it in parallel with profile extraction and risk scoring.

**Speed impact:** Would save ~30s by starting EBITDA earlier.

**Quality impact — MODERATE DEGRADATION:**

The current EBITDA prompt includes risk assessment context (overall score, tier, analysis summary). This helps the AI understand *where AI has the most P&L impact* — the tree isn't just a generic P&L decomposition, it's an AI-focused analysis.

Without risk context:
- The tree becomes a generic financial decomposition
- AI opportunity mapping to P&L nodes loses specificity
- The `summary` field can't reference risk themes

The EBITDA tree's value to PE users is showing "here's where AI opportunities map to your P&L." Without knowing the risk profile, the AI can't emphasize the right line items.

**Decision: REJECTED** — the risk-aware EBITDA tree is a key differentiator of the analysis.

---

## Approved Changes

| # | Change | Speed Impact | Quality Impact |
|---|--------|-------------|----------------|
| 1 | Split risk assessment into 2×4 parallel calls | 49s → ~30s | Minimal |
| 2 | Flatten EBITDA schema (remove recursive `$ref`) | 70s → ~30s | None |

## Projected Pipeline Timing

```
ScrapeAndResolve:                 2s   (unchanged)
ParallelProfileAndRisk:          ~30s  (was 49s — risk split 2×4)
ParallelOpportunitiesAndEbitda:  ~40s  (was 70s — flat EBITDA schema)
PersistResults:                   0.1s (unchanged)
Total:                           ~72s  (was 121s — 40% faster)
```

## Implementation Notes

### Risk Assessment Split

- Split categories into 2 groups of 4, grouped by thematic relevance (external threats vs internal/operational)
- Each call uses the same system prompt and full company context
- Each call returns 4 `{category, score, rationale}` objects
- Programmatic aggregation:
  - `overall_score` = mean of 8 scores, rounded to 1 decimal
  - `tier` = "critical" if ≥8.5, "high" if ≥6.5, "moderate" if ≥3.5, else "low"
  - `top_risks` = top 3 categories sorted by score descending
  - `analysis_summary` = template: "[Company] faces [tier] AI disruption risk (overall: [score]/10). Highest risk areas: [top1] ([score1]/10), [top2] ([score2]/10), and [top3] ([score3]/10)."

### EBITDA Schema Flattening

- Replace recursive `$ref` node schema with flat array of `{id, parent_id, label, type, value_range, description, percentage_of_parent}`
- Keep all fields — `description` (hover tooltip) and `percentage_of_parent` (conditional display) are retained for PE user experience; removing them saves only ~2-3s which is negligible
- Eliminate recursive `$ref` — this is the primary performance lever (simpler constrained decoding state machine, less structural token overhead)
- Keep `summary`, `revenue_estimate`, `ebitda_estimate` at the top level
- Programmatic tree reconstruction: group by `parent_id`, attach children, return roots
- Frontend receives the same nested `EbitdaNode[]` structure — no frontend changes needed
- `linked_opportunity_indices` continues to be computed programmatically after tree reconstruction

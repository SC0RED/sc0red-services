## Context

This change introduces an AI-generated Balanced Scorecard strategy map as the headline artifact of the rebranded **Vector Advisory** product (formerly Janus). The change came out of a leadership meeting where the strategic positioning of the product shifted from "AI risk-score generator" to "AI-augmented advisory companion." The strategy map is the artifact that anchors that positioning.

**Inputs to the design process** (the calibration corpus):
- The Kaplan & Norton 2000 HBR article "Having Trouble with Your Strategy? Then Map It" — provides the framework, four perspectives, three customer value propositions (Operational Excellence / Customer Intimacy / Product Leadership), four internal-process categories, learning-and-growth triad, anti-patterns (KPI scorecard illusion), and the Mobil exemplar.
- A 2011 Wawa strategy map deck produced by the leader during prior consulting work — the only direct evidence of the leader's house style. Shows: customer-voice quotes for the Customer perspective, Internal Process objectives organised into 2-3 named themes connected to revenue strategies, the People & Organization perspective (renamed from Learning & Growth) with the unusual triad of People / Technology / Financial Management, narrative connector phrases between perspectives, 50-150 word "We will…" objective definitions, and explicit naming of real initiatives.
- The Balanced Scorecard Institute template image — provides the visual layout: vision/mission/strategic-priorities/strategic-results header band, compact 4-perspective × 3-objective grid, scorecard columns to the right (Measures / Targets / Initiatives), core values strip at the bottom.

**Constraint**: the leader is no longer in the BSC consulting business and is not providing additional exemplars. We work with what we have.

**Concurrent changes**: `rename-janus-to-vector-advisory` is in flight (rename + section reorder + branding alignment). It explicitly defers the strategy-map placement decision to this change. The placement decision lives here; the rename ships the surrounding section order.

**Stakeholders**: leadership (positioning bet), engineering (implementation), prospects (the audience for the conversion artifact), the leader (one-time corpus contributor).

## Goals / Non-Goals

**Goals:**
- Produce a credible, AI-generated strategy map for every analysed company, anchored in the leader's house style and grounded in publicly available information.
- The map sits at the top of the analysis page (position 3, after header + overview cards) with a "Contact us for deep dive" CTA directly below it.
- The PDF includes a Strategy Map section as the first content section after the Executive Summary.
- Hallucination-control by design: confidence markers on every objective, public-data-only scope, explicit "What's Missing?" gaps that frame uncertainties as deep-dive conversation starters rather than authoritative claims.
- Strict "no measures / targets / initiatives" boundary in v1 — that absence is the visible value of a deep-dive engagement.
- Reuse Janus's existing pipeline architecture: `RequestStep` subclass, prompt files in `prompts/strategy_map/`, persistence on the assessment record, frontend rendering analogous to existing analytical components.

**Non-Goals:**
- Generating consultant-grade strategy maps. The bar is "credible enough to spark a conversation."
- User-editable strategy maps (no edit UI in v1; always shows the latest pipeline output).
- Industry-specific objective libraries. v1 ships with a single `default.md` industry pattern; per-industry refinement is a v2 driven by real customer feedback.
- Strategy-map history / versioning / regeneration UI.
- Custom CTA mechanics (embedded form, Calendly, modal). v1 links to the existing `https://www.sc0red.com/contact` page.
- Streaming or progressive UI while generation runs. The strategy map appears when the analysis completes (the existing async polling already handles this).
- Multi-language / localisation. English-only for v1.
- Strategic frameworks other than Balanced Scorecard (no OKRs, no Hoshin Kanri, no value-stream maps).

## Decisions

### 1. Calibration corpus structure (not training data, not RAG)

**Decision**: The leader's expertise is encoded as a set of markdown files — system prompt, framework guides, style guide, anti-patterns, exemplars, per-step templates — loaded at generation time via Janus's existing `load_system_prompt` / `load_guide` / `load_template` / `load_schema` helpers. No fine-tuning, no vector store, no embedding model.

**Alternatives considered:**

| Option | Why rejected |
|---|---|
| Fine-tune a base model on the leader's corpus | We have one full exemplar (Wawa). Fine-tuning needs hundreds. |
| RAG with vector retrieval over the corpus | Adds infrastructure (embedding model + vector store) for a corpus of ~10 files. Overkill at this scale. |
| Pure in-prompt instructions, no exemplars | Misses the leader's distinctive house style. AI defaults to generic K&N. |
| Few-shot in prompt + system grounding | The decided approach. Small corpus, high leverage, zero new infra. |

**Trade-off**: When the corpus grows (more industries, more exemplars), in-prompt loading hits context-window limits. Mitigation: the file structure leaves room for a future RAG layer that selects 2-3 most relevant exemplars per industry; v1 simply loads everything, assuming corpus stays small.

### 2. The seven-step generation chain (not a single prompt)

**Decision**: Generate the strategy map via seven LLM calls in sequence (or in parallel where dependencies allow):

```
Step 1 — Vision / Mission synthesis      (depends on scraped content)
Step 2 — Customer Value Proposition       (depends on Step 1 + opps + value chain)
         classification (1 of 3 + hybrid case)
Step 3 — Financial perspective objectives (depends on EBITDA tree + Step 2)
Step 4 — Customer perspective objectives  (depends on Step 2 + reviews + opps)
Step 5 — Internal Processes objectives    (depends on opps + value chain + Step 2)
Step 6 — Organizational Capacity          (depends on talent risk + tech signals)
         objectives (People/Tech/Culture)
Step 7 — Arrows + "What's Missing?" gaps  (depends on Steps 1-6)
```

Steps 3-6 can run in parallel after Steps 1-2 complete (each takes a different slice of pipeline output). This brings end-to-end latency to roughly 4 sequential AI rounds: Step 1 → Step 2 → (3, 4, 5, 6 in parallel) → Step 7.

**Alternatives considered:**

| Option | Why rejected |
|---|---|
| Single mega-prompt for the whole map | Output reliability degrades at this complexity. The seven-step chain enforces structure: each step's output is JSON-validated before feeding the next. Plus the value-prop classification (Step 2) is the single highest-leverage decision and benefits from being its own focused step. |
| Two steps: classification + everything | Better than one step but loses the per-perspective focus and parallelism. |
| Eight or more steps (e.g. split arrows from gaps) | Diminishing returns. Steps 7's two outputs naturally co-generate from the same context. |

**Trade-off**: Seven calls vs. one means more cost and more latency. Estimate: $0.10-0.30 per analysis, +30-90s end-to-end. Acceptable given the analysis already takes minutes; users polling for completion don't notice a 30-second extension.

### 3. Output schema is JSON, validated, persisted

**Decision**: The seven-step chain produces a single JSON document conforming to `schemas/strategy_map_output.json`. The schema captures:

- `vision: string`
- `mission: string`
- `valueProposition: { primary: enum, secondary?: enum, rationale: string }`
- `strategicPriorities: [{ name: string, result: string }]` (3 items)
- `financial: { objectives: Objective[] }` (3 items)
- `customer: { objectives: CustomerVoiceObjective[] }` (3-4 items)
- `internalProcesses: { themes: [{ name: string, objectives: Objective[] }] }` (2-3 themes)
- `organizationalCapacity: { people, technology, culture: Objective }` (1 each)
- `arrows: Arrow[]` (linked-hypotheses, 5-8 items)
- `whatsMissing: Gap[]` (2-4 items, each with title + description + deep-dive framing)
- `coreValues: string[]` (3-6 items, "(inferred)" if synthesised)
- `confidenceMarkers: { [objectiveId]: 'HIGH' | 'MEDIUM' | 'LOW' }`

Each `Objective` has `id`, `title`, `definition` (50-150 words, "We will…" voice), `confidence`, and an `originalIndices` field for cross-reference where applicable (e.g. EBITDA opportunity links).

**Alternatives considered:**

| Option | Why rejected |
|---|---|
| Markdown output | Hard to render reliably in React. Hard to validate. Hard to version. |
| Free-form structured output | LLM compliance is unreliable without a schema. Output drifts across regenerations. |
| Multiple schemas, one per step | Adds complexity for marginal benefit. A single rolled-up schema with optional fields is cleaner. |

### 4. Customer Value Proposition is a 4-way enum, not 3

**Decision**: The `valueProposition.primary` field is one of:
- `operational_excellence`
- `customer_intimacy`
- `product_leadership`
- `hybrid` (with `secondary` filled in to name the second proposition)

Mobil's case in the HBR article is hybrid (customer intimacy + operational excellence). Rather than force a single-pick that misrepresents real companies, we allow the AI to flag a hybrid case and explain it.

**Trade-off**: The hybrid option is a hallucination risk — the AI may default to "hybrid" when it can't decide. Mitigation: prompt explicitly requires that if hybrid is chosen, the rationale field must justify why neither single proposition fits; we'll review for accuracy on real analyses pre-launch.

### 5. House style is enforced by prompt, not by code

**Decision**: The Vector house style (customer-voice quotes for C, themed I groups, "We will…" definitions, P&O renaming, narrative connectors, etc.) is encoded as **prompt instructions** in `guides/vector_style_guide.md` and reinforced by the Wawa exemplar in `exemplars/wawa_2011.md`. The frontend rendering follows the schema; the schema doesn't enforce style at the field level.

**Alternatives considered:**

| Option | Why rejected |
|---|---|
| Schema-level enforcement (e.g. `customer.objective.format = 'quoted'`) | Brittle. Style is voice, not structure. Adding format constraints to schema invites schema sprawl. |
| Post-process validation (regex-check for first-person quotes) | Generates false positives, blocks legitimate generations. |
| Style guide + few-shot example + prompt instructions | The chosen approach. LLMs are good at style mimicry when the example is concrete. |

**Trade-off**: Style consistency depends on prompt quality. Mitigation: the generation step has unit tests that assert schema conformance; pre-launch we sample 5-10 real analyses and have a stakeholder eyeball the style before going live.

### 6. Confidence markers are per-objective, three-tiered, set by the generation step

**Decision**: Every objective carries one of `HIGH`, `MEDIUM`, `LOW` confidence:

- **HIGH** — directly inferred from concrete public data (e.g. financial objective derived from the EBITDA tree's revenue branch)
- **MEDIUM** — typical of similar companies in this industry (e.g. customer intimacy objectives that follow industry pattern)
- **LOW** — inferred from absence; reasonable but unverified (e.g. cultural objectives where public data is sparse)

The frontend renders the marker as a small visual chip on each objective card. The "What's Missing?" panel can elevate LOW-confidence items as deep-dive candidates.

**Why this matters**: distinguishes responsible inference from hallucination. Prospects reading the map can see which claims are grounded vs. which are pattern-matching. This is the central honesty mechanic.

### 7. "What's Missing?" gaps drive the deep-dive CTA

**Decision**: Step 7 of the generation chain identifies 2-4 strategic gaps the public-data analysis cannot resolve. Each gap has:
- `title` — short label of the gap
- `description` — 1-2 sentences explaining why it's a gap
- `deepDiveFraming` — 1 sentence framing what a Vector Advisory deep-dive would cover

These are surfaced as a panel beneath the strategy map, with a single sentence linking to the contact page: *"Vector Advisory's deep-dive engagement addresses these gaps. Contact us to learn more →"*

**Why this matters**: gaps make the CTA *specific*. Generic "contact us" → low conversion. "Contact us to discuss your customer-segment strategy" → higher conversion. Each generated map produces its own conversion bait.

### 8. Page placement: position 3 (after overview cards, before Top Actions)

**Decision**: On the analysis detail page, the strategy map renders immediately after the existing AnalysisHeader + AnalysisOverviewCards (score + radar). The deep-dive CTA renders directly below the strategy map. Top Actions, Value Chain, EBITDA, Risk Profile, Opportunities, and the document/re-analysis footer follow in the order established by `rename-janus-to-vector-advisory`.

**Why position 3 and not position 1?**: overview cards are a one-row visual orientation (overall score, risk dimensions radar). They establish "what you're looking at" in 5 seconds. The strategy map then provides the strategic narrative. Putting the strategy map before the overview cards would skip the at-a-glance orientation that prospects find useful first.

**Why not at the end?**: the strategy map is the conversion artifact. Hiding it after 7 sections of detail kills its lead-gen role. The "What's Missing?" gaps need to be visible on first scroll.

**Trade-off**: position 3 risks readers scrolling past it to "the real data" (Top Actions, Value Chain). Mitigation: future iteration can elevate to position 2 or 1 if analytics show low engagement; the placement is configurable via component composition order.

### 9. PDF integration mirrors screen placement

**Decision**: The PDF section order becomes:

```
Cover → Executive Summary → Strategy Map → Top Actions → Value Chain →
EBITDA → Risk Profile → Opportunity Roadmap → Methodology → Back Cover
```

A `PrintStrategyMap` print component is added under `frontend/src/components/print/`. It uses `print-section--break-before` so the strategy map starts on a fresh page, and renders without the live "What's Missing?" deep-dive CTA (replaced with a simpler "Strategic gaps to address" header — the back cover handles the conversion CTA in print).

### 10. Persistence: extend the assessment record, not a new table

**Decision**: The `StrategyMap` is persisted on the existing assessment record alongside `riskScores`, `opportunities`, `ebitdaTree`, `valueChain`. No new DynamoDB table.

**Alternatives considered:**

| Option | Why rejected |
|---|---|
| New `strategy_maps` table | Splits the analysis artefact across two reads. Adds JOIN logic. No real benefit at our scale. |
| Embed in the company record | Wrong granularity — re-analysis produces a new strategy map; assessment record is the right home. |
| Don't persist, regenerate on read | Costs $0.10-0.30 per page view. No. |

**Trade-off**: The assessment record grows. Acceptable given DynamoDB item size limits (400KB) and observed sizes (typical assessment is ~30KB; strategy map adds ~5-10KB).

## Risks / Trade-offs

- **Risk**: AI hallucinates objectives that look credible but aren't grounded in the company's actual strategy.
  - **Mitigation**: confidence markers + public-data scope + "What's Missing?" framing. The product's positioning explicitly says "this is what we can infer from public data; the deep dive validates."
- **Risk**: 75% of executive teams don't have consensus on their own customer value proposition (HBR article). The AI will sometimes pick wrong.
  - **Mitigation**: the hybrid option in the schema; the Step 2 prompt emphasises tentative framing ("the company appears to pursue X based on public positioning").
- **Risk**: Generic objectives ("improve customer satisfaction") slip past the prompt rules.
  - **Mitigation**: anti-patterns guide is explicit; few-shot Wawa exemplar shows specificity; pre-launch we manually review 10 generated maps and refine prompts on miss patterns.
- **Risk**: The "What's Missing?" gaps consistently miss real gaps (because the AI doesn't know what it doesn't know).
  - **Mitigation**: the gaps are framed as conversation starters, not authoritative diagnostics. Even imperfect gaps drive the CTA. Real customer feedback steers iteration.
- **Risk**: Per-analysis cost grows by $0.10-0.30. Multiplied across portfolio scans (potentially 50+ companies), per-scan cost could grow $5-15.
  - **Mitigation**: monitor in CloudWatch; if cost is prohibitive, future iteration can skip strategy-map generation for portfolio-scan companies and only generate for single-analysis pages.
- **Risk**: Section reorder + new section regresses the recently-shipped PDF visual quality.
  - **Mitigation**: re-run the visual verification gate from `improve-pdf-export-content` (3 representative analyses, before/after PDF capture) as part of this change's rollout.
- **Risk**: The leader's house style (Wawa) doesn't generalise. Different industries / business models may need different conventions.
  - **Mitigation**: ship with Wawa as the sole exemplar; collect customer feedback; if industry-specific patterns are needed, add `guides/industry_patterns/<industry>.md` files in v2 driven by data.
- **Risk**: Latency. Adding 30-90s to analysis time degrades user experience.
  - **Mitigation**: Steps 3-6 run in parallel (4 LLM calls concurrent). Worst-case end-to-end is ~60s additional. The analysis is already async (existing polling UI); users don't watch the spinner second-by-second.
- **Risk**: The "Contact us" page is a sc0red company-level form, not strategy-map-aware. Conversion attribution is weak — we won't easily know which strategy-map gap drove the click.
  - **Mitigation**: append URL parameters to the contact link (`?source=strategy-map&analysis-id={id}&gap={gap-id}`) so the contact form can attribute (if it preserves query params). Even without server-side attribution, frontend analytics can track clicks per gap.
- **Risk**: This change introduces a third in-flight delta against `polished-pdf-export`'s section-order requirement. Archive ordering matters.
  - **Mitigation**: same as `rename-janus-to-vector-advisory` — the deltas resolve cleanly when archived in dependency order. Tasks doc captures the ordering.

## Migration Plan

The strategy map is additive to the existing analysis output. Migration is straightforward:

```
Step 1 — Land the calibration corpus (markdown files, JSON schema)
         and the new pipeline step on `development`. Generation runs
         for new analyses but old analyses (without `strategyMap`) 
         continue to render — frontend conditionally hides the section.

Step 2 — Smoke-test on 3 representative analyses (the same set used
         for the PDF visual verification): one sparse, one mid-size,
         one with a deep EBITDA tree. Capture before/after page +
         PDF screenshots.

Step 3 — Land the frontend strategy-map components and the section
         placement at position 3 of the analysis page. PDF integration
         lands together.

Step 4 — Re-analyse the test set so generated strategy maps appear
         on those analyses. Visual review.

Step 5 — Announce to leadership / stakeholders that the strategy
         map is live on `dev.vector.sc0red.com` (assuming the rename
         change has shipped first; otherwise on `dev.janus.sc0red.com`).

Step 6 — Promote dev → testing → production with the same review
         gate at each stage.

Step 7 — Post-launch: 90-day observability window monitoring
         (a) generation-time latency, (b) AI cost per analysis,
         (c) "Contact us" CTA click-through, (d) any "Contact us"
         form submissions attributed to strategy-map source.
         Iterate on prompts based on observed misses.
```

**Backward compatibility**: existing analyses without `strategyMap` don't auto-regenerate. The frontend's conditional render handles this gracefully. If we want all analyses to have strategy maps, a small backfill script can iterate the assessment table and trigger re-analysis for each — out of scope for v1.

**Rollback strategy**: if generation produces poor-quality output post-launch, the fastest rollback is a feature flag on the frontend (`SHOW_STRATEGY_MAP=false`) that hides the section without disrupting the pipeline. The backend continues generating; we just don't show it. If prompts need rework, iterate on `prompts/strategy_map/` files and redeploy — no schema migration.

## Open Questions

- **Per-objective unique IDs**: should they be deterministic (e.g. `F1`, `F2`, `C1` like the Wawa example) or random UUIDs? Deterministic is more readable in the schema but requires conventions for ordering. Going with deterministic prefix + index (`F1, F2, F3, C1, C2, C3, C4, I1.1, I1.2, I2.1, ..., O.P, O.T, O.C`) — easier to reference in arrows.
- **Strategic Priorities source**: the BSCi template has 3 explicit Strategic Priorities at the top with corresponding Strategic Results. Are these distinct from Internal Process themes, or the same thing? My read: in Wawa they collapse — Internal Process themes ("Grow Through Foodservice", "Deliver Convenience and Value", "Expand Profitably") effectively ARE the strategic priorities. We use Internal Process themes as the source of strategic priorities; the schema field `strategicPriorities` is populated from the same generation as `internalProcesses.themes`.
- **Whether to generate a vision when none is publicly stated**: yes, but mark as `(synthesised)` — this is one of the standard "What's Missing?" gap candidates if the company has a weak public-facing vision.
- **How to surface the customer value proposition on the page**: as a chip near the strategy map header? As a row in the perspective grid? My recommendation: a small chip directly under "Strategy Map" title, like a tag — non-disruptive, present.
- **Re-analysis behaviour**: when a user uploads documents and triggers re-analysis, the strategy map regenerates. This is automatic (it's part of the pipeline) but worth confirming nobody objects to map churn between re-analyses.
- **Industry default `default.md`**: what does this file contain? Probably: light scaffolding for "if you can't tell the industry, here are common objective patterns across sectors." Concrete content TBD during implementation.

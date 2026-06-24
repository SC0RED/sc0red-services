## Context

Today the EBITDA tree (`build_ebitda_tree.py` + `_ebitda_templates.py`) and the value chain (`build_value_chain.py` + `value_chain_templates.py`) are **deterministic**: a keyword match on the AI-extracted `business_model` string selects one of five hardcoded industry templates (`saas`/`services`/`ecommerce`/`manufacturing`/`financial_services`); the template supplies the revenue mix, margins, and revenue-per-employee assumptions. The `enforce-fact-vs-forecast-data-integrity` change removed the silent SaaS default so a *no-match* now renders an "insufficient public data" placeholder.

The Century case proved the residual flaw: a *loose match* ("Professional services providing debt settlement…" → `services` template) still misrepresents the company (project/retainer/training revenue, an R&D cost line) for a success-fee business. The model itself knows the right answer — the templates discard that knowledge.

Two assets make the fix low-risk:
- **A proven decomposition precedent.** The strategy map already runs a DAG of small structured AI calls — `generate_perspectives_decomposed` → `_strategy_map_perspective_rounds.py` (Round 2 ≈ 13 parallel calls, Round 3 ≈ 9), each with a `per_call` schema, all via `FutureManager`, with adversarial yes/no verification calls (`synth_yesno`, `arrow_yesno`).
- **Native web search already in the SDK.** `signalfield_core` `query_structured(input_text, json_schema, **kwargs)` forwards `tools`; `StructuredResponse` returns `web_sources: list[WebSearchSource{url,title,snippet}]` + `has_web_search`; the price sheet tracks `web_search_cost` (~$0.01/search). Provider is OpenAI (`gpt-5.4-mini` standard / `gpt-5.1` advanced).

Constraints (CLAUDE.md): RequestStep subclasses wired through `FactoryManager → Sc0redServicesFactoriesFactory → CompanyAnalysisFactory`; parallel AI via `FutureManager` + `run_structured_ai_call`; prompts/schemas externalized under `src/pipeline/prompts/`; fail-fast; files < 400 lines; 95% coverage; feature-branch → PR.

## Goals / Non-Goals

**Goals**
- Derive the company's *actual* revenue model, mix, margins, revenue range, cost drivers, and operating-model steps via decomposed AI research — accurate for atypical businesses like debt settlement.
- Ground quantitative facts with the model's native web search where it helps; capture citations.
- Tag every fact with a provenance tier + deterministic confidence + a one-line basis; present estimates honestly but rigorously.
- Reuse the strategy-map DAG/`FutureManager` pattern; keep each AI call small and short-answered.

**Non-Goals**
- UX/perceived-latency optimization (streaming order, skeletons) — deferred.
- A new external data vendor (Tavily/SerpAPI/Crunchbase) — explicitly avoided; we use the provider's native `web_search`.
- Guaranteeing a *true* revenue figure for private companies — when no figure is disclosed and search finds none, the number stays a labelled `DERIVED-ESTIMATE` (or the surface falls to the placeholder).
- Replacing the risk/opportunity/strategy-map steps — unchanged.

## Decisions

### Decision 1: A 3-round question DAG, one RequestStep orchestrator
Model the work as a directed acyclic graph of small questions, executed in rounds. Independent questions in a round run in parallel via `FutureManager`; each round waits for the prior (the dependency barrier). Mirror `_strategy_map_perspective_rounds.py` so the parallelism cap, token accounting, render/schema helpers, and verification pattern are reused, not reinvented.

```
ROUND 1 — independent, parallel
  Q1 company_type            (scraped content)            no search
  Q2 revenue_model           (world knowledge + content)  no search
  Q3 disclosed_figures       (content + docs)             SEARCH on
  Q4 scale_signals           (scraped content)            no search
ROUND 2 — depends on R1
  Q5 revenue_mix             (←Q1,Q2)                     no search
  Q6 margin_band             (←Q1)                        no search
  Q7 revenue_range           (←Q2,Q3,Q4)                  SEARCH on
  Q8 cost_drivers            (←Q1)                        no search
  Q9 operating_model_steps   (←Q1,Q2)  [value chain]      no search
ROUND 3 — assemble + verify
  assemble EBITDA tree (Q5,Q6,Q7,Q8) + value chain (Q9)
  adversarial yes/no plausibility checks → set/downgrade confidence
```

Alternatives considered: (a) one big AI call returning the whole tree — rejected: that's the original ~27s call, harder to verify, weaker per-fact provenance; (b) keep templates as a fallback prior — rejected: any concrete templated number is exactly the fabricated-fact problem; the placeholder is the correct floor.

### Decision 2: Selective web search, not always-on
Enable `tools=[web_search]` only on questions where the world (not the model's memory) holds the answer — the disclosed-figures lookup (Q3) and the revenue-range estimate (Q7). Qualitative questions (type, model, mix, margins, cost drivers, operating steps) the model answers from training knowledge → no search. This bounds cost to ~1–3 searches/analysis and keeps latency on the search-bearing calls only. Rationale: the customer's complaint was the wrong *model* (fixable with zero search); search only upgrades the *numbers*.

### Decision 3: Extend `run_structured_ai_call`, don't fork it
`run_structured_ai_call` currently calls `query_structured(input_text, json_schema)` and returns `(label, content, elapsed, token_counts)` — no `tools`, and it discards `web_sources`. Add an optional `tools` parameter (default `None`, behaviour unchanged for all existing callers) and return `web_sources` in the result tuple/struct. All existing call sites keep working; research steps opt into search. Keep the single shared call path per CLAUDE.md.

### Decision 4: Provenance tier drives deterministic confidence
Each fact carries `provenance ∈ {DISCLOSED, INDUSTRY_TYPICAL, DERIVED_ESTIMATE}` and a `basis` string. Confidence is a pure function of provenance (e.g. `DISCLOSED→high`, `INDUSTRY_TYPICAL→medium`, `DERIVED_ESTIMATE→low/medium`), never AI-self-rated — same auditable, reproducible philosophy as the existing `ebitda-tree-confidence` labels. A non-empty `web_sources`/document/site citation sets `DISCLOSED` and attaches the source. The research-question schemas ask the model to *self-declare* the provenance + basis, but the tier is reconciled against whether a real citation exists (a model claiming `DISCLOSED` with no source is downgraded).

### Decision 5: Adversarial plausibility verification
After assembly, run cheap yes/no checks (strategy-map `synth_yesno` pattern) per key fact, e.g. *"Given this scraped content, is a {revenue_model} revenue model plausible for this company? yes/no + one-line why."* A "no" downgrades confidence or, for the revenue model itself, forces the surface to the placeholder. These run in parallel in Round 3.

### Decision 6: Models + persistence are additive
Add `provenance`, `basis`, and `citations` (list of `{url,title}`) to `EbitdaNode`/`EbitdaTreeResult` and `ValueChainStep`/`ValueChainResult`, all optional with safe defaults so pre-existing records deserialize unchanged (same backward-compat posture as the `grounded` fields). Thread them through `persist_results.py` → `assessment_repository`/`_assessment_subrecord_ops` → `analysis_payload` → frontend/PDF/MCP.

### Decision 7: File-size discipline mirrors the strategy map
The research orchestrator, the round runners, the question prompts/schemas, and the assemblers will each be their own module (the strategy map split into `_strategy_map_perspectives.py` + `_strategy_map_perspective_rounds.py` + decomposed templates for exactly this reason). Target < 400 lines per file from the start.

## Risks / Trade-offs

- **[Hallucinated numbers presented confidently]** → Mitigation: deterministic confidence tied to provenance (a guessed number is `DERIVED_ESTIMATE`, never `high`), adversarial verification, and the "show your work" basis that exposes the reasoning to the reader.
- **[Web search returns wrong/old figures for a private company]** → Mitigation: citations are shown so the reader can judge; conflicting/low-quality sources → keep `DERIVED_ESTIMATE`; never assert `DISCLOSED` without a concrete source.
- **[Cost/latency creep from many AI calls]** → Mitigation: selective search (Decision 2), parallel rounds (wall-clock ≈ slowest chain), reuse of the strategy-map worker caps; telemetry already tracks per-call tokens + web-search count.
- **[Loss of determinism vs templates]** → Accepted: the org already accepted this for the strategy map; auditability is preserved via deterministic confidence + stored citations + the recorded basis.
- **[Provider web_search availability/quota in headless/cron runs]** → Mitigation: search is best-effort; a search failure degrades a fact to `DERIVED_ESTIMATE`, it does not fail the analysis (fail-soft on the *enrichment*, fail-fast on programming errors).

## Migration Plan

1. Land additive model fields + the `run_structured_ai_call` tools/`web_sources` extension (no behaviour change for existing callers).
2. Build the research steps + orchestrator behind the factory wiring; rewrite the two builders as assemblers; delete the template modules and their keyword logic.
3. Thread provenance/citations through persistence + payload; update frontend/PDF/MCP to render them.
4. Update the `report-data-integrity` audit rule (provenance-or-placeholder instead of no-silent-default).
5. Rollback: revert the branch; additive fields keep old records valid.

## Open Questions

- Exact confidence mapping per tier and the precise question/schema wording — settle during implementation against real companies (Century as the canonical fixture).
- Whether the disclosed-figures and revenue-range searches should be one combined searched call or two — measure cost/latency.

## Documented Next Step (out of scope here)

**UX / perceived-latency optimization.** With financials now AI-researched (several calls), tune the experience: stream the headline risk/opportunities first and let the EBITDA tree + value chain populate after; add skeleton/loading affordances; consider caching research per domain. Quality lands in this change; the experience pass is deliberately separate so it isn't rushed.

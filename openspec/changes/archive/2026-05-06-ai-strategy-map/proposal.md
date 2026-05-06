## Why

The product is being repositioned as **Vector Advisory** (separate change `rename-janus-to-vector-advisory`) — an AI-augmented advisory companion for mid-market PE buyers and operators. A risk score + opportunity list isn't enough to support that positioning; the rebranded product needs a **strategic-narrative artifact** at the top of every analysis. The artifact has two jobs:

1. **Demonstrate strategic thinking.** Show prospects that Vector Advisory frames analysis around how the business creates value, not just where it's exposed to AI risk. The Balanced Scorecard strategy map (Kaplan & Norton) is the recognised lingua franca of strategy-as-execution and the right framework to use.
2. **Drive lead-gen conversions.** The strategy map is the headline conversion artifact. It deliberately stops at high-level objectives — leaving measures, targets, and initiatives as the "what we'd cover in a deep dive" hook. A "Contact us for deep dive" CTA links to the existing sc0red contact form (`https://www.sc0red.com/contact`); each generated map highlights 2-4 specific strategic gaps as deep-dive conversation starters.

The scope is **public-data only** — the AI generates strategy maps from content Janus already scrapes plus any documents the user uploads. The output is intentionally a teaser quality, not a consultant-grade deliverable. Hallucination concerns are mitigated by explicit confidence markers on every objective and by the framing "this is what we can infer from public data; the deep-dive engagement validates and extends."

The leader brings the calibration: the canonical Kaplan & Norton HBR article (theory + Mobil exemplar), one full strategy map he produced for a real client (Wawa, 2011) showing his house style (customer-voice quotes, themed Internal Process groupings, "We will…" definitions, the People & Organization perspective), and the BSCi visual template (vision/mission/strategic-priorities header + scorecard columns to the right). Together these three resources are sufficient to ground AI generation; no further leader engagement is required for v1.

## What Changes

- **New backend pipeline step**: `GenerateStrategyMap` (`RequestStep` subclass) inserted between `ComputeValueChain` and `PersistResults` in `CompanyAnalysisFactory`. The step generates a strategy map from existing pipeline outputs (risk scores, opportunities, EBITDA tree, value chain, scraped content) plus any `document_text` the user uploaded.
- **New AI-generation chain** with seven steps, each producing a JSON-validated fragment of the final map:
  1. Vision / Mission synthesis
  2. Customer Value Proposition classification (1 of 3, or named hybrid)
  3. Financial perspective (3 objectives)
  4. Customer perspective (3-4 objectives in customer voice)
  5. Internal Processes perspective (4-6 objectives organised into 2-3 themes)
  6. Organizational Capacity perspective (3 objectives — People / Technology / Culture)
  7. Cause-and-effect arrows + "What's Missing?" gaps
- **Calibration corpus** in `backend/src/pipeline/prompts/strategy_map/`:
  - `system/strategy_map_generator.md` — system prompt
  - `guides/kaplan_norton_framework.md` — framework + 3 value propositions + 4 IP categories
  - `guides/vector_style_guide.md` — house style (extracted from Wawa)
  - `guides/anti_patterns.md` — KPI illusion, generic-objective trap, etc.
  - `exemplars/mobil_2000.md` — HBR Mobil case as few-shot example
  - `exemplars/wawa_2011.md` — leader's house-style example
  - `templates/01-07_*.md` — per-step user prompt templates
  - `schemas/strategy_map_output.json` — JSON output schema
- **New `StrategyMap` data model** (`src/models/model_strategy_map.py`) capturing vision, mission, strategic priorities, the four perspectives, arrows, gaps, and confidence markers. Persisted on the assessment record alongside existing `riskScores`, `opportunities`, `ebitdaTree`, `valueChain`.
- **API surface**: `GET /api/analysis/{id}` response gains a `strategyMap` field. Frontend `AnalysisData` type extended.
- **Frontend strategy map components** under `frontend/src/components/strategy-map/`:
  - `StrategyMapView.tsx` — composition root rendering vision / mission / strategic priorities / 4 perspectives / "What's Missing?" / CTA
  - `PerspectiveRow.tsx` — one perspective with its objectives (customer-voice, themed I, etc.)
  - `ObjectiveCard.tsx` — single objective with confidence marker + definition tooltip
  - `WhatsMissingPanel.tsx` — 2-4 gaps with deep-dive framing
  - `DeepDiveCTA.tsx` — link-out to `https://www.sc0red.com/contact`
- **Analysis page placement**: strategy map renders at position 3 (after the existing header + overview cards), with the deep-dive CTA directly below it. Existing sections (Top Actions → Value Chain → EBITDA → Risk → Opportunities) follow.
- **PDF export integration**: a `PrintStrategyMap` print component is added; the PDF section order becomes Cover → Executive Summary → **Strategy Map → Top Actions** → Value Chain → EBITDA → Risk Profile → AI Opportunity Roadmap → Methodology → Back Cover.
- **NOT included in v1**:
  - Measures, targets, or initiatives generation (those are deep-dive deliverables; their visible absence is the conversion hook)
  - User-editable strategy map (read-only render)
  - Industry-pattern files beyond `default.md` (added in a follow-up if real customer feedback warrants)
  - Custom-domain CTA mechanic (e.g. embedded form, Calendly) — link to existing contact page only
  - Strategy map versioning / history / re-generation UI (always shows the latest pipeline output)
  - Async / streaming UI while generation runs (the analysis already runs async; the map appears when persistence completes)

## Capabilities

### New Capabilities
- `ai-strategy-map`: AI-generated Balanced-Scorecard strategy map from public data, rendered at the top of the analysis page and in the PDF, with confidence markers, "What's Missing?" gap detection, and a deep-dive CTA. Lives at `openspec/specs/ai-strategy-map/spec.md` post-archive.

### Modified Capabilities
- `polished-pdf-export`: The PDF section order is extended to include a Strategy Map section as the first content section after the Executive Summary, with the same advisory narrative ordering applied to the rest of the document. Mirrors the on-screen analysis page placement.

## Impact

- **Backend** (~10 files):
  - `src/pipeline/pipeline_steps/generate_strategy_map.py` (new step ~250 lines)
  - `src/pipeline/pipeline_factories/company_analysis_factory.py` (wire new step)
  - `src/models/model_strategy_map.py` (new model ~120 lines)
  - `src/models/model_company.py` and assessment models (extend with strategy_map field)
  - `src/repositories/dynamodb/assessment_repository.py` (persist new field)
  - `src/handlers/analysis_handlers.py` (return new field in API response)
  - `src/pipeline/pipeline_steps/persist_results.py` (persist new field)
  - 8 markdown / JSON files under `src/pipeline/prompts/strategy_map/`
- **Frontend** (~8 files):
  - 5 new components under `src/components/strategy-map/`
  - `src/components/print/PrintStrategyMap.tsx` for PDF
  - `src/lib/types/api.ts` (extend `AnalysisData` with `strategyMap`)
  - `src/app/(authenticated)/analysis/[analysisId]/AnalysisDetail.tsx` (render strategy map at position 3)
  - `src/app/print/[analysisId]/PrintReport.tsx` (insert strategy map section)
  - `src/app/print/print.css` (per-section styling)
- **Tests**: unit tests for the pipeline step (mocked AI), schema validation tests, RTL tests for each new frontend component, PrintReport composition test extended.
- **Cost / latency**: 7 LLM calls per analysis (vs. ~5 today). Each call is 2-8K tokens of context. Estimated additional cost: ~$0.10-0.30 per analysis with Claude. Added latency: 30-90s end-to-end for the strategy-map step (parallelisable; 4 of 7 steps can run concurrently).
- **Dependencies**: no new npm or Python dependencies. Reuses existing AI client factory, prompt loader, `RequestStep` base, persistence layer.
- **Data model**: `StrategyMap` is additive — existing analyses without it continue to render (the frontend conditionally renders the section).
- **Coordination with rename-janus-to-vector-advisory**: this change is conceptually downstream — the rename ships the section reorder + brand; this ships the strategy map at position 3. Either can land first, but the rename should ideally land first so the brand is consistent when the strategy map appears.
- **Coordination with polished-pdf-export / improve-pdf-export-content**: this change adds a third delta against `polished-pdf-export`'s section-order requirement. At archive time, the deltas resolve: polished-pdf-export ships the original order; improve-pdf-export-content updates it; rename-janus-to-vector-advisory updates it again; this change adds the strategy map to it.

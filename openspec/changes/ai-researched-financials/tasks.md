## 1. AI-call wrapper — web search + sources

- [ ] 1.1 Extend `run_structured_ai_call` (`ai_call.py`) to accept an optional `tools` argument (default `None`; existing callers unchanged) and pass it to `query_structured`
- [ ] 1.2 Capture and return `web_sources` from the `StructuredResponse` (additive to the return shape); record web-search count in telemetry
- [ ] 1.3 Add a small helper to build the provider `web_search` tool config
- [ ] 1.4 Unit tests: no-tools call unchanged; tools call forwards tools + returns `web_sources`; search failure fails soft

## 2. Models — provenance + citations

- [ ] 2.1 Add `provenance` (DISCLOSED|INDUSTRY_TYPICAL|DERIVED_ESTIMATE), `basis`, and `citations` (list of `{url,title}`) to `EbitdaNode`/`EbitdaTreeResult` and `ValueChainStep`/`ValueChainResult` — additive, optional, safe defaults (legacy records deserialize)
- [ ] 2.2 Add a deterministic `confidence_from_provenance(tier, verdict)` helper
- [ ] 2.3 Unit tests for defaults + the confidence mapping

## 3. Research prompts + schemas

- [ ] 3.1 Author per-question prompt templates under `src/pipeline/prompts/` (company_type, revenue_model, disclosed_figures, scale_signals, revenue_mix, margin_band, revenue_range, cost_drivers, operating_model_steps)
- [ ] 3.2 Author short per-question output schemas (one-liner/structured short answers; each asks the model to self-declare provenance + basis)
- [ ] 3.3 Author the adversarial plausibility-check prompt + yes/no schema (strategy-map pattern)

## 4. Research orchestrator (the DAG)

- [ ] 4.1 New module(s) under `pipeline_steps/` for the round runners (parallel within round via `FutureManager`, sequential across rounds) — mirror `_strategy_map_perspective_rounds.py`; keep each file < 400 lines
- [ ] 4.2 Round 1 (parallel): company_type, revenue_model, disclosed_figures (search on), scale_signals
- [ ] 4.3 Round 2 (depends on R1, parallel): revenue_mix, margin_band, revenue_range (search on), cost_drivers, operating_model_steps
- [ ] 4.4 Round 3: adversarial verification calls (parallel); apply downgrade/reject rules
- [ ] 4.5 Reconcile self-declared provenance against actual citations (downgrade unsourced "disclosed")
- [ ] 4.6 Unit tests for each round runner with mocked `run_structured_ai_call`

## 5. Assemblers replace templates

- [ ] 5.1 Rewrite `build_ebitda_tree.py` as an assembler over researched facts (revenue mix + margins + range + cost drivers → node tree with provenance/confidence/citations)
- [ ] 5.2 Rewrite `build_value_chain.py` as an assembler over the researched operating-model steps (with per-step provenance)
- [ ] 5.3 Delete `_ebitda_templates.py` and `value_chain_templates.py` and all keyword-template logic
- [ ] 5.4 Keep the insufficient-data placeholder as the floor (model undeterminable / verification rejects the revenue model)
- [ ] 5.5 Wire the research orchestrator + assemblers as `RequestStep`s through `CompanyAnalysisFactory` (replace `ComputeEbitdaTree`/`ComputeValueChain` wiring)
- [ ] 5.6 Update/replace the existing build-ebitda / build-value-chain tests for the researched path (debt-settlement fixture → success-fee model, no template artifacts)

## 6. Persistence + payload

- [ ] 6.1 Thread provenance/basis/citations through `persist_results.py`
- [ ] 6.2 Persist + read them in `assessment_repository.py` and `_assessment_subrecord_ops.py` (legacy default-safe)
- [ ] 6.3 Surface them in `analysis_payload.py` (camelCase) + MCP read tools (`tools_read.py`)
- [ ] 6.4 Repository + payload tests including legacy-record round-trip

## 7. Frontend + PDF rendering

- [ ] 7.1 Render per-fact provenance tier + confidence + one-line basis on the EBITDA + value-chain web surfaces; show citations when DISCLOSED
- [ ] 7.2 Mirror on the PDF (`PrintEbitdaOutline`, value-chain print)
- [ ] 7.3 Frontend types (`api.ts`) gain the additive fields
- [ ] 7.4 Vitest/RTL tests: estimate "shows its work"; disclosed shows citation; legacy data renders

## 8. Audit rule update

- [ ] 8.1 Update the data-integrity audit check: fact-bearing surfaces must carry provenance OR render the placeholder (replaces the "no silent default template" check, since templates are gone)
- [ ] 8.2 Update the audit-rule test

## 9. Validation & verification

- [ ] 9.1 `ruff check` + `ruff format` + naming validator clean on changed files
- [ ] 9.2 `pyright src/` introduces no new error category
- [ ] 9.3 `pytest tests/ -q` passes with coverage ≥ 95%
- [ ] 9.4 Frontend `tsc --noEmit` + lint + `vitest run` pass
- [ ] 9.5 Run the `architecture-reviewer` agent; resolve CRITICAL before commit
- [ ] 9.6 Reproduce the Century debt-settlement case end-to-end → success-fee revenue model, provenance-labelled figures, citations where found, no template artifacts
- [ ] 9.7 Run the E2E suite per CLAUDE.md before opening the PR (verify the mock-AI path still produces a grounded tree; adjust the mock to exercise the researched path if needed)

## 10. Documented next step (do NOT implement here)

- [ ] 10.1 Record the deferred UX/latency optimization (stream financials after the headline; skeletons; per-domain research caching) in this change's design.md "next step" (already noted) — confirm it carries forward; do not build it in this change

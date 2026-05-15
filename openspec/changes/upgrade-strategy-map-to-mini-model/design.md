## Context

Janus's AI pipeline currently dispatches every call to `gpt-5.1` via signalfield-core's `OPENAI_MODEL_MAP`. The 2026-05-15 dev deploy log captured a `184.55s` call (`GenerateStrategyMap.ai_call_priorities`) — driven entirely by `gpt-5.1` hitting OpenAI's 180s `httpx.READ` timeout and the SDK retrying successfully. The single call dominated wall-clock for the entire `GenerateStrategyMap` step.

A parallel investigation of `assessment_engine` (a sibling Sc0red product that makes substantially more AI calls per request than Janus and has **never** reported this issue) revealed one functional difference: assessment_engine upgraded `Precision.STANDARD` from `gpt-5.1` to `gpt-5.4-mini` in March 2026 after a benchmark (SPE-1586) that produced:

| Metric | gpt-5.1 | gpt-5.4-mini | Delta |
|---|---|---|---|
| Avg latency | 3.4s | 1.7s | -50.8% |
| Total cost | $0.1396 | $0.0842 | -39.7% |
| Schema compliance | 100% | 100% | 0 |
| Errors | 0 | 0 | — |

Every other piece of infrastructure between the two products — `httpx.Timeout`, `max_retries=2`, the `FutureManager`, the `retry_wrapper.py` decorator — is functionally identical.

**Smaller models also have tighter latency distributions.** This is the property that explains why assessment_engine doesn't see the 180s tail spike. Mini variants run on more numerous, smaller serving instances → less queueing variance under burst load. The 184s `gpt-5.1` outlier is the kind of pathology mini largely avoids.

## Goals / Non-Goals

**Goals:**
- Cut Janus's per-analysis AI cost by ~40%.
- Cut Janus's strategy-map wall-clock by ~40-50%.
- Eliminate the multi-minute tail-latency spikes that the new token telemetry surfaces.
- Preserve output quality at or above current bar — validated by a Janus-specific benchmark, not assumed from assessment_engine's results.

**Non-Goals:**
- Streaming responses (orthogonal optimization).
- Anthropic provider parity (Janus is OpenAI-only on the hot path).
- Per-call timeout enforcement in `run_structured_ai_call` (right fix is model upgrade, not timeout shortening — though tighter timeouts could be a future hardening).
- A finer-grained 3-tier precision enum (`FAST`/`STANDARD`/`ADVANCED`). Binary STANDARD vs ADVANCED matches assessment_engine and is sufficient.
- Migrating non-OpenAI providers (Anthropic) to a mini variant.

## Decisions

### §1 — Keep precision binary (STANDARD = mini, ADVANCED = full)

assessment_engine kept `Precision` as a binary enum: `STANDARD = "gpt-5.4-mini"`, `ADVANCED = "gpt-5.1"`. Host apps choose per call site.

**Alternative considered:** add `Precision.FAST` as a third tier dedicated to mini, keeping `STANDARD = gpt-5.1`. Rejected because:
- Three tiers means three sets of pricing entries, three test fixtures, three rows on every per-model report — more maintenance forever.
- assessment_engine's binary shape is proven to work for a Sc0red product with similar latency / quality concerns.
- Host apps wanting per-call-site discrimination already have it via `precision=Precision.ADVANCED` at the call site — no enum change required.

### §2 — Benchmark before SDK ship, ship before adoption

Three-stage rollout:

1. **Janus benchmark PR** — proves mini works on Janus's prompts. No production change.
2. **SDK ship PR** — updates `OPENAI_MODEL_MAP` in signalfield-core only after the benchmark confirms safety. Released as `v0.3.0`.
3. **Janus adoption PR** — bumps SDK pin. Migrates every call site at once (since they all use `Precision.STANDARD`).

**Alternative considered:** ship the SDK change first and let Janus adopt later. Rejected because:
- assessment_engine is already on `v0.2.0` and using mini through their own AIClient (they don't depend on signalfield-core). Janus is the only host of signalfield-core's `OPENAI_MODEL_MAP`, so any SDK change should be gated on Janus's benchmark.
- Releasing a model change blindly into signalfield-core would mean any future host app gets the new default whether or not they've benchmarked.

### §3 — Quality gate is human-review on benchmark outputs

The assessment_engine benchmark's quality validation was: schema compliance + a human eyeballing ~18 prompt outputs and tagging each ✅ / 🟡 / 🔴.

We adopt the same. Specifically for Janus:

- Schema compliance: required 100% on both models.
- Errors: required 0 on candidate.
- Latency: required avg reduction ≥ 30%.
- Content review: human reads every benchmarked prompt's output on both models and tags as:
  - ✅ Equivalent — same information, similar phrasing.
  - 🟡 Acceptable — shorter or restructured but accurate. Tolerated for strategy-map decomposition (the existing assessment_engine pattern accepts shorter outputs as the price of mini).
  - 🔴 Regression — material accuracy loss, missing required info, factually wrong.

**Gate:** zero 🔴 findings on strategy-map calls. 🔴 findings on other call sites (DetailOpportunities, risk_batch, ideation) get individual treatment — those call sites pass `Precision.ADVANCED` to retain `gpt-5.1` while the rest migrate.

**Alternative considered:** automated quality metrics (BLEU, ROUGE, embedding cosine). Rejected because the content review is the right granularity for this scale — 20 prompts × 5 min/prompt = ~2 hours, single-shot, no infrastructure required. Automated metrics work for ongoing regression detection (a future concern) but not for the initial gate.

### §4 — Benchmark prompts come from real Janus call sites, not synthetic

The `benchmark_prompts.json` we build must use **real prompt templates rendered with realistic data**. assessment_engine's approach: one prompt per `task_type` × representative customer scenario. For Janus:

- Pull the actual rendered prompt for each per-call schema from a real analysis (e.g., use the existing dev deployment's CloudWatch logs — they capture `prompt_len`).
- Cover the 6 distinct schemas: `arrow_yesno`, `arrows_priorities`, `*_objective_detail`, `*_titles`, `mission_text`, `vp_primary` (strategy-map) plus `profile`, `risk_batch`, `ideation`, `detail` (other steps).
- Use one prompt per schema initially. Expand to multiple if a single sample shows borderline results.

**Alternative considered:** synthesise representative prompts manually. Rejected — real production prompts catch issues that hand-written ones won't (e.g., long scrape excerpts, specific company-context phrasing).

### §5 — Don't change `Precision.ADVANCED`

ADVANCED stays on `gpt-5.1`. Two reasons:

1. **It's the escape hatch** for call sites that fail the mini benchmark. Forcing both tiers to mini removes that hatch.
2. **assessment_engine's pattern.** They benchmarked, kept ADVANCED on `gpt-5.1`. We copy a known-good pattern.

If a future call site needs more quality than `gpt-5.1`, that's a separate change (e.g., `Precision.PREMIUM = "gpt-5.5"`).

### §6 — Benchmark runner is a copy-paste, not a fork

assessment_engine's `scripts/benchmark/run_benchmark.py` and `compare_results.py` are vanilla openai-SDK Python scripts with zero assessment_engine imports. We **copy** them into `backend/scripts/benchmark/`, replace `benchmark_prompts.json`, and run.

**Alternative considered:** import as a shared library or factor out a common benchmark package. Rejected — premature abstraction. Two callers (assessment_engine and Janus) is not a library; if a third Sc0red product needs benchmarking we can extract then.

## Risks / Trade-offs

### [Risk] Janus prompts may behave differently from assessment_engine's

The assessment_engine benchmark covered question-answering, summarisation, name resolution, match scoring, chat, thesis streamlining, document audit, leader enrichment — 8 task types. Janus's hot calls are different:
- Strategy-map decomposition (60+ short yes/no + per-objective detail calls)
- Risk batch scoring + rationale
- Opportunity ideation (creativity matters)
- Opportunity detail implementation steps

A model that's great at "explain a risk score in 175 words" may be weaker at "generate one creative opportunity title". The benchmark exists precisely to surface this.

**Mitigation:** the quality gate is "zero 🔴 on strategy-map; investigate 🔴 individually elsewhere". Worst case: strategy-map moves to mini (the biggest latency win — 60 calls × 2.5s = 150s saved), while ideation/risk/detail stay on `gpt-5.1` via explicit `Precision.ADVANCED` at those call sites.

### [Risk] Mini may degrade structured output adherence under unusual prompts

The assessment_engine benchmark showed 100% schema compliance on both. But mini variants historically were more prone to schema drift on heavily-nested schemas or large enum spaces. Janus's `strategy_map_output.json` is the largest assembled schema in the codebase, but the **per-call schemas** mini receives are tiny.

**Mitigation:** the boundary validator added in #311 catches schema violations at the call boundary with a clear error. If mini ever produces a non-compliant response, the existing retry layer + boundary validator catches it cleanly. The pre-assembly boundary check is now a load-bearing safety net.

### [Risk] OpenAI may change pricing or deprecate gpt-5.4-mini

Model lifecycles are unpredictable. `gpt-5.4-mini` is current as of 2026-05, but OpenAI deprecates models on ~12-18 month cycles.

**Mitigation:** the benchmark runner is now in-repo. When a new model lands, run it through the same flow, decide whether to upgrade. The model name is a single string in one config; switching costs nothing.

### [Trade-off] Outputs are typically 30-80% as long on mini

assessment_engine's report shows mini outputs ranging from 0.32× to 0.87× the length of `gpt-5.1` outputs (median ~0.65×). Less prose, same structure.

For Janus:
- Strategy-map `definition` fields (50-1200 chars) — shorter is fine, especially at the lower end.
- DetailOpportunities `roi_estimate` and `implementation_steps` — shorter could lose specificity. **Highest risk surface.**
- Risk `rationale` (2-3 sentences) — already brief; further shortening might lose audit-trail nuance.

**Mitigation:** the content review during the benchmark catches this per-prompt. Surfaces that fail human review keep `gpt-5.1` via `Precision.ADVANCED`.

### [Trade-off] Smaller serving infrastructure ≠ never slow

Mini reduces tail latency but doesn't eliminate it. We may still see occasional 30-60s outliers (vs the 180s outliers we see today). The new token telemetry (#313) gives us the data to monitor.

**Acceptable** — even 60s outliers in a single call are 3× better than 180s, and the boundary validator + retry layer handles them.

## Migration Plan

### Phase 1: Benchmark (Janus PR, ~2 days)

1. Copy `assessment_engine/scripts/benchmark/` → `janus/backend/scripts/benchmark/`.
2. Strip `benchmark_prompts.json` to Janus-specific content.
3. Construct ~10-15 prompts from real strategy-map + other call-site outputs.
4. Run `python run_benchmark.py --model gpt-5.1 --baseline` (cost ~$2-5).
5. Run `python run_benchmark.py --model gpt-5.4-mini` (cost ~$1-2).
6. Run `python compare_results.py` → markdown report.
7. Human review: tag each prompt's output as ✅ / 🟡 / 🔴.
8. Commit results JSON + comparison report to `backend/scripts/benchmark/results/`.

**Stop here if** quality gates fail. The benchmark itself has value — we now know which call sites are mini-safe and which aren't.

### Phase 2: SDK ship (signalfield-core PR, ~half day)

1. Update `OPENAI_MODEL_MAP`:
   ```python
   OPENAI_MODEL_MAP: dict[str, str] = {
       Precision.STANDARD.value: "gpt-5.4-mini",
       Precision.ADVANCED.value: "gpt-5.1",
   }
   ```
2. Add `gpt-5.4-mini` pricing to `MODEL_PRICING`.
3. Update tests to assert both model strings are valid mappings.
4. Cut `v0.3.0` release.

### Phase 3: Janus adoption (Janus PR, ~1 day)

1. Bump `signalfield-core[all]` pin in `backend/pyproject.toml` from `v0.2.0` → `v0.3.0`. Run `uv sync`.
2. If benchmark Phase 1 flagged 🔴 on specific call sites:
   - In those call sites, override `Precision.STANDARD` → `Precision.ADVANCED`.
   - Example: `DetailOpportunities._run_ai_call` if ROI quality degrades.
3. Run full backend suite — expect no test changes; tests mock the AI client.
4. Architecture-reviewer pass.
5. Open PR, ship via dev → testing → production.

### Phase 4: Soak + telemetry validation (post-prod, ~7 days)

1. Token telemetry (#313) shows per-call latency. Watch:
   - `tokens_in_*` and `tokens_out_*` should stay similar (input is the same; output is ~0.65× length).
   - `cached_tokens_*` should stay similar (cache routing is model-agnostic).
   - `ai_call_*` should drop ~50% on average; tail outliers should drop from 180s to <60s.
2. If any call site shows quality regressions in real analyses, surface and address with `Precision.ADVANCED` override.

## Open Questions

- **Should we run the benchmark on testing or production data?** Production has real analyses with diverse companies; testing has limited samples. **Resolved approach**: pull rendered prompts from production CloudWatch logs (we have telemetry now). Cost a couple of $; quality is real.
- **Do we benchmark with web_search tool enabled?** assessment_engine's benchmark used web_search on some prompts. Janus uses web_search only in scrape_and_resolve (no AI there). **Resolved approach**: skip web_search in the Janus benchmark — all our AI calls are pure structured-output.
- **What about local dev / docker-compose mock AI?** The benchmark hits OpenAI directly. Local dev (`docker-compose.e2e.yml`'s `ai-mock`) is unaffected by the model upgrade — it returns canned responses regardless of model name. **Resolved**: no change needed to local dev.
- **Cost of running the benchmark.** Estimated $3-7 per full run (10-15 prompts × 2 models). Acceptable.

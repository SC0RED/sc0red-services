# Upgrade Janus AI Calls to gpt-5.4-mini Where Quality Allows

## Why

The 2026-05-15 dev deploy log showed `GenerateStrategyMap.ai_call_priorities` taking **184.55s** for one call — driven by OpenAI's 180s `httpx.READ` timeout firing, then the SDK retry succeeding in ~5s. The single call dominated the entire `GenerateStrategyMap` step (184s out of 226s = 81%) and added ~3 minutes to the analysis wall clock.

Investigation revealed:

- The OpenAI SDK config, retry layers, FutureManager parallelism, and prompt structure are all functionally identical between Janus (via signalfield-core) and assessment_engine.
- **The single difference**: assessment_engine upgraded `Precision.STANDARD` from `gpt-5.1` → `gpt-5.4-mini` in March 2026 (SPE-1586) after a benchmark showed **-50.8% avg latency, -39.7% cost, 100% schema compliance preserved**.
- Janus's `signalfield-core` pin maps both `Precision.STANDARD` and `Precision.ADVANCED` to `gpt-5.1`. Every Janus AI call runs on full `gpt-5.1`.
- The `gpt-5.4-mini` model has a much tighter latency distribution — smaller, more numerous serving infrastructure → fewer multi-minute tail-latency spikes. The 184s outlier we saw is the kind of pathology mini largely avoids.

The cost of staying on `gpt-5.1` for Janus:

- 2× latency on average per AI call (3.4s vs 1.7s benchmarked).
- ~40% higher OpenAI bill on every analysis.
- Recurring multi-minute tail spikes on the burst phases — every strategy-map analysis fires 60+ parallel calls and the slowest one defines wall-clock.

This change ports assessment_engine's model choice to Janus, gated on a Janus-specific benchmark to confirm output quality holds for our prompts.

## What Changes

### A. SDK side (signalfield-core)

- **`OPENAI_MODEL_MAP`** in `signalfield_core/services/providers/openai_provider.py`:
  - `Precision.STANDARD.value` → `"gpt-5.4-mini"` (was `"gpt-5.1"`)
  - `Precision.ADVANCED.value` → `"gpt-5.1"` (unchanged)
- **`MODEL_PRICING`** in `signalfield_core/models/model_price_sheet.py`: add `gpt-5.4-mini` pricing entry (input $0.75/M, output $4.50/M per OpenAI published rates as of 2026-03).
- Ship as `v0.3.0` (minor — public-API-visible model change).

Host applications that don't want the mini upgrade can pin to `v0.2.x` until they benchmark. assessment_engine is already on mini; Janus will adopt it via this change.

### B. Janus side — benchmark first

- Port assessment_engine's `scripts/benchmark/` runner to `backend/scripts/benchmark/` (~270 LOC, vanilla OpenAI SDK, zero internal deps).
- Build `benchmark_prompts.json` from real Janus prompts — at minimum **one prompt per call site** across the 6 schemas Janus uses today:
  - Strategy-map: `arrow_yesno`, `arrows_priorities`, one `*_objective_detail`, one `*_titles`, `mission_text`, `vp_primary`
  - Other: `profile`, `risk_batch`, `ideation`, `detail`
- Run baseline (`gpt-5.1`) and candidate (`gpt-5.4-mini`); save to `results/`.
- Run `compare_results.py` to produce a markdown report.
- **Quality gates** (mirroring assessment_engine SPE-1586):
  - Schema compliance: 100% on both → required, gate ship.
  - Errors: 0 on candidate → required, gate ship.
  - Latency: average reduction ≥ 30% → required (otherwise the change buys nothing).
  - Content diffs: every prompt's output is read by a human (~20 prompts × 5 min = ~2 hrs). Reviewer scores each as ✅ equivalent / 🟡 acceptable (shorter but accurate) / 🔴 regression. Gate ship on **zero 🔴 findings** for strategy-map calls; investigate 🔴 individually for risk/ideation/detail.

### C. Janus side — adopt the upgrade

- Bump `signalfield-core` pin in `backend/pyproject.toml` from `v0.2.0` → `v0.3.0`. Janus's `ai_call.py` already uses `Precision.STANDARD` everywhere — this single pin bump migrates every AI call to mini.
- **No code changes** to call sites needed if benchmark passes.
- If benchmark surfaces 🔴 regressions on specific call sites:
  - Pass `Precision.ADVANCED` at those call sites (e.g., `DetailOpportunities._run_ai_call`).
  - These calls retain `gpt-5.1` while the rest migrate to mini.

### D. Documentation

- Add `backend/scripts/benchmark/README.md` documenting how to re-run the benchmark when OpenAI publishes a new model.
- Commit the baseline + candidate results JSON + comparison markdown to `backend/scripts/benchmark/results/` for posterity.

## Impact

**Affected specs:**
- `ai-strategy-map` — adds a requirement that AI call sites use the precision level appropriate to their quality bar. No call-site changes if benchmark passes.

**Affected code:**

| Repo | Files |
|---|---|
| signalfield-core | `services/providers/openai_provider.py`, `models/model_price_sheet.py`, matching tests |
| janus | `backend/pyproject.toml` (SDK pin), `backend/scripts/benchmark/` (new), optionally `ai_call.py` for per-call-site precision overrides |

**Affected workloads:**

| Call site | Volume / analysis | Quality risk on mini | Latency win |
|---|---|---|---|
| **Strategy-map arrow yes/no** | 30–60 calls | LOW (bool + 1 sentence) | HUGE (60 × ~2.5s → 60 × ~1.2s) |
| **Strategy-map priorities** | 1 call | MED (holistic synthesis) | HIGH (the tail-prone one — 184s incident) |
| **Strategy-map objective detail** | 10–15 calls | LOW (50-1200 char definitions) | MED |
| **Strategy-map titles / themes / vision / mission / VP** | 10 calls | LOW–MED | LOW (already <5s each) |
| **DetailOpportunities** | 5 calls | MED (implementation steps + ROI) | MED |
| **ParallelProfileRiskAndIdeation extract_profile** | 1 call | MED (13-field classification) | LOW |
| **ParallelProfileRiskAndIdeation assess_risk batches** | 2 calls | MED (rationale audit trail) | MED |
| **ParallelProfileRiskAndIdeation ideate_*** | 8 calls | MED (creativity / quality bar) | MED |
| **DiscoverPortfolio extract_portfolio** | 1 call | LOW (URL list extraction) | LOW |
| **ValidatePortfolio** | N calls | LOW (yes/no) | LOW |

**Cost / latency expected outcomes:**

Assuming benchmark confirms the assessment_engine result generalises:
- Per-analysis OpenAI cost: **~40% reduction**.
- Per-analysis wall-clock: **~40-50% reduction** on `GenerateStrategyMap` (the heaviest AI step); marginal on the rest.
- Tail-latency spikes: largely eliminated (the 180s outlier was a `gpt-5.1` pathology that mini's serving infrastructure handles differently).

## Order of operations

1. **Benchmark first** (Janus PR, ~2 days work) — port the runner, build Janus prompts, run both models, produce the comparison report. **No production change yet.**
2. If benchmark passes quality gates: **SDK PR** to bump signalfield-core to `v0.3.0`. Same shape as the `expose-per-call-token-counts` PR (#15).
3. **Janus adoption PR** — bump SDK pin to `v0.3.0`, soak on dev → testing → production.
4. **Per-call-site precision overrides** (if benchmark flagged 🔴 surfaces) — small follow-up PR that adds `precision=Precision.ADVANCED` at those call sites.

## Non-Goals

- **Streaming responses.** A separate optimization; orthogonal to model choice.
- **Anthropic provider support.** Janus's hot path is OpenAI-only.
- **Per-call timeout configuration in run_structured_ai_call.** Useful eventually but out of scope here — the right fix for the 180s tail is model upgrade, not timeout tightening.
- **Token-budget enforcement.** Out of scope.
- **Backfilling production analyses with the new model.** New analyses use the new model; old ones keep their original output.

## Open Questions

- **Will Janus's prompts get the same -50% latency win?** The assessment_engine benchmark covered 18 prompts across their workload. Janus's strategy-map decomposition and risk-batch prompts are different shapes. **Resolved approach**: run the benchmark; let data decide. Quality gate is "average latency reduction ≥ 30%" — if mini doesn't deliver that, abandon the change.
- **Should we add `Precision.FAST` as a third tier?** assessment_engine kept it binary (STANDARD = mini, ADVANCED = full). Three tiers (FAST/STANDARD/ADVANCED) gives finer per-call-site control but adds enum-maintenance overhead. **Resolved approach**: keep binary for now — host apps that need finer control can pass `precision=Precision.ADVANCED` at specific call sites.
- **Pricing accuracy.** OpenAI updates published rates periodically. **Resolved approach**: pin pricing per model in `MODEL_PRICING` and revisit when OpenAI republishes. Pricing inaccuracy affects aggregate cost telemetry, not pipeline correctness.

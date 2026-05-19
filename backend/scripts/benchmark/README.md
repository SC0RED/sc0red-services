# sc0red Services AI Model Benchmark Suite

Evaluate an OpenAI model against the current `gpt-5.1` baseline for sc0red Services's strategy-map, profile, risk, ideation, and detail-opportunity workloads.

Ported from `assessment_engine/scripts/benchmark/` (2026-05-15) for the OpenSpec change `upgrade-strategy-map-to-mini-model`. Goal: produce the data needed to decide whether to migrate sc0red Services's `Precision.STANDARD` model from `gpt-5.1` to `gpt-5.4-mini` (assessment_engine made this switch in March 2026 and saw ~50% lower latency + ~40% lower cost on their workload).

## Quick start

```bash
cd backend
export OPENAI_API_KEY="sk-..."          # use a dev key — full run costs ~$3-7

# 1. Baseline (current sc0red Services model)
uv run python scripts/benchmark/run_benchmark.py --model gpt-5.1 --baseline

# 2. Candidate (proposed model)
uv run python scripts/benchmark/run_benchmark.py --model gpt-5.4-mini

# 3. Compare
uv run python scripts/benchmark/compare_results.py \
    --baseline scripts/benchmark/results/gpt-5.1_baseline.json \
    --candidate scripts/benchmark/results/gpt-5.4-mini_$(date +%Y-%m-%d).json \
    --output scripts/benchmark/results/comparison_gpt-5.1_vs_gpt-5.4-mini.md
```

The comparison markdown lands at `results/comparison_*.md`. **Read every prompt's output side-by-side and tag each as ✅ equivalent / 🟡 acceptable (shorter but accurate) / 🔴 regression**. The OpenSpec change documents the quality gate: zero 🔴 on strategy-map prompts is required to ship.

## What's benchmarked

`benchmark_prompts.json` contains 10 prompts — one per distinct AI call site in sc0red Services's pipeline:

| Prompt ID | Task type | Volume per analysis | Quality risk on mini | Latency win |
|---|---|---|---|---|
| `strategy_map_arrow_yesno_01` | arrow yes/no | 30-60 calls | LOW (bool + 1 sentence) | 🟢 HUGE |
| `strategy_map_arrows_priorities_01` | holistic priorities | 1 call | MED (the 184s tail-latency outlier) | 🟢 HIGH |
| `strategy_map_internal_detail_01` | objective elaboration | 10-15 calls | LOW (50-1200 char definition) | 🟡 MED |
| `strategy_map_financial_titles_01` | title list | 3 calls | LOW (short titles) | 🔵 LOW |
| `strategy_map_mission_text_01` | mission statement | 2 calls | LOW–MED | 🔵 LOW |
| `strategy_map_vp_primary_01` | value-prop classifier | 2 calls | LOW (single enum) | 🔵 LOW |
| `profile_extract_01` | company profile | 1 call | MED (13-field classify) | 🔵 LOW |
| `risk_batch_01` | risk scoring + rationale | 2 calls | MED (audit-trail quality) | 🟡 MED |
| `ideation_01` | opportunity ideation | 8 calls | MED (creativity bar) | 🟡 MED |
| `detail_01` | impl steps + ROI | 5 calls | MED (specificity bar) | 🟡 MED |

Total prompt size: ~12K input tokens (matches typical production prompt sizes — the strategy-map prompts cache ~80% of these on production runs, but the benchmark sees full token cost because each call hits cold).

## Files

| File | Purpose |
|---|---|
| `run_benchmark.py` | Runner — hits OpenAI Responses API directly with each prompt, captures cost/latency/schema-compliance |
| `compare_results.py` | Diff two result JSONs → markdown report with per-prompt comparison |
| `build_prompts.py` | Regenerates `benchmark_prompts.json` from real sc0red Services templates rendered against the Acme Robotics fixture. Re-run when templates change. |
| `benchmark_prompts.json` | The 10 prompts. Committed for reproducibility. |
| `results/` | Output directory for benchmark runs. Committed alongside the OpenSpec change so the upgrade decision is auditable. |

## Regenerating `benchmark_prompts.json`

If you update a sc0red Services prompt template:

```bash
cd backend && uv run python scripts/benchmark/build_prompts.py
```

The fixture (Acme Robotics — Series C collaborative warehouse-robot company) lives in `build_prompts.py` as Python constants. Edit the constants there to adjust company size, industry, perspective objectives, etc.

## Adding a new model

```bash
# 1. Add pricing to MODEL_PRICING in run_benchmark.py (input/output cost per 1M tokens)
# 2. Run the candidate
uv run python scripts/benchmark/run_benchmark.py --model <new-model>

# 3. Compare against the baseline you established earlier
uv run python scripts/benchmark/compare_results.py \
    --baseline results/gpt-5.1_baseline.json \
    --candidate results/<new-model>_$(date +%Y-%m-%d).json
```

## Cost

Full benchmark run (10 prompts × ~12K input tokens each):

| Model | Per run (est.) |
|---|---|
| `gpt-5.1` | $0.15–$0.30 (input cost dominates) |
| `gpt-5.4-mini` | $0.09–$0.18 |
| `gpt-5.5` | $0.60–$1.20 |

Round-trip "baseline + candidate" is typically under $0.50. The OpenSpec migration plan budgets $3-7 because it allows for multiple iterations on prompt shape.

## Fidelity to production

The benchmark mirrors what sc0red Services production sends to OpenAI:
- **System prompts** are loaded per call type (strategy-map / profile / risk / ideation / detail) and passed via `instructions=` — same as `ai_call.run_structured_ai_call`.
- **`reasoning.effort` + `text.verbosity`** are passed through (default `low` / `medium` matching production).
- **`text.format`** uses strict JSON schema with `additionalProperties=false`.
- Token-cost calc matches OpenAI published rates per the `MODEL_PRICING` table in `run_benchmark.py`.

## What's NOT covered

- **Local docker-compose `ai-mock` server**: the benchmark hits OpenAI directly; the mock is unaffected by model choice.
- **Production prompts**: the fixture is hand-crafted, not pulled from CloudWatch. If you want to validate against a specific production analysis, edit `build_prompts.py` to use that scrape's content.
- **Caching behaviour**: OpenAI's prompt cache is per-organisation and depends on prompt-prefix byte-identity. The benchmark sees cold-cache pricing; production benefits from the cache-hit telemetry shipped in PR #313.
- **Tail-latency distribution**: a single benchmark run gives one sample per prompt. To characterise the tail, run the benchmark 5-10 times and take p50/p95/p99.

## See also

- OpenSpec change: `openspec/changes/upgrade-strategy-map-to-mini-model/`
- assessment_engine's original benchmark (the inspiration for this port): `/Users/vedratnavelani/Documents/sf-github/assessment_engine/scripts/benchmark/`
- assessment_engine's published comparison report (the precedent for the migration decision): `assessment_engine/scripts/benchmark/results/comparison_gpt-5.1_vs_gpt-5.4-mini.md`

# Upgrade Janus AI Calls to gpt-5.4-mini — Tasks

> Three-phase rollout per design.md migration plan. Phase 1 (benchmark) is a Janus PR. Phase 2 (SDK ship) only happens if Phase 1 passes quality gates. Phase 3 (Janus adoption) bumps the SDK pin.

## 1. Janus benchmark PR

### 1.1 Port the benchmark runner

- [ ] 1.1.1 Copy `assessment_engine/scripts/benchmark/run_benchmark.py` → `janus/backend/scripts/benchmark/run_benchmark.py`. ~270 LOC vanilla openai SDK; no internal-module imports needed.
- [ ] 1.1.2 Copy `assessment_engine/scripts/benchmark/compare_results.py` → `janus/backend/scripts/benchmark/compare_results.py`. ~330 LOC.
- [ ] 1.1.3 Copy `assessment_engine/scripts/benchmark/README.md` → `janus/backend/scripts/benchmark/README.md`. Update example commands for Janus models + paths.
- [ ] 1.1.4 Create `janus/backend/scripts/benchmark/results/` directory (gitignored except for the published outputs).

### 1.2 Build Janus-specific benchmark prompts

Real production prompts (pulled from a recent dev/testing analysis) rendered against the canonical schemas. One prompt per distinct schema; expand to multiple per schema only if borderline.

- [ ] 1.2.1 `arrow_yesno` — pull an `arrow_O.P_I1.1` prompt from a recent CloudWatch event (~17K input tokens, bool + 1-sentence output).
- [ ] 1.2.2 `arrows_priorities` — pull the holistic priorities prompt (~16K input tokens, 2-3 priorities output).
- [ ] 1.2.3 `financial_objective_detail` — pull one detail prompt (~14K input, 50-1200 char definition).
- [ ] 1.2.4 `customer_titles` — pull one titles prompt (~13K input, list of titles).
- [ ] 1.2.5 `mission_text` — pull one mission-text prompt (~12K input, short text).
- [ ] 1.2.6 `vp_primary` — pull one value-prop classifier prompt (~13K input, single enum value).
- [ ] 1.2.7 `profile` — pull one company-profile extraction prompt (entire scrape excerpt as input).
- [ ] 1.2.8 `risk_batch` — pull one risk-batch prompt (8 risk scores + rationale output).
- [ ] 1.2.9 `ideation` — pull one ideation prompt (creative opportunity title + description output).
- [ ] 1.2.10 `detail` — pull one DetailOpportunities prompt (implementation steps + ROI output).
- [ ] 1.2.11 Save the 10 prompts as `backend/scripts/benchmark/benchmark_prompts.json` matching assessment_engine's format.

### 1.3 Run baseline + candidate

- [ ] 1.3.1 Set `OPENAI_API_KEY` in the shell (use a dev key — benchmark costs ~$5).
- [ ] 1.3.2 Run baseline: `python run_benchmark.py --model gpt-5.1 --baseline`. Saves to `results/gpt-5.1_baseline.json`.
- [ ] 1.3.3 Run candidate: `python run_benchmark.py --model gpt-5.4-mini`. Saves to `results/gpt-5.4-mini_<date>.json`.
- [ ] 1.3.4 Run comparison: `python compare_results.py --baseline results/gpt-5.1_baseline.json --candidate results/gpt-5.4-mini_<date>.json --output results/comparison_gpt-5.1_vs_gpt-5.4-mini.md`.

### 1.4 Human quality review

- [ ] 1.4.1 Open `results/comparison_gpt-5.1_vs_gpt-5.4-mini.md`. For each of the 10 prompts, read both outputs side-by-side.
- [ ] 1.4.2 Tag each prompt as ✅ equivalent / 🟡 acceptable (shorter but accurate) / 🔴 regression.
- [ ] 1.4.3 Document the tagging in the comparison report (edit the markdown).
- [ ] 1.4.4 Apply quality gate: zero 🔴 findings on strategy-map prompts (`arrow_yesno`, `arrows_priorities`, `*_detail`, `*_titles`, `mission_text`, `vp_primary`). 🔴 findings on others (`profile`, `risk_batch`, `ideation`, `detail`) get individual treatment in Phase 3.

### 1.5 Janus benchmark PR

- [ ] 1.5.1 Architecture-reviewer pass on the benchmark runner (it's standalone, but check no dead code, no swallowed exceptions).
- [ ] 1.5.2 PR title: `chore(benchmark): port AI model benchmark runner from assessment_engine`. Body links to the comparison report.
- [ ] 1.5.3 CI green → merge to `development`. This is a docs/tooling PR — no production behaviour change, no deploy gate.

**Gate to Phase 2**: benchmark report committed; quality gates met or per-call-site override plan documented.

## 2. SDK ship (signalfield-core)

### 2.1 Update OPENAI_MODEL_MAP

- [ ] 2.1.1 In `signalfield-core/signalfield_core/services/providers/openai_provider.py`, change:
  ```python
  OPENAI_MODEL_MAP: dict[str, str] = {
      Precision.STANDARD.value: "gpt-5.4-mini",   # was "gpt-5.1"
      Precision.ADVANCED.value: "gpt-5.1",
  }
  ```
- [ ] 2.1.2 Update `signalfield-core/signalfield_core/models/model_price_sheet.py` to add `gpt-5.4-mini` pricing entry: input $0.75/M, output $4.50/M (per OpenAI published rates 2026-03; verify current rates before commit).
- [ ] 2.1.3 Confirm the `MODEL_PRICING` lookup in `AIClient.__init__` resolves cleanly for both precisions.

### 2.2 SDK tests

- [ ] 2.2.1 Update `tests/unit/services/providers/test_openai_provider.py` to assert `OPENAI_MODEL_MAP["standard"] == "gpt-5.4-mini"`.
- [ ] 2.2.2 Update `tests/unit/services/test_ai_client.py` pricing tests to expect the new mini pricing.
- [ ] 2.2.3 Run `uv run pytest tests/ -q` — all green, coverage ≥ baseline.

### 2.3 Ship

- [ ] 2.3.1 PR title: `feat(provider): upgrade Precision.STANDARD to gpt-5.4-mini`. Body links to Janus benchmark report.
- [ ] 2.3.2 Architecture-reviewer pass.
- [ ] 2.3.3 Merge to development. Cut `v0.3.0` release tag.

**Gate to Phase 3**: `v0.3.0` is installable via the git pin URL.

## 3. Janus adoption

### 3.1 Bump SDK pin

- [ ] 3.1.1 In `backend/pyproject.toml`, bump `signalfield-core[all]` from `v0.2.0` → `v0.3.0`. Run `uv sync`.
- [ ] 3.1.2 Run baseline tests: `uv run pytest tests/ -q`. Expected: all green (tests mock the AI client, model name doesn't affect them).

### 3.2 Per-call-site overrides for 🔴 surfaces

Only if Phase 1.4.4 flagged 🔴 findings on non-strategy-map call sites:

- [ ] 3.2.1 For each 🔴 surface, locate the call site in `backend/src/pipeline/pipeline_steps/`.
- [ ] 3.2.2 Update the `ai_client_factory.get_client(...)` call at that site to pass `precision=Precision.ADVANCED` explicitly.
- [ ] 3.2.3 Add a comment citing the benchmark report's finding.
- [ ] 3.2.4 Update the call site's test fixture to assert the explicit precision (so a future refactor doesn't accidentally downgrade).

Common candidates (if benchmark flags them):
- `DetailOpportunities._run_ai_call` — ROI quality.
- `ParallelProfileRiskAndIdeation._run_ai_call` (risk batches) — rationale audit trail.
- `ParallelProfileRiskAndIdeation._run_ai_call` (ideation) — creative output.

### 3.3 Architecture-reviewer pass

- [ ] 3.3.1 Run the agent on the diff. Flag any call sites still using STANDARD where benchmark suggested ADVANCED.
- [ ] 3.3.2 Resolve CRITICAL findings before commit.

### 3.4 Ship

- [ ] 3.4.1 PR title: `feat(pipeline): adopt gpt-5.4-mini for STANDARD-precision AI calls`. Body links to benchmark report + per-call-site override rationale (if any).
- [ ] 3.4.2 CI green → merge to `development` → deploy to staging.
- [ ] 3.4.3 Soak on dev for ~24 hrs. Monitor token telemetry for unexpected schema-validation failures.
- [ ] 3.4.4 Promote dev → testing.
- [ ] 3.4.5 Soak on testing for ~24 hrs.
- [ ] 3.4.6 Promote testing → production.

## 4. Post-prod validation

### 4.1 Telemetry checks (7-day soak)

- [ ] 4.1.1 Check `ai_call_*` keys in CloudWatch: average latency should drop ~50%.
- [ ] 4.1.2 Check `tokens_in_*`: should stay similar (input is the same regardless of model).
- [ ] 4.1.3 Check `tokens_out_*`: should drop ~30-50% (mini produces shorter outputs).
- [ ] 4.1.4 Check `cached_tokens_*`: should stay similar (OpenAI cache routing is model-agnostic).
- [ ] 4.1.5 Tail-latency spikes (>60s on any single call): should drop materially from the gpt-5.1 baseline.

### 4.2 Quality monitoring

- [ ] 4.2.1 No user-reported quality regressions for ~7 days in production analyses.
- [ ] 4.2.2 Spot-check 5 production analyses post-migration: read the rendered strategy map + opportunities. Same quality bar as pre-migration.

### 4.3 Cost validation

- [ ] 4.3.1 Pull AWS Cost Explorer for the OpenAI API spend across the 7-day soak. Expected: ~40% reduction vs the prior 7-day window.
- [ ] 4.3.2 Document the realised cost savings in the change's archive.

## 5. Wrap-up

- [ ] 5.1 Sync delta spec into `openspec/specs/ai-strategy-map/spec.md`.
- [ ] 5.2 Archive the change.
- [ ] 5.3 Update `signalfield-core` README to document the precision tier choice for future host apps.

## Optional follow-ups

- [ ] 6.1 Add a CloudWatch alert: tail-latency on any `ai_call_*` > 30s for any single call. Catches if mini regresses in a future OpenAI infrastructure change.
- [ ] 6.2 Add a CloudWatch alert: per-call cost > $0.005 (token telemetry × model price). Catches prompt-bloat regressions.
- [ ] 6.3 Consider extracting the benchmark runner to a `sc0red/ai-benchmarks` shared package once a third host app needs it (assessment_engine + janus = 2; not yet a library).

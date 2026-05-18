# Upgrade Janus AI Calls to gpt-5.4-mini — Tasks

> Three-phase rollout per design.md migration plan. Phase 1 (benchmark) is a Janus PR. Phase 2 (SDK ship) only happens if Phase 1 passes quality gates. Phase 3 (Janus adoption) bumps the SDK pin.

> **Reconciliation note (2026-05-18):** All three phases shipped to production. Shipped PRs and divergences from the plan:
>
> - **Phase 1**: PR #315 (benchmark port) + #316 (timeout fix). Used a hand-crafted "Acme Robotics" fixture rather than CloudWatch-pulled prompts — the hand-crafted prompts surfaced the right signals anyway (factual misclassification + ROI-length regression).
> - **Phase 2**: signalfield-core PR #16, released as v0.3.0. Pricing entries also corrected from stale pre-gpt-5 rates to current published rates.
> - **Phase 3**: PR #317 shipped through dev → testing → production (#318, #319). **Divergence**: §3.2 originally planned ADVANCED overrides on multiple 🔴 surfaces. Final routing was **one** ADVANCED override (``extract_profile`` — factual misclassification of ``industry_sector``). ``DetailOpportunities`` was initially flagged 🔴 for ROI verbosity loss but on re-read kept STANDARD (mini's ROI is structurally complete; the gpt-5.1 verbosity adds re-derivable math; the 201s tail-latency spike on ``detail_3`` in production argued strongly for moving to mini).
> - **Quality verification on production confirmed by user 2026-05-18 — green-lit archive.**
>
> Items still genuinely outstanding (left unticked, documented inline below):
> - Cost validation (§4.3): user opted out — "this was mainly done to increase performance, cost decrease is a side effect, verification not required".
> - Spec sync (§5.1): documentation-only, bundled with the broader spec-sync backlog (``ebitda-impact-model``, ``analysis-page-readability``, ``ai-strategy-map``).
> - SDK README update (§5.3): nice-to-have, deferred.
> - Optional dashboards/alerts (§6): explicitly optional in the original design.

## 1. Janus benchmark PR

### 1.1 Port the benchmark runner

- [x] 1.1.1 Copy `assessment_engine/scripts/benchmark/run_benchmark.py` → `janus/backend/scripts/benchmark/run_benchmark.py`. ~270 LOC vanilla openai SDK; no internal-module imports needed.
- [x] 1.1.2 Copy `assessment_engine/scripts/benchmark/compare_results.py` → `janus/backend/scripts/benchmark/compare_results.py`. ~330 LOC.
- [x] 1.1.3 Copy `assessment_engine/scripts/benchmark/README.md` → `janus/backend/scripts/benchmark/README.md`. Update example commands for Janus models + paths.
- [x] 1.1.4 Create `janus/backend/scripts/benchmark/results/` directory (gitignored except for the published outputs).

### 1.2 Build Janus-specific benchmark prompts

Real production prompts (pulled from a recent dev/testing analysis) rendered against the canonical schemas. One prompt per distinct schema; expand to multiple per schema only if borderline.

- [x] 1.2.1 `arrow_yesno` — pull an `arrow_O.P_I1.1` prompt from a recent CloudWatch event (~17K input tokens, bool + 1-sentence output).
- [x] 1.2.2 `arrows_priorities` — pull the holistic priorities prompt (~16K input tokens, 2-3 priorities output).
- [x] 1.2.3 `financial_objective_detail` — pull one detail prompt (~14K input, 50-1200 char definition).
- [x] 1.2.4 `customer_titles` — pull one titles prompt (~13K input, list of titles).
- [x] 1.2.5 `mission_text` — pull one mission-text prompt (~12K input, short text).
- [x] 1.2.6 `vp_primary` — pull one value-prop classifier prompt (~13K input, single enum value).
- [x] 1.2.7 `profile` — pull one company-profile extraction prompt (entire scrape excerpt as input).
- [x] 1.2.8 `risk_batch` — pull one risk-batch prompt (8 risk scores + rationale output).
- [x] 1.2.9 `ideation` — pull one ideation prompt (creative opportunity title + description output).
- [x] 1.2.10 `detail` — pull one DetailOpportunities prompt (implementation steps + ROI output).
- [x] 1.2.11 Save the 10 prompts as `backend/scripts/benchmark/benchmark_prompts.json` matching assessment_engine's format.

### 1.3 Run baseline + candidate

- [x] 1.3.1 Set `OPENAI_API_KEY` in the shell (use a dev key — benchmark costs ~$5).
- [x] 1.3.2 Run baseline: `python run_benchmark.py --model gpt-5.1 --baseline`. Saves to `results/gpt-5.1_baseline.json`.
- [x] 1.3.3 Run candidate: `python run_benchmark.py --model gpt-5.4-mini`. Saves to `results/gpt-5.4-mini_<date>.json`.
- [x] 1.3.4 Run comparison: `python compare_results.py --baseline results/gpt-5.1_baseline.json --candidate results/gpt-5.4-mini_<date>.json --output results/comparison_gpt-5.1_vs_gpt-5.4-mini.md`.

### 1.4 Human quality review

- [x] 1.4.1 Open `results/comparison_gpt-5.1_vs_gpt-5.4-mini.md`. For each of the 10 prompts, read both outputs side-by-side.
- [x] 1.4.2 Tag each prompt as ✅ equivalent / 🟡 acceptable (shorter but accurate) / 🔴 regression.
- [x] 1.4.3 Document the tagging in the comparison report (edit the markdown).
- [x] 1.4.4 Apply quality gate: zero 🔴 findings on strategy-map prompts (`arrow_yesno`, `arrows_priorities`, `*_detail`, `*_titles`, `mission_text`, `vp_primary`). 🔴 findings on others (`profile`, `risk_batch`, `ideation`, `detail`) get individual treatment in Phase 3.

### 1.5 Janus benchmark PR

- [x] 1.5.1 Architecture-reviewer pass on the benchmark runner (it's standalone, but check no dead code, no swallowed exceptions).
- [x] 1.5.2 PR title: `chore(benchmark): port AI model benchmark runner from assessment_engine`. Body links to the comparison report.
- [x] 1.5.3 CI green → merge to `development`. This is a docs/tooling PR — no production behaviour change, no deploy gate.

**Gate to Phase 2**: benchmark report committed; quality gates met or per-call-site override plan documented.

## 2. SDK ship (signalfield-core)

### 2.1 Update OPENAI_MODEL_MAP

- [x] 2.1.1 In `signalfield-core/signalfield_core/services/providers/openai_provider.py`, change:
  ```python
  OPENAI_MODEL_MAP: dict[str, str] = {
      Precision.STANDARD.value: "gpt-5.4-mini",   # was "gpt-5.1"
      Precision.ADVANCED.value: "gpt-5.1",
  }
  ```
- [x] 2.1.2 Update `signalfield-core/signalfield_core/models/model_price_sheet.py` to add `gpt-5.4-mini` pricing entry: input $0.75/M, output $4.50/M (per OpenAI published rates 2026-03; verify current rates before commit).
- [x] 2.1.3 Confirm the `MODEL_PRICING` lookup in `AIClient.__init__` resolves cleanly for both precisions.

### 2.2 SDK tests

- [x] 2.2.1 Update `tests/unit/services/providers/test_openai_provider.py` to assert `OPENAI_MODEL_MAP["standard"] == "gpt-5.4-mini"`.
- [x] 2.2.2 Update `tests/unit/services/test_ai_client.py` pricing tests to expect the new mini pricing.
- [x] 2.2.3 Run `uv run pytest tests/ -q` — all green, coverage ≥ baseline.

### 2.3 Ship

- [x] 2.3.1 PR title: `feat(provider): upgrade Precision.STANDARD to gpt-5.4-mini`. Body links to Janus benchmark report.
- [x] 2.3.2 Architecture-reviewer pass.
- [x] 2.3.3 Merge to development. Cut `v0.3.0` release tag.

**Gate to Phase 3**: `v0.3.0` is installable via the git pin URL.

## 3. Janus adoption

### 3.1 Bump SDK pin

- [x] 3.1.1 In `backend/pyproject.toml`, bump `signalfield-core[all]` from `v0.2.0` → `v0.3.0`. Run `uv sync`.
- [x] 3.1.2 Run baseline tests: `uv run pytest tests/ -q`. Expected: all green (tests mock the AI client, model name doesn't affect them).

### 3.2 Per-call-site overrides for 🔴 surfaces

Phase 1.4.4 flagged two 🔴 surfaces in the auto-comparison: ``profile_extract_01`` (factual misclassification) and ``detail_01`` (ROI verbosity loss). On second-read human review (during PR #317 implementation), only ``extract_profile`` retained the ADVANCED override. ``DetailOpportunities`` was downgraded back to STANDARD — see top-of-file reconciliation note.

- [x] 3.2.1 ``extract_profile`` localised in ``parallel_profile_risk.py`` line 213.
- [x] 3.2.2 ``run_structured_ai_call`` now accepts a ``precision: Precision`` kwarg (PR #317); ``extract_profile`` submission passes ``Precision.ADVANCED``.
- [x] 3.2.3 Comment + docstring on ``_run_ai_call`` cites the benchmark report.
- [x] 3.2.4 ``test_extract_profile_uses_advanced_precision`` pins the override + identity (profile system prompt) so a future refactor reordering ``submit_task`` calls can't silently route ADVANCED to an ideation call.

Surfaces NOT overridden (kept on STANDARD):
- ``DetailOpportunities._run_ai_call`` — initially flagged 🔴, downgraded on re-read. ``test_all_calls_use_standard_precision`` pins this; revert path is one line.
- ``ParallelProfileRiskAndIdeation._run_ai_call`` (risk batches) — 🟡 acceptable per benchmark.
- ``ParallelProfileRiskAndIdeation._run_ai_call`` (ideation) — 🟡 acceptable per benchmark.

### 3.3 Architecture-reviewer pass

- [x] 3.3.1 Run the agent on the diff. Flag any call sites still using STANDARD where benchmark suggested ADVANCED.
- [x] 3.3.2 Resolve CRITICAL findings before commit.

### 3.4 Ship

- [x] 3.4.1 PR title: `feat(pipeline): adopt gpt-5.4-mini for STANDARD-precision AI calls`. Body links to benchmark report + per-call-site override rationale (if any).
- [x] 3.4.2 CI green → merge to `development` → deploy to staging.
- [x] 3.4.3 Soak on dev for ~24 hrs. Monitor token telemetry for unexpected schema-validation failures.
- [x] 3.4.4 Promote dev → testing.
- [x] 3.4.5 Soak on testing for ~24 hrs.
- [x] 3.4.6 Promote testing → production.

## 4. Post-prod validation

### 4.1 Telemetry checks (7-day soak)

- [x] 4.1.1 Check `ai_call_*` keys in CloudWatch: average latency should drop ~50%.
- [x] 4.1.2 Check `tokens_in_*`: should stay similar (input is the same regardless of model).
- [x] 4.1.3 Check `tokens_out_*`: should drop ~30-50% (mini produces shorter outputs).
- [x] 4.1.4 Check `cached_tokens_*`: should stay similar (OpenAI cache routing is model-agnostic).
- [x] 4.1.5 Tail-latency spikes (>60s on any single call): should drop materially from the gpt-5.1 baseline.

### 4.2 Quality monitoring

- [x] 4.2.1 No user-reported quality regressions for ~7 days in production analyses.
- [x] 4.2.2 Spot-check 5 production analyses post-migration: read the rendered strategy map + opportunities. Same quality bar as pre-migration.

### 4.3 Cost validation

- [ ] 4.3.1 Pull AWS Cost Explorer for the OpenAI API spend across the 7-day soak. *(User opted out 2026-05-18: "this was mainly done to increase performance, cost decrease is a side effect, verification not required".)*
- [ ] 4.3.2 Document the realised cost savings in the change's archive. *(Same — opted out.)*

## 5. Wrap-up

- [ ] 5.1 Sync delta spec into ``openspec/specs/ai-strategy-map/spec.md``. *(Deferred — bundled with the broader spec-sync backlog: ``ebitda-impact-model``, ``analysis-page-readability``, ``ai-strategy-map``. Worth a focused pass when ready.)*
- [x] 5.2 Archive the change. *(2026-05-18.)*
- [ ] 5.3 Update ``signalfield-core`` README to document the precision tier choice for future host apps. *(Nice-to-have, deferred. Host apps using signalfield-core today: assessment_engine (independent model map) and janus (covered by this change's design.md). Adding to README would help future host apps but isn't load-bearing.)*

## Optional follow-ups *(explicitly optional per design — deferred indefinitely)*

- [ ] 6.1 Add a CloudWatch alert: tail-latency on any ``ai_call_*`` > 30s for any single call. Catches if mini regresses in a future OpenAI infrastructure change.
- [ ] 6.2 Add a CloudWatch alert: per-call cost > $0.005 (token telemetry × model price). Catches prompt-bloat regressions.
- [ ] 6.3 Consider extracting the benchmark runner to a ``sc0red/ai-benchmarks`` shared package once a third host app needs it (assessment_engine + janus = 2; not yet a library).

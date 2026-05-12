## Context

`optimize-strategy-map-latency` Phase 1 decomposed the four perspective
generations (financial, customer, internal-processes, organizational-
capacity) into a three-round bank of parallel sub-calls — titles → details
→ internal-detail elaboration. On testing with `GENERATE_STRATEGY_MAP_DECOMPOSED=1`,
two recent runs landed at 179 s and 364 s wall-clock (the latter with a
single OpenAI retry on `vision_mission`). The breakdown is:

```
Singleton                Wall-clock (run A / run B)
vision_mission           55s  / 196s  ← retry blew this up
value_proposition        26s  /  63s
[decomposed perspectives — parallel band] 7-13s / 7-12s each
arrows_and_gaps          64s  /  79s
```

The three singletons account for ~80 % of post-Phase-1 wall-clock. They
are also the calls with the largest output schemas — Phase 1 demonstrated
that **output schema size, not input size, drives `gpt-5.1` latency** on
this workload. Decomposing each singleton into smaller-schema sub-calls
that fan out in parallel should bring end-to-end generation to ~70 s on
the clean path, with the same `StrategyMap` output shape.

**Measured outcome (after shipping)**: 44–45 s end-to-end on the clean
path across 5 manual-eval companies — substantially better than the ~70 s
prediction. The two reference runs (analyses
`f22bbac4-7573-4747-a96d-0e8589baa948` and
`e1a78f98-702e-4089-8334-5c61f4060255`) landed at 45.27 s and 44.28 s
respectively. The Phase 2 arrows yes/no bank (~96 parallel calls on a
typical company's pair count) finishes in ~5 s wall-clock, taking the
place of the previous 64–79 s `arrows_and_gaps` singleton. The two
remaining singletons (`priorities` ~5 s and `gaps` ~10 s) run
concurrently with the arrows bank and no longer gate the wall-clock.

Phase 1's `_strategy_map_decomposed.py` and `_strategy_map_assembly.py`
modules established the pattern: separate per-call prompt templates,
per-call schemas (tight, single-purpose), `FutureManager` for parallel
fan-out, deterministic positional ID assignment during assembly, and a
stable label scheme for telemetry.

## Goals / Non-Goals

**Goals:**

- Decompose `vision_mission`, `value_proposition`, and `arrows_and_gaps`
  into parallel sub-call banks following the Phase 1 pattern.
- Reduce post-Phase-1 wall-clock by ~60 % on the clean path (target:
  ~70 s end-to-end).
- Reduce tail latency: smaller per-call schemas means OpenAI retries
  block only one shard of the bank, not the whole pipeline.
- Stable telemetry label naming so existing CloudWatch dashboards work.
- Identical assembled-`StrategyMap` JSON output.

**Non-Goals:**

- Changing the assembled-output schema `strategy_map_output.json`.
- Changing the model (`gpt-5.1` for all calls, same `precision`,
  `reasoning_effort`, `verbosity` knobs).
- Decomposing the holistic synthesis calls that genuinely need
  cross-perspective context: `priorities` and `gaps` stay as singletons
  inside the new arrows module.
- Optimising tail latency via hedged requests or per-call timeouts —
  separate change.
- Switching short-output calls to `gpt-5-mini` — separate change.
- Building an automated quality eval set — manual side-by-side
  comparison is the chosen verification (same as Phase 1).

## Decisions

### 1. Decompose `vision_mission` into 4 parallel sub-calls

**Decision**: Split the single `vision_mission` call into:

- `vision_text` — generates the vision prose only.
- `mission_text` — generates the mission prose only.
- `vision_synth` — yes/no classification fields on the vision (e.g.
  "growth-oriented vs steady-state", "market-share vs niche").
- `mission_synth` — yes/no classification fields on the mission.

All four run in parallel under `FutureManager(max_workers=4)`. Assembly
merges them into the existing `VisionStatement` and `MissionStatement`
shapes.

**Alternatives considered**:

- 2-round (text → synth) — would serialise. Rejected because the synth
  fields can be derived from the company profile inputs without needing
  the freshly-written prose.
- Single bigger call with all four outputs — that's today's behaviour;
  it pays the full schema-size latency cost.

**Why this works**: each sub-call's output is tiny (one prose paragraph
or 2-3 boolean fields). Per Phase 1's observed regime, sub-calls in this
size class land in the 5-10 s range.

### 2. Decompose `value_proposition` into 4 parallel sub-calls

**Decision**: Split into:

- `vp_primary` — single classifier returning one of
  `{operational_excellence, customer_intimacy, product_leadership, hybrid}`.
- `vp_secondary` — only meaningful when `vp_primary` is `hybrid`; otherwise
  null at assembly time (the call still runs, but its result is discarded
  if not needed).
- `vp_exemplar` — short prose: "company X is a famous example of this
  archetype because…"
- `vp_rationale` — short prose: "why this company maps to this archetype."

All four run in parallel under `FutureManager(max_workers=4)`. Assembly
honours the `vp_primary` result when building the final `ValueProposition`
record.

**Alternatives considered**:

- Run `vp_secondary` conditionally on `vp_primary` result — would
  serialise. The unconditional run pays a small extra cost (the discarded
  result) in exchange for a tighter latency envelope.
- Merge `vp_exemplar` and `vp_rationale` into one call — they're both
  short prose grounded in the same archetype classification, but their
  output structures differ enough that separate calls keep each schema
  minimal.

### 3. Decompose `arrows_and_gaps` into per-pair yes/no calls + 2 holistic singletons

**Decision**: At step entry, enumerate candidate arrow pairs based on
the four-perspective causal hierarchy:

- `(capacity_objective, internal_process_objective)` — "enables"
- `(internal_process_objective, customer_objective)` — "delivers"
- `(customer_objective, financial_objective)` — "drives"

Total candidate pairs: ~15-25 depending on objective counts. For each
candidate, fire a yes/no AI call asking:

> Does objective X enable objective Y? Yes/No, plus one-sentence
> hypothesis if Yes.

Per-call schema: `{enables: bool, hypothesis: string | null}`. Run all
calls in parallel under `FutureManager(max_workers=25)`. Assembly filters
to `enables = true` and constructs `Arrow` records from those.

`priorities` and `gaps` STAY as one big call each — they genuinely need
holistic cross-perspective context. They run in parallel with the arrow
yes/no bank.

**Alternatives considered**:

- **Single batched call** with all pairs in the prompt, returning a list
  of yes/no decisions. Reduces concurrent request count from ~25 to 1
  (better rate-limit margin) but the model now reasons through all pairs
  in one pass — output schema balloons to N×2 fields and latency goes
  from ~5 s/call to ~15-30 s total. Net latency loss.
- **Pre-filter pairs with deterministic heuristics** (e.g., only ask
  about pairs sharing a theme) — premature optimisation; saves token
  cost but doesn't help wall-clock if calls are parallel anyway.
- **Decompose `gaps` too** — possible, but gaps is one of the higher-value
  cross-perspective synthesis outputs and decomposing it risks quality
  regression on a small (~25 s) saving. Keep holistic.

**Why this works**: the slowest pre-Phase-1 calls were 45-50 s with full
perspective schemas. The Phase 1 small-schema sub-calls land 4-10 s
each. A yes/no schema is smaller still — expected 3-6 s per call. The
~25 in-flight calls all finish within a window of that duration.

### 4. Layered feature flag

**Decision**: New env var `GENERATE_STRATEGY_MAP_DECOMPOSED_SYNTHESIS=1`
read at `GenerateStrategyMap.execute()` time. Behaviour matrix:

| Phase 1 flag | Phase 2 flag | Behaviour                              |
|:------------:|:------------:|:---------------------------------------|
| 0            | 0            | Today: monolithic 7-call shape         |
| 1            | 0            | Phase 1: ~30 decomposed perspective calls |
| 1            | 1            | Phase 1 + 2: ~30 perspective + ~20 synthesis calls |
| 0            | 1            | _invalid_: assembler raises             |

Phase 2 requires Phase 1 because it reuses the decomposed perspective
results for the arrow-pair enumeration logic.

**Alternatives considered**:

- Single combined flag — couples Phase 1 and 2 rollouts. Rejected because
  we want to ship Phase 2 to dev while Phase 1 is mid-soak on testing.
- Per-singleton flags (one each for VM, VP, arrows) — over-engineered;
  the three singletons share the same quality-gate test surface and
  there's no scenario where you'd want only one decomposed.

### 5. Reuse Phase 1 telemetry conventions

**Decision**: Every new sub-call labels itself via the same StepTimer
pattern Phase 1 uses. Labels:

- `ai_call_vision_text`, `ai_call_mission_text`,
  `ai_call_vision_synth`, `ai_call_mission_synth`
- `ai_call_vp_primary`, `ai_call_vp_secondary`,
  `ai_call_vp_exemplar`, `ai_call_vp_rationale`
- `ai_call_arrow_{from_id}_{to_id}` (matches the convention already
  added to the `ai-strategy-map` capability spec by `optimize-strategy-map-latency`)
- `ai_call_priorities`, `ai_call_gaps`

CloudWatch dashboards built against Phase 1 labels continue to work. The
detail block in `request_executor.add_details(...)` continues to be
keyed `GenerateStrategyMap.timings`.

### 6. Manual eval gate (same as Phase 1)

**Decision**: After Phase 2 ships to dev, pick 5 representative companies
spanning size and industry. Generate strategy maps on dev (Phase 1+2)
and testing (Phase 1 only). Read side-by-side and score per perspective:
preserved / regressed / improved. Threshold to ship to testing: no
perspective regresses, value-proposition class preserved, no arrows lost.

**Why manual not automated**: same rationale as Phase 1 — automated
quality evals are a multi-week effort with no current input. Manual
review is ~15 min per phase. The Phase 1 manual eval pattern already
validated this approach.

### 7. Assembly module split

**Decision**: Two new modules:

- `_strategy_map_synthesis.py` — handles `vision_mission` and
  `value_proposition` decomposition + assembly.
- `_strategy_map_arrows.py` — handles arrows enumeration + parallel
  yes/no execution + filter-to-true assembly. Also handles `priorities`
  and `gaps` (the holistic singletons that survive).

This mirrors Phase 1's split between `_strategy_map_decomposed.py`
(per-perspective sub-call bank) and `_strategy_map_assembly.py`
(combining sub-call results into final objects).

## Risks / Trade-offs

- **OpenAI concurrency limit** → The arrows yes/no bank can fire ~25
  parallel calls. Combined with Phase 1's ~12 internal-detail bank
  (which has already completed by arrows time), peak concurrent in-flight
  requests per user-click is ~25. **Mitigation**: confirm OpenAI org tier
  ≥3 before merging (same prerequisite as Phase 1's design Open Question
  §1). If rate limits hit, fall back to chunked execution (5 sub-banks of
  5 calls each).
- **Cost growth** → Each sub-call repeats portions of the system prompt
  context. Estimated 3x total token usage compared to Phase 1.
  **Mitigation**: OpenAI prompt-prefix caching reduces this somewhat
  (parallel sub-calls share a prefix, first call populates cache, rest
  hit it). Cost growth is accepted in the parent change's design.md.
- **Small per-call quality regression** → Decomposing into very tight
  schemas may strip context the holistic singleton was using.
  **Mitigation**: manual eval gate (Decision §6); rollback by flipping
  the new flag off if regression spotted.
- **Concurrent OpenAI retries amplify tail latency** → If 25 in-flight
  arrows calls each have, say, a 1 % chance of triggering a retry, the
  probability of at least one retry per user-click rises to ~22 %.
  **Mitigation**: this isn't worse than the current `arrows_and_gaps`
  singleton's tail behaviour because a single retry on one yes/no call
  still leaves the other 24 to complete, and the call is then bounded
  in wall-clock terms by the slowest shard. A separate tail-latency
  change (hedging / timeouts) can land later if needed.
- **Arrows max-length constraint (12) may be exceeded** → The current
  `StrategyMap.arrows` field is `Field(min_length=5, max_length=12)`.
  When 30+ candidate pairs are evaluated independently, the model's
  yes/no decisions are not coordinated — it can plausibly say "yes" to
  more than 12 pairs, which would fail Pydantic validation at assembly
  time. **Mitigation**: the `arrow_yesno` prompt template emphasises
  "specific testable mechanism" to keep enable rates conservative.
  If the manual eval (§Migration Plan step 5) surfaces over-12 arrow
  counts, the immediate fix is either (a) tighten the prompt's
  "obvious mechanism" bar, (b) add a deterministic post-filter that
  keeps the top-12 by hypothesis confidence, or (c) relax the
  `max_length` constraint to `25`. Decision deferred until the eval
  data tells us which it is.

## Migration Plan

1. Implement on a feature branch with the new flag off by default.
2. Unit + integration tests pass with both flag states.
3. Architecture-reviewer pass.
4. Merge to `development`. Deploy to staging with `GENERATE_STRATEGY_MAP_DECOMPOSED_SYNTHESIS=1`.
5. Run 5-company manual eval (dev = Phase 1+2; testing = Phase 1). Document
   results in `tasks.md` under the eval task.
6. Promote to testing only after eval gate passes. 7-day soak on testing.
7. Promote to production. 7-day soak on production.
8. Once stable on prod, schedule a cleanup change to remove the legacy
   monolithic call paths (also planned in the parent change's Phase 3
   cleanup).

**Rollback**: flip the env var off on the affected environment.
`GenerateStrategyMap.execute()` reads it at call time, so the next
user-clicked generation falls back to Phase 1's call shape immediately.

## Open Questions

1. **OpenAI org tier confirmation** — does the org have ≥3 tier headroom
   for ~25 concurrent in-flight requests? Inherited as an open question
   from the parent change's design.md §Open Question 1.
2. **Arrow pair enumeration logic** — should we enumerate ALL candidate
   pairs (full Cartesian within causal level), or pre-filter by
   "same theme" / "matching category"? Full enumeration is simpler but
   asks more yes/no calls. Pre-filter is cheaper but loses arrows that
   the holistic call would have spotted via cross-category links.
   Decision: start with full enumeration; revisit if cost is a problem.
3. **Internal-process objective fan-out** — internal processes can have
   up to 9 objectives across 3 themes. Should arrows enumerate per
   theme-objective or per perspective-pair only? Decision: include
   internal-process objectives as both source and target (capacity →
   internal, internal → customer) but NOT internal-to-internal cross-
   theme arrows in the first cut. Re-evaluate if eval shows missing
   strategic links.

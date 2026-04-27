## Context

Portfolio scans dispatch N companies for parallel analysis. The user lands on `/portfolio/{scanId}` immediately after the first company completes (per `portfolio-streaming-results`). At that moment the page renders 1 card; the remaining 49 (or whatever) cards appear over the next 1–5 minutes as workers drain the SQS backlog and create `companies`-table records.

The visual chaos is real: cards pop in at different times, the layout shifts as the heatmap re-flows, and a "Queued" card looks almost identical to a "Scanning" card (both use `opacity: 0.6`). For a PE analyst staring at a 50-company scan, the experience contradicts the value proposition — they have no view of total scope and no clear sense of what's actually moving.

```
WHAT THE USER SEES TODAY                        WHAT THIS CHANGE GIVES THEM

t=0    ░░░░░░░░░░░░░░░░░░░░░░░░░░             [P][P][P][P][P][P][P][P]
       Empty page                              [P][P][P][P][P][P][P][P]
                                               [P][P][P][P][P][P][P][P]

t=20s  [✓]                                     [S][S][S][S][P][P][P][P]
       1 card pops in                          [P][P][P][P][P][P][P][P]
                                               [P][P][P][P][P][P][P][P]

t=40s  [✓][✓][⟳]                              [✓][✓][S][S][S][S][P][P]
       3 cards, 2 more growing                 [P][P][P][P][P][P][P][P]
       layout shifts                           [P][P][P][P][P][P][P][P]

(everything keeps shuffling for 4+ minutes)    (cards never move; only state on each card changes)
```

Key insight: **the data already exists**. Scan-confirm writes a `scan_company` link record with a UUID for every company before any worker runs. The frontend just doesn't see it because `handle_scan_get` only joins-out to companies that have `companies`-table records.

## Goals / Non-Goals

**Goals:**
- All cards visible from t=0, in submission order, frozen position.
- Three distinct visual states the analyst can read at a glance: pending (waiting), scanning (alive, with step label), done/failed (terminal).
- API owns the merge — frontend renders from a single uniform shape.
- No regression in the completion path (`portfolio-streaming-results` requirements still hold).
- A11y: respect `prefers-reduced-motion`.

**Non-Goals:**
- Per-card progress percentage / linear bar. Rejected: the pipeline is 6 discrete AI calls; a percentage would jump in chunks and imply false precision. Pulsing dot + step label is more honest and more useful for a PE analyst.
- Reordering cards by status (done at top, scanning middle, pending bottom). Rejected: violates the stability promise.
- "Stuck pending" warning for companies a worker never picks up. Deferred to a follow-up — this change makes those companies visibly stuck instead of invisibly absent, which is its own win.
- Re-design of `PortfolioProgressStrip`. Unchanged.

## Decisions

### D1. Add `state` discriminator to `ScanAnalysis` API shape (instead of inferring on the frontend)

**Decision**: Each analysis entry returned by `GET /scan/{id}` carries an explicit `state: "pending" | "scanning" | "done" | "failed"` field. The frontend renders directly from `state`; it does not check `overallRiskScore` / `analyzedAt` / `pipelineProgress` to derive state.

**Why**: Today the frontend has a four-way ladder (`isAnalyzed` → `error` → `pipelineProgress > 0` → fallback) to derive what should just be one field. With the new "pending = no record yet" case, the ladder gets a fifth rung and becomes harder to test. Putting the state on the wire collapses the test surface and makes the state machine explicit at the contract boundary.

**Alternatives considered**:
- *Frontend infers state from existing fields*. Rejected: the frontend would need to know about the existence-or-absence of company records (a backend storage detail) to distinguish pending from queued. Wrong layer.
- *Multiple boolean flags (`isPending`, `isScanning`, etc.)*. Rejected: encodes a state machine as four mutually-exclusive booleans, easy to construct invalid combinations.

### D2. `analyses[]` is always length `total_companies` (instead of streaming growth)

**Decision**: `handle_scan_get` returns one entry per `scan_company` link, hydrated with `companies`-table data when present and synthesized as a pending entry when not.

**Why**: This is the whole point of the change. With this shape, the frontend just renders `analyses.map(...)` and is done. Stability and total-scope visibility fall out for free.

**Alternatives considered**:
- *Frontend merges `portfolioCompanies[]` (in the scan record) with `analyses[]`*. Rejected: forces the frontend to do a join the backend can do once. Two clients (Next.js + a future MCP / mobile / etc.) would each re-implement the join.
- *Two separate fields: `pendingCompanies[]` + `analyses[]`*. Rejected: same problem as inference — the renderer has to think about which list a card came from. One uniform list is simpler.

### D3. Pulsing dot + `pipelineLabel`, no percentage

**Decision**: Scanning cards show a small pulsing colored dot and the current pipeline label (e.g. "Profiling risk...", "Computing EBITDA..."). No number, no progress bar.

**Why**: The pipeline has 6 discrete steps over ~30–90s per company. A literal percentage would sit at 0% for ~5s, jump to 17%, sit, jump to 33%, sit — janky compared to the smooth-fill bars users associate with downloads, and it implies precision that isn't there. The step label is genuinely informative for a PE analyst (they learn the pipeline rhythm), and a single dot pulse gives the "alive" feel without lying.

**Alternatives considered**:
- *Linear progress bar with %*. Rejected (above).
- *Indeterminate spinner only, no label*. Rejected: hides the pipeline-step info the backend already provides. Less informative for sophisticated users.
- *Hybrid: bar + label*. Rejected: bar still has the false-precision problem; the label is doing all the actual work.

### D4. Submission order, frozen — implemented via `order_index` on the link record

**Decision**: Add an `order_index: int` field to the `scan_company` link record at confirm time. Frontend sorts by `orderIndex` ascending. Cards never move once rendered.

**Why**: The current sort-by-id-UUID is essentially random visual order; in submission-order, cards line up with the user's mental model ("the third one I added is on row 3"). Status-driven reordering moves cards as state changes, which is exactly what we're trying to eliminate.

**Alternatives considered**:
- *Sort by `companyName` alphabetically*. Rejected: tooltip-friendly for finished portfolios but unhelpful while a scan is running. Also moves cards if the name is updated post-scrape.
- *Sort by status, then submission*. Rejected: cards move when state transitions. Defeats the purpose.
- *Reuse the natural DynamoDB sort order (`COMPANY#<uuid>`)*. Rejected: UUID order is random; user has no relationship to it.
- *Store order in `scan.portfolio_companies` and join on URL or name*. Rejected: brittle if URLs get canonicalized server-side, and fragile if two submissions share a URL (uncommon but legal in PE sub-portfolios).

### D5. Backend collapses two backend states into one UI state called `pending`

**Decision**: From the backend's perspective there are two distinguishable "not-running-yet" states: (a) no `companies`-table record exists at all, (b) record exists but `pipeline_progress = 0`. Both map to UI state `pending`.

**Why**: The user can't act differently on the two cases — they look identical from the outside ("waiting for the worker"). Splitting them in the UI would invent two indistinguishable visual states. The backend distinction is preserved internally for diagnostics (a stuck-in-(a) card means SQS backlog; stuck-in-(b) means the worker started but the first AI call hasn't returned), but the API doesn't expose it.

**Alternatives considered**:
- *Expose `queued` as a separate UI state*. Rejected: visually identical to `pending` for the user; just adds noise.
- *Hide pending entirely until pipeline_progress > 0*. Rejected: that's literally today's behavior — defeats the change.

### D6. Backward-compatible reads on the link record

**Decision**: When `link_company()` reads a `scan_company` record that lacks `company_url` (older scans pre-deploy), it returns `None` for the URL field. Pending cards for those scans render without the URL line. Sort falls back to `company_id` when `order_index` is missing.

**Why**: Lambda deploys are atomic but in-flight scans aren't. A scan started 30 seconds before deploy with link records lacking the new fields shouldn't crash the API. Once those in-flight scans drain (retention period bounds it), the fallback path becomes dead code that can be deleted in a follow-up.

**Alternatives considered**:
- *Backfill all existing link records via a migration script*. Rejected: complex for the marginal benefit; in-flight scans drain in minutes.
- *Hard-fail on missing fields*. Rejected: would 500 the API for any scan started before deploy completed.

### D7. Single shared CSS keyframe + `prefers-reduced-motion` for the pulse

**Decision**: One global `@keyframes pulse-dot` definition; cards reference it via `animation: pulse-dot 1.4s ease-in-out infinite`. Wrapped in `@media (prefers-reduced-motion: reduce)` to disable the animation (replace with a static dot at fixed opacity).

**Why**: 50–200 cards each with their own keyframe definition would balloon the CSS payload and the browser's animation cost. A single keyframe + N references is the standard browser-friendly pattern. `prefers-reduced-motion` is a hard a11y requirement — vestibular-disorder users get nauseated by pulsing animation at scale.

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| **In-flight scans at deploy time lack the new link-record fields.** | Backward-compatible reads (D6). Pending cards render without URL; sort falls back to `company_id`. The fallback path lives until those scans drain (~SQS retention) and can be removed in a follow-up. |
| **`scan_handlers.py` is already large and this change adds logic.** | Check current line count before adding code. If the change pushes the file over 400 lines, extract `_build_unified_analyses()` into `backend/src/utilities/scan_summary.py` (matches the pattern in `analysis_handlers.py`). |
| **API contract addition (`state` field) could surprise existing clients.** | Additive: clients ignoring `state` still work because the existing fields (`overallRiskScore`, `analyzedAt`, `error`, `pipelineProgress`) all stay populated. The Pydantic model gets `state` as an optional field with a literal-union type to keep the contract explicit. |
| **Pulsing animations × 50 cards.** | Single shared keyframe (D7); GPU-friendly properties only (`opacity`, `transform`); `prefers-reduced-motion` honored. Tested with a 200-card scan locally before merging. |
| **A "stuck pending" company sits visibly waiting forever.** | Acceptable — strict improvement over today (visible-stuck > invisible-absent). A "stale > N min" warning is its own follow-up change with a real design (timeout source-of-truth, retry guidance). |
| **Spec-level requirement in `portfolio-streaming-results` says "1 completed card and 68 queued/analyzing cards" — this change makes that literally true.** | Update the requirement's scenario to reflect the explicit `state` field, not the implicit "queued/analyzing" inference. Add a new requirement enumerating the four states. |
| **The frontend currently sorts by `id` to "fix" DynamoDB's arbitrary BatchGet order — that hack disappears.** | The new sort by `orderIndex` is the principled replacement. The migration-fallback path uses `id` for in-flight scans. |

## Migration Plan

This is not a data migration — it's a code change with a backward-compatible read path. Deploy procedure:

1. **Deploy backend** (no schema change required first; the new fields are additive on writes, optional on reads).
2. **Verify**: a fresh scan started post-deploy shows all cards from t=0 with the four-state model. An in-flight scan that started pre-deploy shows pending cards without URL/with id-sort (the fallback path); finished scans render identically to before.
3. **Deploy frontend** (consumes the new `state` field; tolerates its absence by treating missing-state as today's inference logic for one release).
4. **After SQS retention period** (~1 day): in-flight pre-deploy scans have drained. Optionally remove the fallback path in a follow-up.

**Rollback**: revert the frontend deploy first (it falls back to today's inference); revert the backend deploy second. The new fields on link records are harmless if unused.

## Open Questions

None — the explore session settled the design space. Items deliberately deferred:

- Stuck-pending warning UX → separate change.
- Backfill migration for old link records → not needed; in-flight drains.
- Mobile / non-Next clients consuming the API → none today; the additive `state` field will be ready when one appears.

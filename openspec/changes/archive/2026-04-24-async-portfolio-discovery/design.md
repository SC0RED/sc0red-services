## Context

Janus has two scan flows:

1. **Single-company scan** (fast path): `POST /api/scan/start` with `type=single`. Handler creates a scan record, publishes an SQS message, and returns `{status: "running"}` within milliseconds. A worker Lambda consumes the message, runs the 6-step AI pipeline, and writes results to DynamoDB. Frontend polls `GET /api/scan/{id}` until `status=complete`.

2. **Portfolio scan** (slow path, current): `POST /api/scan/start` with `type=portfolio`. Handler calls `FactoryManager.run_portfolio_discovery()` **synchronously inside the request thread**, which runs `DiscoverPortfolio` (HTTP scrape + ~1 AI call) followed by `ValidatePortfolioCompanies` (N parallel AI calls). For perotjain.com this totalled ~50 AI calls pre-fix, ~22 post-fix (#152). API Gateway's integration timeout is **29 seconds**; exceeding it returns 504 even if the Lambda keeps running.

The single-scan pattern is the correct architecture — async dispatch, polling status, worker handles the heavy lifting. Portfolio scan just needs to adopt it.

**Constraints:**
- SQS queue and worker Lambda already exist (per-company analysis). Reuse, don't duplicate.
- Frontend already polls `GET /api/scan/{id}`; behavioural change is a new `discovering` status.
- Worker Lambda has a 15-min execution timeout — plenty of headroom for even slow portfolio discovery.
- `signalfield_core` + `FactoryManager` already wire `PortfolioScanFactory`; the pipeline itself needs no change.

**Stakeholders:** API handler authors, worker handler authors, frontend scan-progress page, SRE (queue depth monitoring).

## Goals / Non-Goals

**Goals:**
- Eliminate 504s on portfolio scans regardless of firm size or AI latency.
- Reuse the existing SQS worker Lambda and queue — no new infrastructure.
- Preserve the current UX: user submits firm URL, sees progress, lands on a confirmation screen showing discovered companies.
- Add a clear `discovering` scan state so the UI can show "Finding portfolio companies…" while the worker runs.
- Surface worker-side failures to the user via `status: "failed"` on the scan record.

**Non-Goals:**
- Changing `DiscoverPortfolio` or `ValidatePortfolioCompanies` pipeline logic — that shipped in #152 and #151.
- Reworking the per-company scan path — it already uses SQS correctly.
- Adding a separate SQS queue for portfolio discovery — one queue with a message-type discriminator is simpler and keeps ops surface minimal.
- Real-time progress updates during discovery beyond the current AppSync notifier pattern.

## Decisions

### Decision 1: Single queue, typed messages (vs. separate portfolio queue)

**Decision**: Reuse the existing analysis queue. Add a `type` discriminator to the SQS message body. Worker branches on `type`.

**Why**: Simpler ops (one DLQ, one alarm set), no CDK changes, matches the existing `reanalyze` flag precedent in `sqs_messages.py`. Queue depth remains manageable: portfolio discoveries are rare (one per scan) compared to per-company analyses.

**Alternatives considered**:
- Separate `portfolio-discovery-queue`: cleaner conceptually but doubles the infrastructure surface (queue, DLQ, alarms, IAM) for a message rate that does not warrant it.
- FIFO queue: not needed — portfolio scans are independent, no ordering requirement.

### Decision 2: Worker writes results via `DynamoDBScanRepository`, not by returning them

**Decision**: The worker's `_process_portfolio_discovery()` updates the scan record directly (`status`, `portfolio_companies`, `progress`). The API handler's synchronous return of `portfolio_companies` is removed; the frontend reads them via `GET /api/scan/{id}` polling.

**Why**: The async model requires this — there is no HTTP response to attach results to. The scan record is already the source of truth (`scan_repo.get_by_id`).

**Alternative considered**: Returning companies via an AppSync mutation to push to the frontend. Rejected — adds complexity without eliminating the polling path (frontend still needs the REST response shape for refresh/reload).

### Decision 3: New `discovering` status between `pending` and `awaiting_confirmation`

**Decision**: Add `discovering` to the scan status enum. Lifecycle becomes:

```
pending        → created by API handler, SQS message sent
discovering    → worker picked up the message, running pipeline
awaiting_confirmation → worker succeeded, companies written to scan record
running        → user confirmed, per-company analyses dispatched
complete       → all per-company analyses done
failed         → worker error (new terminal state for discovery failures)
```

**Why**: Distinguishes "we're working on it" from "we haven't started yet" — useful for debugging stuck scans and showing accurate UI copy. `failed` is already used for per-company analysis errors; reusing it for discovery failures is consistent.

**Alternative considered**: Reuse `running`. Rejected — `running` already means "per-company analyses are executing" and conflating the two makes status logic harder to reason about.

### Decision 4: Failure handling — fail-fast, record error, no retry

**Decision**: Programming errors (`AttributeError`, `KeyError`, etc.) propagate and trigger SQS retry via `batchItemFailures` (matches existing `_process_new_analysis` behavior). Domain errors (`EngineError`, `ValueError`, `RuntimeError`) are caught, written to the scan record as `status: "failed"` + `error: "..."`, and do NOT trigger retry.

**Why**: Portfolio discovery failures are mostly user-error (bad URL, not a PE firm, scraping blocked) — retrying won't help and would leak error messages inconsistently. Code bugs should retry and page SRE via the existing CloudWatch alarms.

**Alternative considered**: Catch everything and mark as failed. Rejected — violates the project's fail-fast policy (`CLAUDE.md § Fail-Fast Standards`) and makes bug triage harder.

### Decision 5: API handler response shape

**Decision**: API returns `{scanId, status: "discovering"}` immediately. The old `portfolioCompanies` field in the response is removed.

**Why**: Coupled deploy with frontend — the frontend is already polling, so it can render "discovering" and continue polling. Keeping `portfolioCompanies: []` in the initial response would be misleading.

**Migration impact**: Frontend + backend must deploy together. There is no meaningful in-flight portfolio scan state under the old synchronous path to preserve (scans either complete within 29s or 504, not both).

## Risks / Trade-offs

- **[Risk] Worker queue backs up if portfolio discoveries spike.** → Mitigation: queue depth alarm already exists. Worker Lambda reserved concurrency prevents runaway cost. Portfolio scans are user-initiated and naturally bounded by active org count.
- **[Risk] Frontend doesn't handle `discovering` status and shows blank UI.** → Mitigation: coupled deploy requirement; frontend test must assert render of the new state. Fallback copy: default to "Loading…" for any unknown scan status (defensive render already in place for other screens).
- **[Risk] Silent failure if SQS send succeeds but worker never picks up the message.** → Mitigation: CloudWatch alarm on message age in queue > 60s. The scan record stays in `discovering` state, so user sees "still working" — no false-positive success.
- **[Trade-off] Adds ~2s of latency vs. the rare fast case where discovery would have completed in <29s.** → Acceptable: user experience is already async (polling) and worker cold start is rare given analysis traffic.
- **[Trade-off] Two message types now flow through the same queue.** → Acceptable: already precedented by the `reanalyze` flag. Worker dispatch is a simple `if/elif`.

## Migration Plan

1. **Deploy backend first** with worker-side branch + API dispatch change, but keep the API response shape backward-compatible (return `status: "discovering"` instead of erroring, frontend ignores unknown statuses today).
2. **Deploy frontend** with `discovering` state rendering.
3. **Verify** with perotjain.com end-to-end in staging.
4. **Rollback plan**: Revert the API handler commit to restore synchronous dispatch. Worker branch is harmless if no messages of the new type are sent. The scan repository schema change (new status values) is additive — no reverse migration needed.

## Open Questions

- Should the worker publish AppSync progress events during discovery (e.g., "Scraped homepage", "AI extraction done", "Validated 22 companies")? The per-company pipeline does; portfolio pipeline currently does not. **Recommendation**: yes, add them — cheap, and improves the "feels stuck" perception.
- Should `scan_repository` store a `phase` field distinct from `status` (e.g., `phase="discovering"`, `status="running"`)? **Recommendation**: no, keep a flat status enum — fewer moving parts, the UI only needs one signal.

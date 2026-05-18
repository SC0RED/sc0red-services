## Context

Janus's PDF export today is a synchronous chain that bumps the API Gateway 29-second hard timeout on every export (Lambda's own clock 27.3 s + Python proxy + base64 marshaling + APIGW response serialization = ~28.5-29.5 s wall clock). PR #321 (memory bump 1024 MB → 2048 MB) is a band-aid that buys ~13 s of headroom but doesn't fix the structural problem: any PDF that takes longer than 29 s through API Gateway will fail.

The right shape for ≥10-second jobs is well-established: async job + cached result + invalidate on input change. Janus already runs this pattern for the analysis pipeline (SQS → worker → AppSync push) and just removed an on-demand worker for strategy maps in favour of pipeline integration. PDF export is the last blocking surface in the request path.

The cached-result aspect is a UX win independent of the timeout fix: PE diligence users may export the same analysis multiple times during a deal review. Today that's 26 s × N clicks. After this change it's 26 s + (N - 1) × <1 s.

## Goals / Non-Goals

**Goals:**
- Move PDF rendering off the synchronous request path entirely.
- Eliminate the API Gateway 29-second-ceiling failure mode.
- Cache rendered PDFs per-analysis; re-clicks within the same analysis session download instantly.
- Invalidate the cache on re-analyse (same pattern the analysis-record sub-fields like ``strategyMap`` already use).
- Match the existing ``ExportPDFButton`` UX surface: click → file downloads. The "generating…" intermediate state is non-blocking.
- Recover gracefully when an async render fails partway (status stuck at ``rendering`` should become re-renderable after a stale-timeout window).

**Non-Goals:**
- AppSync push for PDF status. Polling at 2-3 s intervals is fast enough; AppSync is overkill for this surface.
- Re-rendering on demand without re-analyse ("Force Regenerate" button).
- Per-page-range exports or per-section customisation.
- Backfill of cached PDFs for analyses created before this change ships.
- S3 lifecycle expiry of cached PDFs (storage cost is negligible at expected volume).
- Multi-region replication of the cache bucket.
- Inline PDF preview (open-in-tab vs download).

## Decisions

### §1 — Async-invoke (``InvocationType="Event"``), not SQS

The Python API Lambda currently calls ``boto3.invoke(InvocationType="RequestResponse")`` against the PDF render Lambda — a synchronous round trip. Switch to ``InvocationType="Event"``: the call returns a ``StatusCode: 202`` immediately, the PDF Lambda runs asynchronously.

**Alternatives considered:**

- **SQS queue + Lambda consumer.** Adds ordered retry + DLQ for stuck jobs out of the box. Heavier to wire up (queue construct, IAM policies, batch-size config, DLQ + alarm).
- **Step Functions.** Overkill for a single-step async job.
- **EventBridge scheduled retry.** Useful for periodic regeneration but not for one-off user-triggered work.

**Why async-invoke wins for Janus:**
- One job per user click, no ordering requirement, no batch processing.
- Reserved-concurrency cap (5, already in place) protects against runaway loops.
- Lambda async-invoke includes built-in retry (2 retries by default, configurable) with backoff.
- DLQ can still be attached to the Lambda's async invocation config for failure visibility.
- Mirrors the inline strategy-map pattern we just established — fewer moving parts.

**Trade-off accepted:** SQS would give us ordered FIFO if multiple PDF requests pile up for the same analysis. Async-invoke serialises by the analysis-record write contention (only one render can update ``pdfExport.status`` to ``rendering`` at a time), so the de-dup happens at the data layer instead. Good enough.

### §2 — Cache state lives on the analysis record, not a separate table

The analysis record already carries optional sub-fields (``strategyMap``, ``ebitdaTree``, ``valueChain``, etc.) that are invalidated on re-analyse. ``pdfExport`` is the same pattern.

```python
class PdfExportStatus(str, Enum):
    RENDERING = "rendering"
    READY = "ready"
    FAILED = "failed"


class PdfExportRecord(BaseModel):
    status: PdfExportStatus
    s3_key: str
    started_at: datetime          # for stale-detection on RENDERING
    generated_at: datetime | None  # set when status flips to READY
    error: str | None              # set when status flips to FAILED
```

**Alternatives considered:**

- **Separate ``pdf_export_jobs`` DynamoDB table.** Cleaner separation but adds a new write path, a new GSI for the per-analysis lookup, and a new invalidation point on re-analyse. The sub-field pattern is already established and reuses the existing assessment-repository write helpers.

**Why sub-field wins:**
- Re-analyse invalidation is already a single write to the assessment record — we just clear an additional field.
- Atomicity is free: the same DynamoDB transaction that completes the re-analyse can clear ``pdfExport``.
- Read path is the same as ``strategyMap``: single ``GetItem`` returns the full state.

### §3 — One PDF per analysis, S3 key = ``pdf-exports/<analysisId>.pdf``

Single-object-per-analysis means re-renders overwrite the previous cached PDF. The presigned URL never changes per analysis.

**Alternatives considered:**

- **Content-hash keying (e.g., ``pdf-exports/<analysisId>/<hash>.pdf``).** Robust to "analysis content changed but re-analyse wasn't triggered" edge cases (e.g., partial schema changes). Strictly more complex; introduces an orphan-object cleanup question.
- **Versioning via S3 object versions.** Stores history but doesn't help the UX; users always want the latest.

**Why per-analysis key wins:**
- Re-analyse is the only sanctioned path that should invalidate the cache. There's no "analysis content silently changed" path that bypasses re-analyse today.
- DELETE-on-re-analyse is a single S3 call. Trivial cleanup.
- Presigned URLs can be short-lived (60 s) because each click mints a fresh one.

### §4 — Frontend uses POST + polling, not WebSockets or AppSync

The POST endpoint returns 200 (cached) or 202 (rendering). The status endpoint is polled at 2 s intervals for the typical 15-second render path, backing off to 5 s for stale-rendering edge cases.

**Alternatives considered:**

- **AppSync subscription.** Janus already has AppSync infrastructure (for analysis progress). Could ride the same channel. **Rejected for this change** because:
  - Render path is short (~15 s on the new memory allocation). Poll lag of 2 s is invisible.
  - AppSync wiring adds a new subscription topic, a new event publisher in the Python proxy, and a new client-side handler. Net code churn for ~2 s of perceived improvement.
  - Polling is dead-simple to reason about and test.
- **Server-sent events (SSE).** Same complexity as AppSync without the existing infrastructure benefit.
- **Long-polling.** Indistinguishable from regular polling at our cadence; not worth the added complexity.

**Why polling wins:**
- Simplest possible client + server contract.
- Network cost is trivial (status response is ~200 bytes).
- Backend implementation reuses the existing GET handler pattern.
- If users complain about the 2-second perceived lag later, swap polling for AppSync push without changing the data model.

### §5 — Stale-rendering recovery via ``started_at`` timestamp comparison

If the PDF Lambda crashes mid-render, ``pdfExport.status`` stays at ``rendering`` forever, blocking the user. The status endpoint compares ``started_at`` against current wall clock and treats ``rendering`` older than 60 s as effectively ``failed``:

```python
RENDERING_STALE_AFTER_SECONDS = 60

def is_stale(status: PdfExportStatus, started_at: datetime) -> bool:
    if status != PdfExportStatus.RENDERING:
        return False
    age = (datetime.now(UTC) - started_at).total_seconds()
    return age > RENDERING_STALE_AFTER_SECONDS
```

When the status endpoint detects a stale-rendering record, it returns ``status: "failed"`` to the frontend (so the UI moves out of the polling loop and offers retry) AND a subsequent POST to ``/api/export/pdf/<id>`` is allowed to re-trigger the render.

**Alternatives considered:**

- **Wait for Lambda's own retry mechanism.** Async-invoke has built-in retries (2 by default). If both fail, the message goes to the DLQ. But the user has no visibility into this — they're stuck on a polling spinner indefinitely.
- **Health-check / heartbeat from the PDF Lambda.** Adds complexity for a low-frequency edge case.

**Why timestamp comparison wins:**
- Simple: one timestamp, one threshold, one comparison.
- Self-correcting: even if the watchdog logic isn't perfect, the user's next click resolves the situation.
- Generous threshold (60 s): typical render is 15 s; a 60 s threshold tolerates the 2-retry Lambda case (each retry: ~15 s + back-off) before declaring stale.

### §6 — Existing GET ``/api/export/pdf/<analysisId>`` route stays during rollout

The frontend's ``ExportPDFButton`` is a high-traffic surface. Migrating it to POST + poll in one shot risks a regression on a feature users may already be using. **Deploy in two phases:**

1. **Phase A**: Ship the new POST + status endpoints + S3 bucket + async-invoke. Existing GET route keeps working (synchronous, calls PDF Lambda the old way via the Python proxy with ``RequestResponse``).
2. **Phase B**: Migrate ``ExportPDFButton`` to POST + poll. New users hit the cached path. Synchronous GET keeps working as a fallback for any external integrations we missed.
3. **Phase C (cleanup, later PR)**: Delete the synchronous GET route + remove the ``RequestResponse`` codepath from the Python proxy. Only POST + async-invoke remains.

This trades a small temporary code duplication for a safe rollback story: if Phase B regresses, frontend reverts to GET without backend rollback.

**Alternative considered:** big-bang migration. Rejected — too much surface area to verify in one PR; rollback would require a coupled frontend + backend revert.

### §7 — Re-analyse invalidation extends the existing pattern

The re-analyse handler already clears ``strategyMap`` from the analysis record (per the ``redesign-strategy-map`` Phase 3 change archived 2026-05-15). Extending it:

```python
def handle_reanalyse(...):
    # Existing: clear strategyMap
    accessor.clear_strategy_map()
    # NEW: clear pdfExport + delete S3 object
    pdf_export = accessor.get_pdf_export()
    if pdf_export and pdf_export.s3_key:
        s3_client().delete_object(Bucket=PDF_EXPORTS_BUCKET, Key=pdf_export.s3_key)
    accessor.clear_pdf_export()
    # Existing: kick off the pipeline
    ...
```

The S3 delete is best-effort: if it fails, the next render will overwrite the orphan object anyway. We log but don't fail the re-analyse.

**No alternative seriously considered** — extending the existing pattern is obviously right.

## Risks / Trade-offs

### Risk: Async-invoke failure modes are less observable than synchronous

The frontend used to see HTTP 5xx from the synchronous chain when the render failed. With async-invoke, the failure happens off the request path — frontend just sees ``status: "rendering"`` for longer than expected.

**Mitigation:**
- ``started_at`` + 60 s stale check converts indefinite-rendering into surfaced ``failed`` state.
- DLQ on PDF Lambda + CloudWatch alarm catches systematic failures the user might not retry through.
- The PDF Lambda updates the assessment record's ``pdfExport.status = "failed"`` + ``error`` field on any handled exception, so the frontend gets a real error to display.

### Risk: Concurrent re-analyse + render race

User clicks Export → render starts → user clicks Re-analyse before render finishes. Two scenarios:

1. **Re-analyse wins the race**: it deletes the S3 object and clears ``pdfExport``. The PDF Lambda finishes its render and writes to the now-deleted S3 key, then writes ``pdfExport.status = "ready"`` against the stale analysis state. User sees a "ready" PDF that doesn't match the post-re-analyse content.
2. **PDF Lambda wins**: render completes, writes to S3 + record. Re-analyse fires, deletes S3 object + clears ``pdfExport``. Clean state.

**Mitigation:** the PDF Lambda's final DynamoDB write includes a condition expression: ``attribute_exists(pdfExport)`` AND ``pdfExport.started_at == <the timestamp we owned>``. If re-analyse cleared the field in between, the conditional update fails and the Lambda discards the rendered PDF (it's stale by definition). The S3 object orphaned by this race is cleaned up the next time a render writes the same key.

### Risk: Stale 60-second threshold may be too aggressive for slow renders

If a single analysis somehow takes >60 s to render (e.g., 20+ pages on a future analysis shape), the stale check would incorrectly flag it as failed.

**Mitigation:** the 60 s threshold is well above the 13-15 s typical render time and the 30 s Lambda timeout. Lambda would have terminated itself before 60 s. The threshold is safe relative to the Lambda timeout floor. If render times approach 30 s on real data, we re-tune.

### Risk: Frontend polling adds load proportional to concurrent renders

If 50 users export PDFs concurrently, each polling every 2 s, that's 25 RPS on the status endpoint for ~15 s. ~375 requests total. Not a real concern (the endpoint is a single DynamoDB read), but worth noting.

**Mitigation:** none needed. DynamoDB single-item reads scale trivially; the status endpoint can serve 1000s of RPS.

### Trade-off: Two endpoints (POST + GET status) instead of one

We could combine them: every POST returns the current status (cached → 200 with URL, rendering → 202 with current state, also reset to 200/url when complete). The frontend would re-POST to "poll".

**Why we kept them separate:**
- POST has side-effects (may enqueue a render). Re-POSTing every 2 s feels wrong even if the side-effect is idempotent.
- GET is cacheable, even if we don't cache it today. POST is not.
- Separation is the conventional REST idiom; readers don't have to reason about side-effect-on-poll semantics.

### Trade-off: Frontend code paths get more complex

Today: click button → spinner → file. After: click → POST → branch on cached-vs-not → maybe poll → maybe download → handle stale → handle failed → retry. ~3-4× the state surface.

**Acceptable** because the cached-vs-cold split is genuinely two different UX flows; trying to flatten them would just hide the complexity. ``ExportPDFButton`` test coverage absorbs the new branches.

## Migration Plan

### Phase 1 — Backend skeleton (Janus PR, ~2 days)

1. Add ``PdfExportRecord`` Pydantic model + ``pdfExport: PdfExportRecord | None`` field on the assessment.
2. Add S3 bucket + IAM grants in ``pdf_render_construct.py``.
3. Add module to mint presigned URLs (``backend/src/handlers/pdf_render_handlers.py`` — same file or a new ``pdf_export_handlers.py``).
4. New routes:
   - ``POST /api/export/pdf/<analysisId>`` — enqueues render if needed, returns cache status.
   - ``GET /api/export/pdf/<analysisId>/status`` — returns the ``pdfExport`` sub-record (with stale-rendering detection).
5. Extend re-analyse handler to clear ``pdfExport`` + ``DELETE`` S3 object.
6. Backend unit tests for the new handlers, mocking S3 + Lambda + DynamoDB.

### Phase 2 — PDF Lambda owns the S3 write (Janus PR, ~1 day)

1. Update ``backend/lambdas/pdf-render/src/handler.ts`` to:
   - Render PDF as today.
   - PUT to S3 ``pdf-exports/<analysisId>.pdf``.
   - Conditionally update DynamoDB: ``pdfExport.status = "ready"``, ``s3_key``, ``generated_at`` (with ``started_at`` match guard).
   - On failure: set ``pdfExport.status = "failed"`` + ``error`` field.
2. Switch the Python proxy's invocation to ``InvocationType="Event"`` when called via the new POST route.
3. Keep the synchronous ``RequestResponse`` path alive for the existing GET route (Phase A of decision §6).
4. Lambda DLQ + CloudWatch alarm on async-invoke failures.

### Phase 3 — Frontend migration (Janus PR, ~2 days)

1. ``ExportPDFButton`` becomes status-aware:
   - POST on click.
   - Branch on response: 200-with-url → direct download; 202 → enter polling state.
   - Polling: 2 s × 10, then 5 s × indefinite (until ``ready`` or ``failed``).
   - Toast for "Generating PDF…" during render.
   - Auto-trigger download once status flips to ``ready``.
2. Update the ``api/export/pdf/[analysisId]/route.ts`` Next.js handler to delegate to the new POST endpoint.
3. Tests covering: cached, cold path, concurrent click, stale detection, failed-state retry.

### Phase 4 — Cleanup (smaller follow-up PR, ~half day)

1. Remove the synchronous GET ``/api/export/pdf/<analysisId>`` codepath from the backend.
2. Remove the ``RequestResponse`` boto3 invocation from the Python proxy.
3. Delete dead frontend code paths.
4. Archive the OpenSpec change once Phase 4 lands.

### Soak gates

- **Dev → testing**: at least 24 hours of operation post-Phase 3 with no user-visible 504s, no stuck-rendering reports.
- **Testing → production**: same. Verify with a fresh production analysis that POST + poll works end-to-end.
- **Cleanup (Phase 4)**: only after production has been stable for ~7 days on the new path.

## Open Questions

- **Should the POST endpoint be idempotent within a render window?** Today: clicking Export twice in 5 s would enqueue two renders. With the proposed status check, the second click sees ``rendering`` and skips. **Resolved**: the data-model status check provides idempotency for free. No explicit idempotency-token needed.
- **What's the right Lambda async retry policy?** Default is 2 retries with exponential back-off. **Resolved**: keep the default. Two retries + the user's "click again to retry" path = 3 effective attempts before the user has to escalate.
- **Should the S3 bucket allow public-read on the cached objects (avoiding presigned URLs)?** No. Presigned URLs scoped to the user's session keep the auth posture intact; public-read would let anyone with the URL download. Compliance + security both push us toward presigned.
- **Do we surface render progress to the user (e.g., "page 3 of 8")?** Tempting but adds a meaningful Lambda-side reporting hook for a small UX gain. **Resolved**: no — keep the surface to ``rendering`` / ``ready`` / ``failed`` for v1. Add granular progress only if users ask.
- **Should we cap the per-org concurrent PDF renders?** Today: 5 reserved-concurrency on the Lambda. **Resolved**: keep the existing cap; add per-org throttling only if a single org gets abusive (none today).

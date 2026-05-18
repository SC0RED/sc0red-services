# Async PDF Export with Per-Analysis Caching + Re-Analyse Invalidation

## Why

PDF export is currently a synchronous request chain that bumps right against API Gateway's 29-second hard timeout ceiling:

```
[Browser] → [Amplify SSR] → [Backend APIGW] → [Python proxy] → [PDF Lambda]
                                  ▲                                  │
                            29s ceiling                          26-28s render
```

On 2026-05-18, a production export returned 504 to the browser while the Lambda log confirmed the PDF rendered successfully. The bytes were generated; they couldn't be delivered through the synchronous chain in time.

PR #321 shipped a band-aid (Lambda memory 1024 MB → 2048 MB, roughly halving render time). That buys headroom but doesn't fix the structural problem: **any request that takes longer than 29s through API Gateway will fail, and PDF rendering inherently scales with analysis size.** As analyses grow (more opportunities, longer descriptions, larger EBITDA trees), we'll hit the ceiling again.

There are also two UX problems the synchronous path creates today:

1. **Every click re-renders.** Click Export → 26s render → download. Click Export again on the same analysis → another 26s render. Wasted Lambda time, wasted user wait.
2. **Blocking spinner.** Users stare at a loading state for 26+ seconds. PE diligence users in particular may want to keep navigating the page while their deliverable generates.

This change moves PDF rendering off the synchronous request path entirely. The pattern mirrors what we already do for the analysis pipeline (SQS + worker + AppSync push) and what the just-archived ``redesign-strategy-map`` change established: blocking work behind an async job, cached result invalidated on re-analyse.

## What Changes

### A. Backend — render pipeline becomes async

- **New POST endpoint** ``/api/export/pdf/<analysisId>``: enqueues a render if no fresh PDF exists, returns ``{status, jobId}`` (200 with URL if cached, 202 with job state if rendering).
- **New GET endpoint** ``/api/export/pdf/<analysisId>/status``: returns the current ``pdfExport`` sub-record on the analysis. Polled by the frontend at ~2 s intervals.
- **PDF render Lambda invocation switches from synchronous to async**. The Python proxy ``boto3.invoke`` with ``InvocationType="Event"`` rather than ``RequestResponse``. The PDF Lambda's responsibility shifts from "return PDF bytes" to "upload PDF to S3 + update the analysis record".

### B. Data model — analysis record gains a ``pdfExport`` sub-field

```
analysis = {
  ...existing fields,
  pdfExport: {
    status: "rendering" | "ready" | "failed",
    s3Key: "pdf-exports/<analysisId>.pdf",
    generatedAt: <ISO-timestamp>,           // ready state
    startedAt:   <ISO-timestamp>,           // rendering state — stale-check anchor
    error:       <string>,                  // failed state
  } | undefined,
}
```

Mirrors the existing ``strategyMap`` sub-record pattern: cached state lives on the analysis, naturally invalidated when the analysis is.

### C. Storage — PDF bytes live in S3, not in the response stream

- **New S3 bucket** ``janus-<env>-pdf-exports`` with bucket-owner-enforced encryption, no public access, server-side encryption (SSE-S3).
- Object key: ``pdf-exports/<analysisId>.pdf``. One object per analysis; re-render overwrites.
- IAM: PDF Lambda has ``s3:PutObject``; Python API Lambda has ``s3:GetObject`` (to mint presigned URLs).
- **No lifecycle policy initially** — storage cost is rounding error (~1 MB × 1000 analyses = 1 GB ≈ $0.02/month). Revisit if cost ever matters.

### D. Frontend — ExportPDFButton becomes status-aware

- Click triggers POST to ``/api/export/pdf/<analysisId>`` (not GET).
- **Cached path**: response 200 with ``url`` → button immediately redirects to presigned URL → browser downloads (sub-second perceived).
- **Cold path**: response 202 → button enters "Generating PDF (~15 s)…" state → polls ``/status`` at 2-3 s intervals → when status flips to ``ready``, auto-downloads.
- **Concurrent clicks**: second click on the same analysis during render sees ``status: "rendering"`` and joins the same poll cycle — no duplicate render.
- **Navigation during render**: if the user leaves the page, the render continues. On return, clicking Export sees ``status: "ready"`` and downloads instantly.

### E. Re-analyse invalidation

- The re-analyse handler already clears ``strategyMap`` (per the ``redesign-strategy-map`` Phase 3 change). Extend the same logic to clear ``pdfExport`` and ``DELETE`` the S3 object.
- After re-analyse, the next click on Export PDF will trigger a fresh render against the updated analysis.

### F. Stale-job recovery

If the PDF Lambda crashes mid-render, ``status: "rendering"`` would otherwise stay forever, blocking the user. The status endpoint compares ``startedAt`` against the current time and treats ``rendering`` older than 60 s as stale, allowing a re-trigger on the next click.

## Impact

**Affected specs:**
- ``polished-pdf-export`` (existing capability — adds new requirements for async rendering, cache lookup, re-analyse invalidation, stale-job recovery; modifies the existing "ExportPDFButton" + "Export PDF returns a binary PDF" requirements).

**Affected code:**

| Repo | Files |
|---|---|
| Backend | ``handlers/pdf_render_handlers.py`` (proxy becomes async-invoke); new ``handlers/pdf_export_handlers.py`` for status endpoint; ``repositories/dynamodb/assessment_repository.py`` (read/write ``pdfExport`` sub-field); re-analyse handler (extend invalidation); new module to mint presigned S3 URLs |
| PDF Lambda | ``backend/lambdas/pdf-render/src/handler.ts`` — writes to S3 + updates assessment record instead of returning bytes via response |
| Infrastructure | ``stacks/pdf_render_construct.py`` (S3 bucket + IAM); ``stacks/janus_stack.py`` (route registration); env vars (``PDF_EXPORTS_BUCKET``) |
| Frontend | ``components/ExportPDFButton.tsx`` (status-aware); ``app/api/export/pdf/[analysisId]/route.ts`` (becomes a thin proxy to the new status endpoint); types in ``lib/types/api.ts`` |
| Models | ``models/model_company.py`` — ``Analysis`` gains optional ``pdfExport`` field |

**Affected workloads:**

- **Per-click wall clock**: synchronous render (26-28 s) → first click ~15 s, subsequent clicks <1 s (cached). Re-clicks on the same analysis are the dominant case once analyses settle.
- **Lambda spend**: roughly halved — cached clicks don't trigger renders. Across a 100-analyses-per-day workload with ~3 clicks per analysis, that's ~67% of clicks served from cache.
- **API Gateway 504s**: eliminated. The synchronous chain stops being the gating constraint.
- **User-facing UX**: blocking 26-s spinner replaced with either an instant download (cached) or a non-blocking "generating…" toast (cold). User can navigate freely during render.

**Migration story:** the existing ``GET /api/export/pdf/<analysisId>`` route keeps a small synchronous compatibility path during rollout (POST is the new primary). Once the frontend is fully on the POST + poll flow, the synchronous GET is removed. Tracked as a Phase 4 cleanup task.

## Non-Goals

- **Re-rendering on demand without re-analyse.** "Force regenerate" UI is out of scope. If the cached PDF is wrong but the analysis is correct, the workaround is re-analyse. We can add an explicit invalidate button later if users ask for it.
- **PDF preview before download.** Inline preview (open in browser tab) is a separate feature. This change preserves the existing "click → download to disk" pattern.
- **Backfilling PDFs for existing analyses.** New clicks render the new way; existing analyses without a cached PDF just trigger a render on next click.
- **AppSync push for PDF status.** Polling is fast enough (2-3 s lag) for a workload that runs in ~15 s. AppSync push can be a follow-up if the polling lag becomes a complaint.
- **Per-page-range PDFs / partial PDFs.** Always full analysis.
- **S3 lifecycle policy.** Storage cost is rounding error; no automatic expiry today.
- **Multi-region / cross-AZ resilience.** Same single-region story as today.

## Open Questions

- **Should the POST endpoint accept overrides (e.g., page format, opportunity filter)?** Current synchronous path takes the analysis as-is. Adding overrides would complicate caching (cache key becomes analysisId + override-fingerprint). **Resolved**: no overrides at the POST endpoint — keep it analysisId-only. If users need per-export customisation, that's a separate feature on top of the async machinery.
- **Frontend polling cadence: 2 s, 3 s, or exponential back-off?** 2 s is responsive but chatty. **Resolved**: 2 s for the first 10 polls (covers the typical ~15 s render), then back off to 5 s for stale-rendering cases.
- **Should the status endpoint cost a Cognito JWT round-trip per poll?** Yes — same auth boundary as every other backend endpoint. The cost is minimal (~1 ms validation) and avoids weakening the auth posture.
- **What happens if the PDF Lambda async-invoke fails before the Lambda runs (e.g., reserved-concurrency throttle)?** ``boto3.invoke(InvocationType="Event")`` returns ``StatusCode: 202`` immediately — invocation failures are visible only in CloudWatch Lambda failure metrics + DLQ. **Resolved**: add a DLQ on the PDF Lambda + a CloudWatch alarm that triggers re-marking ``failed`` status on the assessment record. Frontend then re-renders on next click. Failure recovery is asynchronous.

# Async PDF Export with Cache — Tasks

> Four-phase rollout per design.md migration plan. Phases 1+2 (backend skeleton + PDF Lambda) ship together; Phase 3 (frontend migration) ships after a dev/testing soak; Phase 4 (cleanup) lands after production stability.

## 1. Phase 1 — Backend skeleton (new endpoints + S3 bucket + data model)

### 1.1 Data model

- [ ] 1.1.1 In ``backend/src/models/model_company.py``, add a ``PdfExportStatus`` ``str, Enum`` with values ``RENDERING``, ``READY``, ``FAILED``.
- [ ] 1.1.2 Add a ``PdfExportRecord(BaseModel)`` with fields: ``status: PdfExportStatus``, ``s3_key: str``, ``started_at: datetime``, ``generated_at: datetime | None``, ``error: str | None``.
- [ ] 1.1.3 Add an optional ``pdf_export: PdfExportRecord | None`` field on the ``Analysis`` model (the assessment record).
- [ ] 1.1.4 ``CompanyAccessor`` helpers: ``set_pdf_export(...)``, ``get_pdf_export()``, ``clear_pdf_export()``. Mirror the existing ``set_strategy_map`` / ``clear_strategy_map`` shape.

### 1.2 S3 bucket + IAM

- [ ] 1.2.1 In ``infrastructure/stacks/pdf_render_construct.py``, define an S3 bucket ``janus-<env>-pdf-exports`` with SSE-S3, block-all-public-access, bucket-owner-enforced object ownership, no lifecycle policy.
- [ ] 1.2.2 Grant the PDF Lambda ``s3:PutObject`` on the bucket. Pass the bucket name as the env var ``PDF_EXPORTS_BUCKET``.
- [ ] 1.2.3 Grant the API Lambda ``s3:GetObject`` on the bucket. Pass the bucket name to the API Lambda as ``PDF_EXPORTS_BUCKET``.
- [ ] 1.2.4 ``cdk synth`` cleanly under each environment config (dev / testing / production).

### 1.3 New backend handlers

- [ ] 1.3.1 New file ``backend/src/handlers/pdf_export_handlers.py``. Wire two routes:
  - ``POST /api/export/pdf/<analysisId>`` → ``handle_post_export(...)``
  - ``GET  /api/export/pdf/<analysisId>/status`` → ``handle_get_export_status(...)``
- [ ] 1.3.2 ``handle_post_export``:
  - Auth + analysis-visibility check (existing assessment-read pattern).
  - Read ``analysis.pdf_export``.
  - If ``status == READY``: mint a 60-second presigned S3 URL via ``s3:GetObject``, return ``200 {status, url, generated_at}``.
  - If ``status == RENDERING`` AND not stale: return ``202 {status, started_at}`` (idempotent dedup).
  - Otherwise (absent / FAILED / stale RENDERING): write ``pdf_export = {status: RENDERING, started_at: now, s3_key: "pdf-exports/<id>.pdf"}`` to the assessment record. Async-invoke the PDF Lambda with ``InvocationType="Event"``. Return ``202``.
- [ ] 1.3.3 ``handle_get_export_status``:
  - Auth + visibility check.
  - Read ``analysis.pdf_export``. If absent, return ``200 {status: "none"}``.
  - Apply the stale-check: ``RENDERING`` with ``started_at`` older than 60 s → respond as ``failed`` (with synthetic ``error`` field). Do NOT mutate the persisted record.
  - If ``READY``: mint a presigned URL + return.
  - Else: return ``status`` as stored.
- [ ] 1.3.4 Stale-detection constant ``RENDERING_STALE_AFTER_SECONDS = 60`` lives next to the handler module.
- [ ] 1.3.5 New module ``backend/src/handlers/pdf_presigned_url.py`` (or co-located helper): ``mint_pdf_url(s3_key, expires_seconds=60) -> str``. Uses module-level boto3 S3 client (cache across Lambda warm-restart).

### 1.4 Re-analyse invalidation

- [ ] 1.4.1 In the re-analyse handler (locate via ``grep -rn "clear_strategy_map" backend/src``), extend the existing clear-pre-pipeline-state logic:
  - Read ``analysis.pdf_export``.
  - If present + ``s3_key`` set, attempt ``S3.delete_object`` (best-effort; log but don't fail on error).
  - Call ``accessor.clear_pdf_export()``.
- [ ] 1.4.2 Tests for the re-analyse handler's new invalidation logic (mock S3 delete + assert DynamoDB clear).

### 1.5 Backend tests (Phase 1)

- [ ] 1.5.1 ``test_pdf_export_handlers.py`` (new file). Cases:
  - First click (no ``pdf_export``) → 202, async-invoke called once, record written.
  - Cached path (``pdf_export.status = "ready"``) → 200 with presigned URL, no async-invoke.
  - In-flight (``status = "rendering"``, not stale) → 202 with existing ``started_at``, no second async-invoke.
  - Stale rendering (>60 s old) → handle_post enqueues a fresh render.
  - Status endpoint stale detection → returns ``failed`` without mutating.
  - Failed state ``status = "failed"`` → POST enqueues fresh render.
- [ ] 1.5.2 ``test_reanalyse_handler.py`` extension (or existing test file): verify S3 delete + ``pdf_export`` clear happen on re-analyse, S3 failure doesn't fail re-analyse.
- [ ] 1.5.3 Full suite: ``uv run pytest tests/ -q`` green, coverage ≥ 95%.

## 2. Phase 2 — PDF Lambda owns the S3 write

### 2.1 Lambda handler refactor

- [ ] 2.1.1 In ``backend/lambdas/pdf-render/src/handler.ts``, change the contract from "return base64 PDF" to "PUT to S3 + UpdateItem assessment record". Inputs from the event payload: ``analysisId``, ``token``, ``frontendBaseUrl``, ``companyName``, plus the new ``startedAt`` timestamp (passed by the Python proxy so the conditional UpdateItem matches).
- [ ] 2.1.2 After rendering the PDF:
  - ``PutObject`` to ``PDF_EXPORTS_BUCKET`` at key ``pdf-exports/<analysisId>.pdf``. Use SSE-S3 (bucket policy enforces).
  - Conditional ``UpdateItem`` on the assessment record: set ``pdf_export.status = "ready"``, ``pdf_export.s3_key``, ``pdf_export.generated_at = now``. Condition expression: ``pdf_export.status = "rendering" AND pdf_export.started_at = <input startedAt>``.
  - If the conditional fails: log + exit cleanly. The orphan S3 object is harmless (next render overwrites).
- [ ] 2.1.3 On any thrown exception:
  - Best-effort UpdateItem to set ``pdf_export.status = "failed"``, ``pdf_export.error = <message truncated to 500 chars>``. Same conditional ``started_at`` guard.
  - Re-throw so Lambda's async-invoke retry kicks in.

### 2.2 Lambda IAM + DLQ

- [ ] 2.2.1 In ``pdf_render_construct.py``, grant the PDF Lambda:
  - ``s3:PutObject`` on the bucket (Phase 1.2.2).
  - ``dynamodb:UpdateItem`` on the assessment table.
- [ ] 2.2.2 Add an SQS DLQ for the PDF Lambda's async-invoke failures. Lambda async config: ``maxEventAge`` reasonable (e.g., 5 min — beyond this, the user has clicked again anyway), ``onFailure`` → DLQ.
- [ ] 2.2.3 CloudWatch alarm on DLQ ``ApproximateNumberOfMessagesVisible > 0``.

### 2.3 Python proxy switch

- [ ] 2.3.1 ``backend/src/handlers/pdf_render_handlers.py`` (or new handler): the new async-invoke path passes ``InvocationType="Event"``. The synchronous GET path (existing) keeps ``RequestResponse`` for Phase A backward compat.
- [ ] 2.3.2 Add ``started_at`` to the async payload so the Lambda can match it in the conditional UpdateItem.

### 2.4 Lambda tests (Phase 2)

- [ ] 2.4.1 ``backend/lambdas/pdf-render/tests/handler.test.ts``:
  - Success path: render → PutObject called once with correct key + bucket → UpdateItem called with condition expression.
  - Stale-write path: UpdateItem fails (conditional check) → handler logs + exits cleanly, no retry.
  - Render failure: UpdateItem called with ``status: "failed"`` + error message, then re-throws.
- [ ] 2.4.2 Integration test that exercises the full path with localstack or moto (S3 + DynamoDB).

### 2.5 Ship Phase 1 + 2 together

- [ ] 2.5.1 Combined PR: backend skeleton (Phase 1) + Lambda async owner (Phase 2). They're tightly coupled (the new POST endpoint needs the Lambda to write the result back).
- [ ] 2.5.2 Architecture-reviewer pass on the diff.
- [ ] 2.5.3 Ship through dev → testing → production. **The synchronous GET path is still active**, so frontend behaviour is unchanged at this stage.
- [ ] 2.5.4 Smoke test on dev: hit the new POST endpoint directly (curl), verify the async-invoke fires, S3 object appears, assessment record updates.

## 3. Phase 3 — Frontend migration

### 3.1 ExportPDFButton becomes status-aware

- [ ] 3.1.1 In ``frontend/src/components/ExportPDFButton.tsx``:
  - On click: POST to ``/api/export/pdf/<analysisId>`` (not GET).
  - If response is 200 with ``url``: ``window.location = url`` (browser handles the download via S3's ``Content-Disposition``).
  - If response is 202: enter polling state. Label becomes "Generating PDF…". Button disabled.
- [ ] 3.1.2 Polling cycle:
  - Interval: 2 s for first 10 polls (~20 s of typical render window), then 5 s indefinitely until ``ready`` or ``failed``.
  - On ``ready``: read ``url`` from the status response, ``window.location = url``, button returns to idle.
  - On ``failed``: show error Toast with ``error`` text, button returns to idle.
- [ ] 3.1.3 The "Generating PDF…" Toast is dismissible. If the user dismisses + navigates away, the render continues. Returning to the page + clicking Export sees the cached state.

### 3.2 Next.js route updates

- [ ] 3.2.1 ``frontend/src/app/api/export/pdf/[analysisId]/route.ts``: change ``GET`` handler → ``POST`` handler. Forward to the new backend ``POST /api/export/pdf/<id>`` endpoint. Return the backend's response verbatim.
- [ ] 3.2.2 Add a sibling ``frontend/src/app/api/export/pdf/[analysisId]/status/route.ts``: ``GET`` forwarded to backend ``GET /api/export/pdf/<id>/status``.
- [ ] 3.2.3 Authentication / cookie forwarding: reuse ``backendFetch`` so the Cognito JWT is attached.

### 3.3 Frontend tests

- [ ] 3.3.1 ``ExportPDFButton.test.tsx``: cover the four UX flows:
  - Cached: click → POST returns 200 + url → window.location set.
  - Cold: click → POST returns 202 → polling starts → eventually ready → window.location set.
  - Failed (from poll): polling sees ``failed`` → Toast shown → button idle.
  - Stale: polling sees synthetic ``failed`` (60 s+ rendering) → same as failed flow.
- [ ] 3.3.2 Mock ``fetch`` for the polling cycle; assert poll cadence matches 2 s × 10 then 5 s back-off.

### 3.4 Ship Phase 3

- [ ] 3.4.1 Architecture-reviewer pass.
- [ ] 3.4.2 PR + dev deploy. Verify the new flow works end-to-end on dev with a real analysis.
- [ ] 3.4.3 Dev soak: ~24 hours, no user-visible regressions.
- [ ] 3.4.4 Promote dev → testing. Soak ~24 hours.
- [ ] 3.4.5 Promote testing → production.

## 4. Phase 4 — Cleanup

### 4.1 Remove the synchronous path

- [x] 4.1.1 ``backend/src/handlers/pdf_render_handlers.py``: deleted (the module is gone; the async POST is the only PDF entry point now).
- [x] 4.1.2 ``backend/src/handlers/api_gateway_handler.py``: removed the legacy ``register_pdf_render_routes`` import + wiring.
- [x] 4.1.3 Frontend ``[analysisId]/route.ts``: removed the legacy GET handler + the ``signToken`` / ``readSigningSecret`` / ``readFrontendBaseUrl`` / ``invokeRenderLambda`` / ``resolveOrgId`` helpers; only the async POST handler remains.
- [x] 4.1.4 Deleted ``backend/tests/unit/handlers/test_pdf_render_handlers.py`` + the legacy GET tests from ``frontend/src/tests/api/export/pdf/route.test.ts``.
- [x] 4.1.5 ``signToken`` removed from both ``backend/lambdas/pdf-render/src/token.ts`` and ``frontend/src/lib/pdf/token.ts`` (production now signs in Python only). Test-only ``signTokenForTest`` helper kept in each test directory to mint tokens for the verify-side tests.

### 4.2 Ship Phase 4

- [ ] 4.2.1 PR + dev deploy. CI green.
- [ ] 4.2.2 Promote dev → testing → production.
- [ ] 4.2.3 Final sanity: a fresh production analysis still exports correctly.

## 5. Post-prod soak

### 5.1 Telemetry

- [ ] 5.1.1 Check Lambda invocation counts: cached-path POSTs should NOT trigger PDF Lambda invocations. CloudWatch ``Invocations`` metric drops materially for the PDF Lambda.
- [ ] 5.1.2 Check S3 ``BucketSizeBytes`` growing slowly as new analyses cache.
- [ ] 5.1.3 No DLQ messages on the PDF Lambda async-invoke for ~7 days.
- [ ] 5.1.4 No HTTP 504s on the export endpoint for ~7 days.

### 5.2 Quality monitoring

- [ ] 5.2.1 Spot-check 5 production PDFs (cached + cold paths). Same quality bar as pre-migration.
- [ ] 5.2.2 No user reports of "PDF download started something different" (e.g., wrong analysis).

## 6. Wrap-up

- [ ] 6.1 Sync delta spec into ``openspec/specs/polished-pdf-export/spec.md``.
- [ ] 6.2 Archive this change.

## Out-of-scope (deferred / non-goals)

- AppSync push for PDF status (polling is good enough; revisit if user reports lag).
- "Force regenerate" UI without re-analyse (workaround: re-analyse).
- Inline PDF preview / open-in-tab.
- Backfilling cached PDFs for existing analyses (cold-render on next click is fine).
- Per-page-range exports.
- S3 lifecycle policy (revisit if storage cost ever matters).
- Per-org concurrent-render throttling beyond the existing reserved-concurrency cap.

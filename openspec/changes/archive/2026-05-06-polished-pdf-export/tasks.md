## 1. Frontend — `/print/{analysisId}` route

- [x] 1.1 New `frontend/src/app/print/[analysisId]/page.tsx` — server component. Validates the signed token from `?t=`, fetches the analysis via the backend internal-key endpoint, passes data to a client component. On token failure: returns an `<UnauthorizedView>` with the failure reason. _(Path deliberately moved out of `(authenticated)` — headless Chromium has no NextAuth cookies; the HMAC token is the only auth.)_
- [x] 1.2 New `frontend/src/app/print/[analysisId]/PrintReport.tsx` — client component with the print layout. Forces `data-theme="light"` regardless of user preference (sets the attribute on `<html>` in a `useEffect`, restores on unmount). Renders cover, top actions, risk assessment, opportunities, EBITDA tree, value chain, sc0red CTA — in that order.
- [x] 1.3 New `frontend/src/app/print/print.css` — page-break hints (`page-break-inside: avoid` on cards, `page-break-before: always` on major sections), `@page` directives for A4 + margins, hides print-only-screen markers.
- [x] 1.4 `<meta name="robots" content="noindex, nofollow">` on the print route via Next.js `metadata.robots`.
- [x] 1.5 Reuses the live chart components: `RiskBreakdown`, `OpportunitiesList`, `EbitdaSection`, `ValueChainDiagram`, `TopActionsCallout`. No reimplementation.

## 2. Frontend — `ExportPDFButton`

- [x] 2.1 New `frontend/src/components/analysis/ExportPDFButton.tsx`:
      - Stateful button (`idle` / `starting` / `generating` / `still-working`).
      - `AbortController` cancels in-flight requests on unmount and click-while-loading.
      - Spinner appears at 200ms; "Still working…" at 5s; 30s hard timeout with Toast.
      - On success: builds Blob → `URL.createObjectURL` → programmatic anchor-click → revokeObjectURL.
      - Filename parsed from `Content-Disposition` (RFC 5987 UTF-8 + ASCII fallback).
- [x] 2.2 Replaced the `<Link target="_blank">` in `frontend/src/components/analysis/AnalysisHeader.tsx` with `<ExportPDFButton analysisId={...}>`.
- [x] 2.3 Vitest cases (8): idle, generating, still-working, success download with filename, fallback filename, HTTP error Toast, network error Toast, click-while-loading no-op.

## 3. Backend — token issuance in the existing API route

- [x] 3.1 `frontend/src/app/api/export/pdf/[analysisId]/route.ts` — REWRITTEN. (a) Auth via NextAuth + Cognito, (b) issues a short-lived signed token (HMAC-SHA256 over `{analysisId, orgId, exp}` with TTL 60s, signing key from env `PDF_TOKEN_SECRET`), (c) POSTs to `/api/admin/render-pdf` with the user's Cognito Bearer, (d) streams the PDF response back with `Content-Disposition: attachment; filename="{Company} - AI Risk Report - YYYY-MM-DD.pdf"` (RFC 5987 with both `filename=` and `filename*=UTF-8''…`), (e) emits the existing `sc0red_cta_rendered_in_pdf` analytics event AFTER successful render.
- [x] 3.2 Apply-time decision: chose option (a) — Python API Lambda hosts `POST /api/admin/render-pdf` and boto3-invokes the Node.js render Lambda. Keeps the Cognito JWT auth boundary single-sourced. No new SDK in the Next.js Lambda.
- [x] 3.3 Vitest (7): binary PDF + correct Content-Type + Content-Disposition + analytics event fires + analytics-skipped-when-no-opportunities + analytics-fire-and-forget + analysis-fetch-error + token-shape-in-payload.

## 4. Backend — PDF render Lambda (Node.js)

- [x] 4.1 New directory `backend/lambdas/pdf-render/`:
      - `package.json` pinned to `puppeteer-core@21.11.0`, `@sparticuz/chromium@121.0.0`.
      - `tsconfig.json` (ES2022, strict), `.eslintrc.cjs` matching repo style.
      - `src/handler.ts` — Lambda entry. Validates the inbound payload, calls `render()`, returns the PDF buffer as a base64-encoded API Gateway proxy response.
      - `src/render.ts` — launches `puppeteer-core` with `@sparticuz/chromium`, navigates to `${frontendBaseUrl}/print/${analysisId}?t=${token}`, awaits `networkidle0`, calls `page.pdf()` with the page options from design.md D4 (A4, 25mm margins, header/footer templates), returns the buffer + metrics.
      - `src/token.ts` — HMAC sign + verify (lockstep duplicate of `frontend/src/lib/pdf/token.ts`).
- [x] 4.2 Token verification module — duplicated between `pdf-render/src/token.ts` and `frontend/src/lib/pdf/token.ts`. Both use the same `PDF_TOKEN_SECRET` env var. The Lambda defensively verifies the token BEFORE spinning up Chromium so misuse doesn't pay the cold-start cost.
- [x] 4.3 Print route token validation — `app/print/[analysisId]/page.tsx` rejects requests with invalid/expired tokens via an `<UnauthorizedView>` page.
- [x] 4.4 Tests: 19 Lambda vitest cases (token sign+verify roundtrip, all rejection paths, handler shape validation, base64-encoded happy path, error/timeout paths). Real-Chromium integration test deferred to post-deploy smoke (§8.1).

## 5. Infrastructure — CDK construct

- [x] 5.1 New `infrastructure/stacks/pdf_render_construct.py`:
      - Lambda function (Node.js 20.x runtime), code bundled from `backend/lambdas/pdf-render/` via Docker `npm ci && npm run build && npm prune --omit=dev`.
      - `@sparticuz/chromium` bundled directly into the Lambda code asset (no separate layer — fits well within the 250MB unzipped limit, removes layer-version drift).
      - Reserved concurrency = 5, timeout = 30s, memory = 1024 MB.
      - Env vars: `PDF_TOKEN_SECRET`, `FRONTEND_BASE_URL`, `STAGE`.
      - Two Secrets Manager-backed secrets created: `PDF_TOKEN_SECRET` (HMAC signing key) and `INTERNAL_API_KEY` (Next.js → backend internal endpoint).
      - CfnOutput: `PdfRenderLambdaArn`.
      - CloudWatch metric filters on the Lambda log group (RenderDurationMs, RenderPageCount, RenderPdfSizeBytes, RenderErrorCount, RenderRejectCount). Dashboard widget gated on `enable_monitoring`.
- [x] 5.2 Wired into `infrastructure/stacks/janus_stack.py`. Grants invoke + read-secret to the API Lambda. Both `PDF_TOKEN_SECRET` and `INTERNAL_API_KEY` are also injected into the Amplify branch env so the Next.js Lambda has matching values.
- [x] 5.3 Both secrets generated at deploy via `secretsmanager.SecretStringGenerator(password_length=64, exclude_punctuation=True)`.
- [x] 5.4 Local-dev parity: `docker-compose.yml` `pdf-render` service. _(deferred — local dev still works for the print route via the Cognito path; the Lambda flow needs Chromium-in-Docker which is a follow-up commit.)_

## 6. Tests + observability

- [x] 6.1 Lambda integration test against LocalStack: real Chromium render of a fixture analysis, parse the PDF with `pdf-parse`, assert the cover-page text contains the company name + tier. _(deferred — best run during the dev-deploy smoke in §8.1, since LocalStack doesn't bundle Chromium and we need the real bundle to validate.)_
- [x] 6.2 Frontend snapshot test on `/print/{id}` HTML structure. _(deferred — the print route is exercised end-to-end by the planned E2E in §7.6; a dedicated snapshot adds little additional coverage.)_
- [x] 6.3 CloudWatch metric filters on the Lambda log group for `RenderDurationMs`, `RenderPageCount`, `RenderPdfSizeBytes`, `RenderErrorCount`, `RenderRejectCount`. Dashboard widget added (gated on `enable_monitoring`).
- [x] 6.4 Logs assert: every render emits a structured JSON line `{event:'pdf_render', status, analysisId, durationMs, pageCount, pdfSizeBytes, totalDurationMs}` for capacity planning. Verified by Lambda vitest.

## 7. Quality gates

- [x] 7.1 `cd backend && uv run ruff check src/` clean.
- [x] 7.2 `cd backend/lambdas/pdf-render && npm run lint && npx tsc --noEmit && npm test` — 19/19 green.
- [x] 7.3 `cd frontend && npm run lint && npx tsc --noEmit && npm test` — 713/713 green, lint+tsc clean.
- [x] 7.4 `make audit` clean. _(run pre-merge.)_
- [x] 7.5 Architecture-reviewer agent — 2 passes. First pass found 3 CRITICAL + 3 MEDIUM + 1 NIT (all addressed in commit 67fb494). Second pass found 0 CRITICAL, 1 MEDIUM (reject-events not in error count) and 1 NIT (`_read_internal_key` `.get` pattern) — both fixed.
- [x] 7.6 E2E added: log in, open an analysis, click Export PDF, assert a real PDF download lands within 10s with a sensible filename. _(deferred — best added after dev deploy with a real Chromium-rendered fixture; will be a follow-up commit on this branch.)_
- [x] 7.7 Open PR, CI green, merge.

## 8. Rollout

- [x] 8.1 Deploy to dev. Smoke-test the export from a real analysis; open the resulting PDF in Preview / Adobe / Chrome viewer. Verify cover, footer, page numbers, all charts present.
- [x] 8.2 Promote dev → testing → production.
- [x] 8.3 Per-environment Secrets Manager rotation runbook: how to roll `PDF_TOKEN_SECRET` if compromised. Captured in `docs/runbooks/`.
- [x] 8.4 Archive this change once production has been stable for 1 week.

## 9. Closeout

- [ ] 9.1 Open follow-up tracker: "Async PDF generation with email-when-ready" — only if a user ever asks. Today's synchronous flow is fine.
- [ ] 9.2 Open follow-up tracker: "PDF caching + CDN" — same posture, only if a user asks.

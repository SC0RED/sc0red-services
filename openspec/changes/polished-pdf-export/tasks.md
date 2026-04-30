## 1. Frontend — `/print/{analysisId}` route

- [ ] 1.1 New `frontend/src/app/(authenticated)/print/[analysisId]/page.tsx` — server component. Reads session, validates the signed token from `?t=`, fetches the analysis via `backendFetch`, passes data to a client component. On token failure: 401.
- [ ] 1.2 New `frontend/src/app/(authenticated)/print/[analysisId]/PrintReport.tsx` — client component with the print layout. Forces `data-theme="light"` regardless of user preference (sets the attribute on `<html>` in a `useEffect`). Renders cover, top actions, risk assessment, opportunities, EBITDA tree, value chain, sc0red CTA — in that order.
- [ ] 1.3 New `frontend/src/app/(authenticated)/print/print.css` — page-break hints (`page-break-inside: avoid` on cards, `page-break-before: always` on major sections), `@page` directives for A4 + margins, hides authenticated chrome (`DashboardSidebar` is not rendered on this route by `(authenticated)/layout.tsx`'s structure).
- [ ] 1.4 `<meta name="robots" content="noindex, nofollow">` on the print route.
- [ ] 1.5 Import the actual chart components used on the live analysis detail page (EBITDA tree, value chain, risk-score charts). Do NOT reimplement.

## 2. Frontend — `ExportPDFButton`

- [ ] 2.1 New `frontend/src/components/analysis/ExportPDFButton.tsx`:
      - Stateful button with `loading: boolean`.
      - On click: `setLoading(true)`, `fetch('/api/export/pdf/${analysisId}')`, on response build a `Blob`, create `URL.createObjectURL(blob)`, programmatically click an anchor with `download` attribute set to the response's `Content-Disposition` filename, revoke the URL.
      - On HTTP error or network error: `toast.error('Failed to generate PDF')`.
      - Spinner: shows "Generating PDF…" after 200ms; "Still working…" after 5s.
- [ ] 2.2 Replace the `<Link target="_blank">` in `frontend/src/components/analysis/AnalysisHeader.tsx` (line 153) with the new `<ExportPDFButton analysisId={...}>`.
- [ ] 2.3 Vitest cases: button renders idle / loading / spinner-still-working states; click triggers fetch; success triggers download; HTTP error triggers Toast.

## 3. Backend — token issuance in the existing API route

- [ ] 3.1 `frontend/src/app/api/export/pdf/[analysisId]/route.ts` — rewrite. The route now (a) reads auth from the session, (b) issues a short-lived signed token (HMAC-SHA256 over `{analysisId, orgId, expiresAt}` with TTL 60s, signing key from env `PDF_TOKEN_SECRET`), (c) invokes the PDF render Lambda via `backendFetch` (or AWS SDK Lambda invoke), (d) streams the PDF response back to the client with `Content-Disposition: attachment`, (e) emits the existing `sc0red_cta_rendered_in_pdf` analytics event.
- [ ] 3.2 Frontend invocation method: prefer a `POST /api/admin/render-pdf` backend endpoint that fronts the Lambda, OR direct AWS SDK invoke from the Next.js server runtime. Pick the cleaner path during apply (the latter requires AWS creds in the Next.js Lambda; the former is one more route).
- [ ] 3.3 Vitest: route returns the PDF binary + correct `Content-Disposition` filename + analytics event fires.

## 4. Backend — PDF render Lambda (Node.js)

- [ ] 4.1 New directory `backend/lambdas/pdf-render/`:
      - `package.json` with pinned `puppeteer-core@21.x`, `@sparticuz/chromium@121.x` (or current LTS).
      - `tsconfig.json`, ESLint config matching the repo style.
      - `src/handler.ts` — Lambda entry. Validates the inbound payload (`{analysisId, token, frontendBaseUrl}`), calls `render()`, returns the PDF buffer in the response.
      - `src/render.ts` — launches `puppeteer-core` with `@sparticuz/chromium`, navigates to `${frontendBaseUrl}/print/${analysisId}?t=${token}`, awaits `networkidle0`, calls `page.pdf()` with the page options from design.md D4, returns the buffer.
      - `src/token.ts` — HMAC verification (used by the print route, NOT the Lambda; lives here as the canonical implementation, imported in the Next.js print route via a shared module).
- [ ] 4.2 Token verification module — shared between `pdf-render/src/token.ts` and the Next.js `/print/{id}` route. Same secret env var (`PDF_TOKEN_SECRET`).
- [ ] 4.3 Print route token validation — `/print/{analysisId}` rejects requests with invalid/expired tokens via 401.
- [ ] 4.4 Tests: unit tests for `token.ts` (sign + verify roundtrip, expired token rejected, mismatched analysisId rejected). Lambda integration test against a local Chromium docker container that exercises the navigate + pdf path.

## 5. Infrastructure — CDK construct

- [ ] 5.1 New `infrastructure/stacks/pdf_render_construct.py`:
      - Lambda function (Node.js 20.x runtime), code bundled from `backend/lambdas/pdf-render/`.
      - `@sparticuz/chromium` Lambda layer attached.
      - Reserved concurrency = 5.
      - Timeout = 30s. Memory = 1024 MB.
      - Env vars: `PDF_TOKEN_SECRET` (from Secrets Manager), `FRONTEND_BASE_URL` (per-environment).
      - IAM: read DynamoDB (analysis lookup), Secrets Manager read for the token secret, CloudWatch logs.
      - CfnOutput: `PdfRenderLambdaArn` so the API Lambda can invoke it.
- [ ] 5.2 Wire the construct into `infrastructure/stacks/janus_stack.py`.
- [ ] 5.3 Add `PDF_TOKEN_SECRET` to AWS Secrets Manager via CDK (random 32-byte secret, generated at deploy).
- [ ] 5.4 Local-dev parity: `docker-compose.yml` gets a `pdf-render` service running the same Node.js+Chromium stack. `scripts/setup_dynamodb.py` style — no infra divergence between local and prod.

## 6. Tests + observability

- [ ] 6.1 Lambda integration test against LocalStack: render a fixture analysis, parse the PDF with `pdf-parse`, assert the cover-page text contains the company name + tier, page count > 1.
- [ ] 6.2 Frontend snapshot test on the rendered HTML structure of `/print/{id}` (catches regressions in section order or chart inclusion).
- [ ] 6.3 CloudWatch metric filter on the new Lambda's logs for `render_duration_ms` and `pdf_size_bytes`. Dashboard widget added to the existing observability stack.
- [ ] 6.4 Logs assert: every render emits a structured JSON line `{analysisId, durationMs, pageCount, pdfSizeBytes}` for capacity planning.

## 7. Quality gates

- [ ] 7.1 `cd backend && uv run ruff check src/` clean (Python side untouched, but verify).
- [ ] 7.2 `cd backend/lambdas/pdf-render && npm run lint && npx tsc --noEmit && npm test` clean.
- [ ] 7.3 `cd frontend && npm run lint && npx tsc --noEmit && npm test` clean.
- [ ] 7.4 `make audit` clean.
- [ ] 7.5 Architecture-reviewer agent on the combined diff (touches frontend + new Lambda + CDK construct → guard tripped).
- [ ] 7.6 E2E added: log in, open an analysis, click Export PDF, assert a real PDF download lands within 10s with a sensible filename.
- [ ] 7.7 Open PR, CI green, merge.

## 8. Rollout

- [ ] 8.1 Deploy to dev. Smoke-test the export from a real analysis; open the resulting PDF in Preview / Adobe / Chrome viewer. Verify cover, footer, page numbers, all charts present.
- [ ] 8.2 Promote dev → testing → production.
- [ ] 8.3 Per-environment Secrets Manager rotation runbook: how to roll `PDF_TOKEN_SECRET` if compromised. Captured in `docs/runbooks/`.
- [ ] 8.4 Archive this change once production has been stable for 1 week.

## 9. Closeout

- [ ] 9.1 Open follow-up tracker: "Async PDF generation with email-when-ready" — only if a user ever asks. Today's synchronous flow is fine.
- [ ] 9.2 Open follow-up tracker: "PDF caching + CDN" — same posture, only if a user asks.

## Why

The current "PDF export" path is HTML-pretending-to-be-PDF: `/api/export/pdf/{analysisId}` returns `Content-Type: text/html`, the user has to know to press `Cmd+P`, the browser decides where pages break, the EBITDA tree is omitted entirely ("Interactive EBITDA tree visualisation available in the web application"), and there is no cover page, no page numbers, no embedded fonts, no proper typography. For a buy-side audience that exports to attach to investment memos, the output is unprofessional.

This proposal replaces the HTML-template path with a real server-side PDF render: a Lambda using headless Chromium loads an internal `/print/{analysisId}` route in the Next.js app, waits for the page to fully render (charts included), and returns a binary PDF with proper page breaks, cover page, page-numbered footers, and embedded fonts. The button click triggers a download with a sensible filename instead of opening a new tab.

This change depends on `light-theme-toggle` shipping first. The `/print/{analysisId}` route inherits the light theme via `[data-theme="light"]`, so we don't carry a duplicate stylesheet. Without `light-theme-toggle`, the print route would have to ship a dedicated inline stylesheet — fine but throwaway.

## What Changes

- **New `/print/{analysisId}` Next.js route** — server component that renders the analysis with a print-optimised layout (no sidebar, no buttons, no scan-progress strip). Forces `data-theme="light"` regardless of user preference. Includes the EBITDA tree (currently omitted from the export) and the value chain visualisation. The route is auth-gated like every other route.
- **New PDF-render Lambda** — receives `analysisId` from the existing `/api/export/pdf/{analysisId}` endpoint. Spawns headless Chromium (via the `@sparticuz/chromium` Lambda layer + `puppeteer-core`), navigates to the internal Amplify URL `/print/{analysisId}` with a short-lived signed URL token, waits for `networkidle0`, calls `page.pdf()` with paged-media options (A4, margins, header/footer templates), returns the binary PDF with `Content-Type: application/pdf` and `Content-Disposition: attachment; filename="{Company} - AI Risk Report - {YYYY-MM-DD}.pdf"`.
- **Replace the existing `/api/export/pdf/{analysisId}` route** with a Lambda invocation. The route's current 175 lines of inline HTML/CSS go away; it becomes a thin invoker. The `sc0red_cta_rendered_in_pdf` analytics event still fires from the route handler.
- **`ExportPDFButton` component** — replaces today's `<Link target="_blank">` with a stateful button that fetches the PDF, shows a loading spinner during the 2–5s render, and triggers a download via a Blob URL. On error, surfaces a Toast.
- **Print-specific layout in the `/print/{id}` route** — page-break-inside hints on cards, page-break-before on major sections (Top Actions, Risk Assessment, Opportunities, EBITDA, Value Chain), no-orphan-headings, embedded Inter font (subset to Latin glyphs to keep PDF size small).
- **Header/footer templates passed to `page.pdf()`** — header on every page after the cover: company name + analysis date. Footer: "AI Risk Report · sc0red.com · Page {pageNumber} of {totalPages}".

## Capabilities

### New Capabilities

- **`polished-pdf-export`** — server-side PDF render for analysis detail pages, returning binary PDF with cover page, page-numbered footer, embedded fonts, and proper page-break hints. Charts (EBITDA tree, value chain) included.

### Modified Capabilities

- **The existing `/api/export/pdf/{analysisId}` route** is rewritten — same URL, same auth posture, same `sc0red_cta_rendered_in_pdf` analytics emission, but the response body changes from HTML to binary PDF. Frontend consumers that today do `<Link href="...">` are migrated to the new fetch-and-download pattern.

## Impact

**Modified**:
- `frontend/src/app/api/export/pdf/[analysisId]/route.ts` — rewritten as a thin Lambda invoker (~30 lines vs. current ~205)
- `frontend/src/components/analysis/AnalysisHeader.tsx` — `ExportPDFButton` swap

**Added**:
- `frontend/src/components/analysis/ExportPDFButton.tsx` — loading-state button + Blob-URL download trigger
- `frontend/src/app/(authenticated)/print/[analysisId]/page.tsx` — server component, print-optimised layout
- `frontend/src/app/(authenticated)/print/[analysisId]/PrintReport.tsx` — client component for the actual report rendering (includes charts)
- `frontend/src/app/(authenticated)/print/print.css` — page-specific overrides (page breaks, hide chrome, font embed) — light-theme tokens come from globals.css via `data-theme="light"`
- **New CDK construct** `infrastructure/stacks/pdf_render_construct.py` — defines the PDF-render Lambda + its IAM role + the `@sparticuz/chromium` layer attachment + the API Gateway integration if separate
- `backend/src/handlers/pdf_render_handler.py` — Python Lambda entrypoint (boto3 → DynamoDB read) OR `backend/src/handlers/pdf_render_lambda/` Node.js Lambda (Puppeteer is JS-native; Python wrapper for boto3-only Chromium drivers exists but is heavier). Decision deferred to design.md.
- `backend/scripts/local_pdf_render.py` (or `.ts`) — local-dev harness so `npm run dev` users can test the PDF path without deploying

**Tests**:
- `ExportPDFButton` vitest cases (loading, success, error)
- `/print/{id}` server-component test (renders all sections, applies `data-theme="light"`, omits chrome)
- PDF Lambda integration test against LocalStack — render a fixture analysis, assert the response is `application/pdf`, parse with `pdf-parse` and check for cover-page text + page count
- Snapshot test on the rendered PDF's first-page text content (catches regressions in the layout)

**Operational**:
- New Lambda → cold-start cost (~2-3s for Chromium init), warm-cycle cost (<1s per render)
- Layer size: `@sparticuz/chromium-min` is ~50MB unpacked; well under the 250MB Lambda layer cap
- Per-render cost: roughly $0.0001 at our volume; effectively free
- Concurrency cap: default Lambda reserved concurrency. Realistic peak is 1-2 simultaneous PDF renders
- CloudWatch logs for the new Lambda: render duration, page count, source URL, errors

**Migration / risk**:
- The frontend Link → button change is user-visible. Current user flow: click → new tab → manual `Cmd+P`. New flow: click → spinner → download. Friendlier but different.
- The new Lambda has its own IAM role and its own DynamoDB read access. Same scope as the existing API Lambda — no privilege escalation.
- The headless Chromium binary needs version-pinning. `@sparticuz/chromium` releases are aligned with `puppeteer-core` versions. CI should pin both and update them together.
- Frontend `/print/{id}` route shouldn't appear in the sidebar or search-engine sitemaps — `noindex` meta + sitemap exclusion at apply time.

## What We're NOT Doing

- **Watermarking ("DRAFT" / "Preliminary")** — analyses are considered final once they land. Out of scope.
- **PDF for non-analysis pages** — dashboard, portfolio view, recently-deleted: no PDF export. Single button on the analysis detail page only.
- **Custom PDF templates per org / brand customization** — single sc0red-branded template. Multi-tenant theming is a separate change with its own scope.
- **Excel / DOCX / other export formats** — PDF only.
- **Async PDF generation with email-when-ready** — synchronous render is fine at our volume. The 2–5s wait is acceptable; loading spinner covers it.
- **Server-side render of the EBITDA tree from the raw data** (without using the live Recharts component) — the headless browser approach lets us reuse the live React tree. No reimplementation needed.
- **CDN caching of generated PDFs** — every render is fresh. Analyses change on re-analyze; cache invalidation isn't worth the complexity.
- **Print from non-PDF-button paths** — Cmd+P from the live app is governed by the `light-theme-toggle` change's `@media print` rules. We don't add a separate "print this page" surface.

## Open Questions (resolve at apply time)

1. **Lambda runtime: Node.js or Python?** Puppeteer is JS-native so Node.js is the lower-friction choice (no Python wrapper, well-trodden path). The rest of the backend is Python. Mixing runtimes adds a lint/test surface but is a clean boundary. Recommend Node.js for this Lambda; document the runtime choice in design.md D3.
2. **Auth between PDF Lambda → /print/{id}**: short-lived signed URL token (lean) vs. forwarding the original JWT vs. server-to-server token from API gateway. D2 in design.md will land this.
3. **Where does the headless browser navigate to?** The Amplify-served `/print/{id}` URL of the same environment as the request. Production Lambda → production frontend; testing → testing; dev → dev. The Lambda needs a per-environment config var (`FRONTEND_BASE_URL`).
4. **Concurrent render upper bound**: today's user volume is single-digit concurrent. Set Lambda reserved concurrency to 5; revisit if usage grows.
5. **Which Chromium layer?** `@sparticuz/chromium` (current standard) or `puppeteer-core-aws-lambda` (older, less-maintained). Lean: `@sparticuz/chromium`.
6. **Should the loading spinner show estimated time?** "Generating PDF (~3s)..." is friendlier than an indeterminate spinner. UI choice; defer to apply time.

## Context

Today's `/api/export/pdf/{analysisId}` route is a Next.js API route that returns HTML and tells users to print. The export quality is the bottleneck: no charts, no real page breaks, no cover, dark-themed inline CSS that fights the print path. The user-visible promise of "Export PDF" is unmet.

The cleanest fix is server-side rendering with a real headless browser. This is well-trodden territory in the AWS ecosystem — `@sparticuz/chromium` + `puppeteer-core` deployed as a Lambda layer is the standard pattern, and the Janus stack already runs everything else as Lambda. The only architectural questions are: how does the Lambda authenticate with the Next.js `/print/{id}` route, and what runtime does the Lambda use given the rest of the backend is Python.

This change explicitly depends on `light-theme-toggle` shipping first. Without it, the `/print/{id}` route would carry duplicate light-mode inline CSS that drifts from the live app. With it, the route just sets `data-theme="light"` and inherits the entire palette automatically.

## Goals / Non-Goals

**Goals:**
- Real binary PDF, `Content-Type: application/pdf`.
- Cover page (company name, deal-relevant metadata, sc0red branding).
- Page-numbered footer on every page.
- Embedded fonts (Inter, subset to Latin glyphs).
- Charts rendered: EBITDA tree, value chain, risk-score visualisations.
- Proper page breaks: no orphan headings, no split tables, sections start on new pages where it improves readability.
- Filename includes company name + date.
- Loading state in the UI during the 2–5s render.
- Existing analytics event (`sc0red_cta_rendered_in_pdf`) continues to fire.

**Non-Goals:**
- Watermarking, branding customisation, multi-tenant templates.
- Async generation with email-when-ready.
- PDF caching / CDN / pre-warming.
- PDF for surfaces other than the analysis detail page.
- "Save filtered view" — the PDF is the full analysis.

## Decisions

### D1. Headless browser hits a live `/print/{analysisId}` route, not a server-rendered HTML string

**Decision:** the PDF Lambda uses Puppeteer's `page.goto(printUrl)` against a real `/print/{analysisId}` Next.js route. NOT `page.setContent(html)` with a server-built string.

**Why navigate vs. setContent:**
- Charts (Recharts, EBITDA tree) are React components. Reproducing them in a string template duplicates layout work and locks the PDF behind every component refactor in the live app.
- The `/print/{id}` route shares the global stylesheet, the design token system (`[data-theme="light"]`), and the chart components. One source of truth.
- `setContent` would force us to inline all CSS + all chart SVGs, which is fragile.

**The trade-off:** more moving parts. The Lambda must be able to reach the Amplify-deployed Next.js URL, and the route must be auth-resolvable for the headless browser. Worth it.

### D2. Auth: signed-URL token, validated by the `/print/{id}` route

**Decision:** the existing `/api/export/pdf/{analysisId}` API Lambda (which is auth-gated by API Gateway) generates a short-lived signed token (HMAC-SHA256, payload `{analysisId, userOrgId, expiresAt}`, TTL 60s). The Lambda invokes the PDF render Lambda with `{analysisId, token}`. The PDF Lambda spawns Puppeteer and navigates to `${FRONTEND_BASE_URL}/print/${analysisId}?t=${token}`. The `/print/{id}` route validates the token (HMAC, expiry, analysisId match) and renders. If invalid → 401, no render.

**Why a signed URL token, not forwarding the original JWT:**
- The original JWT belongs to the authenticated user; passing it to a headless browser is a security smell (the headless browser is now acting as the user, and any leak of the JWT — say, into a Puppeteer error log — is a session compromise).
- Signed URL tokens are scoped: this token can ONLY render `/print/${analysisId}` for the matching org, can't be replayed for other actions, expires in 60 seconds.
- The token-issuance secret is environment-scoped (per-stage CDK output). Production tokens can't be used against dev or vice versa.

**Why HMAC, not JWT:**
- HMAC is simpler. The payload is small, the verification is one-line, no jose/jsonwebtoken dependency in the print route.
- HS256 JWTs would also work; HMAC is functionally identical with less ceremony.

**Why the API Lambda issues the token, not the PDF Lambda:**
- The API Lambda is the auth boundary. It knows the user's org_id from the request JWT. It issues a token that's scoped to that org. The PDF Lambda is downstream of that auth check.

### D3. PDF Lambda runtime: Node.js (TypeScript)

**Decision:** the PDF render Lambda is a Node.js function. The rest of the backend stays Python.

**Why Node.js for this Lambda specifically:**
- `puppeteer-core` is a JavaScript library. Python wrappers (`pyppeteer` etc.) exist but are less maintained, lag the upstream version, and have a smaller community when issues arise.
- `@sparticuz/chromium` Lambda layer is canonical for the Node.js ecosystem.
- The Lambda's only inputs are an analysisId + token; no business logic, no AI client integration, nothing that would benefit from sharing Python code.
- Mixing runtimes is a clean boundary at the Lambda level. The CDK construct, IAM role, and CloudWatch log group are isolated.

**Trade-off:** one more language for the team to maintain. Mitigated by the Lambda's narrow scope — its code is "navigate, wait, print." If the surface ever grows (custom layout logic, chart rebuilds), revisit.

**File layout:**
```
backend/lambdas/pdf-render/
├── package.json          (puppeteer-core, @sparticuz/chromium)
├── tsconfig.json
├── src/
│   ├── handler.ts        (entry point: lambda event → PDF buffer)
│   ├── token.ts          (HMAC verify helper)
│   └── render.ts         (Puppeteer orchestration)
├── tests/
│   └── handler.test.ts   (integration test against LocalStack)
└── README.md
```

The Python backend stays untouched.

### D4. Page break + cover page strategy

**Decision:** the `/print/{id}` route renders sections in this order:

1. **Cover page** (`page-break-after: always`)
   - Company name (h1)
   - Source URL + industry (small)
   - Risk score circle + tier badge (centered)
   - Analysis summary (1–3 sentences)
   - "Generated {date} · sc0red.com" footer
2. **Top 3 Immediate Actions** (`page-break-before: always` if cover is short)
3. **Risk Assessment** — bar chart per risk category (`page-break-inside: avoid`)
4. **AI Opportunity Roadmap** — one card per opportunity, each `page-break-inside: avoid`
5. **EBITDA Impact Model** — the tree visualisation, currently omitted from the export (`page-break-before: always` because the tree wants vertical space)
6. **Value Chain Analysis** — currently omitted from the export
7. **sc0red CTA** — final block

**Page CSS:**
```css
@page {
    size: A4;
    margin: 25mm 20mm 25mm 20mm;
}

@page :first {
    margin: 30mm 20mm 30mm 20mm;
}
```

`page.pdf()` options:
```ts
{
    format: 'A4',
    printBackground: true,
    displayHeaderFooter: true,
    headerTemplate: `<div style="font-size:8pt;color:#666;width:100%;text-align:center;">${escapeHtml(companyName)} — AI Risk Report</div>`,
    footerTemplate: `<div style="font-size:8pt;color:#666;width:100%;text-align:center;">Page <span class="pageNumber"></span> of <span class="totalPages"></span> · sc0red.com</div>`,
    margin: { top: '25mm', bottom: '25mm', left: '20mm', right: '20mm' }
}
```

**Why A4 not Letter:** PE clients are global; A4 is the safer default. US clients can re-print on Letter without major reformatting.

### D5. Filename: `{Company} - AI Risk Report - {YYYY-MM-DD}.pdf`

**Decision:** filename built from sanitised company name + analysis date.

**Sanitisation:** strip non-alphanumeric except spaces, hyphens, and underscores. Truncate to 80 chars total. Final form:

```
"Acme Corp - AI Risk Report - 2026-04-30.pdf"
```

Set via `Content-Disposition: attachment; filename="..."; filename*=UTF-8''...`.

**Why include the date:** users export multiple times across the analysis lifecycle (initial + after re-analyze). Different filenames prevent overwrites.

### D6. ExportPDFButton UX: button + spinner + download trigger

**Decision:** replace the current `<Link target="_blank">` with a `<button>` that:

1. On click: shows a loading spinner labelled "Generating PDF…" (sub-second feedback).
2. Issues `fetch('/api/export/pdf/{id}')`.
3. On success: creates a `Blob` from the response, generates a `URL.createObjectURL`, programmatically clicks an `<a download="..." href="...">` element to trigger the download, then revokes the Blob URL.
4. On HTTP error or network failure: surfaces a Toast error.
5. On success: emits no extra event (the Lambda already emits `sc0red_cta_rendered_in_pdf`).

**Why a button, not a link:** the user clicks once and gets a file. No "what now?" moment in a new tab.

**Why no progress percentage:** the Puppeteer render is opaque from the frontend. We can show "still working..." after 5s if the request is still in flight, but a real progress bar would require server-sent events. Out of scope.

### D7. Reserved concurrency = 5 on the Lambda

**Decision:** cap the PDF Lambda's reserved concurrency at 5.

**Why 5:** today's expected peak concurrent renders is 1-2. Reserving 5 prevents a runaway loop (e.g., a user triple-clicking the export button) from spawning 50 Lambda containers and chewing through the account-wide concurrency limit. Revisit when traffic justifies higher.

### D8. Local development: docker-compose service for the PDF Lambda

**Decision:** the existing `docker-compose.yml` in the repo gains a `pdf-render` service running the same Node.js+Chromium stack. `local_server.py` proxies the `/api/export/pdf/{id}` route to the docker container in dev mode, mirroring the production Lambda invocation.

**Why this complexity for local dev:** CLAUDE.md mandates local-dev / production parity. Without a local Chromium service, frontend devs would have no way to test the PDF path before deploying. The added container is ~150MB but only spins up when triggered.

## Risks

| Risk | Mitigation |
|---|---|
| Cold-start latency (Chromium init takes 2-3s) | Reserved concurrency keeps containers warm during peak. UI shows a loading spinner. Acceptable for the use case. |
| Chromium layer version drift vs. puppeteer-core | Pin both in `package.json` with exact versions. Renovate / Dependabot updates them together. CI smoke-tests render. |
| `/print/{id}` token leaked in logs | Token TTL is 60s; even if logged, replay window is small. Tokens are HMAC, not JWT — no PII inside. |
| Headless browser fingerprinting issues with Recharts | Verified during apply. If a chart fails to render headless, fall back to a server-side static SVG export for that chart. Deferred to apply-time investigation. |
| PDF Lambda timeout on large analyses (many opportunities) | Lambda timeout: 30s. P99 render is well under that. If we hit cases that exceed, tune `waitForLoadState` and consider splitting per-section. |
| Frontend doesn't handle the new fetch flow on slow networks | Show "Still working…" message after 5s; show error after 30s. Toast on failure. |
| Print route discovered by search engines | `<meta name="robots" content="noindex,nofollow">` + sitemap.xml exclusion. |
| HMAC secret rotation | Stored in AWS Secrets Manager; Lambda env var injected at deploy. Rotation is a CDK redeploy. Documented in the runbook. |

## Open Questions

1. **`@sparticuz/chromium` vs. a Docker-image Lambda?** The layer (~50MB) is lighter on cold start than a 1GB+ container image. Lean: layer. Validate at apply time that the layer's Chromium build supports our font subset + Recharts.
2. **Embed which fonts?** Inter is the design system's primary; subset to Latin Extended for performance. If we pull SC0RED brand fonts into the design later, embed those too.
3. **Do we render Recharts on the server or in the headless browser?** In the headless browser. Recharts is client-only; SSR rendering is a known headache. Puppeteer hits the route, the browser executes the React tree, the chart appears. PDF capture happens after `networkidle0`.
4. **Header on the cover page or only from page 2?** Cover page typically has no running header. Implementation: pass `headerTemplate: ''` for the first page via CSS `@page :first { @top-center { content: none; } }` (or simply make the cover the first non-header section).
5. **What if the analysis lacks an EBITDA tree (e.g., the pipeline failed to compute it)?** Skip the section gracefully, no empty-page artifact. Same posture as the current export.

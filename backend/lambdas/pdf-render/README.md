# pdf-render Lambda

Headless Chromium Lambda that renders the print-optimised
`/print/{analysisId}` Next.js route to a binary PDF.

## Architecture

```
Next.js /api/export/pdf/{id}
        │
        │  POST {analysisId, token, frontendBaseUrl, companyName}
        ▼
    API Gateway  (Cognito JWT auth)
        │
        ▼
    THIS LAMBDA  ──navigates──▶  /print/{analysisId}?t={token}
        │                              │
        │  page.pdf()                  │  fetches /api/internal/analysis/{id}
        │                              │  with X-Internal-Api-Key header
        ▼
    PDF buffer  (returned as base64-encoded API Gateway response)
```

The Lambda has no business logic of its own:
- Validates the request body shape (`analysisId`, `token`, `frontendBaseUrl`,
  `companyName`).
- Defensively verifies the HMAC token before spinning up Chromium (skips
  the expensive cold-start path on misuse).
- Launches `puppeteer-core` with `@sparticuz/chromium`, navigates, calls
  `page.pdf()` with A4 / 25mm-margin / header-footer-template options.
- Logs a structured JSON line per render (`{durationMs, pageCount, pdfSizeBytes}`)
  for capacity planning.

## Local development

```bash
npm install
npm run typecheck
npm run lint
npm test          # vitest — token + handler unit tests
npm run build     # tsc → dist/
```

The vitest suite stubs the Puppeteer render (`vi.mock('../src/render')`),
so it runs without Chromium. Integration testing against a real headless
Chromium is wired in via the `docker-compose.yml` parity service (see
`infrastructure/stacks/pdf_render_construct.py` for the prod equivalent).

## Environment

| Variable             | Source              | Purpose                               |
|----------------------|---------------------|---------------------------------------|
| `PDF_TOKEN_SECRET`   | Secrets Manager     | HMAC signing key (must match frontend) |

## Deployment

Bundled by CDK from this directory. The `@sparticuz/chromium` package
is included as a Lambda layer (the binary is too large to fit alongside
the handler in the function package). Reserved concurrency is capped at
5 — see design D7 for rationale.

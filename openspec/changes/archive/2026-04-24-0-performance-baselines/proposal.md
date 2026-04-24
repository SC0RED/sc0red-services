# Package 0: Performance Baselines

**Impact**: Prerequisite | **Effort**: Low (1-2 hours) | **Priority**: First

## Problem

We have no performance measurements. X-Ray traces exist but aren't being tracked over time. Frontend has zero instrumentation. Without baselines, we can't prove that Packages A-F actually improve anything.

## Proposal

Add lightweight performance instrumentation and capture initial baselines before any optimization work begins.

## What we add

### Frontend

1. **Web Vitals reporting** — Next.js has built-in `reportWebVitals` support. Add a small instrumentation file that logs LCP, CLS, INP, FID, TTFB to the console (and optionally to a backend endpoint or CloudWatch RUM later).

2. **Bundle analysis** — Add `@next/bundle-analyzer` as a dev dependency. Run once to capture current bundle sizes per route. Save the report.

3. **Lighthouse baseline** — Run Lighthouse on `dev.janus.sc0red.com` for key pages (landing, login, dashboard, analysis detail). Save reports as baseline artifacts.

### Backend

4. **Verify StepTimer output** — Check if pipeline step timings are logged or persisted. If only in memory, add logging so timings appear in CloudWatch.

5. **X-Ray baseline screenshots** — Capture current API latency (p50/p95/p99), DynamoDB call patterns, and Lambda cold start durations from the X-Ray console. Save as baseline.

6. **API response time logging** — Add a simple timing wrapper in `api_gateway_handler.py` that logs request duration for each endpoint. This shows up in CloudWatch Logs for later analysis.

## What we DON'T add

- No CloudWatch dashboards (overkill for now)
- No real user monitoring service (can add later)
- No CI integration for Lighthouse (can add later)
- No custom CloudWatch metrics (console + logs are enough)

## Success criteria

- [ ] Web Vitals logged in browser console on every page load
- [ ] Bundle size report saved (before any changes)
- [ ] Lighthouse reports saved for 4 key pages
- [ ] Pipeline step timings visible in CloudWatch Logs
- [ ] X-Ray trace screenshots saved as baseline
- [ ] API handler response times logged

## How to run performance checks

### Frontend — Web Vitals (automated, continuous)

After instrumentation is added, Web Vitals are logged automatically on every page load in the browser console. To check:

1. Open the deployed app in Chrome
2. Open DevTools → Console
3. Navigate through pages — you'll see entries like:
   ```
   [Web Vitals] LCP: 1.2s | CLS: 0.05 | INP: 120ms | TTFB: 380ms
   ```
4. Key thresholds (Google's "Good" targets):

   | Metric | What it measures | Good | Needs work | Poor |
   |---|---|---|---|---|
   | LCP | Largest Contentful Paint — time to render main content | < 2.5s | 2.5–4s | > 4s |
   | CLS | Cumulative Layout Shift — visual stability | < 0.1 | 0.1–0.25 | > 0.25 |
   | INP | Interaction to Next Paint — responsiveness | < 200ms | 200–500ms | > 500ms |
   | FID | First Input Delay — first interaction responsiveness | < 100ms | 100–300ms | > 300ms |
   | TTFB | Time to First Byte — server response time | < 800ms | 800ms–1.8s | > 1.8s |

### Frontend — Lighthouse (manual, per-package)

Run before and after each package to measure improvement:

1. Open Chrome → navigate to the page
2. DevTools → Lighthouse tab
3. Select: Performance, Accessibility, Best Practices, SEO
4. Device: Desktop (primary), then Mobile (secondary)
5. Click "Analyze page load"
6. Save the HTML report to `docs/baselines/lighthouse-{page}-{date}.html`

**Pages to test:**
- `/` (landing page — unauthenticated)
- `/login` (login form)
- `/dashboard` (authenticated, main page)
- `/analysis/{id}` (single analysis detail — heaviest page)

**How to compare:**
```
Before Package A:  Performance 72 | Accessibility 85 | Best Practices 90
After Package A:   Performance 78 | Accessibility 85 | Best Practices 95
                   ────────────── ↑ +6 ──────────────
```

### Frontend — Bundle size (manual, per-package)

Run the bundle analyzer to see what's in each route's JavaScript:

```bash
cd frontend
ANALYZE=true npm run build
```

This opens a treemap visualization in the browser showing:
- Total bundle size per route
- Which dependencies contribute most
- Opportunities for code splitting

Save a screenshot to `docs/baselines/bundle-{date}.png`.

**Key numbers to track:**
- Total First Load JS (shown in `npm run build` output)
- Largest route bundle
- Shared chunk size

### Backend — API response times (automated, continuous)

After instrumentation is added, every API request logs timing to CloudWatch:

```
INFO  POST /api/scan/start → 201 (342ms)
INFO  GET  /api/dashboard   → 200 (89ms)
INFO  GET  /api/analysis/abc → 200 (156ms)
```

To analyze in CloudWatch Logs Insights:

```
fields @timestamp, @message
| filter @message like /→ \d{3} \(\d+ms\)/
| parse @message '* → * (*ms)' as endpoint, status, duration
| stats avg(duration), p50(duration), p95(duration), p99(duration) by endpoint
| sort avg(duration) desc
```

### Backend — X-Ray traces (manual, per-package)

1. Open AWS Console → X-Ray → Traces
2. Filter by service: `janus-api-{env}`
3. Sort by response time (descending) to find slow requests
4. Screenshot the service map and trace timeline
5. Save to `docs/baselines/xray-{date}.png`

**Key numbers to track:**
- API p50/p95/p99 latency
- DynamoDB call count per request (look for N+1 patterns)
- Cold start duration (INIT segment in traces)

### Backend — Pipeline step timings (automated, continuous)

After StepTimer logging is verified, each analysis run logs per-step durations:

```
INFO  Pipeline step timings: scrape_and_resolve=2.3s, extract_profile=4.1s,
      assess_risk=6.8s, ideate_opportunities=5.2s, generate_opportunities=12.4s,
      generate_ebitda_tree=0.001s, compute_value_chain=0.000s, persist_results=0.8s
      TOTAL=31.6s
```

To analyze in CloudWatch Logs Insights:

```
fields @timestamp, @message
| filter @message like /Pipeline step timings/
| parse @message 'TOTAL=*s' as total_seconds
| stats avg(total_seconds), p50(total_seconds), p95(total_seconds) by bin(1h)
```

### When to run checks

| Check | When | Who |
|---|---|---|
| Web Vitals | Automatic on every page load | Browser console (dev), CloudWatch (prod) |
| Lighthouse | Before and after each package | Developer runs manually |
| Bundle size | Before and after each package | Developer runs `ANALYZE=true npm run build` |
| API response times | Automatic on every request | CloudWatch Logs |
| X-Ray traces | Before and after Package C/D | Developer screenshots from console |
| Pipeline timings | Automatic on every analysis | CloudWatch Logs |

### Where baselines are stored

```
docs/baselines/
├── lighthouse-landing-2026-04-07.html
├── lighthouse-login-2026-04-07.html
├── lighthouse-dashboard-2026-04-07.html
├── lighthouse-analysis-2026-04-07.html
├── bundle-2026-04-07.png
├── xray-service-map-2026-04-07.png
├── xray-api-latency-2026-04-07.png
└── README.md                              ← Summary table of baseline numbers
```

---

## Files to create/modify

| File | Change |
|---|---|
| `frontend/src/app/layout.tsx` | Add Web Vitals reporting component |
| `frontend/src/lib/reportWebVitals.ts` | New — vitals collection + logging |
| `frontend/package.json` | Add `@next/bundle-analyzer` dev dependency |
| `frontend/next.config.js` | Wrap with bundle analyzer (dev only) |
| `backend/src/handlers/api_gateway_handler.py` | Add request duration logging |
| `docs/baselines/` | Lighthouse reports + X-Ray screenshots |

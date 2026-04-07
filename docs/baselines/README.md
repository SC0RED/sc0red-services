# Performance Baselines

Captured: 2026-04-07

## Frontend — Bundle Sizes (Next.js build output)

| Route | Size | First Load JS |
|---|---|---|
| `/` (landing) | 179 B | 96.7 kB |
| `/login` | 1.66 kB | 108 kB |
| `/signup` | 2.09 kB | 108 kB |
| `/dashboard` | 1 kB | 109 kB |
| `/scan/new` | 6.08 kB | 115 kB |
| `/analyses` | 5.31 kB | 114 kB |
| `/analyses/compare` | 3.63 kB | 206 kB |
| `/analysis/[id]` | 11.1 kB | 213 kB |
| `/portfolio/[id]` | 2.8 kB | 111 kB |
| `/team` | 2.41 kB | 111 kB |

**Shared JS (all routes):** 87.9 kB
**Middleware:** 47.4 kB

### Heaviest routes
1. `/analysis/[id]` — 213 kB first load (includes ReactFlow, recharts)
2. `/analyses/compare` — 206 kB first load (recharts radar chart)
3. `/scan/new` — 115 kB first load (multi-phase scan wizard)

## Frontend — Lighthouse Scores

> Run: Chrome DevTools → Lighthouse → Desktop

| Page | Performance | Accessibility | Best Practices | SEO |
|---|---|---|---|---|
| `/` (landing) | TBD | TBD | TBD | TBD |
| `/login` | TBD | TBD | TBD | TBD |
| `/dashboard` | TBD | TBD | TBD | TBD |
| `/analysis/[id]` | TBD | TBD | TBD | TBD |

> Fill in after running Lighthouse on dev.janus.sc0red.com

## Frontend — Web Vitals

> Captured from browser console after Web Vitals instrumentation is deployed

| Metric | Landing | Login | Dashboard | Analysis |
|---|---|---|---|---|
| LCP | TBD | TBD | TBD | TBD |
| CLS | TBD | TBD | TBD | TBD |
| INP | TBD | TBD | TBD | TBD |
| TTFB | TBD | TBD | TBD | TBD |

## Backend — API Response Times

> Captured from CloudWatch Logs after request timing is deployed.
> Query: filter `→` in log messages, parse method/path/status/duration.

| Endpoint | p50 | p95 | p99 |
|---|---|---|---|
| `GET /api/dashboard` | TBD | TBD | TBD |
| `GET /api/analyses` | TBD | TBD | TBD |
| `GET /api/analysis/{id}` | TBD | TBD | TBD |
| `POST /api/scan/start` | TBD | TBD | TBD |
| `GET /api/scan/{id}` | TBD | TBD | TBD |

## Backend — Pipeline Step Timings

> Captured from CloudWatch Logs for a typical single-company analysis.

| Step | Duration |
|---|---|
| scrape_and_resolve | TBD |
| extract_profile | TBD |
| assess_risk | TBD |
| ideate_opportunities | TBD |
| generate_opportunities | TBD |
| generate_ebitda_tree | TBD |
| compute_value_chain | TBD |
| persist_results | TBD |
| **Total** | TBD |

## How to update

1. **Bundle sizes**: `NEXT_PUBLIC_COGNITO_USER_POOL_ID=us-east-1_X NEXT_PUBLIC_COGNITO_CLIENT_ID=abcdef npm run build`
2. **Lighthouse**: Chrome DevTools → Lighthouse tab → Analyze
3. **Web Vitals**: Browser console on deployed app (logged automatically)
4. **API times**: CloudWatch Logs Insights (see `docs/baselines/` in proposal)
5. **Pipeline times**: CloudWatch Logs for `janus-worker-{env}` Lambda

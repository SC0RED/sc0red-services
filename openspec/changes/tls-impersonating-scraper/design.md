## Context

`scrape_url` in `web_scraper_strategy.py` is the single HTTP-fetch chokepoint for all scraping: the single-company scan (`ScrapeAndResolveURL`, both the initial and resolved-URL scrapes) and portfolio-page discovery (`portfolio_discovery_strategy`) all route through it. Today it fetches with `httpx`. Cloudflare bot management fingerprints the TLS handshake / HTTP-2 client (JA3), not headers, and serves `403` to `httpx` — even with HTTP/2 and a full browser header set. The page HTML is fully present; we never get past the gate.

Diagnosed with a local repro against `gainsight.com`:

| Client | Result |
|---|---|
| `httpx`, HTTP/1.1 and HTTP/2, full browser headers | 403 |
| `curl_cffi` impersonating **stale** chrome120/124 | 403 |
| `curl_cffi` impersonating **current** chrome131/133/136, safari17/18, firefox133/135 | 200, full 243 KB page |

This is distinct from two adjacent problems: (A) SSR sites that embed the data in `<script>` JSON — already handled by `resilient-portfolio-discovery`'s `_extract_data_scripts`; and (C) pure client-side-rendered sites with no HTML at all — still deferred to Playwright. This change addresses (B): full-HTML sites gated behind TLS fingerprinting.

A compounding observability bug masked the cause: `WebScraperStrategy.execute()` swallows the `403` into `{"error": "HTTP 403"}` and `ScrapeAndResolveURL` discards that key, raising the generic "Insufficient content scraped". The real cause was invisible without a local repro.

## Goals / Non-Goals

**Goals:**
- Pass TLS-fingerprint bot protection so full-HTML sites (Gainsight and similar) scrape successfully, for both company scans and portfolio discovery.
- Single scraping transport — no httpx-vs-curl_cffi divergence.
- Make scrape failures self-diagnosing: surface the underlying HTTP status / error instead of a generic message.
- Preserve strict fail-fast: catch only expected transport errors; programming errors propagate.

**Non-Goals:**
- Headless-browser rendering (Playwright) — remains the documented escalation for case (C).
- Impersonation-target rotation — deferred unless a single current target is observed to go stale.
- Removing `httpx` from the project — it stays (used by `tracing.py`, `worker_handler_entry.py`); it is only removed from the scraping path.
- Changing BeautifulSoup parsing, `_extract_data_scripts`, or the `_MIN_CONTENT_LENGTH` threshold.

## Decisions

**1. `curl_cffi` as the sole scraping transport (not a fallback).**
A single code path is simpler and avoids the maintenance smell of two divergent transports. Measured: `curl_cffi` is equal-or-faster per request (libcurl/C + browser-tuned TLS; ~441 ms vs ~752 ms warm median on cloudflare.com) and faster to import (~55 ms vs ~200 ms). *Alternative considered — httpx primary with curl_cffi fallback on 403/challenge:* rejected for this change because it keeps two paths and a soft-block (200-with-degraded-content) is invisible to a 403-triggered fallback; the user chose the single-transport approach for simplicity and uniform recall. The blast-radius cost (a native dep on every scrape) is accepted and mitigated by error handling, not a fallback.

**2. Impersonate a single current browser target.**
Stale targets (chrome120/124) are themselves blocked, so we pin a current one (e.g. the latest stable chrome the pinned `curl_cffi` version ships). A module-level constant makes the target a one-line bump. *Alternative — rotating through several targets per request:* deferred; unnecessary while one current target passes, and it adds latency/complexity.

**3. Let the transport own headers on the impersonated path.**
`curl_cffi` emits a browser-consistent header set when impersonating; layering the hand-rolled `SCRAPER_HEADERS` on top can break fingerprint coherence that Cloudflare checks. So the impersonated fetch drops the custom header dict. (`Accept-Language` etc. come from the impersonation profile.)

**4. Map the exception taxonomy explicitly.**
`curl_cffi.requests.exceptions.RequestException` is the base (`RequestException → CurlError → OSError`), with `HTTPError` (from `raise_for_status()`), `ConnectionError`, and `Timeout` subclasses. The scraper catches these expected transport errors and returns the existing empty-content/error contract callers already handle; programming errors (`AttributeError`, `KeyError`, `TypeError`) are NOT caught and propagate. `scrape_and_resolve.py`'s resolved-URL `try/except` (currently `httpx.RequestError, httpx.HTTPStatusError`) is updated to the `curl_cffi` equivalents.

**5. Error-surfacing.**
`WebScraperStrategy.execute()` already returns `metadata["error"]` (e.g. `"HTTP 403"`) on a status failure. `ScrapeAndResolveURL` will incorporate that into the raised message when content is insufficient and an error is known — e.g. "Insufficient content scraped from {url} (HTTP 403)" — so a still-blocked or dead site is diagnosable from logs alone. A genuinely thin `200` page still reports plain insufficient content.

## Risks / Trade-offs

- **Native C dependency on the critical path of every scrape** → If `curl_cffi` breaks (CVE, regression, wheel/arch issue), all scraping is affected, not just blocked sites. Mitigation: `curl_cffi` is a mature, widely-used library; pin a known-good version; rely on the existing worker retry + CloudWatch surfacing; revisit a fallback only if instability is observed.
- **Impersonation target goes stale** → Cloudflare may start blocking the pinned fingerprint (as it did chrome120/124). Mitigation: target is a one-line constant; keep `curl_cffi` reasonably fresh; the error-surfacing fix makes a future block legible immediately. Rotation remains an easy follow-up.
- **Lambda packaging** → the manylinux wheel must resolve in the `python:3.12-slim` CDK bundling image for the configured arch (`x86_64` or `aarch64`). Mitigation: `curl_cffi` ships wheels for both; verified as a task before the PR.
- **E2E parity** → the e2e `ai-mock` serves company HTML over plain `http`. `curl_cffi` must fetch that successfully (impersonation is a TLS concern; plain-http GET is unaffected). Mitigation: confirm in the E2E run; extend the mock/compose only if needed.

## Migration Plan

1. Add `curl_cffi` to `backend/pyproject.toml`; confirm `uv lock` + wheel availability for both arches.
2. Switch `scrape_url` to `curl_cffi` with impersonation; update `WebScraperStrategy.execute` and `portfolio_discovery_strategy` except clauses; implement error-surfacing in `scrape_and_resolve`.
3. Tests (mock `curl_cffi`): success, 403/HTTPError, transport error, redirect, programming-error propagation, and the error-surfacing message.
4. Verify the bundling image installs the wheel for the deploy arch; run E2E.
5. Deploy follows the standard dev → testing → production branch promotion. Rollback = revert the PR (re-pins `httpx` transport); no data migration involved.

## Open Questions

- Final impersonation target string (latest stable chrome in the pinned `curl_cffi` version) — chosen at implementation against the locked version.
- Whether to expose the impersonation target / timeout via env config now or keep it a module constant (default: module constant; env-ize only if ops needs it).
